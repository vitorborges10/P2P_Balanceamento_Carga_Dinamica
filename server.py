import socket
import threading
import json
import time
from collections import deque

# ─── Configuração ────────────────────────────────────────────────────────────
HOST        = '0.0.0.0'
PORT        = 8000
SERVER_UUID = "Master_Alpha"   # Identificador deste Master

# ─── Fila de Tarefas (Sprint 2) ───────────────────────────────────────────────
# Cada item é um dict: {"TASK": "QUERY", "USER": "<nome>"}
fila_lock  = threading.Lock()
fila_tarefas: deque = deque()

# Log de workers e tarefas concluídas
log_lock = threading.Lock()


def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    with log_lock:
        print(f"[{ts}] {msg}")


# ─── Utilitários de rede ──────────────────────────────────────────────────────
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


# ─── Gerador de tarefas simuladas ─────────────────────────────────────────────
def gerador_de_tarefas():
    """Adiciona tarefas fictícias à fila a cada alguns segundos."""
    usuarios = ["Alice", "Bob", "Carlos", "Diana", "Eduardo"]
    contador = 1
    while True:
        time.sleep(5)                # nova tarefa a cada 5 s
        user = usuarios[contador % len(usuarios)]
        tarefa = {"TASK": "QUERY", "USER": user}
        with fila_lock:
            fila_tarefas.append(tarefa)
        log(f"[FILA] Nova tarefa adicionada → USER={user} "
            f"(total na fila: {len(fila_tarefas)})")
        contador += 1


# ─── Handler de cliente (thread por conexão) ──────────────────────────────────
def tratar_cliente(conn: socket.socket, addr):
    try:
        log(f"[CONEXÃO] Nova conexão de {addr}")

        # ── Lê a primeira mensagem ────────────────────────────────────────────
        payload = receber_json(conn)
        log(f"[RECV {addr}] {payload}")

        task = payload.get("TASK", "").upper()

        # ════════════════════════════════════════════════════════════════════
        # Sprint 1 – HEARTBEAT
        # ════════════════════════════════════════════════════════════════════
        if task == "HEARTBEAT":
            resposta = {
                "SERVER_UUID": SERVER_UUID,
                "TASK":        "HEARTBEAT",
                "RESPONSE":    "ALIVE"
            }
            enviar_json(conn, resposta)
            log(f"[HEARTBEAT] ALIVE enviado para {addr}")
            return

        # ════════════════════════════════════════════════════════════════════
        # Sprint 2 – Apresentação de Worker (WORKER: ALIVE)
        # ════════════════════════════════════════════════════════════════════
        worker_status = payload.get("WORKER", "").upper()

        if worker_status == "ALIVE":
            worker_uuid       = payload.get("WORKER_UUID", "DESCONHECIDO")
            server_uuid_orig  = payload.get("SERVER_UUID")     # None = local

            if server_uuid_orig:
                log(f"[WORKER] Emprestado recebido: UUID={worker_uuid} "
                    f"(origem: {server_uuid_orig})")
            else:
                log(f"[WORKER] Local recebido: UUID={worker_uuid}")

            # ── Verifica fila e entrega tarefa ────────────────────────────────
            with fila_lock:
                tarefa = fila_tarefas.popleft() if fila_tarefas else None

            if tarefa:
                log(f"[FILA] Entregando tarefa {tarefa} → Worker {worker_uuid}")
                enviar_json(conn, tarefa)

                # ── Aguarda reporte de status (OK | NOK) ─────────────────────
                reporte = receber_json(conn)
                log(f"[REPORTE {worker_uuid}] {reporte}")

                status_reporte = reporte.get("STATUS", "").upper()
                if status_reporte == "OK":
                    log(f"[LOG] Worker {worker_uuid} concluiu "
                        f"QUERY com SUCESSO (USER={tarefa.get('USER')})")
                elif status_reporte == "NOK":
                    log(f"[LOG] Worker {worker_uuid} reportou FALHA "
                        f"na QUERY (USER={tarefa.get('USER')})")
                else:
                    log(f"[AVISO] Status inesperado de {worker_uuid}: {status_reporte}")

                # ── Envia ACK independentemente do resultado ──────────────────
                ack = {"STATUS": "ACK", "WORKER_UUID": worker_uuid}
                enviar_json(conn, ack)
                log(f"[ACK] Enviado para Worker {worker_uuid}")

            else:
                # Fila vazia
                log(f"[FILA] Sem tarefas. Enviando NO_TASK para Worker {worker_uuid}")
                enviar_json(conn, {"TASK": "NO_TASK"})

            return

        # ════════════════════════════════════════════════════════════════════
        # Mensagem desconhecida
        # ════════════════════════════════════════════════════════════════════
        log(f"[AVISO] Payload desconhecido de {addr}: {payload}")

    except json.JSONDecodeError as e:
        log(f"[ERRO] JSON inválido de {addr}: {e}")
    except ConnectionError as e:
        log(f"[ERRO] Conexão perdida com {addr}: {e}")
    except Exception as e:
        log(f"[ERRO] Falha inesperada com {addr}: {e}")
    finally:
        conn.close()


# ─── Loop principal do servidor ───────────────────────────────────────────────
def iniciar_master():
    # Inicia gerador de tarefas em background
    t_gerador = threading.Thread(target=gerador_de_tarefas, daemon=True)
    t_gerador.start()
    log("[GERADOR] Thread de geração de tarefas iniciada.")

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        s.bind((HOST, PORT))
        s.listen(100)
        log(f"=== Master '{SERVER_UUID}' ativo na porta {PORT} ===\n")

        while True:
            conn, addr = s.accept()
            t = threading.Thread(target=tratar_cliente,
                                 args=(conn, addr), daemon=True)
            t.start()

    except Exception as e:
        log(f"[FATAL] Erro no servidor: {e}")
    finally:
        s.close()


if __name__ == "__main__":
    iniciar_master()