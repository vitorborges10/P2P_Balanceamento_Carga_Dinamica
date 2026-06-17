# SPRINT 4 — ESPECIFICAÇÃO FINAL: SUPERVISOR E MONITORAMENTO

**Versão:** 1.0  
**Data:** 17/06/2026  
**Escopo:** Integração com Supervisor de Métricas e dashboard web em tempo real

---

## 1. VISÃO GERAL

Sprint 4 é a **fase final** do projeto P2P com Balanceamento de Carga Dinâmico. Seu objetivo é:

1. Consolidar as implementações das Sprints 1, 2 e 3
2. Integrar um **Supervisor de Métricas** centralizado (infraestrutura do professor)
3. Enviar relatórios de desempenho via TLS/TCP
4. Monitorar e visualizar o cluster em tempo real via dashboard web

**Pré-requisitos:**
- Sprint 1: Heartbeat (Worker ↔ Master) ✅
- Sprint 2: Ciclo de tarefas (apresentação, distribuição, ACK) ✅
- Sprint 3: Protocolo M2M e redirecionamento dinâmico ✅

---

## 2. ARQUITETURA SPRINT 4

### 2.1 Componentes

```
┌──────────────────┐       ┌──────────────────┐
│   Master A       │       │   Master B       │
│  (seu código)    │◄─────►│  (seu código)    │
│                  │       │                  │
│  • Workers       │       │  • Workers       │
│  • Tarefas       │       │  • Tarefas       │
│  • Métricas      │       │  • Métricas      │
└────────┬─────────┘       └────────┬─────────┘
         │                          │
         │  TLS/TCP (porta 443)     │
         └──────────┬───────────────┘
                    │
         ┌──────────▼──────────┐
         │ Supervisor (443)    │
         │ nuted-ia.dev        │
         │                     │
         │ • Agregação         │
         │ • Dashboard         │
         └─────────────────────┘
                    │
         ┌──────────▼──────────┐
         │ Browser HTTP        │
         │ https://nuted-ia... │
         │ /supervisor/        │
         │ dashboard/          │
         └─────────────────────┘
```

### 2.2 Fluxo de Dados

1. **Master coleta**: CPU, memória, disco, workers, tarefas
2. **Master monta**: Payload JSON (v1.0 sprint4-monitor)
3. **Master conecta**: TLS/TCP ao Supervisor
4. **Master envia**: JSON (sem \n, sem HTTP, sem recv)
5. **Supervisor recebe**: Armazena e agrega
6. **Dashboard atualiza**: Visualização em tempo real

---

## 3. PAYLOAD SPRINT 4 — PERFORMANCE_REPORT

### 3.1 Estrutura Completa

```json
{
  "server_uuid": "master_8",
  "hostname": "master_8.A.local",
  "role": "master",
  "task": "performance_report",
  "timestamp": "2026-06-08T12:34:56Z",
  "message_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "payload_version": "sprint4-monitor",
  "performance": {
    "system": {
      "uptime_seconds": 12345,
      "load_average_1m": 3.20,
      "load_average_5m": 2.50,
      "cpu": {
        "usage_percent": 85.42,
        "count_logical": 8,
        "count_physical": 4
      },
      "memory": {
        "total_mb": 16384,
        "available_mb": 8192,
        "percent_used": 62.18,
        "memory_used": 8000
      },
      "disk": {
        "total_gb": 512.0,
        "free_gb": 250.0,
        "percent_used": 45.0
      }
    },
    "farm_state": {
      "workers": {
        "total_registered": 6,
        "workers_utilization": 4,
        "workers_alive": 6,
        "workers_idle": 2,
        "workers_borrowed": 1,
        "workers_received": 1,
        "workers_failed": 0,
        "workers_home": 5,
        "workers_available_capacity": 2,
        "borrowed_workers": [
          { "direction": "out", "peer_uuid": "master_7" },
          { "direction": "in", "peer_uuid": "master_7" }
        ]
      },
      "tasks": {
        "tasks_pending": 42,
        "tasks_running": 4,
        "tasks_completed": 150,
        "tasks_failed": 3,
        "oldest_task_age_s": 312
      }
    },
    "config_thresholds": {
      "max_task": 100,
      "warn_cpu_percent": 85,
      "warn_memory_percent": 85,
      "release_task": 60
    },
    "neighbors": [
      {
        "server_uuid": "master_7",
        "status": "available",
        "last_heartbeat": "2026-06-08T12:34:56Z"
      }
    ]
  }
}
```

### 3.2 Descrição de Campos

