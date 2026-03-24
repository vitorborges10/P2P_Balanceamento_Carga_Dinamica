📡 Sistema Distribuído P2P com Balanceamento de Carga

Disciplina: Arquitetura de Sistemas Distribuídos
Professor: Michel Junio Ferreira Rosa

📌 Status

Projeto em desenvolvimento — Sprint 1 (Heartbeat) concluída

📖 Visão Geral

Este projeto implementa um sistema distribuído baseado em arquitetura P2P (Peer-to-Peer) com suporte a balanceamento de carga dinâmico.

Um nó Master gerencia múltiplos Workers, distribuindo tarefas e monitorando carga. A comunicação ocorre via TCP + JSON, seguindo um protocolo padronizado que garante interoperabilidade entre diferentes implementações.

🏗️ Estrutura do Projeto
.
├── server.py
├── client.py
└── README.md
🏗️ Arquitetura
🔹 Master
Atua como servidor TCP
Recebe requisições dos Workers
Processa mensagens JSON
Responde conforme o protocolo
Suporta múltiplas conexões via threads
🔹 Worker
Atua como cliente TCP
Envia requisições periódicas (heartbeat)
Aguarda resposta do Master
Implementa reconexão automática
📡 Protocolo
🔄 HEARTBEAT

Requisição (Worker → Master)

{"SERVER_UUID": "Rafael", "TASK": "HEARTBEAT"}

Resposta (Master → Worker)

{"SERVER_UUID": "Master_Alpha", "TASK": "HEARTBEAT", "RESPONSE": "ALIVE"}
⚙️ Configuração

Antes de executar o Worker, configure o IP do Master no arquivo client.py:

DEST_IP = '127.0.0.1'
Para testes locais: 127.0.0.1
Para rede: utilizar o IP da máquina onde o servidor está rodando
▶️ Execução
1. Iniciar o Master
python server.py
2. Iniciar o Worker
python client.py
🔁 Fluxo de Comunicação
Worker conecta ao Master via TCP
Envia mensagem JSON com delimitador \n
Master realiza parsing da mensagem
Master responde com "ALIVE"
Worker exibe o resultado no terminal
📊 Exemplo de Execução

Worker:

Heartbeat enviado...
[STATUS]: ALIVE (Confirmado por Master_Alpha)

Falha de conexão:

[STATUS]: OFFLINE - Tentando reconectar...
⚙️ Detalhes Técnicos
Comunicação via Sockets TCP
Formato de dados: JSON
Delimitador de mensagem: \n
Concorrência no servidor com Threads
Loop contínuo em ambos os nós
Timeout e reconexão automática no cliente
🚀 Próximos Passos
Implementar detecção de sobrecarga (threshold)
Criar protocolo de negociação entre Masters
Permitir empréstimo dinâmico de Workers
Simular carga de trabalho
