import socket
import json
import time
import random
import uuid

# ─── Configuração ────────────────────────────────────────────────────────────
MASTER_IP   = '127.0.0.1'
MASTER_PORT = 8000

# UUID único deste Worker (gerado uma vez na inicialização)
WORKER_UUID = str(uuid.uuid4())[:8].upper()   # ex: "A3F7C1B2"

# SERVER_UUID do Master original (None = Worker local, preencha se for emprestado)
# Ex: SERVER_UUID_ORIGINAL = "Master_B"
SERVER_UUID_ORIGINAL = None

HEARTBEAT_INTERVAL = 10   # segundos entre heartbeats
TASK_POLL_INTERVAL  = 3   # segundos de espera quando não há tarefa


# ─── Utilitários de rede ──────────────────────────────────────────────────────
def conectar():
    """Cria e retorna um socket TCP conectado ao Master."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect((MASTER_IP, MASTER_PORT))
    return s


def enviar_json(sock, payload: dict):
    """Serializa o payload e envia com delimitador \\n."""
    sock.sendall((json.dumps(payload) + "\n").encode('utf-8'))


def receber_json(sock) -> dict:
    """Lê do socket até encontrar \\n e retorna o dict parseado."""
    buffer = ""
    while True:
        data = sock.recv(4096).decode('utf-8')
        if not data:
            raise ConnectionError("Conexão encerrada pelo Master.")
        buffer += data
        if "\n" in buffer:
            linha = buffer.split("\n")[0]
            return json.loads(linha.strip())


# ─── Sprint 1 – Heartbeat ─────────────────────────────────────────────────────
def ciclo_heartbeat():
    """Envia um HEARTBEAT ao Master e loga o resultado."""
    try:
        s = conectar()
        enviar_json(s, {"SERVER_UUID": WORKER_UUID, "TASK": "HEARTBEAT"})
        res = receber_json(s)
        print(f"[HEARTBEAT] Status: {res.get('RESPONSE')} "
              f"(confirmado por {res.get('SERVER_UUID')})")
        s.close()
    except Exception as e:
        print(f"[HEARTBEAT] OFFLINE – Tentando reconectar... ({e})")


# ─── Sprint 2 – Ciclo de Tarefa ───────────────────────────────────────────────
def montar_apresentacao() -> dict:
    """
    Payload 2.1 / 2.1b – Apresentação do Worker ao Master.
    Inclui SERVER_UUID apenas se o Worker for 'emprestado'.
    """
    payload = {
        "WORKER": "ALIVE",
        "WORKER_UUID": WORKER_UUID
    }
    if SERVER_UUID_ORIGINAL:                          # Worker emprestado
        payload["SERVER_UUID"] = SERVER_UUID_ORIGINAL
    return payload


def simular_processamento(tarefa: dict) -> str:
    """
    Simula o processamento de uma QUERY.
    Retorna "OK" ou "NOK" aleatoriamente (90 % de sucesso).
    """
    user = tarefa.get("USER", "desconhecido")
    duracao = random.uniform(0.5, 2.0)
    print(f"[TASK]  Processando QUERY do usuário '{user}' "
          f"(simulando {duracao:.1f}s de trabalho)...")
    time.sleep(duracao)
    status = "OK" if random.random() < 0.9 else "NOK"
    print(f"[TASK]  Processamento concluído → {status}")
    return status


def ciclo_tarefa():
    """
    Executa um ciclo completo do Sprint 2:
      1. Apresenta-se ao Master (WORKER ALIVE + WORKER_UUID)
      2. Recebe tarefa (QUERY) ou NO_TASK
      3. Se QUERY: processa, reporta status (OK|NOK), aguarda ACK
      4. Se NO_TASK: aguarda antes do próximo ciclo
    """
    try:
        s = conectar()

        # ── Passo 1: Apresentação ─────────────────────────────────────────────
        apresentacao = montar_apresentacao()
        enviar_json(s, apresentacao)
        print(f"[APRESENTAÇÃO] Enviado: {apresentacao}")

        # ── Passo 2: Receber tarefa ───────────────────────────────────────────
        resposta_master = receber_json(s)
        print(f"[MASTER → WORKER] {resposta_master}")

        task_type = resposta_master.get("TASK")

        if task_type == "NO_TASK":
            print("[FILA] Sem tarefas disponíveis. Aguardando próximo ciclo.")
            s.close()
            time.sleep(TASK_POLL_INTERVAL)
            return

        if task_type == "QUERY":
            # ── Passo 3a: Processar ──────────────────────────────────────────
            status = simular_processamento(resposta_master)

            # ── Passo 3b: Reportar status (Worker → Master) ──────────────────
            reporte = {
                "STATUS":      status,
                "TASK":        "QUERY",
                "WORKER_UUID": WORKER_UUID
            }
            enviar_json(s, reporte)
            print(f"[REPORTE] Enviado: {reporte}")

            # ── Passo 4: Aguardar ACK (Master → Worker) ──────────────────────
            ack = receber_json(s)
            print(f"[ACK] Recebido: {ack}")
            if ack.get("STATUS") == "ACK":
                print("[CICLO] Tarefa concluída com sucesso. Worker liberado.\n")
            else:
                print(f"[AVISO] Resposta inesperada no lugar do ACK: {ack}\n")

        else:
            print(f"[AVISO] TASK desconhecida recebida: {task_type}")

        s.close()

    except Exception as e:
        print(f"[ERRO] Falha no ciclo de tarefa: {e}")


# ─── Loop principal ───────────────────────────────────────────────────────────
def main():
    print(f"=== Worker iniciado | UUID: {WORKER_UUID} "
          f"| Emprestado de: {SERVER_UUID_ORIGINAL or 'N/A'} ===\n")

    ultimo_heartbeat = 0

    while True:
        agora = time.time()

        # Heartbeat a cada HEARTBEAT_INTERVAL segundos
        if agora - ultimo_heartbeat >= HEARTBEAT_INTERVAL:
            ciclo_heartbeat()
            ultimo_heartbeat = time.time()

        # Ciclo de tarefa (Sprint 2)
        ciclo_tarefa()


if __name__ == "__main__":
    main()