#### Campos Raiz (11 obrigatórios)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `server_uuid` | string | Identificador único do Master (ex: "master_8") |
| `hostname` | string | FQDN do nó (ex: "master_8.A.local") |
| `role` | string | Papel: "master" (fixo) |
| `task` | string | Tipo de relatório: "performance_report" (fixo) |
| `timestamp` | string (ISO-8601) | Momento da coleta: "YYYY-MM-DDTHH:MM:SSZ" |
| `message_id` | string (UUID v4) | Identificador único da mensagem |
| `payload_version` | string | Versão do schema: "sprint4-monitor" |
| `performance` | object | Dados de desempenho (ver seções abaixo) |

#### performance.system

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `uptime_seconds` | int | Segundos desde inicialização do Master |
| `load_average_1m` | float | CPU load nos últimos 1 minuto |
| `load_average_5m` | float | CPU load nos últimos 5 minutos |
| `cpu.usage_percent` | float | % de CPU em uso (0-100) |
| `cpu.count_logical` | int | CPUs lógicas (threads) |
| `cpu.count_physical` | int | CPUs físicas (cores) |
| `memory.total_mb` | int | RAM total em MB |
| `memory.available_mb` | int | RAM disponível em MB |
| `memory.percent_used` | float | % de RAM em uso (0-100) |
| `memory.memory_used` | int | RAM utilizada em MB |
| `disk.total_gb` | float | Espaço total em disco em GB |
| `disk.free_gb` | float | Espaço livre em disco em GB |
| `disk.percent_used` | float | % de disco em uso (0-100) |

#### performance.farm_state.workers

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `total_registered` | int | Total de workers: locais + emprestados |
| `workers_utilization` | int | Workers executando tarefa neste momento |
| `workers_alive` | int | Workers respondendo (heartbeat OK) |
| `workers_idle` | int | Workers ociosos (= total - utilization) |
| `workers_borrowed` | int | Workers emprestados para outros Masters |
| `workers_received` | int | Workers recebidos de outros Masters |
| `workers_failed` | int | Workers com falha (não respondendo) |
| `workers_home` | int | Workers nativos (= total - borrowed) |
| `workers_available_capacity` | int | Capacidade livre (= idle) |
| `borrowed_workers[]` | array | Lista de empréstimos ativos |
| `borrowed_workers[].direction` | string | "out" (enviado) ou "in" (recebido) |
| `borrowed_workers[].peer_uuid` | string | `server_uuid` do Master na outra ponta |

#### performance.farm_state.tasks

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `tasks_pending` | int | Tarefas aguardando execução (fila) |
| `tasks_running` | int | Tarefas em execução neste momento |
| `tasks_completed` | int | Total de tarefas concluídas (OK) |
| `tasks_failed` | int | Total de tarefas com falha (NOK) |
| `oldest_task_age_s` | int | Idade da tarefa pendente mais antiga em segundos |

#### performance.config_thresholds

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `max_task` | int | Threshold de saturação (ex: 100) |
| `warn_cpu_percent` | int | Limiar para alerta CPU (ex: 85) |
| `warn_memory_percent` | int | Limiar para alerta memória (ex: 85) |
| `release_task` | int | Threshold de liberação de workers (ex: 60) |

#### performance.neighbors[]

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `server_uuid` | string | Identificador do Master vizinho |
| `status` | string | "available" ou "unavailable" |
| `last_heartbeat` | string (ISO-8601) | Timestamp do último heartbeat recebido |

---

## 4. PROTOCOLO DE ENVIO — TLS/TCP

### 4.1 Conexão

**Servidor:**
- Host: `nuted-ia.dev`
- Porta: `443`
- Protocolo: **TLS 1.2+ sobre TCP**
- SNI: `nuted-ia.dev`

### 4.2 Procedimento

1. Abrir socket TCP com `nuted-ia.dev:443`
2. Envolver socket com TLS (SSL context padrão, SNI = `nuted-ia.dev`)
3. Serializar payload em JSON (UTF-8)
4. Enviar JSON via `socket.sendall()` (**sem \n, sem delimitador, sem HTTP**)
5. Fechar socket imediatamente (**SEM recv, SEM response**)

### 4.3 Código de Referência

```python
import socket
import ssl
import json

def enviar_metricas(payload: dict):
    """Envia payload para supervisor via TLS/TCP."""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    
    # Criar conexão TCP
    sock = socket.create_connection(
        ("nuted-ia.dev", 443),
        timeout=10
    )
    
    # Envolver em TLS
    ctx = ssl.create_default_context()
    sock = ctx.wrap_socket(sock, server_hostname="nuted-ia.dev")
    
    # Enviar JSON (sem \n, sem HTTP)
    sock.sendall(data)
    
    # Fechar sem recv
    sock.close()
```

### 4.4 Requisitos Estritos

- ✅ **SEM caractere `\n` ao final**
- ✅ **SEM HTTP headers (GET, POST, etc.)**
- ✅ **SEM aguardar resposta (recv)**
- ✅ **Timeout: 10 segundos**
- ✅ **TLS obrigatório** (não TCP simples)
- ✅ **SNI obrigatório**
- ✅ **Fechar socket** após envio

