# 📡 Sistema Distribuído P2P com Balanceamento de Carga

**Disciplina:** Arquitetura de Sistemas Distribuídos  
**Professor:** Michel Junio Ferreira Rosa  

---

## 📌 Status
Projeto em desenvolvimento — **Sprint 1 (Heartbeat) concluída**

---

## 📖 Visão Geral

Este projeto implementa um sistema distribuído baseado em arquitetura **P2P (Peer-to-Peer)** com suporte a **balanceamento de carga dinâmico**.

Um nó **Master** gerencia múltiplos **Workers**, distribuindo tarefas e monitorando carga. A comunicação ocorre via **TCP + JSON**, seguindo um protocolo padronizado que garante interoperabilidade entre diferentes implementações.

---

## 🏗️ Estrutura do Projeto
  ├── server.py /n
  ├── client.py /n
  └── README.md /n


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

Resposta (Master → Worker)

{"SERVER_UUID": "Master_Alpha", "TASK": "HEARTBEAT", "RESPONSE": "ALIVE"}

## ⚙️ Configuração

Antes de executar o Worker, configure o IP do Master no arquivo client.py:
DEST_IP = '127.0.0.1'

## 🔁 Fluxo de Comunicação
Worker conecta ao Master via TCP
Envia mensagem JSON com delimitador \n
Master realiza parsing da mensagem
Master responde com "ALIVE"
Worker exibe o resultado no terminal
