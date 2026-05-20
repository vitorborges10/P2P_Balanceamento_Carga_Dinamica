# 📡 Sistema Distribuído P2P com Balanceamento de Carga

**Disciplina:** Arquitetura de Sistemas Distribuídos
**Professor:** Michel Junio Ferreira Rosa

**Alunos:**
- Vitor de Assis Patricio Borges
  - RA: 22304737
  - GitHub: vitorborges10
- Rafael Furtado Guimarães Estevão
  - RA: 22305974
  - GitHub: Kayarf

## 📌 Status
Projeto em desenvolvimento — **Sprint 3 concluída**

## 📖 Visão Geral

Este projeto implementa um sistema distribuído baseado em arquitetura **P2P (Peer-to-Peer)** com suporte a **balanceamento de carga dinâmico**.

Um nó **Master** processa requisições de **Workers** e negocia com um **Master vizinho** para compartilhar capacidade quando necessário.
A comunicação é feita via **TCP + JSON** com um protocolo simples de controle de tarefas e redistribuição.

## 🏗️ Estrutura do Projeto

```
.
├── server.py
├── client.py
└── README.md
```

## 🔹 Master
- Executa em `server.py`
- Aceita conexões de Workers e Masters vizinhos
- Distribui tarefas de `QUERY`
- Negocia empréstimo de workers quando a fila está saturada

## 🔹 Worker
- Executa em `client.py`
- Envia `HEARTBEAT` periódico ao Master
- Recebe tarefas ou comandos de redirecionamento
- Pode ser emprestado a outro Master temporariamente

## 📡 Protocolo

### HEARTBEAT

**Worker → Master**
```json
{"SERVER_UUID": "<WORKER_UUID>", "TASK": "HEARTBEAT"}
```

**Master → Worker**
```json
{"SERVER_UUID": "MASTER_A", "TASK": "HEARTBEAT", "RESPONSE": "ALIVE"}
```

### TAREFA

**Master → Worker**
```json
{"TASK": "QUERY", "USER": "Alice"}
```

**Worker → Master**
```json
{"STATUS": "OK", "TASK": "QUERY", "WORKER_UUID": "<WORKER_UUID>"}
```

### P2P

- `REQUEST_HELP`: Master pede ajuda a outro Master
- `COMMAND_REDIRECT`: Master instrui Worker a conectar em outro Master
- `COMMAND_RELEASE`: Master instrui worker emprestado a voltar ao Master original
- `REGISTER_TEMPORARY_WORKER`: Worker informa ao Master temporário que é um worker emprestado

## ⚙️ Configuração

No `client.py`, ajuste `MASTER_IP` e `MASTER_PORT` para o endereço do Master desejado:

```python
MASTER_IP = '127.0.0.1'
MASTER_PORT = 8000
```

No `server.py`, ajuste `HOST`, `PORT`, `PEER_HOST` e `PEER_PORT` para configurar um Master e seu vizinho.

## 🔁 Fluxo de Comunicação

1. Worker conecta ao Master via TCP
2. Envia JSON com delimitador `\n`
3. Master processa a mensagem e responde
4. Worker recebe tarefas ou comandos de redirecionamento
5. Worker reporta resultado e aguarda ACK
