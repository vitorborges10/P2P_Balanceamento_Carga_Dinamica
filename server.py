import socket
import threading
import json
import time
import uuid
from collections import deque

HOST = '127.0.0.1'
PORT = 8000
SERVER_UUID = "MASTER_A"

PEER_HOST = '127.0.0.1'
PEER_PORT = 8001
PEER_UUID = "MASTER_B"

fila_lock = threading.Lock()
fila_tarefas: deque = deque()

SATURATION_THRESHOLD = 10
RELEASE_THRESHOLD = 3

redirecionamentos_pendentes = 0
workers_emprestados = set()
workers_para_liberar = set()

state_lock = threading.Lock()
log_lock = threading.Lock()

def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    with log_lock:
        print(f"[{ts}] {msg}")

def enviar_json(conn: socket.socket, payload: dict):
    conn.sendall((json.dumps(payload) + "\n").encode('utf-8'))

def receber_json(conn: socket.socket) -> dict:
    buffer = ""
    while True:
        data = conn.recv(4096).decode('utf-8')
        if not data:
            raise ConnectionError("Cliente desconectou.")
        buffer += data
        if "\n" in buffer:
            linha = buffer.split("\n")[0]
            return json.loads(linha.strip())

def notificar_retorno(worker_uuid: str):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect((PEER_HOST, PEER_PORT))
        payload = {
            "TYPE": "NOTIFY_WORKER_RETURNED",
            "REQUEST_ID": str(uuid.uuid4()),
            "PAYLOAD": {
                "WORKER_ID": worker_uuid
            }
        }
        enviar_json(s, payload)
        log(f"[P2P] Notificação de retorno do Worker {worker_uuid} enviada ao vizinho.")
        s.close()
    except Exception as e:
        log(f"[P2P ERRO] Falha ao notificar devolução: {e}")

def monitorar_carga():
    global redirecionamentos_pendentes

    while True:
        time.sleep(5)
        with fila_lock:
            carga_atual = len(fila_tarefas)

        with state_lock:
            pending_redirects = redirecionamentos_pendentes
            has_borrowed = bool(workers_emprestados)

        if carga_atual >= SATURATION_THRESHOLD and pending_redirects == 0:
            log(f"[CARGA ALTA] {carga_atual} tarefas. Iniciando REQUEST_HELP...")
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(3)
                s.connect((PEER_HOST, PEER_PORT))
                req_help = {
                    "TYPE": "REQUEST_HELP",
                    "REQUEST_ID": str(uuid.uuid4()),
                    "PAYLOAD": {
                        "MASTER_ID": SERVER_UUID,
                        "CURRENT_LOAD": carga_atual,
                        "CAPACITY": SATURATION_THRESHOLD,
                        "WORKERS_NEEDED": 2
                    }
                }
                enviar_json(s, req_help)
                res = receber_json(s)
                s.close()
                log(f"[P2P RESPOSTA] Vizinho respondeu: {res.get('TYPE')}")
            except Exception as e:
                log(f"[P2P ERRO] Falha ao pedir ajuda ao vizinho: {e}")

        if carga_atual <= RELEASE_THRESHOLD and has_borrowed:
            log(f"[CARGA BAIXA] {carga_atual} tarefas. Liberando workers emprestados.")
            with state_lock:
                for w_uuid in list(workers_emprestados):
                    workers_para_liberar.add(w_uuid)
                    workers_emprestados.remove(w_uuid)

def gerador_de_tarefas():
    usuarios = ["Alice", "Bob", "Carlos", "Diana", "Eduardo"]
    contador = 1
    while True:
        time.sleep(1)
        user = usuarios[contador % len(usuarios)]
        tarefa = {"TASK": "QUERY", "USER": user}
        with fila_lock:
            fila_tarefas.append(tarefa)
        if contador % 5 == 0:
            log(f"[FILA] Tarefas acumuladas: {len(fila_tarefas)}")
        contador += 1

