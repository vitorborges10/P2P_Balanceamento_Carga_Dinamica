import socket
import ssl
import threading
import json
import time
import uuid
import psutil
import os
from collections import deque

HOST        = '192.168.15.6'
PORT        = 8000          
SERVER_UUID = "master_8"
HOSTNAME    = "master_8.A.local"
MASTER_ID   = "8"

PEER_HOST = '192.168.15.19'
PEER_PORT = 8001            

SATURATION_THRESHOLD = 100   
RELEASE_THRESHOLD    = 4    

SUPERVISOR_HOST     = "nuted-ia.dev"
SUPERVISOR_PORT     = 443
SUPERVISOR_TLS      = True
SUPERVISOR_SNI      = "nuted-ia.dev"
SUPERVISOR_INTERVAL = 10   

fila_lock  = threading.Lock()
fila_tarefas: deque = deque()

state_lock = threading.Lock()
log_lock   = threading.Lock()

workers_emprestados:         dict = {}
meus_workers_emprestados:    dict = {}
workers_para_liberar:        set  = set()
redirecionamentos_pendentes: int  = 0
pedidos_em_andamento:        dict = {}
fila_destinos_redirect:      deque = deque()


tasks_lock          = threading.Lock()
tasks_running_list: list = [] 
tasks_completed     = 0
tasks_failed        = 0

START_TIME = time.time()

peer_server_uuid = f"peer_{PEER_HOST}"
peer_uuid_lock   = threading.Lock()

def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    with log_lock:
        print(f"[{ts}] {msg}")


def new_request_id() -> str:
    return str(uuid.uuid4())


def enviar_linha(conn: socket.socket, payload: dict):
    conn.sendall((json.dumps(payload) + "\n").encode("utf-8"))


def ler_linha(conn: socket.socket, buffer_state: list) -> dict:
    buffer = buffer_state[0]
    while True:
        if "\n" in buffer:
            linha, resto = buffer.split("\n", 1)
            buffer_state[0] = resto
            return json.loads(linha.strip())
        dados = conn.recv(4096).decode("utf-8")
        if not dados:
            if buffer.strip():
                buffer_state[0] = ""
                return json.loads(buffer.strip())
            raise ConnectionError("Conexão fechada pelo host remoto.")
        buffer += dados


