
# SPRINT 03: PROTOCOLO MASTER-TO-MASTER (P2P)

## OBJETIVO
Implementar o protocolo de negociação Master-to-Master e o ciclo completo de empréstimo e devolução de workers entre dois masters, conforme o plano do projeto (PDF) e o código das Sprints 1, 2 e 3.

Esta especificação cobre:
- Ciclo de vida do empréstimo de workers
- Estrutura exata dos payloads JSON
- Regras de negócio, parsing estrito, tratamento de erros e interoperabilidade

## 1. CONTEXTO E FLUXO GERAL

Quando um master satura sua fila de tarefas, ele solicita ajuda ao master vizinho via TCP/JSON. O vizinho pode aceitar (emprestando workers) ou recusar. Workers emprestados são redirecionados, registrados como temporários e devolvidos quando a carga normaliza. Todo o parsing é estrito, com logs para tipos desconhecidos e validação de campos obrigatórios.

## 2. CICLO DE VIDA DO EMPRÉSTIMO DE WORKERS

1. `request_help`: Master saturado conecta ao vizinho e solicita workers extras.
2. `response_accepted` ou `response_rejected`: Vizinho avalia e responde.
3. `command_redirect`: Vizinho ordena workers a se redirecionarem ao master saturado.
4. `register_temporary_worker`: Worker se apresenta ao novo master.
5. Worker segue ciclo Sprint 02 (`ALIVE`, `QUERY`, `NO_TASK`, `ACK`).
6. `command_release`: Master devolve worker ao master de origem.
7. `notify_worker_returned`: Master notifica origem da devolução.

## 3. ESTRUTURA DOS PAYLOADS JSON

Todas as mensagens usam JSON delimitado por `\n`.

### Estrutura base
```json
{
  "type": "request_help",
  "request_id": "<uuid_v4>",
  "payload": { ... }
}
```

### Exemplos de mensagens

#### `request_help`
```json
{
  "type": "request_help",
  "request_id": "...",
  "payload": {
    "master_id": "A",
    "current_load": 150,
    "capacity": 100,
    "workers_needed": 2
  }
}
```

#### `response_accepted`
```json
{
  "type": "response_accepted",
  "request_id": "...",
  "payload": {
    "workers_offered": 2,
    "worker_details": [
      { "id": "B1", "address": "ip:port_worker_b1" },
      { "id": "B2", "address": "ip:port_worker_b2" }
    ]
  }
}
```

#### `response_rejected`
```json
{
  "type": "response_rejected",
  "request_id": "...",
  "payload": { "reason": "high_load" }
}
```

#### `command_redirect`
```json
{
  "type": "command_redirect",
  "request_id": "...",
  "payload": { "new_master_address": "ip:port" }
}
```

#### `register_temporary_worker`
```json
{
  "type": "register_temporary_worker",
  "request_id": "...",
  "payload": {
    "worker_id": "B1",
    "original_master_address": "ip:port"
  }
}
```

#### `command_release`
```json
{
  "type": "command_release",
  "request_id": "...",
  "payload": { "original_master_address": "ip:port" }
}
```

#### `notify_worker_returned`
```json
{
  "type": "notify_worker_returned",
  "request_id": "...",
  "payload": { "worker_id": "B1" }
}
```

## 4. REGRAS DE NEGÓCIO E PARSING ESTRITO

- `type` deve ser minúsculo e exatamente igual aos exemplos.
- `request_id` deve ser UUID v4.
- Campos obrigatórios ausentes tornam a mensagem inválida.
- Campos desconhecidos são ignorados.
- Mensagens com `type` desconhecido devem ser logadas e ignoradas.
- Todas as mensagens terminam com `\n`.
- Strings de controle (`ALIVE`, `QUERY`, `NO_TASK`, `OK`, `NOK`, `ACK`) são caixa alta.
- Timeout de 5 segundos para negociações master-to-master.
- O parser deve ser tolerante a campos extras, mas estrito quanto aos obrigatórios.
- O master deve aceitar conexões simultâneas de workers e outros masters.
- Locks devem proteger fila de tarefas e workers emprestados.

## 5. CASOS DE TESTE ESSENCIAIS

