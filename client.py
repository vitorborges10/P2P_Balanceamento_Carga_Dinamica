import socket
import json
import time

# Use o IP do Master aqui
DEST_IP = '127.0.0.1' 
PORT = 8000

def enviar_heartbeat():
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((DEST_IP, PORT))

            # Payload Oficial (Tarefa 02)
            payload = {
                "SERVER_UUID": "Rafael",
                "TASK": "HEARTBEAT"
            }

            # Envia JSON + \n
            s.sendall((json.dumps(payload) + "\n").encode('utf-8'))
            print("Heartbeat enviado...")

            # Aguarda Confirmação
            data = s.recv(1024).decode('utf-8')
            if data:
                res = json.loads(data.strip())
                # Definição de Pronto (DoD): Imprimir no Log
                print(f"[STATUS]: {res.get('RESPONSE')} (Confirmado por {res.get('SERVER_UUID')})")

            s.close()
        except Exception as e:
            # DoD: Log de tentativa de reconexão
            print(f"[STATUS]: OFFLINE - Tentando reconectar... ({e})")
        
        # Intervalo do Heartbeat (Tarefa 04)
        time.sleep(10)

if __name__ == "__main__":
    enviar_heartbeat()