---

## 5. LOOP DE ENVIO PERIÓDICO

### 5.1 Timing

- **Envio inicial:** Imediato ao iniciar Master
- **Envios subsequentes:** A cada 10 segundos
- **Intervalo configurável:** `SUPERVISOR_INTERVAL = 10`

### 5.2 Threading

```python
def loop_supervisor():
    """
    Dispara envio de métricas a cada 10s em thread independente.
    - Nunca bloqueia o loop principal de aceitação de conexões
    - Se TLS falhar, próximo ciclo continua normalmente
    """
    log("[SUPERVISOR] Loop iniciado — envio a cada 10s")
    
    # Envio imediato
    threading.Thread(target=_disparar_envio, daemon=True).start()
    
    ultimo = time.time()
    while True:
        time.sleep(0.5)
        if time.time() - ultimo >= SUPERVISOR_INTERVAL:
            ultimo = time.time()
            # Dispara em thread separada (não bloqueia)
            threading.Thread(target=_disparar_envio, daemon=True).start()
```

### 5.3 Tratamento de Erros

```python
def _disparar_envio():
    """
    Tenta enviar; se falhar, registra e continua.
    Próximo ciclo não é afetado.
    """
    try:
        payload = _coletar_metricas()
        _enviar_supervisor(payload)
        log(f"[SUPERVISOR] Enviado: pending={payload[...]}, cpu={...}%")
    except socket.timeout:
        log("[SUPERVISOR TIMEOUT] 10s sem resposta")
    except ConnectionRefusedError:
        log("[SUPERVISOR OFFLINE] Conexão recusada")
    except Exception as e:
        log(f"[SUPERVISOR ERRO] {type(e).__name__}: {e}")
```

---

## 6. COLETA DE MÉTRICAS

### 6.1 Dependências

```python
import psutil      # CPU, memória, disco
import socket
import ssl
import time        # uptime, timestamp
import threading
import json
import uuid        # message_id
```

### 6.2 Funções de Coleta

#### Sistema (psutil)

```python
def _coletar_sistema():
    cpu_pct = psutil.cpu_percent(interval=1)
    load1, load5, _ = psutil.getloadavg()
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return {
        "uptime_seconds": int(time.time() - START_TIME),
        "load_average_1m": round(load1, 2),
        "load_average_5m": round(load5, 2),
        "cpu": {
            "usage_percent": round(cpu_pct, 2),
            "count_logical": psutil.cpu_count(logical=True),
            "count_physical": psutil.cpu_count(logical=False) or 1
        },
        "memory": {
            "total_mb": int(mem.total / 1024 / 1024),
            "available_mb": int(mem.available / 1024 / 1024),
            "percent_used": round(mem.percent, 2),
            "memory_used": int(mem.used / 1024 / 1024)
        },
        "disk": {
            "total_gb": round(disk.total / 1024**3, 1),
            "free_gb": round(disk.free / 1024**3, 1),
            "percent_used": round(disk.percent, 1)
        }
    }
```

#### Farm (de seu código)

```python
def _coletar_farm_state():
    with fila_lock:
        pending = len(fila_tarefas)
        oldest_age_s = 0
        if fila_tarefas:
            oldest_enqueued = fila_tarefas[0].get("_enqueued_at", time.time())
            oldest_age_s = int(time.time() - oldest_enqueued)
    
    with state_lock:
        n_borrowed = len(meus_workers_emprestados)
        n_received = len(workers_emprestados)
    
    with tasks_lock:
        tr = len(tasks_running_list)
    
    total_registered = 5 + n_received  # 5 workers nativos
    workers_idle = total_registered - tr
    
    return {
        "workers": {
            "total_registered": total_registered,
            "workers_utilization": tr,
            "workers_alive": total_registered,
            "workers_idle": workers_idle,
            "workers_borrowed": n_borrowed,
            "workers_received": n_received,
            "workers_failed": 0,
            "workers_home": 5 - n_borrowed,
            "workers_available_capacity": workers_idle,
            "borrowed_workers": [...]
        },
        "tasks": {
            "tasks_pending": pending,
            "tasks_running": tr,
            "tasks_completed": tasks_completed,
            "tasks_failed": tasks_failed,
            "oldest_task_age_s": oldest_age_s
        }
    }
```

---

## 7. DASHBOARD

### 7.1 Acesso

**URL:** `https://nuted-ia.dev/supervisor/dashboard/`

### 7.2 Visualizações

1. **Topologia de Nós**
   - Grafo visual com Masters e Workers
   - Conexões M2M ativas

2. **Métricas Agregadas**
   - CPU/Memória/Disco globais
   - Estatísticas de tasks