def _coletar_metricas() -> dict:
    """Monta o payload completo conforme spec Sprint 4."""
    agora_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    uptime    = int(time.time() - START_TIME)

    cpu_pct          = psutil.cpu_percent(interval=1)
    load1, load5, _  = psutil.getloadavg()
    mem              = psutil.virtual_memory()
    disk             = psutil.disk_usage('/')
    cpu_count_l      = psutil.cpu_count(logical=True)
    cpu_count_p      = psutil.cpu_count(logical=False) or 1

    with fila_lock:
        pending        = len(fila_tarefas)
        oldest_age_s   = 0
        if fila_tarefas:
            oldest_enqueued = fila_tarefas[0].get("_enqueued_at", time.time())
            oldest_age_s    = int(time.time() - oldest_enqueued)

    with state_lock:
        emp_recebidos = dict(workers_emprestados)       
        emp_enviados  = dict(meus_workers_emprestados)  
        n_received    = len(emp_recebidos)
        n_borrowed    = len(emp_enviados)

    with tasks_lock:
        tc = tasks_completed
        tf = tasks_failed
        tr = len(tasks_running_list)

    total_native     = 5
    total_registered = total_native + n_received
    workers_home     = total_native - n_borrowed          
    workers_alive    = total_registered                   
    workers_idle     = max(0, total_registered - tr)

    with peer_uuid_lock:
        p_uuid = peer_server_uuid

    borrowed_list = (
        [{"direction": "out", "peer_uuid": p_uuid} for _ in emp_enviados]
        + [{"direction": "in",  "peer_uuid": p_uuid} for _ in emp_recebidos]
    )

    try:
        test_s = socket.create_connection((PEER_HOST, PEER_PORT), timeout=2)
        test_s.close()
        neighbor_status  = "available"
        neighbor_hb_time = agora_iso
    except Exception:
        neighbor_status  = "unavailable"
        neighbor_hb_time = agora_iso

    return {
        "server_uuid":     SERVER_UUID,
        "hostname":        HOSTNAME,
        "role":            "master",
        "task":            "performance_report",
        "timestamp":       agora_iso,
        "message_id":      new_request_id(),
        "payload_version": "sprint4-monitor",
        "performance": {
            "system": {
                "uptime_seconds":   uptime,
                "load_average_1m":  round(load1, 2),
                "load_average_5m":  round(load5, 2),
                "cpu": {
                    "usage_percent":  round(cpu_pct, 2),
                    "count_logical":  cpu_count_l,
                    "count_physical": cpu_count_p
                },
                "memory": {
                    "total_mb":     int(mem.total    / 1024 / 1024),
                    "available_mb": int(mem.available / 1024 / 1024),
                    "percent_used": round(mem.percent, 2),
                    "memory_used":  int(mem.used     / 1024 / 1024)
                },
                "disk": {
                    "total_gb":    round(disk.total  / 1024**3, 1),
                    "free_gb":     round(disk.free   / 1024**3, 1),
                    "percent_used": round(disk.percent, 1)
                }
            },
            "farm_state": {
                "workers": {
                    "total_registered":         total_registered,
                    "workers_utilization":       tr,
                    "workers_alive":             workers_alive,
                    "workers_idle":              workers_idle,
                    "workers_borrowed":          n_borrowed,
                    "workers_received":          n_received,
                    "workers_failed":            0,
                    "workers_home":              workers_home,
                    "workers_available_capacity": workers_idle,
                    "borrowed_workers":          borrowed_list
                },
                "tasks": {
                    "tasks_pending":      pending,
                    "tasks_running":      tr,
                    "tasks_completed":    tc,
                    "tasks_failed":       tf,
                    "oldest_task_age_s":  oldest_age_s
                }
            },
            "config_thresholds": {
                "max_task":            SATURATION_THRESHOLD,
                "warn_cpu_percent":    85,
                "warn_memory_percent": 85,
                "release_task":        RELEASE_THRESHOLD
            },
            "neighbors": [
                {
                    "server_uuid":    p_uuid,
                    "status":         neighbor_status,
                    "last_heartbeat": neighbor_hb_time
                }
            ]
        }
    }


def _enviar_supervisor(payload: dict):
    """
    Abre conexao TLS sobre TCP, envia JSON e fecha sem \n e sem recv.
    Logica identica ao supervisor.py de referencia que funciona com nuted-ia.dev.
    """
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    sock = socket.create_connection((SUPERVISOR_HOST, SUPERVISOR_PORT), timeout=10)
    try:
        ctx = ssl.create_default_context()
        sock = ctx.wrap_socket(sock, server_hostname=SUPERVISOR_SNI)
        sock.sendall(data)
    finally:
        try:
            sock.close()
        except OSError:
            pass


def _disparar_envio():
    """Coleta e envia métricas em background — nunca bloqueia o loop principal."""
    try:
        payload = _coletar_metricas()
        _enviar_supervisor(payload)
        pending = payload['performance']['farm_state']['tasks']['tasks_pending']
        running = payload['performance']['farm_state']['tasks']['tasks_running']
        log(f"[SUPERVISOR] Métricas enviadas. "
            f"pending={pending} running={running} "
            f"cpu={payload['performance']['system']['cpu']['usage_percent']}%")
    except Exception as e:
        log(f"[SUPERVISOR ERRO] Falha ao enviar métricas: {e}")


def loop_supervisor():
    """
    Envia imediatamente ao iniciar, depois a cada SUPERVISOR_INTERVAL (10s).
    Cada envio ocorre em thread própria: se a conexão TLS travar ou falhar,
    o próximo ciclo de 10s não é atrasado e o nó não fica DOWN no dashboard.
    """
    log(f"[SUPERVISOR] Loop iniciado — envio a cada {SUPERVISOR_INTERVAL}s "
        f"para {SUPERVISOR_HOST}:{SUPERVISOR_PORT} (TLS)")

    # Primeiro envio imediato — evita ficar DOWN nos primeiros 10s
    threading.Thread(target=_disparar_envio, daemon=True).start()

    ultimo = time.time()
    while True:
        time.sleep(0.5)
        if time.time() - ultimo >= SUPERVISOR_INTERVAL:
            ultimo = time.time()
            threading.Thread(target=_disparar_envio, daemon=True).start()

