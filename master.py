import socket
import threading
import json
import time
import uuid
from collections import deque

HOST        = '192.168.15.6'
PORT        = 8001
SERVER_UUID = "MASTER_A"
MASTER_ID   = "A"

PEER_HOST = '192.168.15.19'
PEER_PORT = 8000

SATURATION_THRESHOLD = 10
RELEASE_THRESHOLD    = 4

fila_lock  = threading.Lock()
fila_tarefas: deque = deque()

state_lock = threading.Lock()
log_lock   = threading.Lock()


workers_emprestados: dict = {}
meus_workers_emprestados: dict = {}
workers_para_liberar: set = set()
redirecionamentos_pendentes = 0
pedidos_em_andamento: dict = {}
fila_destinos_redirect: deque = deque()

def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    with log_lock:
        print(f"[{ts}] {msg}")


def new_request_id() -> str:
    return str(uuid.uuid4())


def enviar_linha(conn: socket.socket, payload: dict):
    """Envia um pacote JSON terminado com \n."""
    conn.sendall((json.dumps(payload) + "\n").encode("utf-8"))


def ler_linha(conn: socket.socket, buffer_state: list) -> dict:
    """Lê do socket até encontrar \n e retorna o JSON parseado."""
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

def gerador_de_tarefas():
    usuarios = ["Alice", "Bob", "Carlos", "Diana", "Eduardo"]
    contador = 1
    while True:
        time.sleep(1)
        user = usuarios[contador % len(usuarios)]
        with fila_lock:
            fila_tarefas.append({"TASK": "QUERY", "USER": user})
        if contador % 5 == 0:
            with fila_lock:
                log(f"[FILA] Status: {len(fila_tarefas)} tarefas pendentes.")
        contador += 1


def monitorar_carga():
    """
    Loop a cada 5s verificando o tamanho da fila.
    - Saturação  (>= SATURATION_THRESHOLD): envia request_help ao peer.
    - Normalização (<= RELEASE_THRESHOLD) : marca workers para devolução.
    """
    while True:
        time.sleep(5)

        with fila_lock:
            carga_atual = len(fila_tarefas)

        with state_lock:
            pending_redirects = redirecionamentos_pendentes
            has_borrowed      = bool(workers_emprestados)

        # ── SATURAÇÃO: pedir ajuda ao peer ──────────────────────────────
        if carga_atual >= SATURATION_THRESHOLD and pending_redirects == 0 and not has_borrowed:
            log(f"[CARGA] Fila cheia ({carga_atual} tarefas). Enviando request_help para {PEER_HOST}:{PEER_PORT}...")
            _solicitar_ajuda(carga_atual)

        # ── NORMALIZAÇÃO: marcar workers para devolução ──────────────────
        if carga_atual <= RELEASE_THRESHOLD and has_borrowed:
            log(f"[CARGA] Fila normalizada ({carga_atual} tarefas). Marcando worker(s) para devolução...")
            with state_lock:
                for w_id in list(workers_emprestados.keys()):
                    workers_para_liberar.add(w_id)
                log(f"[DEVOLUÇÃO] Marcados: {list(workers_emprestados.keys())}")


