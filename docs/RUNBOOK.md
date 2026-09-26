# Operational Runbook: Agri-Market Intelligence Platform

Production operations, local development, event stream management, and troubleshooting guide.

---

## Table of Contents
1. [Running Locally](#1-running-locally)
2. [How to Replay Kafka Events](#2-how-to-replay-kafka-events)
3. [How to Check Outbox Lag](#3-how-to-check-outbox-lag)
4. [How to Rotate API Keys and Secrets](#4-how-to-rotate-api-keys-and-secrets)
5. [Remediation: When the Outbox Relay Falls Behind](#5-remediation-when-the-outbox-relay-falls-behind)

---

## 1. Running Locally

### Prerequisites
- Docker Engine 24.0+ and Docker Compose v2.20+
- Python 3.12 (optional, if running without Docker)

### Option A: Complete Local Stack (Recommended)
Start all dependencies (FastAPI, Outbox Relay, Kafka Consumer, Beckn RPC, PostgreSQL/TimescaleDB, NATS JetStream, Redpanda Kafka, Redis, and Adminer):

```bash
# 1. Start all containerized services in background
docker compose up -d

# 2. View running containers
docker compose ps

# 3. Stream combined logs with JSON formatting
docker compose logs -f api outbox-relay kafka-consumer

# 4. Run database migrations to head
docker compose exec api alembic upgrade head
```

#### Service Port Mappings:
| Service | URL / Port | Credentials / Notes |
| :--- | :--- | :--- |
| **FastAPI API Server** | `http://localhost:8000` | OpenAPI docs at `/docs` |
| **Health Check** | `http://localhost:8000/health` | Liveness probe (200 OK) |
| **Readiness Check** | `http://localhost:8000/ready` | DB, Redis, NATS, Kafka |
| **Prometheus Metrics**| `http://localhost:8000/metrics` | Text exposition format |
| **PostgreSQL / TimescaleDB** | `localhost:5432` | user: `postgres`, pass: `postgres`, db: `agrimarket` |
| **Adminer Database UI** | `http://localhost:8080` | System: PostgreSQL, Server: `postgres` |
| **Redpanda Kafka Broker** | `localhost:9092` | Internal listener at `kafka:29092` |
| **NATS JetStream** | `localhost:4222` | HTTP Management at `http://localhost:8222` |
| **Redis Cache** | `localhost:6379` | Database `0` |

### Option B: Local Python Development with Docker Infrastructure
If debugging code directly in your local IDE:

```bash
# 1. Spin up only the backing databases and message brokers
docker compose up -d postgres redis nats kafka

# 2. Apply database migrations locally
alembic upgrade head

# 3. Launch FastAPI server with live reloading
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

---

## 2. How to Replay Kafka Events

The platform implements event-sourcing with an immutable audit log. Replaying events allows reconstructing projection read models, rebuilding caches, and repairing state after downstream subscriber failures.

### Method 1: Using the Platform Replay Utility
Run `app.events.replay` to rebuild CQRS projection state from the transactional outbox:

```bash
# Replay all trade events from the last 24 hours
python -m app.events.replay \
    --topic agri.events.trades \
    --from-time 2026-09-24T00:00:00Z \
    --to-time 2026-09-25T00:00:00Z

# Dry run to inspect affected aggregates without writing changes
python -m app.events.replay \
    --topic agri.events.prices \
    --dry-run
```

### Method 2: Resetting Consumer Group Offsets via Redpanda / Kafka CLI
If the consumer group (`agri-platform-consumer-group`) needs to re-process historical messages from the broker:

```bash
# 1. Stop the consumer worker to release partition locks
docker compose stop kafka-consumer

# 2. Reset consumer group offset to earliest available message
docker compose exec kafka rpk group seek agri-platform-consumer-group \
    --to-start \
    --topics agri.events.trades,agri.events.consents

# Or reset offset to a specific ISO timestamp
docker compose exec kafka rpk group seek agri-platform-consumer-group \
    --to-timestamp 2026-09-24T12:00:00Z \
    --topics agri.events.trades

# 3. Restart consumer worker
docker compose start kafka-consumer
```

---

## 3. How to Check Outbox Lag

The Transactional Outbox pattern guarantees at-least-once message delivery. Outbox lag indicates events written to PostgreSQL that have not yet been acknowledged by Apache Kafka.

### Method 1: Prometheus Metrics (Live)
Query the Prometheus scraper or Prometheus UI:
- `outbox_unprocessed_count`: Total count of pending outbox records.
- `outbox_relay_lag_seconds`: Age in seconds of the oldest unpublished event.

```bash
curl -s http://localhost:8000/metrics | grep outbox_
```
Expected output:
```text
outbox_relay_lag_seconds{channel="kafka"} 0.04
outbox_unprocessed_count{channel="kafka",status="pending"} 0.0
```

### Method 2: Direct Database Diagnostic Query
Connect to PostgreSQL and inspect unprocessed rows and queue latency:

```sql
SELECT
    count(*) AS pending_count,
    min(occurred_at) AS oldest_unprocessed,
    max(occurred_at) AS newest_unprocessed,
    NOW() - min(occurred_at) AS current_lag_interval,
    count(*) FILTER (WHERE retry_count > 0) AS retrying_count,
    count(*) FILTER (WHERE retry_count >= 5) AS dlq_eligible_count
FROM app.outbox_events
WHERE published_at IS NULL;
```

---

## 4. How to Rotate API Keys and Secrets

### A. Rotating Partner / Client API Keys (Zero-Downtime)
1. **Generate New Client Credentials**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/clients \
       -H "Authorization: Bearer <ADMIN_TOKEN>" \
       -H "Content-Type: application/json" \
       -d '{"client_name": "LogisticsPartner-v2", "role": "logistics_partner"}'
   ```
2. **Deploy New Key to Client**: Provide the newly generated `api_key` (`ak_live_...`) to the partner application.
3. **Verify Traffic Shift**: Inspect logs for requests using the new key fingerprint:
   ```bash
   docker compose logs api | grep "LogisticsPartner-v2"
   ```
4. **Revoke Old API Key**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/clients/<OLD_CLIENT_ID>/revoke \
       -H "Authorization: Bearer <ADMIN_TOKEN>"
   ```

### B. Rotating Cluster Secrets in Kubernetes
For `APP_JWT_SECRET_KEY` and `APP_ASSAY_HMAC_SECRET`:
1. Update `deploy/k8s/01-configmap-and-secrets.yaml` with the new secret values.
2. Apply the secret to the cluster:
   ```bash
   kubectl apply -f deploy/k8s/01-configmap-and-secrets.yaml
   ```
3. Trigger a rolling restart with zero dropped requests:
   ```bash
   kubectl rollout restart deployment/agri-api -n agri-platform
   kubectl rollout status deployment/agri-api -n agri-platform
   ```

---

## 5. Remediation: When the Outbox Relay Falls Behind

### Thresholds & Alerts
- **Warning**: `outbox_relay_lag_seconds > 10s` or `outbox_unprocessed_count > 500`
- **Critical**: `outbox_relay_lag_seconds > 60s` or `outbox_unprocessed_count > 2000`

### Triage Step 1: Check Database Lock Contention
Ensure no long-running transactions are blocking `SKIP LOCKED` queries:

```sql
SELECT pid, now() - query_start AS duration, query, state, wait_event_type, wait_event
FROM pg_stat_activity
WHERE state != 'idle' AND query ILIKE '%outbox_events%'
ORDER BY duration DESC;
```

### Triage Step 2: Check Kafka Broker Health & Backpressure
Verify that Kafka/Redpanda is accepting write batches:

```bash
# Check Kafka cluster health
docker compose exec kafka rpk cluster health

# Check network reachability from relay container
docker compose exec outbox-relay python -c "import socket; s = socket.create_connection(('kafka', 29092), timeout=2); print('Connected!'); s.close()"
```

### Triage Step 3: Identify Poison-Pill Records
If a malformed event payload exceeds serialization limits or fails schema conversion:

```sql
SELECT id, event_id, event_type, retry_count, last_error, occurred_at
FROM app.outbox_events
WHERE published_at IS NULL AND retry_count > 0
ORDER BY retry_count DESC
LIMIT 10;
```

### Remediation Actions:
1. **Increase Batch Size Temporarily**:
   Set `APP_EVENT_OUTBOX_BATCH_SIZE=500` in `docker-compose.yml` (or Kubernetes ConfigMap) to increase batch throughput 5x.
2. **Divert Stuck Poison Pills**:
   Manually flag unprocessable events to allow the relay loop to advance:
   ```sql
   UPDATE app.outbox_events
   SET published_at = NOW(),
       last_error = 'manually_diverted_to_dlq'
   WHERE published_at IS NULL AND retry_count >= 5;
   ```
3. **Restart Relay Worker**:
   ```bash
   docker compose restart outbox-relay
   # On Kubernetes:
   kubectl rollout restart deployment/agri-worker-outbox-relay -n agri-platform
   ```
4. **Confirm Lag Normalization**:
   Monitor the Prometheus metric until `outbox_relay_lag_seconds` stabilizes under 0.1s.

---

## 6. Multi-Tenant JetStream and Worker Management

### A. Programmatic Provisioning of Tenant Streams
To programmatically and idempotently provision isolated streams for an FPO/tenant (along with its dedicated DLQ stream):

```python
import asyncio
from app.telemetry.tenancy import TenantStreamManager

async def provision():
    manager = TenantStreamManager()
    result = await manager.provision_tenant_streams("punjab_fpo_01")
    print(f"Primary stream: {result.primary_stream} -> {result.primary_subject}")
    print(f"DLQ stream:     {result.dlq_stream} -> {result.dlq_subject}")

asyncio.run(provision())
```
Or execute from terminal:
```bash
python -c "import asyncio; from app.telemetry.tenancy import TenantStreamManager; asyncio.run(TenantStreamManager().provision_tenant_streams('punjab_fpo_01'))"
```
Output:
```text
Primary stream: AGRI_PUNJAB_FPO_01 -> agri.punjab_fpo_01.>
DLQ stream:     AGRI_PUNJAB_FPO_01_DLQ -> agri.punjab_fpo_01.dlq.>
```

### B. Demonstrating the 120s Deduplication Window
Publishing two messages with the same `msg_id` within 120 seconds drops the duplicate and returns the original message sequence:

```bash
python -c "
import asyncio
from app.telemetry.tenancy import TenantStreamManager

async def test_dedup():
    manager = TenantStreamManager()
    await manager.provision_tenant_streams('mh_fpo_02', duplicate_window_seconds=120)
    engine = manager.engine
    
    # First publication
    msg1 = await engine.publish(
        subject='agri.mh_fpo_02.orders.new',
        payload={'order_id': 'ORD-101'},
        msg_id='dup-check-uuid-001'
    )
    print(f'Attempt 1: Seq={msg1.seq}, Stored Count={len(engine._messages[\"AGRI_MH_FPO_02\"])}')

    # Duplicate publication with identical msg_id within 120s window
    msg2 = await engine.publish(
        subject='agri.mh_fpo_02.orders.new',
        payload={'order_id': 'ORD-101'},
        msg_id='dup-check-uuid-001'
    )
    print(f'Attempt 2: Seq={msg2.seq}, Stored Count={len(engine._messages[\"AGRI_MH_FPO_02\"])}')
    print('SUCCESS: Duplicate dropped by JetStream duplicate_window!')

asyncio.run(test_dedup())
"
```

### C. Demonstrating Poison-Pill DLQ Routing after Max Deliveries
When a worker rejects or crashes on a malformed message exceeding `max_deliver` (e.g. 3 attempts), the message is automatically marked terminated and diverted to `AGRI_{tenant_id}_DLQ`:

```bash
python -c "
import asyncio
from app.telemetry.tenancy import TenantStreamManager

async def test_dlq():
    manager = TenantStreamManager()
    await manager.provision_tenant_streams('ka_fpo_03')
    consumer = manager.create_pull_consumer('ka_fpo_03', 'test_worker', max_deliver=3)
    
    await manager.engine.publish(
        subject='agri.ka_fpo_03.assay.verify',
        payload={'lot_id': 'MALFORMED_LOT_99'},
        msg_id='poison-msg-99'
    )
    
    batch = consumer.fetch(batch_size=1)
    msg = batch[0]
    
    print(f'Delivery 1 failure -> nak()')
    msg.nak()
    print(f'Delivery 2 failure -> nak()')
    msg.nak()
    print(f'Delivery 3 failure (max_deliver reached) -> nak()')
    msg.nak()
    await asyncio.sleep(0.1) # Wait for DLQ routing
    
    dlq_stream = 'AGRI_KA_FPO_03_DLQ'
    dlq_msgs = manager.engine._messages.get(dlq_stream, [])
    print(f'DLQ Stream Messages: {len(dlq_msgs)}')
    print(f'DLQ Headers: {dlq_msgs[0].headers}')
    print('SUCCESS: Poison pill diverted to per-tenant DLQ!')

asyncio.run(test_dlq())
"
```

### D. Demonstrating Graceful Drain on SIGTERM
When a worker receives SIGTERM, it stops accepting new triggers, waits for in-flight tasks to complete up to `TimeoutStopSec`, writes a final status file, and terminates cleanly:

```bash
# 1. Start worker daemon in background
python -m app.workers.ingestion &
WORKER_PID=$!
echo \"Started Ingestion Worker with PID: \$WORKER_PID\"

# 2. Check worker status file
cat /tmp/worker_ingestion_status.json

# 3. Send SIGTERM to initiate graceful drain
kill -TERM $WORKER_PID

# 4. Observe structured shutdown log
# 'Received termination signal in ingestion worker. Initiating graceful shutdown...'
# 'Initiating graceful drain for worker ingestion...'
# 'Worker ingestion in-flight operations drained successfully.'
# 'Worker ingestion cleanly terminated.'

# 5. Confirm final status file
cat /tmp/worker_ingestion_status.json
# Expect: {\"worker\": \"ingestion\", \"status\": \"STOPPED\", ...}
```



---

## 6. Local Development on Windows via WSL2

This section covers the **complete** local workflow for contributors who run Windows with WSL2.
All commands assume **Ubuntu 22.04** (or 24.04) inside WSL2 and **Docker Desktop >= 4.26** configured with the WSL2 backend.

---

### 6.1 One-Time Setup

#### Install WSL2 and the Ubuntu distro

```powershell
# Run in PowerShell (admin)
wsl --install -d Ubuntu
wsl --set-default-version 2
# Reboot if prompted
```

#### Install Docker Desktop

1. Download from https://www.docker.com/products/docker-desktop/
2. During installation, check **Use the WSL2 based engine**.
3. After install: **Settings -> Resources -> WSL Integration** -> enable the `Ubuntu` distro.
4. Apply & restart Docker Desktop.

#### Verify the integration

```bash
# Inside WSL2 shell
docker info | grep -i "Server Version"   # should print a version number
docker compose version                    # should be v2.x
```

#### Clone the repository inside WSL2 (not on the Windows C: drive)

> **Critical**: Always clone into the WSL2 filesystem (`~/` or `/home/user/`) -- **not** `/mnt/c/...`.
> Bind-mounting a Windows path into Docker containers causes severe I/O slowdowns (10-100x) and inotify failures.

```bash
git clone git@github.com:your-org/farmer-marketplace.git ~/projects/farmer-marketplace
cd ~/projects/farmer-marketplace
```

#### Python environment

```bash
sudo apt install -y python3.12 python3.12-venv python3.12-dev
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

#### Environment variables

```bash
cp .env.example .env
# Edit .env. Critical difference for WSL2:
#   DATABASE_URL  -> use 127.0.0.1, NOT localhost (avoids IPv6 resolution issues)
#   REDIS_URL     -> also use 127.0.0.1
```

---

### 6.2 First-Run (Infrastructure -> Migrations -> Backend)

```bash
# 1. Start infrastructure containers
docker compose up -d postgres redis nats kafka

# 2. Wait ~15 s, then verify
docker compose ps   # all should be healthy or running

# 3. Apply migrations
alembic upgrade head
# Final line: Running upgrade <prev> -> 0025_otp_challenges

# 4. Start the FastAPI backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# 5. Smoke-test
curl http://127.0.0.1:8000/ready
```

---

### 6.3 Accessing Services from Windows

| Service | WSL2 URL | Windows Browser URL |
|---------|----------|---------------------|
| FastAPI backend | http://127.0.0.1:8000 | http://localhost:8000 |
| Redpanda Kafka UI | http://127.0.0.1:8080 | http://localhost:8080 |
| Adminer (DB UI) | http://127.0.0.1:8888 | http://localhost:8888 |

> WSL2 automatically bridges ports via **mirrored networking** (Docker Desktop >= 4.26).
> If ports are unreachable, enable **Settings -> Network -> Mirrored network mode** and run `wsl --shutdown && wsl`.

---

### 6.4 Daily Workflow

```bash
# Start the day
docker compose up -d
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Before committing
python -m ruff check app
python -m ruff format app

# After a git pull that adds migrations
alembic upgrade head

# End of day
docker compose stop
```

---

### 6.5 Common WSL2 Gotchas

| Problem | Cause | Fix |
|---------|-------|-----|
| `connection refused` on `127.0.0.1:8000` from Windows | Old WSL2 NAT networking | Enable mirrored mode in Docker Desktop >= 4.26 |
| Tables missing after migration | Wrong DATABASE_URL | Check `.env`; confirm `alembic.ini` is not hardcoded |
| `docker: command not found` inside WSL | Integration not enabled | Docker Desktop -> Resources -> WSL Integration -> enable Ubuntu |
| Slow I/O (pip install, npm install) | Source on `/mnt/c/` | Move project to `~/` (WSL2 native FS) |
| `ModuleNotFoundError` on `uvicorn` | Virtualenv not activated | `source .venv/bin/activate` |
| Redis 503 on `/ready` | Redis container stopped | `docker compose up -d redis` |
| `--reload` stops watching files | inotify limit exceeded | `echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.conf && sudo sysctl -p` |

---

### 6.6 Port-Forward Helper (if mirrored networking unavailable)

Run once per session in **PowerShell (admin)**:

```powershell
$wsl_ip = (wsl hostname -I).Trim().Split()[0]
netsh interface portproxy add v4tov4 listenaddress=127.0.0.1 listenport=8000 connectaddress=$wsl_ip connectport=8000
netsh interface portproxy show v4tov4
# Remove when done:
netsh interface portproxy delete v4tov4 listenaddress=127.0.0.1 listenport=8000
```

---

### 6.7 Resetting the Dev Database

```bash
# Destructive -- removes the postgres volume
docker compose down -v
docker compose up -d postgres
sleep 10
alembic upgrade head
```
