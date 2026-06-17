# SPRINT 4 — APRESENTAÇÃO FINAL E MONITORAMENTO

> **DATA DE APRESENTAÇÃO:** 15/06/2026 (TURMA B e UN) | 11/06/2025 (TURMA A)  
> **DATA DE PROVA:** 22/06/2026 (TURMA B e UN) | 18/06/2026 (TURMA A)

## OBJETIVO

Finalizar a implementação do sistema P2P com balanceamento de carga dinâmico, integrando um **Supervisor de Métricas** que monitora em tempo real o desempenho do cluster via conexão TLS/TCP, exibindo um **dashboard web** com topologia de nós, consumo de recursos, estado dos workers e filas de tarefas.

---

## ARQUITETURA SPRINT 4

### Componentes Principais

1. **Master Node (seu código)**
   - Gerencia workers locais e emprestados
   - Coleta métricas de sistema (CPU, memória, disco)
   - Monitora fila de tarefas e status de workers
   - **NOVO:** Envia relatórios de desempenho via TLS/TCP para o Supervisor

2. **Worker Node (seu código)**
   - Executa tarefas designadas pelo Master
   - Suporta redirecionamento dinâmico (Sprint 3)
   - Responde a heartbeats

3. **Supervisor de Métricas (infraestrutura do professor)**
   - Recebe conexões TLS na porta 443 (nuted-ia.dev)
   - Agrega métricas de múltiplos clusters
   - Exibe dashboard em tempo real: `https://nuted-ia.dev/supervisor/dashboard/`

### Fluxo de Monitoramento

```
Master → [coleta métricas] → [serializa JSON] → [conecta TLS] → Supervisor
                                                      ↓
                                              (envia, fecha sem recv)
                                                      ↓
                                         Dashboard atualizado em tempo real
```

---

## BACKLOG DE TAREFAS (To-Do)

### TAREFA 01 — Coleta de Métricas do Sistema

**OBJETIVO:** Implementar função `_coletar_metricas()` que captura:
- CPU (uso %, lógicas, físicas)
- Memória (total, disponível, % usado)
- Disco (total, livre, % usado)
- Uptime do nó
- Load average (1m, 5m)

**IMPLEMENTAÇÃO:**
- [ ] Importar `psutil` (já disponível no master.py)
- [ ] Capturar CPU: `psutil.cpu_percent()`, `psutil.cpu_count()`
- [ ] Capturar memória: `psutil.virtual_memory()`
- [ ] Capturar disco: `psutil.disk_usage('/')`
- [ ] Calcular uptime: `time.time() - START_TIME`
- [ ] Capturar load: `psutil.getloadavg()`

**VERIFICAÇÃO:**
```python
payload = _coletar_metricas()
assert payload['performance']['system']['cpu']['usage_percent'] >= 0
assert payload['performance']['system']['memory']['total_mb'] > 0
```

---

### TAREFA 02 — Coleta de Estado da Farm

**OBJETIVO:** Implementar função que retorna estado completo da farm:
- Total de workers (locais + emprestados)
- Workers vivos, ociosos, em execução
- Workers emprestados OUT (enviados) e IN (recebidos)
- Tarefas pendentes, em execução, completas, falhadas
- Idade da tarefa pendente mais antiga

**IMPLEMENTAÇÃO:**
- [ ] Contar workers: `total_registered = len(workers_locais) + len(workers_emprestados)`
- [ ] Workers em execução: verificar workers com tarefas ativas
- [ ] Workers ociosos: `total_registered - em_execução`
- [ ] Tarefas: manter contadores `tasks_completed`, `tasks_failed`
- [ ] Idade: calcular `time.time() - oldest_enqueued_at`

**VERIFICAÇÃO:**
```python
farm_state = _coletar_farm_state()
assert farm_state['workers']['total_registered'] >= 0
assert farm_state['tasks']['tasks_pending'] >= 0
```

---

### TAREFA 03 — Montagem do Payload Sprint 4

**OBJETIVO:** Montar o JSON completo conforme especificação (13 campos principais).