- CT01: `request_help` aceito.
- CT02: `request_help` recusado.
- CT03: Correlação de `request_id` com múltiplas negociações.
- CT04: Worker redirecionado registra-se temporariamente.
- CT05: Worker emprestado processa tarefa e recebe ACK.
- CT06: Worker devolvido com `command_release` e `notify_worker_returned`.
- CT07: Timeout de negociação em 5 segundos.
- CT08: Queda de conexão master receptor e recuperação pelo worker.
- CT09: Tipo desconhecido ignorado sem falha.

---
Este documento reflete o protocolo real implementado nas Sprints 1, 2 e 3, alinhado ao plano do projeto e ao código.

## 2. CICLO DE VIDA DO EMPRÉSTIMO DE WORKERS

1. `REQUEST_HELP`
   - MASTER A DETECTA SATURAÇÃO E CONECTA-SE AO MASTER B.
   - MASTER A ENVIA `REQUEST_HELP` COM CARGA ATUAL, CAPACIDADE E NÚMERO DE WORKERS NECESSÁRIOS.
2. `RESPONSE_ACCEPTED` OU `RESPONSE_REJECTED`
   - MASTER B AVALIA SUA CARGA E DISPONIBILIDADE DE WORKERS OCIOSOS.
   - SE ACEITÁVEL, RESPONDE COM `RESPONSE_ACCEPTED` E INCLUI `WORKERS_OFFERED` E `WORKER_DETAILS`.
   - CASO CONTRÁRIO, RESPONDE COM `RESPONSE_REJECTED` CONTENDO `REASON`.
3. `COMMAND_REDIRECT`
   - APÓS ACEITAR, MASTER B ORDENA A CADA WORKER ESCOLHIDO PARA REDIRECIONAR-SE AO MASTER A.
   - O WORKER FINALIZA SUA CONEXÃO COM MASTER B E ABRE NOVA CONEXÃO COM MASTER A.
4. `REGISTER_TEMPORARY_WORKER`
   - O WORKER RECONECTADO APRESENTA-SE AO MASTER A COMO EMPRESTADO.
   - MASTER A REGISTRA O WORKER E PASSA A TRATÁ-LO COMO WORKER TEMPORÁRIO.
5. CICLO DE TAREFAS DA SPRINT 02
   - O WORKER TEMPORÁRIO SEGUE O PROTOCOLO DE TAREFAS JÁ EXISTENTE, ENVIANDO `ALIVE` COM `SERVER_UUID` ORIGINAL E CONSUMINDO `QUERY` OU `NO_TASK`.
6. `COMMAND_RELEASE`
   - QUANDO A CARGA DO MASTER A NORMALIZA (ABAIXO DO THRESHOLD DE LIBERAÇÃO), MASTER A INSTRUI O WORKER A RETORNAR AO MASTER DE ORIGEM.
7. `NOTIFY_WORKER_RETURNED`
   - EM PARALELO, MASTER A NOTIFICA MASTER B QUE O WORKER FOI DEVOLVIDO.
   - MASTER B ATUALIZA SEU ESTADO DE FARM E ACEITA O RETORNO DO WORKER.

## 3. ESTRUTURA EXATA DOS PAYLOADS JSON

TODAS AS MENSAGENS MASTER-TO-MASTER E WORKER-TO-MASTER USAM OBJETOS JSON TERMINADOS COM `\N`.
A ESTRUTURA GENÉRICA DE CADA MENSAGEM P2P É:

```json
{
  "type": "tipo_da_mensagem",
  "request_id": "uuid_unico_para_rastreio",
  "payload": {
    // dados específicos da mensagem
  }
}
```

### 3.1 `REQUEST_HELP`

```json
{
  "type": "request_help",
  "request_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "payload": {
    "master_id": "A",
    "current_load": 150,
    "capacity": 100,
    "workers_needed": 2
  }
}
```

### 3.2 `RESPONSE_ACCEPTED`

```json
{
  "type": "response_accepted",
  "request_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "payload": {
    "workers_offered": 2,
    "worker_details": [
      { "id": "B1", "address": "ip:port_worker_b1" },
      { "id": "B2", "address": "ip:port_worker_b2" }
    ]
  }
}
```

### 3.3 `RESPONSE_REJECTED`

```json
{
  "type": "response_rejected",
  "request_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "payload": {
    "reason": "high_load"
  }
}
```

POSSÍVEIS VALORES DE `REASON`:
- `HIGH_LOAD`
- `NO_WORKERS_AVAILABLE`
- `REFUSED`

### 3.4 `COMMAND_REDIRECT`

