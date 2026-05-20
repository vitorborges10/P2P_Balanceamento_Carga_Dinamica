# P2P BALANCEAMENTO DE CARGA IMPLEMENTATION PLAN

> **FOR AGENTIC WORKERS:** REQUIRED SUB-SKILL: USE SUPERPOWERS:SUBAGENT-DRIVEN-DEVELOPMENT (RECOMMENDED) OR SUPERPOWERS:EXECUTING-PLANS TO IMPLEMENT THIS PLAN TASK-BY-TASK. STEPS USE CHECKBOX (`- [ ]`) SYNTAX FOR TRACKING.

**GOAL:** REFATORAR O PROJETO ATUAL PARA UMA ARQUITETURA PROFISSIONAL COM `SRC/` MODULAR, MANTENDO `SERVER.PY` E `CLIENT.PY` COMO ENTRADAS EXECUTÁVEIS, E ADICIONAR TESTES E DOCUMENTAÇÃO ADEQUADAS.

**ARCHITECTURE:** O PROJETO SERÁ REORGANIZADO EM MÓDULOS CLAROS: PROTOCOLO JSON, LÓGICA DE TAREFAS, COMUNICAÇÃO MASTER-TO-MASTER, E LOGGING. AS ENTRADAS DE EXECUÇÃO NO ROOT PERMANECERÃO MÍNIMAS, ENQUANTO A LÓGICA PRINCIPAL FICARÁ EM `SRC/`.

**TECH STACK:** PYTHON 3.11+, TCP SOCKETS, JSON, THREADING, PYTEST.

---

### TASK 1: CREATE REPOSITORY STRUCTURE AND ROOT ENTRY WRAPPERS

**FILES:**
- CREATE: `SRC/PROTOCOL.PY`
- CREATE: `SRC/TASKS.PY`
- CREATE: `SRC/P2P.PY`
- CREATE: `SRC/LOGGING.PY`
- CREATE: `SRC/MASTER.PY`
- CREATE: `SRC/WORKER.PY`
- CREATE: `TESTS/UNIT/TEST_PROTOCOL.PY`
- CREATE: `TESTS/INTEGRATION/TEST_MASTER_WORKER.PY`
- CREATE: `LOGS/.GITKEEP`
- MODIFY: `SERVER.PY`
- MODIFY: `CLIENT.PY`

- [ ] **STEP 1: CREATE BASIC PACKAGE AND DIRECTORIES**

```bash
mkdir src tests tests/unit tests/integration docs docs/superpowers/plans logs
```

- [ ] **STEP 2: CREATE MINIMAL `SRC/MASTER.PY`**

```python
from src.protocol import receive_json, send_json
from src.tasks import TaskQueue, simulate_load_generator
from src.p2p import start_p2p_monitor
from src.logging import create_logger
import socket
import threading

logger = create_logger('master')

def start_master(host: str, port: int):
    queue = TaskQueue()
    threading.Thread(target=simulate_load_generator, args=(queue,), daemon=True).start()
    threading.Thread(target=start_p2p_monitor, args=(queue,), daemon=True).start()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, port))
    s.listen(100)
    logger.info(f"Master listening on {host}:{port}")

    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_connection, args=(conn, addr, queue), daemon=True).start()


def handle_connection(conn: socket.socket, addr, queue):
    try:
        payload = receive_json(conn)
        logger.info(f"Received from {addr}: {payload}")
    finally:
        conn.close()
```
```

- [ ] **Step 3: Create minimal `src/worker.py`**

```python
FROM SRC.PROTOCOL IMPORT RECEIVE_JSON, SEND_JSON
FROM SRC.LOGGING IMPORT CREATE_LOGGER
IMPORT SOCKET
IMPORT TIME
IMPORT UUID

LOGGER = CREATE_LOGGER('WORKER')

WORKER_UUID = STR(UUID.UUID4())[:8].UPPER()

DEF START_WORKER(MASTER_IP: STR, MASTER_PORT: INT):
    WHILE TRUE:
        TRY:
            S = SOCKET.SOCKET(SOCKET.AF_INET, SOCKET.SOCK_STREAM)
            S.SETTIMEOUT(5)
            S.CONNECT((MASTER_IP, MASTER_PORT))
            SEND_JSON(S, {"SERVER_UUID": WORKER_UUID, "TASK": "HEARTBEAT"})
            RESPONSE = RECEIVE_JSON(S)
            LOGGER.INFO(F"HEARTBEAT RESPONSE: {RESPONSE}")
            S.CLOSE()
        EXCEPT EXCEPTION AS EXC:
            LOGGER.ERROR(F"HEARTBEAT FAILED: {EXC}")
        TIME.SLEEP(10)