**ESTRUTURA:**
```json
{
  "server_uuid": "master_8",
  "hostname": "master_8.A.local",
  "role": "master",
  "task": "performance_report",
  "timestamp": "2026-06-08T12:34:56Z",
  "message_id": "uuid-v4",
  "payload_version": "sprint4-monitor",
  "performance": {
    "system": { ... CPU, memória, disco ... },
    "farm_state": { ... workers, tarefas ... },
    "config_thresholds": { ... limites de saturação ... },
    "neighbors": [ ... status de vizinhos ... ]
  }
}
```

**IMPLEMENTAÇÃO:**
- [ ] Preparar timestamp ISO-8601: `time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())`
- [ ] Gerar message_id: `uuid.uuid4()`
- [ ] Combinar `_coletar_metricas()` + `_coletar_farm_state()`
- [ ] Adicionar thresholds do Master
- [ ] Listar status de vizinhos (M2M)

**VERIFICAÇÃO:**
```python
payload = _montar_payload_sprint4()
assert payload['server_uuid'] == "master_8"
assert 'performance' in payload
assert len(payload) == 11  # campos esperados
```

---

### TAREFA 04 — Conexão TLS/TCP com Supervisor

**OBJETIVO:** Enviar JSON serializado via TLS/TCP sem HTTP.

**PARÂMETROS:**
- Host: `nuted-ia.dev`
- Porta: `443`
- Protocolo: **TLS sobre TCP**
- SNI: `nuted-ia.dev`
- **SEM \n, SEM HTTP, SEM recv()**

**IMPLEMENTAÇÃO:**
```python
def _enviar_supervisor(payload: dict):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    sock = socket.create_connection((SUPERVISOR_HOST, SUPERVISOR_PORT), timeout=10)
    ctx = ssl.create_default_context()
    sock = ctx.wrap_socket(sock, server_hostname=SUPERVISOR_SNI)
    sock.sendall(data)
    sock.close()
```

**CHECKLIST:**
- [ ] Importar `ssl` e `socket`
- [ ] Criar contexto SSL padrão
- [ ] Envolver socket em TLS
- [ ] Enviar dados (sem delimitador)
- [ ] Fechar conexão imediatamente (sem recv)

**VERIFICAÇÃO:**
```bash
# No dashboard: https://nuted-ia.dev/supervisor/dashboard/
# Verificar que seu node_uuid aparece com métricas atualizadas
```

---

### TAREFA 05 — Loop de Envio Periódico

**OBJETIVO:** Disparar envio de métricas a cada 10 segundos em thread independente.

**REQUISITOS:**
- Envio inicial imediato (ao iniciar o Master)
- Posterior: a cada 10s
- **NÃO bloqueie** o loop principal de aceitação de conexões
- Se TLS falhar, próximo ciclo não é atrasado (resiliente)

**IMPLEMENTAÇÃO:**
```python
def loop_supervisor():
    log("[SUPERVISOR] Loop iniciado...")
    
    # Envio imediato
    threading.Thread(target=_disparar_envio, daemon=True).start()
    
    ultimo = time.time()
    while True:
        time.sleep(0.5)
        if time.time() - ultimo >= SUPERVISOR_INTERVAL:
            ultimo = time.time()
            # Dispara em thread para não bloquear
            threading.Thread(target=_disparar_envio, daemon=True).start()
```

**CHECKLIST:**
- [ ] Thread daemon para não travar processo
- [ ] Dispara imediatamente ao iniciar
- [ ] Respeita intervalo de 10s
- [ ] Continua mesmo se falhar

---

### TAREFA 06 — Verificação de Interoperabilidade (O6)

**OBJETIVO:** Garantir que métricas são aceitas pelo supervisor mesmo com variações menores.

**TESTES:**
- [ ] Enviar payload completo
- [ ] Verificar se aparece no dashboard em < 5s
- [ ] Validar que campos obrigatórios estão presentes
- [ ] Confirmar que servidor_uuid matches com a config

---

### TAREFA 07 — Documentação e Logs