3. **Detalhes por Nó**
   - CPU, memória, disco individual
   - Workers vivos/ociosos/emprestados
   - Fila de tarefas

4. **Gráficos Históricos**
   - Série temporal de CPU
   - Série temporal de tarefas
   - Série temporal de carga

5. **Status de Vizinhos**
   - Heartbeat last received
   - Status: available / unavailable

---

## 8. INTEGRAÇÃO COM SPRINTS 1-3

### 8.1 Compatibilidade

- ✅ Heartbeat (Sprint 1): continua funcionando
- ✅ Ciclo de tarefas (Sprint 2): continua funcionando
- ✅ M2M (Sprint 3): continua funcionando
- ✅ Redirecionamento: continua funcionando

### 8.2 Novos Dados

Sprint 4 **apenas adiciona** coleta e envio de métricas; **não modifica** protocolos anteriores.

---

## 9. LOGGING

### 9.1 Eventos Esperados

```
[HH:MM:SS] [INIT] Threads de gerador, carga e supervisor iniciadas.
[HH:MM:SS] [SUPERVISOR] Loop iniciado — envio a cada 10s para nuted-ia.dev:443 (TLS)
[HH:MM:SS] [SUPERVISOR] Métricas enviadas. pending=42 running=4 cpu=85.42%
[HH:MM:SS] [SUPERVISOR TIMEOUT] Peer não respondeu em 5s. request_id=... descartado.
[HH:MM:SS] [SUPERVISOR ERRO] Falha ao enviar métricas: [Connection refused]
```

---

## 10. CASOS DE TESTE

| ID | Cenário | Setup | Ação | Resultado Esperado |
|----|---------|-------|------|-------------------|
| CT01 | Inicialização | Master DOWN | Iniciar Master | Primeira métrica enviada imediatamente |
| CT02 | Loop periódico | Master UP | Aguardar 10s | Segunda métrica enviada; dashboard atualizado |
| CT03 | Falha TLS | Supervisor DOWN | Enviar | Erro logado; próximo ciclo sem delay |
| CT04 | Fila cheia | 100 tasks pending | Simular load | `tasks_pending=100` no dashboard |
| CT05 | Worker emprestado | Receber 2 workers | Registrar | `workers_borrowed=2` no payload |
| CT06 | CPU alta | Executar carga | Coletar | `cpu.usage_percent > 85` acionado |
| CT07 | Timestamp ISO | Qualquer momento | Coletar | Formato: `YYYY-MM-DDTHH:MM:SSZ` |
| CT08 | message_id unique | Enviar 2x | Coletar | Cada UUID v4 diferente |
| CT09 | Interoperabilidade | Master B outro código | Enviar com UUID diferente | Dashboard mostra ambos |
| CT10 | Resilência | Perder worker | Remover | Status atualizado no dashboard |

---

## 11. DEFINIÇÃO DE "PRONTO" (DoD)

- ✅ Payload sprint4-monitor estruturalmente correto (11 campos raiz)
- ✅ Métrica de sistema coletada com `psutil`
- ✅ Métrica de farm coletada de variáveis de estado
- ✅ Conexão TLS/TCP com `nuted-ia.dev:443` funciona
- ✅ JSON enviado SEM \n, SEM HTTP, SEM recv
- ✅ Primeira métrica enviada imediatamente ao iniciar
- ✅ Métricas subsequentes enviadas a cada 10s
- ✅ Loop não bloqueia aceitação de conexões (threads)
- ✅ Falhas TLS não afetam próximo ciclo
- ✅ Dados aparecem no dashboard em < 5s
- ✅ Logs informativos indicam sucesso/erro
- ✅ Compatível com Sprints 1, 2, 3
- ✅ Tolerância a desconexões inesperadas

---

## 12. APRESENTAÇÃO

### 12.1 Checklist

- [ ] Master.py + Worker.py operacionais
- [ ] Sprints 1, 2, 3 testadas
- [ ] Supervisor endpoint acessível
- [ ] Dashboard abierto em navegador
- [ ] Métricas enviadas e visíveis
- [ ] M2M funcionando com redirecionamento
- [ ] Logs limpos

### 12.2 Demo (5 minutos)

1. **Inicializar** Master A e Master B
2. **Simular carga** (fila > threshold)
3. **Observar** request_help nos logs
4. **Assistir** redirecionamento no dashboard
5. **Verificar** métricas atualizando em tempo real
6. **Demonstrar** tolerância a falhas

---

## 13. REFERÊNCIAS

- **Supervisor:** https://nuted-ia.dev/supervisor/dashboard/
- **Python psutil:** https://psutil.readthedocs.io/
- **Python ssl:** https://docs.python.org/3/library/ssl.html
- **RFC ISO-8601:** Timestamps: YYYY-MM-DDTHH:MM:SSZ

---

*Especificação v1.0 — 17/06/2026*
