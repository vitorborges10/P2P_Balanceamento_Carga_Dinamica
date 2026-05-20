import socket
import threading
import json
import time
import uuid
from collections import deque

HOST = '127.0.0.1'
PORT = 8001
SERVER_UUID = "MASTER_B"

PEER_HOST = '127.0.0.1'
PEER_PORT = 8000
PEER_UUID = "MASTER_A"

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
            raise ConnectionError("CLIENTE DESCONECTOU.")
        buffer += data
        if "\n" in buffer:
            linha = buffer.split("\n")[0]
            try:
                payload = json.loads(linha.strip())
            except json.JSONDecodeError as e:
                log(f"[ERRO] JSON INVALIDO: {e}")
                raise
            return payload

def notificar_retorno(worker_uuid: str):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect((PEER_HOST, PEER_PORT))
        payload = {
            "type": "notify_worker_returned",
            "request_id": str(uuid.uuid4()),
            "payload": {
                "worker_id": worker_uuid
            }
        }
        enviar_json(s, payload)
        log(f"[P2P] NOTIFICACAO DE RETORNO DO WORKER {worker_uuid} ENVIADA.")
        s.close()
    except Exception as e:
        log(f"[P2P ERRO] FALHA AO NOTIFICAR DEVOLUCAO: {e}")

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
            log(f"[CARGA ALTA] {carga_atual} TAREFAS. INICIANDO REQUEST_HELP...")
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(3)
                s.connect((PEER_HOST, PEER_PORT))
                req_help = {
                    "type": "request_help",
                    "request_id": str(uuid.uuid4()),
                    "payload": {
                        "master_id": SERVER_UUID,
                        "current_load": carga_atual,
                        "capacity": SATURATION_THRESHOLD,
                        "workers_needed": 2
                    }
                }
                enviar_json(s, req_help)
                res = receber_json(s)
                s.close()
                log(f"[P2P RESPOSTA] VIZINHO RESPONDEU: {res.get('type')}")
            except Exception as e:
                log(f"[P2P ERRO] FALHA AO PEDIR AJUDA: {e}")

        if carga_atual <= RELEASE_THRESHOLD and has_borrowed:
            log(f"[CARGA BAIXA] {carga_atual} TAREFAS. LIBERANDO WORKERS.")
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
            log(f"[FILA] TAREFAS ACUMULADAS: {len(fila_tarefas)}")
        contador += 1

def tratar_cliente(conn: socket.socket, addr):
    global redirecionamentos_pendentes
    try:
        payload = receber_json(conn)
        msg_type = payload.get("type")

        if msg_type is not None:
            if not isinstance(msg_type, str):
                log(f"[ERRO] 'type' NAO E STRING: {msg_type}")
                return
            
            if msg_type != msg_type.lower():
                log(f"[ERRO] 'type' DEVE SER MINUSCULO: {msg_type}")
                return

            tipos_validos = [
                "request_help", "response_accepted", "response_rejected",
                "command_redirect", "register_temporary_worker",
                "command_release", "notify_worker_returned"
            ]

            if msg_type not in tipos_validos:
                log(f"[PROTOCOLO] TYPE DESCONHECIDO: {msg_type}. IGNORADO.")
                return

            if msg_type == "request_help":
                for campo in ["request_id", "payload"]:
                    if campo not in payload:
                        log(f"[ERRO] FALTANDO CAMPO '{campo}' EM {msg_type}")
                        return
                
                with fila_lock:
                    carga = len(fila_tarefas)
                
                if carga < RELEASE_THRESHOLD:
                    with state_lock:
                        redirecionamentos_pendentes += payload["payload"].get("workers_needed", 1)
                    resposta = {
                        "type": "response_accepted",
                        "request_id": payload.get("request_id"),
                        "payload": {"workers_offered": payload["payload"].get("workers_needed", 1)}
                    }
                    log("[P2P] AJUDA ACEITA. PREPARANDO REDIRECIONAMENTO.")
                else:
                    resposta = {
                        "type": "response_rejected",
                        "request_id": payload.get("request_id"),
                        "payload": {"reason": "high_load"}
                    }
                    log(f"[P2P] AJUDA RECUSADA (CARGA: {carga}).")
                enviar_json(conn, resposta)
                return

            if msg_type == "register_temporary_worker":
                w_uuid = payload.get("payload", {}).get("worker_id", "UNK")
                with state_lock:
                    workers_emprestados.add(w_uuid)
                log(f"[WORKER EMPRESTADO] {w_uuid} REGISTRADO.")
                enviar_json(conn, {"status": "ACK"})
                return

            if msg_type == "notify_worker_returned":
                w_uuid = payload.get("payload", {}).get("worker_id", "UNK")
                log(f"[P2P] VIZINHO DEVOLVEU WORKER {w_uuid}.")
                enviar_json(conn, {"status": "ACK"})
                return

        task = payload.get("TASK", "")
        if task == "HEARTBEAT":
            enviar_json(conn, {"SERVER_UUID": SERVER_UUID, "TASK": "HEARTBEAT", "RESPONSE": "ALIVE"})
            return

        worker_status = payload.get("WORKER", "")
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
                    "type": "command_redirect",
                    "request_id": str(uuid.uuid4()),
                    "payload": {"new_master_address": f"{PEER_HOST}:{PEER_PORT}"}
                }
                enviar_json(conn, cmd_redirect)
                log(f"[REDIRECIONAMENTO] WORKER {worker_uuid} ENVIADO PARA {PEER_HOST}:{PEER_PORT}")
                return

            release_now = False
            if server_uuid_orig:
                with state_lock:
                    if worker_uuid in workers_para_liberar:
                        workers_para_liberar.remove(worker_uuid)
                        release_now = True

            if server_uuid_orig and release_now:
                cmd_release = {
                    "type": "command_release",
                    "request_id": str(uuid.uuid4()),
                    "payload": {"original_master_address": server_uuid_orig}
                }
                enviar_json(conn, cmd_release)
                log(f"[DEVOLUCAO] WORKER {worker_uuid} LIBERADO.")
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
        log(f"[ERRO] FALHA COM CLIENTE: {e}")
    finally:
        conn.close()

def iniciar_master():
    threading.Thread(target=gerador_de_tarefas, daemon=True).start()
    threading.Thread(target=monitorar_carga, daemon=True).start()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(100)
    log(f"=== MASTER '{SERVER_UUID}' ATIVO EM {HOST}:{PORT} ===")

    while True:
        conn, addr = s.accept()
        threading.Thread(target=tratar_cliente, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    iniciar_master()