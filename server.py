import socket
import threading
import json

HOST = '0.0.0.0' # Escuta em todas as interfaces
PORT = 8000

def tratar_cliente(conn, addr):
    try:
        print(f"[THREAD] Atendendo Worker em {addr}")
        
        # O projeto pede leitura do stream até encontrar o \n
        buffer = ""
        while True:
            data = conn.recv(1024).decode('utf-8')
            if not data: break
            buffer += data
            if "\n" in buffer:
                break
        
        # 1. Parsing do JSON recebido
        payload_recebido = json.loads(buffer.strip())
        print(f"[MENSAGEM de {addr}]: {payload_recebido}")

        # 2. Lógica de Resposta (Tarefa 03 do Backlog)
        if payload_recebido.get("TASK") == "HEARTBEAT":
            resposta = {
                "SERVER_UUID": "Master_Alpha", # Seu identificador
                "TASK": "HEARTBEAT",
                "RESPONSE": "ALIVE"
            }
            # 3. Envio com delimitador \n (Exigência do projeto)
            mensagem_final = json.dumps(resposta) + "\n"
            conn.sendall(mensagem_final.encode('utf-8'))
            print(f"[RESPOSTA] Enviado ALIVE para {addr}")

    except Exception as e:
        print(f"[ERRO] Falha no processamento: {e}")
    finally:
        conn.close()

def iniciar_master():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        s.bind((HOST, PORT))
        s.listen(100)
        print(f"Master P2P ativo na porta {PORT}...")

        while True:
            conn, addr = s.accept()
            # Dispara thread para não bloquear o Master
            threading.Thread(target=tratar_cliente, args=(conn, addr)).start()
            
    except Exception as e:
        print(f"Erro no servidor: {e}")
    finally:
        s.close()

if __name__ == "__main__":
    iniciar_master()