def tratar_cliente(conn: socket.socket, addr):
    global redirecionamentos_pendentes
    try:
        payload = receber_json(conn)
        task = payload.get("TASK", "").upper()
        msg_type = payload.get("TYPE", "").upper()

        if msg_type == "REQUEST_HELP":
            with fila_lock:
                carga = len(fila_tarefas)

            if carga < RELEASE_THRESHOLD:
                with state_lock:
                    redirecionamentos_pendentes += payload["PAYLOAD"].get("WORKERS_NEEDED", 1)
                resposta = {
                    "TYPE": "RESPONSE_ACCEPTED",
                    "REQUEST_ID": payload.get("REQUEST_ID"),
                    "PAYLOAD": {"WORKERS_OFFERED": payload["PAYLOAD"].get("WORKERS_NEEDED", 1)}
                }
                log(f"[P2P] Ajuda ACEITA. Preparando para redirecionar workers.")
            else:
                resposta = {
                    "TYPE": "RESPONSE_REJECTED",
                    "REQUEST_ID": payload.get("REQUEST_ID"),
                    "PAYLOAD": {"REASON": "HIGH_LOAD"}
                }
                log(f"[P2P] Ajuda RECUSADA (Carga atual: {carga}).")

            enviar_json(conn, resposta)
            return

        if msg_type == "REGISTER_TEMPORARY_WORKER":
            w_uuid = payload["PAYLOAD"].get("WORKER_ID", "UNK")
            with state_lock:
                workers_emprestados.add(w_uuid)
            log(f"[WORKER EMPRESTADO] {w_uuid} registrado com sucesso. Farm expandida!")
            enviar_json(conn, {"STATUS": "ACK"})
            return

        if msg_type == "NOTIFY_WORKER_RETURNED":
            log(f"[P2P] Vizinho devolveu nosso Worker {payload['PAYLOAD'].get('WORKER_ID') }.")
            enviar_json(conn, {"STATUS": "ACK"})
            return

        if task == "HEARTBEAT":
            enviar_json(conn, {"SERVER_UUID": SERVER_UUID, "TASK": "HEARTBEAT", "RESPONSE": "ALIVE"})
            return

        worker_status = payload.get("WORKER", "").upper()
        if worker_status == "ALIVE":
            worker_uuid = payload.get("WORKER_UUID", "DESCONHECIDO")
            server_uuid_orig = payload.get("SERVER_UUID")

            redirect_now = False
            with state_lock:
                if not server_uuid_orig and redirecionamentos_pendentes > 0:
                    redirecionamentos_pendentes -= 1
                    redirect_now = True

            if redirect_now:
                cmd_redirect = {
                    "TYPE": "COMMAND_REDIRECT",
                    "REQUEST_ID": str(uuid.uuid4()),
                    "PAYLOAD": {"NEW_MASTER_ADDRESS": f"{PEER_HOST}:{PEER_PORT}"}
                }
                enviar_json(conn, cmd_redirect)
                log(f"[REDIRECIONAMENTO] Worker {worker_uuid} enviado para {PEER_HOST}:{PEER_PORT}")
                return

            release_now = False
            if server_uuid_orig:
                with state_lock:
                    if worker_uuid in workers_para_liberar:
                        workers_para_liberar.remove(worker_uuid)
                        release_now = True

            if server_uuid_orig and release_now:
                cmd_release = {
                    "TYPE": "COMMAND_RELEASE",
                    "REQUEST_ID": str(uuid.uuid4()),
                    "PAYLOAD": {"ORIGINAL_MASTER_ADDRESS": server_uuid_orig}
                }
                enviar_json(conn, cmd_release)
                log(f"[DEVOLUÇÃO] Worker {worker_uuid} liberado para origem.")
                notificar_retorno(worker_uuid)
                return

            with fila_lock:
                tarefa = fila_tarefas.popleft() if fila_tarefas else None

            if tarefa:
                enviar_json(conn, tarefa)
                try:
                    receber_json(conn)
                except Exception:
                    pass
                enviar_json(conn, {"STATUS": "ACK", "WORKER_UUID": worker_uuid})
            else:
                enviar_json(conn, {"TASK": "NO_TASK"})
            return

    except json.JSONDecodeError:
        pass
    except ConnectionError:
        pass
    except Exception as e:
        log(f"[ERRO] Falha com cliente: {e}")
    finally:
        conn.close()

def iniciar_master():
    threading.Thread(target=gerador_de_tarefas, daemon=True).start()
    threading.Thread(target=monitorar_carga, daemon=True).start()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(100)
    log(f"=== Master '{SERVER_UUID}' ativo em {HOST}:{PORT} ===")

    while True:
        conn, addr = s.accept()
        threading.Thread(target=tratar_cliente, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    iniciar_master()
