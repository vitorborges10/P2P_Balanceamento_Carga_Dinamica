import socket
import json
import time
import random
import uuid

ORIGINAL_MASTER_IP   = '10.62.216.214'
ORIGINAL_MASTER_PORT = 8000          # porta local (8000 na aula)
ORIGINAL_MASTER_ADDR = f"{ORIGINAL_MASTER_IP}:{ORIGINAL_MASTER_PORT}"

MASTER_IP   = ORIGINAL_MASTER_IP
MASTER_PORT = ORIGINAL_MASTER_PORT

WORKER_UUID = str(uuid.uuid4())[:8].upper()

SERVER_UUID_ORIGINAL = None   # preenchido quando emprestado

HEARTBEAT_INTERVAL = 10
TASK_POLL_INTERVAL = 0.1


# ─────────────────────────────────────────────
#  UTILITÁRIOS DE SOCKET
# ─────────────────────────────────────────────
def conectar() -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect((MASTER_IP, MASTER_PORT))
    return s


def enviar_json(sock: socket.socket, payload: dict):
    """Envia JSON terminado com \n (delimitador de mensagem)."""
    sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))


def receber_json(sock: socket.socket) -> dict:
    """Lê do socket até encontrar \n e retorna o JSON parseado."""
    buffer = ""
    while True:
        data = sock.recv(4096).decode("utf-8")
        if not data:
            raise ConnectionError("Conexão encerrada pelo master.")
        buffer += data
        if "\n" in buffer:
            linha = buffer.split("\n")[0]
            return json.loads(linha.strip())


# ─────────────────────────────────────────────
#  HEARTBEAT
# ─────────────────────────────────────────────
def ciclo_heartbeat():
    """
    Verifica se o master atual está ativo.
    Payload enviado  : {"SERVER_UUID": "...", "TASK": "HEARTBEAT", "WORKER_UUID": "..."}
    Payload esperado : {"SERVER_UUID": "...", "TASK": "HEARTBEAT", "RESPONSE": "ALIVE"}
    """
    try:
        s = conectar()
        payload = {
            "SERVER_UUID": SERVER_UUID_ORIGINAL or ORIGINAL_MASTER_ADDR,
            "TASK":        "HEARTBEAT",
            "WORKER_UUID": WORKER_UUID
        }
        enviar_json(s, payload)
        res = receber_json(s)
        s.close()

        response_val = str(res.get("RESPONSE") or res.get("response") or "UNKNOWN").upper()
        server_id    = res.get("SERVER_UUID") or res.get("server_uuid")
        print(f"[HEARTBEAT] {response_val} (MASTER: {server_id})")
    except Exception as e:
        print(f"[HEARTBEAT] OFFLINE - {e}")


# ─────────────────────────────────────────────
#  REGISTRO TEMPORÁRIO (Sprint 3)
# ─────────────────────────────────────────────
def registrar_temporario():
    """
    Após command_redirect: conecta no novo master e envia register_temporary_worker.
    """
    try:
        s = conectar()
        payload = {
            "type":       "register_temporary_worker",
            "request_id": str(uuid.uuid4()),
            "payload": {
                "worker_id":               WORKER_UUID,
                "original_master_address": ORIGINAL_MASTER_ADDR
            }
        }
        enviar_json(s, payload)
        ack = receber_json(s)
        s.close()
        status = str(ack.get("STATUS") or ack.get("status") or "?").upper()
        print(f"[P2P] Registrado no master temporário ({MASTER_IP}:{MASTER_PORT}). ACK: {status}")
    except Exception as e:
        print(f"[ERRO P2P] Falha ao registrar no master temporário: {e}")


# ─────────────────────────────────────────────
#  PAYLOAD DE APRESENTAÇÃO (Sprint 2 / 3)
# ─────────────────────────────────────────────
def montar_apresentacao() -> dict:
    """
    Local     : {"WORKER": "ALIVE", "WORKER_UUID": "..."}
    Emprestado: {"WORKER": "ALIVE", "WORKER_UUID": "...", "SERVER_UUID": "<origem>"}
    """
    payload = {"WORKER": "ALIVE", "WORKER_UUID": WORKER_UUID}
    if SERVER_UUID_ORIGINAL:
        payload["SERVER_UUID"] = SERVER_UUID_ORIGINAL
    return payload


