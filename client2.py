import socket
import json
import time
import random
import uuid

ORIGINAL_MASTER_IP = '127.0.0.1'
ORIGINAL_MASTER_PORT = 8001
ORIGINAL_MASTER_ADDR = f"{ORIGINAL_MASTER_IP}:{ORIGINAL_MASTER_PORT}"

MASTER_IP = ORIGINAL_MASTER_IP
MASTER_PORT = ORIGINAL_MASTER_PORT

WORKER_UUID = str(uuid.uuid4())[:8].upper()
SERVER_UUID_ORIGINAL = None

HEARTBEAT_INTERVAL = 10
TASK_POLL_INTERVAL = 3

def conectar():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect((MASTER_IP, MASTER_PORT))
    return s

def enviar_json(sock, payload: dict):
    sock.sendall((json.dumps(payload) + "\n").encode('utf-8'))

def receber_json(sock) -> dict:
    buffer = ""
    while True:
        data = sock.recv(4096).decode('utf-8')
        if not data:
            raise ConnectionError("CONEXÃO ENCERRADA PELO MASTER.")
        buffer += data
        if "\n" in buffer:
            linha = buffer.split("\n")[0]
            return json.loads(linha.strip())

def ciclo_heartbeat():
    try:
        s = conectar()
        enviar_json(s, {"SERVER_UUID": WORKER_UUID, "TASK": "HEARTBEAT"})
        res = receber_json(s)
        status = res.get("RESPONSE", "UNKNOWN")
        print(f"[HEARTBEAT] {status} (MASTER: {res.get('SERVER_UUID')})")
        s.close()
    except Exception as e:
        print(f"[HEARTBEAT] OFFLINE - {e}")

def registrar_temporario():
    try:
        s = conectar()
        payload = {
            "TYPE": "REGISTER_TEMPORARY_WORKER",
            "REQUEST_ID": str(uuid.uuid4()),
            "PAYLOAD": {
                "WORKER_ID": WORKER_UUID,
                "ORIGINAL_MASTER_ADDRESS": ORIGINAL_MASTER_ADDR
            }
        }
        enviar_json(s, payload)
        receber_json(s)
        s.close()
        print(f"[P2P] REGISTRADO COM SUCESSO NO MASTER TEMPORÁRIO ({MASTER_IP}:{MASTER_PORT}).")
    except Exception as e:
        print(f"[ERRO P2P] FALHA AO REGISTRAR NO NOVO MASTER: {e}")

def montar_apresentacao() -> dict:
    payload = {"WORKER": "ALIVE", "WORKER_UUID": WORKER_UUID}
    if SERVER_UUID_ORIGINAL:
        payload["SERVER_UUID"] = SERVER_UUID_ORIGINAL
    return payload

def ciclo_tarefa():
    global MASTER_IP, MASTER_PORT, SERVER_UUID_ORIGINAL

    try:
        s = conectar()
        apresentacao = montar_apresentacao()
        enviar_json(s, apresentacao)
        resposta_master = receber_json(s)

        task_type = resposta_master.get("TASK")
        msg_type = resposta_master.get("TYPE")

        if msg_type == "COMMAND_REDIRECT":
            s.close()
            novo_endereco = resposta_master.get("PAYLOAD", {}).get("NEW_MASTER_ADDRESS")
            if novo_endereco:
                print(f"\n[COMANDO P2P] FUI EMPRESTADO! REDIRECIONANDO PARA {novo_endereco}...")
                MASTER_IP, port_str = novo_endereco.split(":")
                MASTER_PORT = int(port_str)
                SERVER_UUID_ORIGINAL = ORIGINAL_MASTER_ADDR
                registrar_temporario()
            else:
                print("[ERRO P2P] COMANDO DE REDIRECIONAMENTO INVÁLIDO.")
            return

        if msg_type == "COMMAND_RELEASE":
            s.close()
            print("\n[COMANDO P2P] FUI LIBERADO! RETORNANDO AO MASTER ORIGINAL.")
            MASTER_IP = ORIGINAL_MASTER_IP
            MASTER_PORT = ORIGINAL_MASTER_PORT
            SERVER_UUID_ORIGINAL = None
            return

        if task_type == "NO_TASK":
            s.close()
            time.sleep(TASK_POLL_INTERVAL)
            return

        if task_type == "QUERY":
            time.sleep(random.uniform(0.5, 1.5))
            status = "OK" if random.random() < 0.9 else "NOK"
            reporte = {"STATUS": status, "TASK": "QUERY", "WORKER_UUID": WORKER_UUID}
            enviar_json(s, reporte)
            ack = receber_json(s)
            print(f"[OK] TAREFA '{resposta_master.get('USER')}' CONCLUÍDA. ACK: {ack.get('STATUS')}")
            s.close()
            return

        s.close()
    except Exception as e:
        print(f"[ERRO] FALHA NO CICLO: {e}")
        time.sleep(TASK_POLL_INTERVAL)

def main():
    print(f"=== WORKER {WORKER_UUID} INICIADO ===")
    ultimo_heartbeat = 0
    while True:
        agora = time.time()
        if agora - ultimo_heartbeat >= HEARTBEAT_INTERVAL:
            ciclo_heartbeat()
            ultimo_heartbeat = time.time()
        ciclo_tarefa()

if __name__ == "__main__":
    main()