```
```

- [ ] **STEP 4: CREATE `SERVER.PY` ENTRY WRAPPER**

```python
from src.master import start_master

if __name__ == "__main__":
    start_master('127.0.0.1', 8000)
```
```

- [ ] **Step 5: Create `client.py` entry wrapper**

```python
FROM SRC.WORKER IMPORT START_WORKER

IF __NAME__ == "__MAIN__":
    START_WORKER('127.0.0.1', 8000)
```
```

- [ ] **STEP 6: CREATE PLACEHOLDER TEST FILES**

```python
# tests/unit/test_protocol.py
from src.protocol import parse_message


def test_parse_message_accepts_valid_json():
    payload = parse_message('{"TASK": "HEARTBEAT"}\n')
    assert payload["TASK"] == "HEARTBEAT"
```

```python
# tests/integration/test_master_worker.py
import socket
import threading
from src.master import start_master


def test_master_accepts_heartbeat_connection():
    server_thread = threading.Thread(target=start_master, args=('127.0.0.1', 9000), daemon=True)
    server_thread.start()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('127.0.0.1', 9000))
    sock.close()
```
```

### Task 2: Implement protocol parsing and validation

**Files:**
- Modify: `src/protocol.py`
- Modify: `tests/unit/test_protocol.py`

- [ ] **Step 1: Implement `send_json`, `receive_json`, `parse_message`, and `validate_message`**

```python
IMPORT JSON
IMPORT SOCKET
FROM TYPING IMPORT ANY, DICT


DEF SEND_JSON(SOCK: SOCKET.SOCKET, PAYLOAD: DICT[STR, ANY]):
    SOCK.SENDALL((JSON.DUMPS(PAYLOAD) + "\N").ENCODE('UTF-8'))


DEF RECEIVE_JSON(SOCK: SOCKET.SOCKET) -> DICT[STR, ANY]:
    BUFFER = ""
    WHILE TRUE:
        DATA = SOCK.RECV(4096).DECODE('UTF-8')
        IF NOT DATA:
            RAISE CONNECTIONERROR("CONNECTION CLOSED")
        BUFFER += DATA
        IF "\N" IN BUFFER:
            LINE, REST = BUFFER.SPLIT("\N", 1)
            RETURN PARSE_MESSAGE(LINE + "\N")


DEF PARSE_MESSAGE(RAW: STR) -> DICT[STR, ANY]:
    TRY:
        PAYLOAD = JSON.LOADS(RAW.STRIP())
    EXCEPT JSON.JSONDECODEERROR AS EXC:
        RAISE VALUEERROR(F"INVALID JSON: {EXC}")
    RETURN PAYLOAD


DEF VALIDATE_MESSAGE(PAYLOAD: DICT[STR, ANY], REQUIRED_FIELDS: LIST[STR]):
    MISSING = [FIELD FOR FIELD IN REQUIRED_FIELDS IF FIELD NOT IN PAYLOAD]
    IF MISSING:
        RAISE VALUEERROR(F"MISSING FIELDS: {MISSING}")
```
```

- [ ] **STEP 2: ADD TESTS FOR VALIDATION AND DELIMITER HANDLING**

```python
def test_parse_message_accepts_valid_json():
    payload = parse_message('{"TASK": "HEARTBEAT"}\n')
    assert payload["TASK"] == "HEARTBEAT"


import pytest
from src.protocol import validate_message


def test_validate_message_fails_missing_fields():
    with pytest.raises(ValueError, match="Missing fields"):
        validate_message({"TASK": "HEARTBEAT"}, ["TASK", "SERVER_UUID"])
```
```

### Task 3: Implement Worker lifecycle and task processing

**Files:**
- Modify: `src/worker.py`
- Modify: `src/tasks.py`
- Create: `tests/unit/test_worker.py`

- [ ] **Step 1: Implement worker presentation and QUERY processing**

```python
FROM SRC.PROTOCOL IMPORT SEND_JSON, RECEIVE_JSON
FROM SRC.LOGGING IMPORT CREATE_LOGGER
IMPORT RANDOM
IMPORT SOCKET
IMPORT TIME
IMPORT UUID