# ─────────────────────────────────────────────
#  CICLO DE TAREFA
# ─────────────────────────────────────────────
def ciclo_tarefa():
    global MASTER_IP, MASTER_PORT, SERVER_UUID_ORIGINAL

    try:
        s = conectar()
        enviar_json(s, montar_apresentacao())
        resposta_master = receber_json(s)

        msg_type  = resposta_master.get("type") or resposta_master.get("TYPE")
        task_raw  = resposta_master.get("TASK") or resposta_master.get("task") or ""
        task_type = str(task_raw).upper()

        # ── Mensagens M2M que chegam ao worker ────────────────────────────
        if msg_type is not None:
            msg_type_lower = str(msg_type).lower()

            req_id  = resposta_master.get("request_id") or resposta_master.get("REQUEST_ID")
            payload = resposta_master.get("payload")    or resposta_master.get("PAYLOAD")

            if req_id is None or payload is None:
                print(f"[ERRO] Campo obrigatório ausente em mensagem type='{msg_type}'. Ignorando.")
                s.close()
                return

            # command_redirect
            if msg_type_lower == "command_redirect":
                s.close()
                novo_endereco = payload.get("new_master_address") or payload.get("NEW_MASTER_ADDRESS")
                if novo_endereco:
                    print(f"\n[P2P] command_redirect recebido! → {novo_endereco} (request_id={req_id})")
                    MASTER_IP, port_str  = novo_endereco.split(":")
                    MASTER_PORT          = int(port_str)
                    SERVER_UUID_ORIGINAL = ORIGINAL_MASTER_ADDR
                    registrar_temporario()
                else:
                    print("[ERRO P2P] command_redirect sem new_master_address. Ignorado.")
                return

            # command_release
            if msg_type_lower == "command_release":
                s.close()
                release_addr = payload.get("original_master_address") or payload.get("ORIGINAL_MASTER_ADDRESS")
                print(f"\n[P2P] command_release recebido! Retornando ao master original. (request_id={req_id})")

                if release_addr:
                    try:
                        ip_ret, port_ret = release_addr.split(":")
                        MASTER_IP   = ip_ret
                        MASTER_PORT = int(port_ret)
                    except ValueError:
                        print(f"[P2P AVISO] Endereço inválido ('{release_addr}'). Usando padrão.")
                        MASTER_IP   = ORIGINAL_MASTER_IP
                        MASTER_PORT = ORIGINAL_MASTER_PORT
                else:
                    MASTER_IP   = ORIGINAL_MASTER_IP
                    MASTER_PORT = ORIGINAL_MASTER_PORT

                SERVER_UUID_ORIGINAL = None
                print(f"[P2P] Reconectando ao master original em {MASTER_IP}:{MASTER_PORT}")
                return

            print(f"[PROTOCOLO] TYPE desconhecido: '{msg_type}'. Ignorado.")
            s.close()
            return

        # ── Protocolo de tarefa (Sprint 2) ────────────────────────────────
        if task_type == "NO_TASK":
            s.close()
            time.sleep(TASK_POLL_INTERVAL)
            return

        if task_type == "QUERY":
            user = resposta_master.get("USER") or resposta_master.get("user") or "?"
            time.sleep(random.uniform(0.5, 1.5))   # simula processamento
            status = "OK" if random.random() < 0.9 else "NOK"
            reporte = {
                "STATUS":      status,
                "TASK":        "QUERY",
                "WORKER_UUID": WORKER_UUID
            }
            enviar_json(s, reporte)
            ack = receber_json(s)
            ack_status = str(ack.get("STATUS") or ack.get("status") or "?").upper()
            print(f"[TAREFA] '{user}' concluída. Status={status} | ACK={ack_status}"
                  + (f" [emprestado de {SERVER_UUID_ORIGINAL}]" if SERVER_UUID_ORIGINAL else ""))
            s.close()
            time.sleep(TASK_POLL_INTERVAL)
            return

        print(f"[PROTOCOLO] Mensagem não reconhecida do master: {resposta_master}. Ignorada.")
        s.close()

    except (ConnectionRefusedError, socket.timeout, OSError) as e:
        print(f"[ERRO] Falha ao conectar com master atual ({MASTER_IP}:{MASTER_PORT}): {e}")
        # CT08 — master temporário perdido: voltar ao original
        if SERVER_UUID_ORIGINAL:
            print(f"[CT08] Master temporário perdido. Tentando retornar ao master de origem {ORIGINAL_MASTER_ADDR}...")
            MASTER_IP   = ORIGINAL_MASTER_IP
            MASTER_PORT = ORIGINAL_MASTER_PORT
            SERVER_UUID_ORIGINAL = None
        time.sleep(TASK_POLL_INTERVAL)
    except Exception as e:
        print(f"[ERRO] Falha no ciclo de tarefa: {e}")
        time.sleep(TASK_POLL_INTERVAL)


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
def main():
    print(f"=== WORKER {WORKER_UUID} INICIADO ===")
    print(f"    Master inicial : {MASTER_IP}:{MASTER_PORT}")
    print(f"    Heartbeat a cada {HEARTBEAT_INTERVAL}s | Poll a cada {TASK_POLL_INTERVAL}s")

    ultimo_heartbeat = 0
    while True:
        agora = time.time()
        if agora - ultimo_heartbeat >= HEARTBEAT_INTERVAL:
            ciclo_heartbeat()
            ultimo_heartbeat = time.time()
        ciclo_tarefa()


if __name__ == "__main__":
    main()