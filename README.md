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
- Ryan Ribeiro

## 📌 Status

| Sprint | Objetivo | Status | Entrega |
|--------|----------|--------|---------|
| Sprint 1 | Heartbeat (Worker ↔ Master) | ✅ Completa | - |
| Sprint 2 | Ciclo de tarefas (ALIVE, QUERY, ACK) | ✅ Completa | - |
| Sprint 3 | Protocolo M2M e redirecionamento dinâmico | ✅ Completa | - |
| **Sprint 4** | **Supervisor e monitoramento (Apresentação Final)** | ✅ Completa | **15/06/2026** |

**Atual:** Implementando coleta de métricas e integração com Supervisor (nuted-ia.dev)

## 📖 Visão Geral

Este projeto implementa um sistema distribuído baseado em arquitetura **P2P (Peer-to-Peer)** com suporte a **balanceamento de carga dinâmico**.

Um nó **Master** processa requisições de **Workers** e negocia com um **Master vizinho** para compartilhar capacidade quando necessário.
A comunicação é feita via **TCP + JSON** com um protocolo simples de controle de tarefas e redistribuição.

## 🏗️ Estrutura do Projeto

```
.
├── master.py                    # Nó Master (servidor + supervisor)
├── worker.py                    # Nó Worker (cliente)
├── README.md                    # Este arquivo
├── skills-lock.json             # Lock de dependências
└── docs/
    └── supe (`master.py`)

**Responsabilidades:**
- ✅ Servidor TCP escutando em `HOST:PORT` (padrão: `192.168.15.6:8000`)
- ✅ Gerencia farm de Workers locais (5 workers nativos)
- ✅ Distribui tarefas da fila para Workers
- ✅ Monitora carga e detecta saturação
- ✅ Protocolo M2M: solicita/recebe Workers emprestados
- 🔄 **[Sprint 4]** Coleta métricas (CPU, memória, disco) e envia para Supervisor via TLS/TCP

**Thresholds:**
- `SATURATION_THRESHOLD = 100` tarefas → ativa request_help
- `RELEASE_THRESHOLD = 4` tarefas → devolve Workers emprestados

## 🔹 Worker (`worker.py`)

**Responsabilidades:**
- ✅ Cliente TCP conectando ao Master
- ✅ Envia `HEARTBEAT` a cada 10 segundos
- ✅ Solicita tarefas (QUERY) e reporta status (OK/NOK)
- ✅ Suporta redirecionamento dinâmico (command_redirect)
- ✅ Identifica-se como emprestado com campo `SERVER_UUID`
- ✅ Retorna ao Master de origem quando recebe `command_release`

## 🔹 Supervisor (Infraestrutura)

**[Sprint 4 - Novo]**
- URL: `https://nuted-ia.dev/supervisor/dashboard/`
- Endpoint de coleta: `nuted-ia.dev:443` (TLS/TCP)
- Dashboard em tempo real com métricas de cluster
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

### Master (`master.py`)