LOGGER = CREATE_LOGGER('WORKER')
WORKER_UUID = STR(UUID.UUID4())[:8].UPPER()


DEF BUILD_PRESENTATION_PAYLOAD(ORIGINAL_MASTER: STR | NONE = NONE) -> DICT:
    PAYLOAD = {"WORKER": "ALIVE", "WORKER_UUID": WORKER_UUID}
    IF ORIGINAL_MASTER:
        PAYLOAD["SERVER_UUID"] = ORIGINAL_MASTER
    RETURN PAYLOAD


DEF PROCESS_QUERY(MESSAGE: DICT) -> DICT:
    TIME.SLEEP(RANDOM.UNIFORM(0.5, 1.5))
    STATUS = "OK" IF RANDOM.RANDOM() < 0.9 ELSE "NOK"
    RETURN {"STATUS": STATUS, "TASK": "QUERY", "WORKER_UUID": WORKER_UUID}
```

- [ ] **Step 2: Add Worker unit tests**

```python
FROM SRC.WORKER IMPORT BUILD_PRESENTATION_PAYLOAD, PROCESS_QUERY


DEF TEST_BUILD_PRESENTATION_PAYLOAD_LOCAL():
    PAYLOAD = BUILD_PRESENTATION_PAYLOAD()
    ASSERT PAYLOAD["WORKER"] == "ALIVE"
    ASSERT "SERVER_UUID" NOT IN PAYLOAD


DEF TEST_PROCESS_QUERY_RETURNS_STATUS():
    RESULT = PROCESS_QUERY({"TASK": "QUERY"})
    ASSERT RESULT["TASK"] == "QUERY"
    ASSERT RESULT["STATUS"] IN {"OK", "NOK"}
```
```

### TASK 4: IMPLEMENT MASTER TASK QUEUE, ROUTING AND ACK HANDLING

**FILES:**
- MODIFY: `SRC/MASTER.PY`
- MODIFY: `SRC/TASKS.PY`
- CREATE: `TESTS/UNIT/TEST_TASKS.PY`
- MODIFY: `TESTS/INTEGRATION/TEST_MASTER_WORKER.PY`

- [ ] **STEP 1: IMPLEMENT `TASKQUEUE` AND `SIMULATE_LOAD_GENERATOR`**

```python
from collections import deque
import threading
import time
import uuid

class TaskQueue:
    def __init__(self):
        self._queue = deque()
        self._lock = threading.Lock()

    def enqueue(self, task: dict):
        with self._lock:
            self._queue.append(task)

    def dequeue(self) -> dict | None:
        with self._lock:
            return self._queue.popleft() if self._queue else None

    def size(self) -> int:
        with self._lock:
            return len(self._queue)

    def size(self) -> int:
        with self._lock:
            return len(self._queue)


def simulate_load_generator(queue: TaskQueue):
    users = ["Alice", "Bob", "Carlos", "Diana", "Eduardo"]
    count = 0
    while True:
        time.sleep(1)
        task = {"TASK": "QUERY", "USER": users[count % len(users)]}
        queue.enqueue(task)
        count += 1
```

- [ ] **STEP 2: IMPLEMENT TASK ROUTING IN `SRC/MASTER.PY`**

