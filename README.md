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

---

## 📌 Status
Projeto em desenvolvimento — **Sprint 1 (Heartbeat) concluída**

---

## 📖 Visão Geral

Este projeto implementa um sistema distribuído baseado em arquitetura **P2P (Peer-to-Peer)** com suporte a **balanceamento de carga dinâmico**.

Um nó **Master** gerencia múltiplos **Workers**, distribuindo tarefas e monitorando carga. A comunicação ocorre via **TCP + JSON**, seguindo um protocolo padronizado que garante interoperabilidade entre diferentes implementações.

---

## 🏗️ Estrutura do Projeto

```
.
├── server.py
├── client.py
└── README.md
```

---

## 🏗️ Arquitetura

### 🔹 Master
- Atua como servidor TCP  
- Recebe requisições dos Workers  
- Processa mensagens JSON  
- Responde conforme o protocolo  
- Suporta múltiplas conexões via threads  

### 🔹 Worker
- Atua como cliente TCP  
- Envia requisições periódicas (heartbeat)  
- Aguarda resposta do Master  
- Implementa reconexão automática  

---

## 📡 Protocolo

### 🔄 HEARTBEAT

**Requisição (Worker → Master)**

```json
{"SERVER_UUID": "Rafael", "TASK": "HEARTBEAT"}
```

**Resposta (Master → Worker)**

```json
{"SERVER_UUID": "Master_Alpha", "TASK": "HEARTBEAT", "RESPONSE": "ALIVE"}
```

---

## ⚙️ Configuração

Antes de executar o Worker, configure o IP do Master no arquivo `client.py`:

```python
DEST_IP = '127.0.0.1'
```

---

## 🔁 Fluxo de Comunicação

1. Worker conecta ao Master via TCP  
2. Envia mensagem JSON com delimitador `\n`  
3. Master realiza parsing da mensagem  
4. Master responde com `"ALIVE"`  
5. Worker exibe o resultado no terminal  