def gerador_de_tarefas():
    usuarios = ["Alice", "Bob", "Carlos", "Diana", "Eduardo"]
    contador = 1
    while True:
        time.sleep(1)
        user = usuarios[contador % len(usuarios)]
        with fila_lock:
            fila_tarefas.append({
                "TASK":          "QUERY",
                "USER":          user,
                "_enqueued_at":  time.time()   # para calcular oldest_task_age_s
            })
        if contador % 5 == 0:
            with fila_lock:
                log(f"[FILA] Status: {len(fila_tarefas)} tarefas pendentes.")
        contador += 1

def monitorar_carga():
    while True:
        time.sleep(5)

        with fila_lock:
            carga_atual = len(fila_tarefas)

        with state_lock:
            pending_redirects = redirecionamentos_pendentes
            has_borrowed      = bool(workers_emprestados)

        
        if carga_atual >= SATURATION_THRESHOLD and pending_redirects == 0 and not has_borrowed:
            log(f"[CARGA] Saturação detectada ({carga_atual} tarefas). "
                f"Enviando request_help para {PEER_HOST}:{PEER_PORT}...")
            _solicitar_ajuda(carga_atual)

        
        if carga_atual <= RELEASE_THRESHOLD and has_borrowed:
            log(f"[CARGA] Fila normalizada ({carga_atual} tarefas). "
                f"Marcando worker(s) para devolução...")
            with state_lock:
                for w_id in list(workers_emprestados.keys()):
                    workers_para_liberar.add(w_id)
                log(f"[DEVOLUÇÃO] Marcados para liberar: {list(workers_emprestados.keys())}")


def _solicitar_ajuda(carga_atual: int):
    global redirecionamentos_pendentes

    req_id         = new_request_id()
    workers_needed = 2

    msg = {
        "type":       "request_help",
        "request_id": req_id,
        "payload": {
            "master_id":      MASTER_ID,
            "current_load":   carga_atual,
            "capacity":       SATURATION_THRESHOLD,
            "workers_needed": workers_needed
        }
    }

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)   
        s.connect((PEER_HOST, PEER_PORT))
        enviar_linha(s, msg)
        log(f"[M2M] request_help enviado (request_id={req_id})")

        buf = [""]
        res = ler_linha(s, buf)
        s.close()

        res_type = str(res.get("type") or res.get("TYPE") or "").lower()
        res_id   = res.get("request_id") or res.get("REQUEST_ID")

        if res_id != req_id:
            log(f"[M2M AVISO] request_id da resposta ({res_id}) != enviado ({req_id}). Ignorando.")
            return

        if res_type == "response_accepted":
            p       = res.get("payload") or res.get("PAYLOAD") or {}
            offered = int(p.get("workers_offered") or p.get("WORKERS_OFFERED") or workers_needed)

            peer_mid = p.get("master_id") or p.get("MASTER_ID")
            if peer_mid:
                with peer_uuid_lock:
                    global peer_server_uuid
                    peer_server_uuid = str(peer_mid)

            meu_addr = f"{HOST}:{PORT}"
            with state_lock:
                redirecionamentos_pendentes += offered
                for _ in range(offered):
                    fila_destinos_redirect.append(meu_addr)

            log(f"[M2M] response_accepted. Peer vai redirecionar {offered} worker(s) para {meu_addr}.")

        elif res_type == "response_rejected":
            p      = res.get("payload") or res.get("PAYLOAD") or {}
            reason = p.get("reason") or p.get("REASON") or "desconhecido"
            log(f"[M2M] response_rejected. Motivo: {reason}.")

        else:
            log(f"[M2M] Tipo de resposta desconhecido: '{res_type}'. Ignorado.")

    except socket.timeout:
        
        log(f"[M2M TIMEOUT] Peer não respondeu em 5s. request_id={req_id} descartado.")
    except Exception as e:
        log(f"[M2M ERRO] Falha ao contactar peer {PEER_HOST}:{PEER_PORT}: {e}")