```json
{
  "type": "command_redirect",
  "request_id": "f0e9d8c7-b6a5-4321-fedc-ba9876543210",
  "payload": {
    "new_master_address": "ip_master_A:port"
  }
}
```

### 3.5 `REGISTER_TEMPORARY_WORKER`

```json
{
  "type": "register_temporary_worker",
  "request_id": "c1b2a3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6",
  "payload": {
    "worker_id": "B1",
    "original_master_address": "ip_master_B:port"
  }
}
```

### 3.6 `COMMAND_RELEASE`

```json
{
  "type": "command_release",
  "request_id": "z9y8x7w6-v5u4-t3s2-r1q0-p9o8n7m6l5k4",
  "payload": {
    "original_master_address": "ip_master_B:port"
  }
}
```

### 3.7 `NOTIFY_WORKER_RETURNED`

```json
{
  "type": "notify_worker_returned",
  "request_id": "m1n2b3v4-c5x6-z7a8-s9d0-f1g2h3j4k5l6",
  "payload": {
    "worker_id": "B1"
  }
}
```

## 4. REGRAS DE NEGÓCIO E TRATAMENTO DE ERROS

### 4.1 REGRAS GERAIS DE PROTOCOLO
- `TYPE` DEVE SER TRATADO EM LETRAS MINÚSCULAS EXATAMENTE COMO DEFINIDO: `REQUEST_HELP`, `RESPONSE_ACCEPTED`, `RESPONSE_REJECTED`, `COMMAND_REDIRECT`, `REGISTER_TEMPORARY_WORKER`, `COMMAND_RELEASE`, `NOTIFY_WORKER_RETURNED`.
- `REQUEST_ID` DEVE SER UUID V4.
- TODA MENSAGEM DEVE TERMINAR EM `\N`.
- CAMPOS OBRIGATÓRIOS AUSENTES TORNAM A MENSAGEM INVÁLIDA.
- CAMPOS DESCONHECIDOS DEVEM SER IGNORADOS, MAS NÃO PODEM DERRUBAR O PROCESSO.
- O PARSER DEVE SER TOLERANTE A CAMPOS EXTRAS E ESTRITO QUANTO À PRESENÇA DOS CAMPOS OBRIGATÓRIOS.
- TODAS AS STRINGS DE CONTROLE (`ALIVE`, `QUERY`, `NO_TASK`, `OK`, `NOK`, `ACK`) DEVEM SER TRATADAS EM CAIXA ALTA.

### 4.2 CICLO DE `REQUEST_HELP`
- MASTER SOLICITANTE ENVIA `REQUEST_HELP` QUANDO SUA FILA ULTRAPASSA O THRESHOLD DE SATURAÇÃO.
- MASTER SOLICITANTE AGUARDA NO MÁXIMO 5 SEGUNDOS POR UMA RESPOSTA.
- SE O TIMEOUT OCORRER, O `REQUEST_ID` É DESCARTADO E O MASTER PODE TENTAR OUTRO VIZINHO OU ABORTAR O PEDIDO.

### 4.3 RESPOSTA DO MASTER OFERTANTE
- MASTER OFERTANTE AVALIA CARGA ATUAL E DISPONIBILIDADE DE WORKERS OCIOSOS.
- SE ACEITAR, ENVIA `RESPONSE_ACCEPTED` COM `WORKERS_OFFERED` E `WORKER_DETAILS`.
- SE RECUSAR, ENVIA `RESPONSE_REJECTED` COM `REASON`.
- O `REQUEST_ID` DA RESPOSTA DEVE SER IDÊNTICO AO DA REQUISIÇÃO ORIGINAL.

### 4.4 REDIRECIONAMENTO DE WORKERS
- `COMMAND_REDIRECT` É EMITIDO PELO MASTER OFERTANTE A CADA WORKER SELECIONADO.
- O WORKER DEVE ENCERRAR GRACIOSAMENTE SUA CONEXÃO COM O MASTER ATUAL ANTES DE SE RECONECTAR.
- O WORKER ABRE NOVA CONEXÃO COM O NOVO MASTER E ENVIA `REGISTER_TEMPORARY_WORKER`.
- `REGISTER_TEMPORARY_WORKER` INFORMA O WORKER COMO `WORKER_ID` E `ORIGINAL_MASTER_ADDRESS`.

