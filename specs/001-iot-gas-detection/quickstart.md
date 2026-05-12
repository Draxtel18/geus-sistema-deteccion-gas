# Quickstart: Sistema IoT de Detección de Fugas de Gas

**Feature**: 001-iot-gas-detection | **Date**: 2026-05-11

## Prerequisites

- **Docker** 24.0+ with Docker Compose v2
- **Python** 3.11+ (for local development)
- **Git** 2.40+
- **Make** (optional, for convenience commands)

## Quick Start (Docker)

### 1. Clone and Configure

```bash
# Clone repository
git clone <repository-url>
cd geus-sistema-deteccion-gas

# Copy environment template
cp .env.example .env

# Edit .env with your settings (see Environment Variables below)
```

### 2. Start Infrastructure

```bash
# Start all services
docker compose up -d

# Verify services are running
docker compose ps
```

### 3. Initialize Database

```bash
# Run migrations
docker compose exec app alembic upgrade head

# Create admin user (interactive)
docker compose exec app python -m scripts.create_admin
```

### 4. Verify Installation

```bash
# Check API health
curl http://localhost:8000/api/v1/health

# Expected response:
# {"status":"healthy","version":"1.0.0","checks":{"database":"ok","influxdb":"ok","rabbitmq":"ok","mqtt":"ok"}}
```

## Local Development Setup

### 1. Create Virtual Environment

```bash
# Create venv
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r app/requirements.txt
pip install -r worker/requirements.txt
pip install -r requirements-dev.txt
```

### 2. Start Infrastructure Only

```bash
# Start only infrastructure (DB, brokers)
docker compose up -d postgres influxdb rabbitmq mosquitto redis

# Verify infrastructure
docker compose ps
```

### 3. Run Application Locally

```bash
# Terminal 1: API
cd app
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Workers
cd worker
python main.py
```

### 4. Run Tests

```bash
# Unit tests
pytest tests/unit -v

# Integration tests (requires infrastructure)
pytest tests/integration -v

# All tests with coverage
pytest --cov=app --cov=worker --cov-report=html
```

## Environment Variables

Create `.env` file in project root:

```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=geus_gas
POSTGRES_USER=geus
POSTGRES_PASSWORD=changeme_in_production

# InfluxDB
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=changeme_in_production
INFLUXDB_ORG=geus
INFLUXDB_BUCKET=sensor_readings

# RabbitMQ
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=geus
RABBITMQ_PASSWORD=changeme_in_production
RABBITMQ_VHOST=geus

# MQTT
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
MQTT_BROKER_PORT_TLS=8883
MQTT_USERNAME=backend
MQTT_PASSWORD=changeme_in_production

# Redis (optional: caching)
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=generate_a_secure_random_key_here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Application
APP_ENV=development
APP_DEBUG=true
LOG_LEVEL=DEBUG

# Gas Thresholds (ppm)
GAS_THRESHOLD_WARNING=200
GAS_THRESHOLD_CRITICAL=500

# Test Mode
TEST_MODE_TIMEOUT_MINUTES=30
```

## Docker Compose Services

| Service | Port | Description |
|---------|------|-------------|
| `app` | 8000 | FastAPI backend |
| `worker` | - | Background workers |
| `postgres` | 5432 | PostgreSQL database |
| `influxdb` | 8086 | Time-series database |
| `rabbitmq` | 5672, 15672 | Message broker (AMQP + Management UI) |
| `mosquitto` | 1883, 8883 | MQTT broker |
| `redis` | 6379 | Cache (optional) |
| `prometheus` | 9090 | Metrics collection |
| `grafana` | 3000 | Metrics dashboard |

## Common Commands

```bash
# View logs
docker compose logs -f app
docker compose logs -f worker

# Restart service
docker compose restart app

# Shell into container
docker compose exec app bash

# Database shell
docker compose exec postgres psql -U geus -d geus_gas

# InfluxDB shell
docker compose exec influxdb influx

# RabbitMQ management
open http://localhost:15672  # guest/guest

# Stop all
docker compose down

# Stop and remove volumes (CAUTION: deletes data)
docker compose down -v
```

## Simulating ESP32 (Development)

For testing without physical hardware:

```bash
# Install MQTT client
pip install paho-mqtt

# Run simulator
python scripts/esp32_simulator.py --device-id esp32_test_001
```

The simulator will:
1. Publish readings every 1 second to `gas/reading/esp32_test_001`
2. Listen for commands on `gas/command/esp32_test_001`
3. Simulate gas alerts when `--simulate-alert` flag is used

## API Documentation

Once running, access interactive docs:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Project Structure

```
geus-sistema-deteccion-gas/
├── app/                    # Backend API
│   ├── domain/             # Business logic (DDD)
│   ├── application/        # Use cases
│   ├── infrastructure/     # Adapters (DB, API, messaging)
│   └── main.py
├── worker/                 # Background workers
│   ├── data_collector/
│   ├── gas_detection/
│   ├── alert_handler/
│   └── main.py
├── mosquitto/              # MQTT broker config
├── tests/                  # Test suite
├── scripts/                # Utility scripts
├── specs/                  # Feature specifications
├── docker-compose.yml
└── .env.example
```

## Troubleshooting

### Database connection refused
```bash
# Check PostgreSQL is running
docker compose ps postgres

# Check logs
docker compose logs postgres
```

### MQTT connection failed
```bash
# Check Mosquitto is running
docker compose ps mosquitto

# Test connection
mosquitto_pub -h localhost -p 1883 -t test -m "hello"
```

### Worker not processing messages
```bash
# Check RabbitMQ queues
docker compose exec rabbitmq rabbitmqctl list_queues

# Check worker logs
docker compose logs -f worker
```

### InfluxDB write errors
```bash
# Check InfluxDB health
curl http://localhost:8086/health

# Verify bucket exists
docker compose exec influxdb influx bucket list
```

## Next Steps

1. **Configure production environment** - See deployment docs
2. **Set up monitoring** - Access Grafana at http://localhost:3000
3. **Register ESP32 devices** - Use admin API endpoints
4. **Configure notifications** - Set up push/email in admin panel