def _enviar_notify_worker_returned(worker_id: str, origem_addr: str):
    """Notifica o master de origem que o worker foi liberado (notify_worker_returned)."""
    try:
        ip, port_str = origem_addr.split(":")
        port = int(port_str)
    except ValueError:
        ip, port = PEER_HOST, PEER_PORT

    req_id = new_request_id()
    msg = {
        "type":       "notify_worker_returned",
        "request_id": req_id,
        "payload":    {"worker_id": worker_id}
    }
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((ip, port))
        enviar_linha(s, msg)
        s.close()
        log(f"[M2M] notify_worker_returned → {ip}:{port} "
            f"worker='{worker_id}' (request_id={req_id})")
    except Exception as e:
        log(f"[M2M ERRO] Falha ao enviar notify_worker_returned: {e}")


def tratar_cliente(conn: socket.socket, addr):
    """
    Trata uma conexão persistente. Origens possíveis:
      - Worker próprio ou emprestado (campo WORKER ou TASK=HEARTBEAT)
      - Master vizinho (campo 'type', protocolo M2M)
    Aceita chaves em maiúsculo ou minúsculo para interoperabilidade (O6).
    Campos desconhecidos são ignorados (strict parsing — nota 1 do plano).
    """
    global redirecionamentos_pendentes, peer_server_uuid

    worker_uuid_sessao = None
    buffer_state       = [""]

    try:
        conn.settimeout(60)

        while True:
            try:
                payload = ler_linha(conn, buffer_state)
            except (ConnectionError, socket.timeout):
                break
            except json.JSONDecodeError:
                log(f"[PARSE ERRO] JSON inválido de {addr}. Ignorando.")
                continue

            msg_type_raw = payload.get("type") or payload.get("TYPE")
            if msg_type_raw is not None:
                msg_type = str(msg_type_raw).lower()

                if msg_type == "request_help":
                    req_id          = payload.get("request_id") or payload.get("REQUEST_ID")
                    peer_p          = payload.get("payload") or payload.get("PAYLOAD") or {}
                    workers_pedidos = int(peer_p.get("workers_needed") or
                                         peer_p.get("WORKERS_NEEDED") or 1)

                    peer_mid = peer_p.get("master_id") or peer_p.get("MASTER_ID")
                    if peer_mid:
                        with peer_uuid_lock:
                            peer_server_uuid = str(peer_mid)

                    peer_ip          = addr[0]
                    peer_port_recv   = int(peer_p.get("master_port") or
                                          peer_p.get("MASTER_PORT") or PEER_PORT)
                    solicitante_addr = f"{peer_ip}:{peer_port_recv}"

                    with fila_lock:
                        minha_carga = len(fila_tarefas)

                    if minha_carga < SATURATION_THRESHOLD:
                        with state_lock:
                            redirecionamentos_pendentes += workers_pedidos
                            for _ in range(workers_pedidos):
                                fila_destinos_redirect.append(solicitante_addr)

                        detalhes = [
                            {"id": f"{SERVER_UUID}_W{i+1}", "address": ""}
                            for i in range(workers_pedidos)
                        ]
                        resposta = {
                            "type":       "response_accepted",
                            "request_id": req_id,
                            "payload": {
                                "workers_offered": workers_pedidos,
                                "worker_details":  detalhes
                            }
                        }
                        log(f"[M2M] request_help ACEITO. "
                            f"{workers_pedidos} worker(s) → {solicitante_addr}. "
                            f"(request_id={req_id})")
                    else:
                        resposta = {
                            "type":       "response_rejected",
                            "request_id": req_id,
                            "payload":    {"reason": "high_load"}
                        }
                        log(f"[M2M] request_help RECUSADO "
                            f"(carga={minha_carga} >= {SATURATION_THRESHOLD}). "
                            f"(request_id={req_id})")

                    enviar_linha(conn, resposta)
                    continue

                if msg_type == "notify_worker_returned":
                    req_id = payload.get("request_id") or payload.get("REQUEST_ID") or ""
                    p      = payload.get("payload") or payload.get("PAYLOAD") or {}
                    w_id   = p.get("worker_id") or p.get("WORKER_ID") or "UNK"
                    with state_lock:
                        meus_workers_emprestados.pop(w_id, None)
                    log(f"[M2M] notify_worker_returned. "
                        f"Worker '{w_id}' devolvido ao nosso pool. (request_id={req_id})")
                    continue

                if msg_type == "register_temporary_worker":
                    req_id = payload.get("request_id") or payload.get("REQUEST_ID") or ""
                    p      = payload.get("payload") or payload.get("PAYLOAD") or {}

                    if not (p.get("worker_id") or p.get("WORKER_ID")):
                        log("[ERRO] register_temporary_worker: campo 'worker_id' ausente. Ignorando.")
                        continue
                    if not (p.get("original_master_address") or p.get("ORIGINAL_MASTER_ADDRESS")):
                        log("[ERRO] register_temporary_worker: campo 'original_master_address' ausente. Ignorando.")
                        continue

                    w_id        = p.get("worker_id")        or p.get("WORKER_ID")
                    origem_addr = (p.get("original_master_address") or
                                   p.get("ORIGINAL_MASTER_ADDRESS"))

                    with state_lock:
                        workers_emprestados[w_id] = origem_addr
                    worker_uuid_sessao = w_id

                    enviar_linha(conn, {"STATUS": "ACK", "WORKER_UUID": w_id})
                    log(f"[P2P] Worker emprestado '{w_id}' registrado. "
                        f"Origem: {origem_addr} (request_id={req_id})")
                    continue

                log(f"[M2M] TYPE desconhecido: '{msg_type_raw}'. Ignorado (interoperabilidade).")
                continue

            task_raw = payload.get("TASK") or payload.get("task") or ""
            task_val = str(task_raw).upper()

            # HEARTBEAT (Sprint 1)
            if task_val == "HEARTBEAT":
                worker_uuid_hb = (payload.get("WORKER_UUID") or
                                  payload.get("worker_uuid") or "?")
                enviar_linha(conn, {
                    "SERVER_UUID": SERVER_UUID,
                    "TASK":        "HEARTBEAT",
                    "RESPONSE":    "ALIVE"
                })
                log(f"[HEARTBEAT] Respondido para Worker '{worker_uuid_hb}'.")
                continue

            worker_raw = payload.get("WORKER") or payload.get("worker") or ""
            if str(worker_raw).upper() == "ALIVE":
                worker_uuid      = (payload.get("WORKER_UUID") or
                                    payload.get("worker_uuid") or "DESCONHECIDO")
                server_uuid_orig = (payload.get("SERVER_UUID") or
                                    payload.get("server_uuid"))
                worker_uuid_sessao = worker_uuid

                if not server_uuid_orig:
                    with state_lock:
                        if worker_uuid in meus_workers_emprestados:
                            addr_temp = meus_workers_emprestados.pop(worker_uuid)
                            log(f"[P2P] Worker '{worker_uuid}' retornou ao pool local "
                                f"(estava em {addr_temp}).")
                        workers_emprestados.pop(worker_uuid, None)

                redirect_now     = False
                destino_redirect = ""
                with state_lock:
                    if (not server_uuid_orig
                            and redirecionamentos_pendentes > 0
                            and fila_destinos_redirect):
                        redirecionamentos_pendentes -= 1
                        destino_redirect = fila_destinos_redirect.popleft()
                        redirect_now     = True

                if redirect_now:
                    req_id = new_request_id()
                    enviar_linha(conn, {
                        "type":       "command_redirect",
                        "request_id": req_id,
                        "payload":    {"new_master_address": destino_redirect}
                    })
                    with state_lock:
                        meus_workers_emprestados[worker_uuid] = destino_redirect
                    log(f"[P2P] command_redirect → Worker '{worker_uuid}' "
                        f"para {destino_redirect} (request_id={req_id})")
                    break   

                release_now = False
                if server_uuid_orig:
                    with state_lock:
                        if worker_uuid in workers_para_liberar:
                            workers_para_liberar.discard(worker_uuid)
                            workers_emprestados.pop(worker_uuid, None)
                            release_now = True

                if release_now:
                    req_id = new_request_id()
                    enviar_linha(conn, {
                        "type":       "command_release",
                        "request_id": req_id,
                        "payload":    {"original_master_address": server_uuid_orig}
                    })
                    log(f"[DEVOLUÇÃO] command_release → Worker '{worker_uuid}' "
                        f"retorna a {server_uuid_orig} (request_id={req_id})")
                    threading.Thread(
                        target=_enviar_notify_worker_returned,
                        args=(worker_uuid, server_uuid_orig),
                        daemon=True
                    ).start()
                    break

                with fila_lock:
                    tarefa = fila_tarefas.popleft() if fila_tarefas else None

                if tarefa:
                    
                    tarefa_envio = {k: v for k, v in tarefa.items()
                                    if not k.startswith("_")}
                    enviar_linha(conn, tarefa_envio)

                    task_entry = {
                        "worker_uuid": worker_uuid,
                        "user":        tarefa.get("USER", "?"),
                        "started_at":  time.time(),
                        "borrowed":    bool(server_uuid_orig)
                    }
                    with tasks_lock:
                        tasks_running_list.append(task_entry)

                    try:
                        resultado  = ler_linha(conn, buffer_state)
                        status_val = str(resultado.get("STATUS") or
                                         resultado.get("status") or "?").upper()

                        if status_val not in ("OK", "NOK"):
                            log(f"[AVISO] STATUS inválido recebido: '{status_val}'.")

                        with tasks_lock:
                            global tasks_completed, tasks_failed
                            if status_val == "OK":
                                tasks_completed += 1
                            else:
                                tasks_failed += 1
    
                            if task_entry in tasks_running_list:
                                tasks_running_list.remove(task_entry)

                        emprestado_info = (f" [EMPRESTADO de {server_uuid_orig}]"
                                           if server_uuid_orig else "")
                        log(f"[TAREFA] Worker '{worker_uuid}' concluiu "
                            f"'{tarefa_envio.get('USER', '?')}'. "
                            f"STATUS={status_val}{emprestado_info}")

                        enviar_linha(conn, {"STATUS": "ACK", "WORKER_UUID": worker_uuid})

                    except Exception as e:
                        with tasks_lock:
                            if task_entry in tasks_running_list:
                                tasks_running_list.remove(task_entry)
                        log(f"[ERRO SESSÃO] Falha ao processar tarefa "
                            f"do worker '{worker_uuid}': {e}")
                        
                        with fila_lock:
                            fila_tarefas.appendleft(tarefa)
                        break
                else:
                    enviar_linha(conn, {"TASK": "NO_TASK"})

                continue

            log(f"[PROTOCOLO] Mensagem não reconhecida de {addr}: {payload}. Ignorada.")

    except Exception as e:
        log(f"[CONEXÃO FECHADA] Sessão encerrada ({addr}): {e}")
    finally:
        
        if worker_uuid_sessao:
            with tasks_lock:
                tasks_running_list[:] = [
                    t for t in tasks_running_list
                    if t.get("worker_uuid") != worker_uuid_sessao
                ]
        conn.close()