def _solicitar_ajuda(carga_atual: int):
    """
    Abre conexão com o peer e executa request_help / response.
    Chaves em minúsculo conforme spec (type, request_id, payload).
    CT03: cada chamada tem seu próprio req_id, sem estado global compartilhado.
    CT07: socket.timeout de 5s — descarta request_id e loga.
    """
    global redirecionamentos_pendentes

    req_id         = new_request_id()
    workers_needed = 2

    msg = {
        "type": "request_help",
        "request_id": req_id,
        "payload": {
            "master_id":      MASTER_ID,
            "current_load":   carga_atual,
            "capacity":       SATURATION_THRESHOLD,
            "workers_needed": workers_needed,
            "master_port":    PORT        
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
            log(f"[M2M] response_accepted. Peer vai redirecionar {offered} worker(s).")
            
            meu_addr = f"{HOST}:{PORT}"
            with state_lock:
                redirecionamentos_pendentes += offered
                for _ in range(offered):
                    fila_destinos_redirect.append(meu_addr)

        elif res_type == "response_rejected":
            p      = res.get("payload") or res.get("PAYLOAD") or {}
            reason = p.get("reason") or p.get("REASON") or "desconhecido"
            log(f"[M2M] response_rejected. Motivo: {reason}.")

        else:
            log(f"[M2M] Tipo de resposta desconhecido: '{res_type}'. Ignorado.")

    except socket.timeout:
        
        log(f"[M2M TIMEOUT] Peer não respondeu em 5s. request_id={req_id} descartado.")
    except Exception as e:
        log(f"[M2M ERRO] Falha ao contactar peer: {e}")


def _enviar_notify_worker_returned(worker_id: str, origem_addr: str):
    """
    Notifica o master de origem que o worker foi devolvido.
    notify_worker_returned  (Master A → Master B)  — spec 2.5b
    """
    try:
        ip, port_str = origem_addr.split(":")
        port = int(port_str)
    except ValueError:
        ip, port = PEER_HOST, PEER_PORT

    req_id = new_request_id()
    msg = {
        "type": "notify_worker_returned",
        "request_id": req_id,
        "payload": {"worker_id": worker_id}
    }
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect((ip, port))
        enviar_linha(s, msg)
        s.close()
        log(f"[M2M] notify_worker_returned → {ip}:{port} worker={worker_id} (request_id={req_id})")
    except Exception as e:
        log(f"[M2M ERRO] Falha ao enviar notify_worker_returned: {e}")


def tratar_cliente(conn: socket.socket, addr):
    """
    Trata uma conexão persistente. Pode vir de:
      - Um Worker próprio ou emprestado (campo WORKER ou TASK=HEARTBEAT)
      - Um Master vizinho (campo 'type', protocolo M2M)
    Aceita chaves em maiúsculo ou minúsculo para interoperabilidade (O6).
    """
    global redirecionamentos_pendentes

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
                    workers_pedidos = int(peer_p.get("workers_needed") or peer_p.get("WORKERS_NEEDED") or 1)

                    
                    peer_ip        = addr[0]
                    peer_port_recv = int(peer_p.get("master_port") or peer_p.get("MASTER_PORT") or PEER_PORT)
                    solicitante_addr = f"{peer_ip}:{peer_port_recv}"

                    with fila_lock:
                        minha_carga = len(fila_tarefas)

                    if minha_carga < SATURATION_THRESHOLD:
                        with state_lock:
                            redirecionamentos_pendentes += workers_pedidos
                            
                            for _ in range(workers_pedidos):
                                fila_destinos_redirect.append(solicitante_addr)

                        
                        with state_lock:
                            locais_disponiveis = [
                                wid for wid in list(meus_workers_emprestados.keys())
                            ]
                        detalhes = [
                            {"id": wid, "address": ""}
                            for wid in locais_disponiveis[:workers_pedidos]
                        ]

                        resposta = {
                            "type": "response_accepted",
                            "request_id": req_id,
                            "payload": {
                                "workers_offered": workers_pedidos,
                                "worker_details":  detalhes
                            }
                        }
                        log(f"[M2M] request_help ACEITO. {workers_pedidos} worker(s) → {solicitante_addr}. (request_id={req_id})")
                    else:
                        
                        resposta = {
                            "type": "response_rejected",
                            "request_id": req_id,
                            "payload": {"reason": "high_load"}
                        }
                        log(f"[M2M] request_help RECUSADO (carga={minha_carga}). (request_id={req_id})")

                    enviar_linha(conn, resposta)
                    continue

                
                if msg_type == "notify_worker_returned":
                    req_id = payload.get("request_id") or payload.get("REQUEST_ID")
                    p      = payload.get("payload") or payload.get("PAYLOAD") or {}
                    w_id   = p.get("worker_id") or p.get("WORKER_ID") or "UNK"
                    with state_lock:
                        meus_workers_emprestados.pop(w_id, None)
                    log(f"[M2M] notify_worker_returned. Worker '{w_id}' devolvido. (request_id={req_id})")
                    continue

                
                if msg_type == "register_temporary_worker":
                    req_id = payload.get("request_id") or payload.get("REQUEST_ID")
                    p      = payload.get("payload") or payload.get("PAYLOAD") or {}

                    
                    if not (p.get("worker_id") or p.get("WORKER_ID")):
                        log(f"[ERRO] register_temporary_worker sem worker_id. Ignorando.")
                        continue
                    if not (p.get("original_master_address") or p.get("ORIGINAL_MASTER_ADDRESS")):
                        log(f"[ERRO] register_temporary_worker sem original_master_address. Ignorando.")
                        continue

                    w_id        = p.get("worker_id") or p.get("WORKER_ID")
                    origem_addr = p.get("original_master_address") or p.get("ORIGINAL_MASTER_ADDRESS")

                    with state_lock:
                        workers_emprestados[w_id] = origem_addr
                    worker_uuid_sessao = w_id

                    enviar_linha(conn, {"STATUS": "ACK", "WORKER_UUID": w_id})
                    log(f"[P2P] Worker emprestado '{w_id}' registrado. Origem: {origem_addr} (request_id={req_id})")
                    continue

                
                log(f"[M2M] TYPE desconhecido: '{msg_type_raw}'. Ignorado.")
                continue

            
            task_raw = payload.get("TASK") or payload.get("task") or ""
            task_val = str(task_raw).upper()

            if task_val == "HEARTBEAT":
                worker_uuid_hb = payload.get("WORKER_UUID") or payload.get("worker_uuid")
                resposta_hb = {
                    "SERVER_UUID": SERVER_UUID,
                    "TASK":        "HEARTBEAT",
                    "RESPONSE":    "ALIVE"
                }
                enviar_linha(conn, resposta_hb)
                log(f"[HEARTBEAT] Respondido para Worker '{worker_uuid_hb}'.")
                continue

            
            worker_raw = payload.get("WORKER") or payload.get("worker") or ""
            if str(worker_raw).upper() == "ALIVE":
                worker_uuid      = payload.get("WORKER_UUID") or payload.get("worker_uuid") or "DESCONHECIDO"
                server_uuid_orig = payload.get("SERVER_UUID") or payload.get("server_uuid") 
                worker_uuid_sessao = worker_uuid

                
                if not server_uuid_orig:
                    with state_lock:
                        if worker_uuid in meus_workers_emprestados:
                            addr_temp = meus_workers_emprestados.pop(worker_uuid)
                            log(f"[P2P] Worker '{worker_uuid}' retornou de {addr_temp}.")
                        workers_emprestados.pop(worker_uuid, None)

                
                redirect_now     = False
                destino_redirect = ""
                with state_lock:
                    if not server_uuid_orig and redirecionamentos_pendentes > 0 and fila_destinos_redirect:
                        redirecionamentos_pendentes -= 1
                        destino_redirect = fila_destinos_redirect.popleft()
                        redirect_now     = True

                if redirect_now:
                    req_id = new_request_id()
                    cmd_redirect = {
                        "type":       "command_redirect",
                        "request_id": req_id,
                        "payload":    {"new_master_address": destino_redirect}
                    }
                    enviar_linha(conn, cmd_redirect)
                    with state_lock:
                        meus_workers_emprestados[worker_uuid] = destino_redirect
                    log(f"[P2P] command_redirect → Worker '{worker_uuid}' para {destino_redirect} (request_id={req_id})")
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
                    cmd_release = {
                        "type":       "command_release",
                        "request_id": req_id,
                        "payload":    {"original_master_address": server_uuid_orig}
                    }
                    enviar_linha(conn, cmd_release)
                    log(f"[DEVOLUÇÃO] command_release → Worker '{worker_uuid}' volta para {server_uuid_orig} (request_id={req_id})")
                
                    threading.Thread(
                        target=_enviar_notify_worker_returned,
                        args=(worker_uuid, server_uuid_orig),
                        daemon=True
                    ).start()
                    break 

                
                with fila_lock:
                    tarefa = fila_tarefas.popleft() if fila_tarefas else None

                if tarefa:
                    enviar_linha(conn, tarefa)
                    try:
                        resultado  = ler_linha(conn, buffer_state)
                        status_val = str(resultado.get("STATUS") or resultado.get("status") or "?").upper()

                        if status_val not in ("OK", "NOK"):
                            log(f"[AVISO] STATUS inválido: '{status_val}'. Aceito mesmo assim.")

                        log(f"[TAREFA] Worker '{worker_uuid}' concluiu. STATUS={status_val}"
                            + (f" [EMPRESTADO de {server_uuid_orig}]" if server_uuid_orig else ""))

                        # ACK — spec 2.5
                        enviar_linha(conn, {"STATUS": "ACK", "WORKER_UUID": worker_uuid})
                    except Exception as e:
                        log(f"[ERRO SESSÃO] Falha ao processar tarefa do worker '{worker_uuid}': {e}")
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
        conn.close()


def iniciar_master():
    threading.Thread(target=gerador_de_tarefas, daemon=True).start()
    threading.Thread(target=monitorar_carga,    daemon=True).start()
    log(f"[INIT] Threads de carga e gerador iniciadas.")

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(100)
    log(f"=== MASTER '{SERVER_UUID}' ON-LINE NA PORTA {PORT} ===")
    log(f"    Saturation threshold : {SATURATION_THRESHOLD} tarefas")
    log(f"    Release threshold    : {RELEASE_THRESHOLD} tarefas")
    log(f"    Peer configurado     : {PEER_HOST}:{PEER_PORT}")

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