```python
from src.protocol import receive_json, send_json, validate_message
from src.tasks import TaskQueue
from src.logging import create_logger


def process_worker_request(payload: dict, queue: TaskQueue) -> dict:
    validate_message(payload, ["WORKER", "WORKER_UUID"])
    if payload.get("WORKER", "").upper() != "ALIVE":

        DATA = CONN.RECV(4096).DECODE('UTF-8')
- `src/logging.py`: logger compartilhado e arquivos de log
        # PLANO DE IMPLEMENTAÇÃO: SISTEMA P2P BALANCEAMENTO DE CARGA (SPRINTS 1, 2 E 3)

        ## 1. OBJETIVO GERAL
        Implementar um sistema distribuído P2P com balanceamento dinâmico de carga, conforme o plano do projeto (PDF), cobrindo as Sprints 1, 2 e 3:
        - Sprint 1: Master/Worker básico, distribuição de tarefas e heartbeat.
        - Sprint 2: Pool de workers, fila de tarefas, ACK, e tratamento de ausência de tarefas.
        - Sprint 3: Protocolo Master-to-Master, empréstimo/devolução de workers, parsing estrito e interoperabilidade.

        ## 2. ARQUITETURA DO PROJETO
        - `server.py`: Master principal. Aceita conexões de workers e de outros masters.
        - `client.py`: Worker. Conecta ao master, executa tarefas, pode ser redirecionado.
        - `server2.py`/`client2.py`: Segundo master/worker para simulação P2P.
        - Comunicação via TCP + JSON, delimitado por `\n`.

        ## 3. SPRINT 1: MASTER/WORKER BÁSICO
        - Master aceita conexões de workers.
        - Worker envia heartbeat periódico.
        - Master responde com status.
        - Mensagens:
          - Worker → Master: `{ "SERVER_UUID": "<WORKER_UUID>", "TASK": "HEARTBEAT" }`
          - Master → Worker: `{ "SERVER_UUID": "MASTER_A", "TASK": "HEARTBEAT", "RESPONSE": "ALIVE" }`

        ## 4. SPRINT 2: FILA DE TAREFAS E POOL DE WORKERS
        - Master mantém fila de tarefas (ex: `QUERY`).
        - Worker solicita tarefa, recebe `QUERY` ou `NO_TASK`.
        - Worker executa e responde com status.
        - Master envia ACK.
        - Mensagens:
          - Worker → Master: `{ "WORKER": "ALIVE", "WORKER_UUID": "..." }`
          - Master → Worker: `{ "TASK": "QUERY", "USER": "..." }` ou `{ "TASK": "NO_TASK" }`
          - Worker → Master: `{ "STATUS": "OK"|"NOK", "TASK": "QUERY", "WORKER_UUID": "..." }`
          - Master → Worker: `{ "STATUS": "ACK", "WORKER_UUID": "..." }`

        ## 5. SPRINT 3: PROTOCOLO MASTER-TO-MASTER (P2P)
        - Quando saturado, master solicita ajuda ao vizinho (`REQUEST_HELP`).
        - Master vizinho responde (`RESPONSE_ACCEPTED` ou `RESPONSE_REJECTED`).
        - Se aceito, master vizinho redireciona workers (`COMMAND_REDIRECT`).
        - Worker se registra como temporário (`REGISTER_TEMPORARY_WORKER`).
        - Quando carga normaliza, master devolve worker (`COMMAND_RELEASE`) e notifica origem (`NOTIFY_WORKER_RETURNED`).
        - Parsing estrito: campos obrigatórios, type minúsculo, UUID v4, log de tipos desconhecidos.
        - Mensagens:
          - Master → Master:
            - `REQUEST_HELP`, `RESPONSE_ACCEPTED`, `RESPONSE_REJECTED`, `COMMAND_REDIRECT`, `COMMAND_RELEASE`, `REGISTER_TEMPORARY_WORKER`, `NOTIFY_WORKER_RETURNED`
          - Estrutura base:
            ```json
            { "type": "request_help", "request_id": "<uuid>", "payload": { ... } }
            ```

        ## 6. FLUXOS PRINCIPAIS
        ### 6.1. Worker
        1. Conecta ao master, envia heartbeat.
        2. Solicita tarefa, executa, responde status.
        3. Pode ser redirecionado para outro master.
        4. Retorna ao master original quando liberado.

        ### 6.2. Master
        1. Aceita conexões de workers e masters.
        2. Mantém fila de tarefas.
        3. Negocia empréstimo/devolução de workers via protocolo P2P.
        4. Faz parsing estrito das mensagens.

        ## 7. VALIDAÇÃO E TESTES
        - Testar todos os fluxos: heartbeat, fila, redirecionamento, devolução.
        - Validar parsing estrito: type minúsculo, campos obrigatórios, UUID v4.
        - Testar interoperabilidade entre masters.

        ## 8. REFERÊNCIAS
        - plano_proj_SD-26_1.pdf (protocolo e requisitos)
        - server.py, client.py, server2.py, client2.py (implementação)
        - docs/superpowers/specs/sprint3_master_to_master_protocol.md (detalhe do protocolo)

        ---

        Este plano reflete fielmente o código implementado e cobre todos os requisitos das Sprints 1, 2 e 3 do projeto.

### Plan Self-Review

- [ ] Confirm each task maps to a sprint requirement do documento do projeto
- [ ] Remove any placeholder tests and replace with real socket or unit assertions
- [ ] Ensure root `server.py` and `client.py` remain executable wrappers
- [ ] Validate all file paths and code snippets are consistent