def iniciar_master():
    threading.Thread(target=gerador_de_tarefas, daemon=True).start()
    threading.Thread(target=monitorar_carga,    daemon=True).start()
    threading.Thread(target=loop_supervisor,    daemon=True).start()
    log("[INIT] Threads de gerador, carga e supervisor iniciadas.")

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(100)
    log(f"=== MASTER '{SERVER_UUID}' ({HOSTNAME}) ON-LINE NA PORTA {PORT} ===")
    log(f"    Saturation threshold : {SATURATION_THRESHOLD} tarefas")
    log(f"    Release threshold    : {RELEASE_THRESHOLD} tarefas")
    log(f"    Peer configurado     : {PEER_HOST}:{PEER_PORT}")
    log(f"    Supervisor           : {SUPERVISOR_HOST}:{SUPERVISOR_PORT} (TLS) "
        f"a cada {SUPERVISOR_INTERVAL}s")

    while True:
        try:
            conn, addr = s.accept()
            threading.Thread(target=tratar_cliente, args=(conn, addr), daemon=True).start()
        except KeyboardInterrupt:
            log("Master encerrado pelo usuário.")
            break
        except Exception as e:
            log(f"[ERRO ACEITAR CONEXÃO] {e}")


if __name__ == "__main__":
    iniciar_master()