**OBJETIVO:** Registrar ciclo de envio e status.

**LOGS ESPERADOS:**
```
[HH:MM:SS] [SUPERVISOR] Loop iniciado — envio a cada 10s para nuted-ia.dev:443 (TLS)
[HH:MM:SS] [SUPERVISOR] Métricas enviadas. pending=42 running=4 cpu=85.42%
[HH:MM:SS] [SUPERVISOR ERRO] Falha ao enviar métricas: [Connection timed out]
```

**IMPLEMENTAÇÃO:**
- [ ] Log ao iniciar loop
- [ ] Log a cada envio bem-sucedido com resumo de métricas
- [ ] Log de erros com detalhes (sem travar)

---

## DEFINIÇÃO DE "PRONTO" (DoD)

### CRITÉRIOS DE ACEIÇÃO

1. ✅ Master coleta e monta payload sprint4-monitor conforme especificação
2. ✅ Conexão TLS/TCP com nuted-ia.dev:443 funciona corretamente
3. ✅ Métricas enviadas aparecem no dashboard em < 5s
4. ✅ Servidor_uuid identifica corretamente seu Master
5. ✅ Loop de 10s respeita intervalo e não bloqueia outras operações
6. ✅ Campos obrigatórios sempre presentes (nunca NULL)
7. ✅ Tolerância a falhas: se TLS falhar, próximo ciclo continua
8. ✅ Logs informativos indicam status de envio
9. ✅ Integrável com Sprints 1, 2, 3 sem conflitos
10. ✅ Interopera com outro Master sem conhecer implementação interna (O6)

---

## CASOS DE TESTE

| ID  | Cenário | Ação | Resultado Esperado |
|-----|---------|------|-------------------|
| CT01 | Inicialização | Iniciar Master | Loop supervisor começa imediatamente, primeiro envio feito |
| CT02 | Envio periódico | Aguardar 10s | Segundo envio disparado; dashboard atualizado |
| CT03 | Falha TLS | Supervisor DOWN | Erro registrado; próximo ciclo (10s) não é atrasado |
| CT04 | Métrica de carga | 100 tarefas na fila | `tasks_pending=100` aparece no dashboard |
| CT05 | Workers emprestados | Receber 2 workers | `workers_borrowed=2` no payload |
| CT06 | CPU alta | CPU > 85% | `warn_cpu_percent` acionado no dashboard |
| CT07 | Timestamp ISO | Qualquer momento | ISO-8601 format correto: `YYYY-MM-DDTHH:MM:SSZ` |
| CT08 | message_id único | Cada envio | Cada mensagem tem UUID v4 único |

---

## APRESENTAÇÃO E PROVA

### CHECKLIST PRÉ-APRESENTAÇÃO

- [ ] Código compilável (sem syntax errors)
- [ ] Master.py + Worker.py + Supervisor (infraestrutura)
- [ ] Sprints 1, 2, 3 funcionando
- [ ] Dashboard acessível e mostrando métricas
- [ ] Comunicação M2M (request_help, response, redirect) ativa
- [ ] Redirecionamento dinâmico de workers testado
- [ ] Logs limpos e informativos
- [ ] Nenhuma thread pendurada

### DEMONSTRAÇÃO (LIVE)

1. Iniciar Master A e Master B
2. Simular carga (fila > threshold)
3. Observar request_help via logs
4. Assistir redirecionamento de workers no dashboard
5. Verificar métricas sendo atualizadas em tempo real
6. Demonstrar tolerância a falhas (derrubar worker, observar reconexão)

---

## NOTAS FINAIS

- **Especificação é lei:** Seu payload deve match exatamente a definição Sprint 4 (13 campos)
- **Interoperabilidade O6:** Seu Master deve funcionar com outro Master de outra equipe
- **Resiliência:** TLS falhe, mas não derrube o Master
- **Performance:** Não deixe socket pendurado (sempre close)
- **Logging:** Cada evento em log com timestamp

**Status:** ✅ PRONTO PARA IMPLEMENTAÇÃO

---

*Plan v1.0 — 17/06/2026*