```python
HOST        = '192.168.15.6'       # IP local para escutar
PORT        = 8000                 # Porta TCP
SERVER_UUID = "master_8"           # Identificador único
HOSTNAME    = "master_8.A.local"   # FQDN
MASTER_ID   = "8"                  # Para protocolo M2M

PEER� Como Executar

### 1️⃣ Pré-requisitos

**Python 3.11+**
```bash
python --version
```

**Dependências:**
```bash
pip install psutil
```

### 2️⃣ Executar em máquinas diferentes

**Máquina 1 - Master:**
```bash
cd P2P_Balanceamento_Carga_Dinamica
python master.py
```

**Máquina 2+ - Workers (quantos quiser):**
```bash
cd P2P_Balanceamento_Carga_Dinamica
python worker.py
```

### 3️⃣ Monitorar em tempo real

Acesse o dashboard do Supervisor:
```
https://nuted-ia.dev/supervisor/dashboard/
```

O Master envia métricas a cada 10 segundos via TLS/TCP (porta 443).

## 📊 Protocolo

### Sprint 1 — HEARTBEAT

**Worker → Master**
```json
{"SERVER_UUID": "<WORKER_UUID>", "TASK": "HEARTBEAT", "WORKER_UUID": "..."}
```

**Master → Worker**
```json
{"SERVER_UUID": "MASTER_A", "TASK": "HEARTBEAT", "RESPONSE": "ALIVE"}
```

### Sprint 2 — TAREFA

**Worker → Master (Apresentação)**
```json
{"WORKER": "ALIVE", "WORKER_UUID": "...", "SERVER_UUID": "..."}  // opcional se emprestado
```

**Master → Worker (Entrega)**
```json
{"TASK": "QUERY", "USER": "Alice"}
```
ou
```json
{"TASK": "NO_TASK"}
```

**Worker → Master (Status)**
```json
{"STATUS": "OK", "TASK": "QUERY", "WORKER_UUID": "..."}
```

**Master → Worker (ACK)**
```json
{"STATUS": "ACK", "WORKER_UUID": "..."}
```

### Sprint 3 — PROTOCOLO M2M

**Master A → Master B (Pedido)**
```json
{
  "type": "request_help",
  "request_id": "uuid-v4",
  "payload": {
    "master_id": "A",
    "current_load": 150,
    "capacity": 100,
    "workers_needed": 2
  }
}
```

**Master B → Master A (Aceitar)**
```json
{
  "type": "response_accepted",
  "request_id": "uuid-v4",
  "payload": {
    "workers_offered": 2,
    "worker_details": [
      {"id": "B1", "address": "ip:port"},
      {"id": "B2", "address": "ip:port"}
    ]
  }
}
```

**Master B → Worker B1 (Comando de Redirecionamento)**
```json
{
  "type": "command_redirect",
  "request_id": "uuid-v4",
  "payload": {"new_master_address": "192.168.15.6:8000"}
}
```

**Worker B1 → Master A (Registro Temporário)**
```json
{
  "type": "register_temporary_worker",
  "request_id": "uuid-v4",
  "payload": {
    "worker_id": "B1",
    "original_master_address": "192.168.15.19:8001"
  }
}
```

### Sprint 4 — SUPERVISOR [NOVO]

**Master → Supervisor (a cada 10s via TLS/TCP)**
```json
{
  "server_uuid": "master_8",
  "hostname": "master_8.A.local",
  "role": "master",
  "task": "performance_report",
  "timestamp": "2026-06-17T12:34:56Z",
  "message_id": "uuid-v4",
  "payload_version": "sprint4-monitor",
  "performance": {
    "system": {
      "uptime_seconds": 12345,
      "load_average_1m": 3.20,
      "cpu": {"usage_percent": 85.42, ...},
      "memory": {"total_mb": 16384, ...},
      "disk": {"total_gb": 512.0, ...}
    },
    "farm_state": {
      "workers": {...},
      "tasks": {...}
    },
    "config_thresholds": {...},
    "neighbors": [...]
  }
}
```

## 🔄 Fluxo de Execução

1. **Inicialização:**
   - Master inicia servidor TCP e gerador de tarefas
   - Workers conectam periodicamente
   - Loop de supervisor dispara a cada 10s

2. **Operação Normal:**
   - Master distribui tarefas da fila
   - Workers executam e reportam status
   - Master coleta métricas e envia para supervisor

3. **Saturação:**
   - Master detecta fila > threshold (100 tarefas)
   - Envia `request_help` ao Master vizinho
   - Recebe Workers emprestados
   - Workers emprestados operaam normalmente

4. **Devolução:**
   - Fila normaliza (< 4 tarefas)
   - Master envia `command_release` aos Workers emprestados
   - Workers retornam ao Master original
   - Master notifica `notify_worker_returned`

5. **Monitoramento:**
   - Dashboard em tempo real mostra topologia
   - Gráficos históricos de CPU, memória, tarefas
   - Status de vizinhos (available/unavailable)

## 📈 Métricas Coletadas (Sprint 4)

| Métrica | Fonte | Frequência |
|---------|-------|-----------|
| CPU (%) | psutil | 10s |
| Memória (MB) | psutil | 10s |
| Disco (GB) | psutil | 10s |
| Load Average | psutil | 10s |
| Uptime | time | 10s |
| Workers (total/vivo/ocioso/emprestado) | Estado local | 10s |
| Tarefas (pendentes/rodando/concluídas/falhadas) | Contadores | 10s |
| Status de vizinhos | M2M heartbeat | 10s |

## 📝 Documentação

- **Plan Sprint 4:** [docs/superpowers/plans/2026-06-17-sprint4-presentation-plan.md](docs/superpowers/plans/2026-06-17-sprint4-presentation-plan.md)
- **Specs Sprint 3:** [docs/superpowers/specs/sprint3_master_to_master_protocol.md](docs/superpowers/specs/sprint3_master_to_master_protocol.md)
- **Specs Sprint 4:** [docs/superpowers/specs/sprint4_final_presentation.md](docs/superpowers/specs/sprint4_final_presentation.md)

## 🎯 Objetivos do Projeto

- ✅ **O1:** Arquitetura P2P com Master-Worker
- ✅ **O2:** Simulação de carga de requisições
- ✅ **O3:** Monitoramento de saturação
- ✅ **O4:** Protocolo de consenso M2M
- ✅ **O5:** Redirecionamento dinâmico de Workers
- ✅ **O6:** Autonomia e interoperabilidade
- 🔄 **O4+:** Dashboard com métricas em tempo real (Sprint 4)

## 📅 Datas Importantes

- **Apresentação:** 15/06/2026 (TURMA B/UN) | 11/06/2025 (TURMA A)
- **Prova:** 22/06/2026 (TURMA B/UN) | 18/06/2026 (TURMA A)
- **Dashboard:** https://nuted-ia.dev/supervisor/dashboard/

## ⚠️ Notas de Implementação

- **Delimitador:** Todas as mensagens JSON terminam com `\n`
- **Case Sensitivity:** Valores de controle (ALIVE, QUERY, etc.) em MAIÚSCULA
- **Timeout:** 5 segundos para timeouts de socket
- **Histerese:** Release threshold < Saturation threshold (evita ping-pong)
- **TLS/TCP:** Supervisor usa TLS 1.2+ com SNI
- **Concorrência:** Threading (sem AsyncIO)
SUPERVISOR_HOST     = "nuted-ia.dev"
SUPERVISOR_PORT     = 443
SUPERVISOR_TLS      = True
SUPERVISOR_SNI      = "nuted-ia.dev"
SUPERVISOR_INTERVAL = 10           # A cada 10 segundos
```

### Worker (`worker.py`)

```python
ORIGINAL_MASTER_IP   = '10.62.216.214'   # IP do Master
ORIGINAL_MASTER_PORT = 8000              # Porta do Master

HEARTBEAT_INTERVAL   = 10                # A cada 10 segundos
TASK_POLL_INTERVAL   = 0.1               # Polling de tarefas
```

Antes de executar, certifique-se de que os IPs e portas correspondem à sua rede local
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