### 4.5 REGISTRO E OPERAÇÃO DO WORKER TEMPORÁRIO
- APÓS REGISTRO, O WORKER OPERARÁ SOB O PROTOCOLO DA SPRINT 02.
- O WORKER EMPRESTADO DEVE INCLUIR `SERVER_UUID` NO PAYLOAD DE APRESENTAÇÃO `ALIVE` PARA INDICAR O MASTER DE ORIGEM.
- O MASTER RECEPTOR DEVE REGISTRAR O WORKER COMO TEMPORÁRIO E MANTER A ORIGEM PARA DEVOLVER MAIS TARDE.

### 4.6 DEVOLUÇÃO DO WORKER
- MASTER RECEPTOR MONITORA UM THRESHOLD DE LIBERAÇÃO MENOR QUE O THRESHOLD DE SATURAÇÃO (HISTERESE).
- QUANDO A CARGA NORMALIZA, MASTER RECEPTOR ENVIA `COMMAND_RELEASE` AO WORKER EMPRESTADO.
- EM PARALELO, MASTER RECEPTOR ENVIA `NOTIFY_WORKER_RETURNED` AO MASTER DE ORIGEM PELA CONEXÃO MASTER-TO-MASTER.
- O WORKER DEVE RECONECTAR-SE AO MASTER DE ORIGEM E REAPRESENTAR-SE VIA PROTOCOLO PADRÃO.

### 4.7 TIMEOUT E RESILIÊNCIA
- O MASTER SOLICITANTE DEVE REGISTRAR TIMEOUTS DE NEGOCIAÇÃO E TRATAR O PEER COMO INDISPONÍVEL.
- SE A CONEXÃO MASTER-TO-MASTER CAIR DURANTE A NEGOCIAÇÃO, O SOLICITANTE DESCARTA O `REQUEST_ID` E GRAVA O ERRO EM LOG.
- SE UM WORKER EMPRESTADO PERDER A CONEXÃO COM O MASTER RECEPTOR, ELE DEVE TENTAR RECONECTAR AO MASTER DE ORIGEM.
- MENSAGENS COM `TYPE` DESCONHECIDO DEVEM SER LOGADAS E IGNORADAS.

### 4.8 CONCORRÊNCIA E PROTEÇÃO DE ESTADO
- O MASTER DEVE PROTEGER A FILA DE TAREFAS E O REGISTRO DE WORKERS EMPRESTADOS CONTRA CONDIÇÕES DE CORRIDA.
- PODE USAR LOCKS, SEMÁFOROS OU ESTRUTURAS THREAD-SAFE.
- O MASTER DEVE PODER ACEITAR CONEXÕES DE WORKERS E DE OUTROS MASTERS SIMULTANEAMENTE.

## 5. CASOS DE TESTE DE SPRINT 03

- CT01: `REQUEST_HELP` ACEITO.
- CT02: `REQUEST_HELP` RECUSADO.
- CT03: CORRELAÇÃO DE `REQUEST_ID` COM MÚLTIPLAS NEGOCIAÇÕES SIMULTÂNEAS.
- CT04: WORKER REDIRECIONADO REGISTRA-SE TEMPORARIAMENTE.
- CT05: WORKER EMPRESTADO PROCESSA TAREFA E RECEBE ACK.
- CT06: WORKER DEVOLVIDO COM `COMMAND_RELEASE` E `NOTIFY_WORKER_RETURNED`.
- CT07: TIMEOUT DE NEGOCIAÇÃO EM 5 SEGUNDOS.
- CT08: QUEDA DE CONEXÃO MASTER RECEPTOR E RECUPERAÇÃO PELO WORKER.
- CT09: TIPO DESCONHECIDO IGNORADO SEM FALHA.

## 6. OBSERVAÇÕES IMPORTANTES

- `COMMAND_REDIRECT`, `REGISTER_TEMPORARY_WORKER`, `COMMAND_RELEASE` E `NOTIFY_WORKER_RETURNED` PODEM USAR `REQUEST_ID` PRÓPRIOS PORQUE SÃO FLUXOS INDEPENDENTES.
- A CONEXÃO MASTER-TO-MASTER PODE SER MANTIDA ABERTA EM POOL PARA REUTILIZAÇÃO.
- O NOVO MASTER DEVE ACEITAR WORKERS TEMPORÁRIOS SEM CONHECIMENTO PRÉVIO DA IMPLEMENTAÇÃO DO OUTRO LADO, APENAS SEGUINDO O PROTOCOLO.
