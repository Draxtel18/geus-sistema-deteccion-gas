# Research: Sistema IoT de Detección de Fugas de Gas

**Feature**: 001-iot-gas-detection | **Date**: 2026-05-11

## Technical Decisions

### 1. Python Version & Runtime

**Decision**: Python 3.11+
**Rationale**: Native asyncio improvements, better error messages, required for SQLAlchemy 2.0 async support
**Alternatives Considered**:
- Python 3.10: Lacks some asyncio optimizations
- Python 3.12: Too recent, dependency compatibility concerns

### 2. Web Framework

**Decision**: FastAPI 0.110+
**Rationale**: Native async support, automatic OpenAPI docs, Pydantic v2 integration, high performance with uvicorn
**Alternatives Considered**:
- Flask: Sync-first, requires additional async wrappers
- Django: Heavy for microservices, async support less mature

### 3. MQTT Client

**Decision**: aiomqtt (async wrapper over paho-mqtt)
**Rationale**: Native asyncio integration, TLS support for MQTTS, compatible with Mosquitto broker
**Alternatives Considered**:
- paho-mqtt: Sync-only, requires threading
- gmqtt: Less maintained

### 4. Message Queue (Async Processing)

**Decision**: RabbitMQ + aio-pika
**Rationale**: Reliable message delivery, dead letter queues for failed alerts, native async Python client
**Alternatives Considered**:
- Redis Streams: Less robust delivery guarantees
- Apache Kafka: Overkill for current scale (50 sensors)

### 5. Relational Database

**Decision**: PostgreSQL 15+ with SQLAlchemy 2.0 async
**Rationale**: ACID compliance for users/alerts, native JSON support, constitution mandates SQLAlchemy 2.0
**Alternatives Considered**:
- MySQL: Less JSON support
- SQLite: Not suitable for concurrent access

### 6. Time-Series Database

**Decision**: InfluxDB 2.x with native Python client
**Rationale**: Optimized for high-frequency telemetry (1000 readings/sec), automatic retention policies, constitution mandates native client (no ORM)
**Alternatives Considered**:
- TimescaleDB: Requires PostgreSQL expertise, adds complexity
- QuestDB: Less mature ecosystem

### 7. Authentication & Authorization

**Decision**: JWT tokens with RBAC (4 roles)
**Rationale**: Stateless auth for horizontal scaling, spec defines 4 roles (Admin, Operador, Técnico, Auditor)
**Alternatives Considered**:
- Session-based: Requires shared state, breaks scalability principle
- OAuth2: Overkill for internal system

### 8. API Gateway / Proxy

**Decision**: Nginx with Let's Encrypt (Certbot)
**Rationale**: SSL termination, auto-renewal, spec requires HTTPS (443) and MQTTS (8883)
**Alternatives Considered**:
- Traefik: More complex configuration
- Caddy: Less documentation for MQTT proxying

### 9. Containerization

**Decision**: Docker + Docker Compose
**Rationale**: Consistent deployment, spec assumes Docker on DigitalOcean VPS
**Alternatives Considered**:
- Kubernetes: Overkill for single-VPS deployment
- Podman: Less ecosystem support

### 10. Monitoring Stack

**Decision**: Prometheus + Grafana
**Rationale**: Spec explicitly requires Prometheus + Grafana for metrics
**Alternatives Considered**:
- Datadog: Cost concerns
- ELK Stack: More suited for logs than metrics

### 11. ESP32 Communication Protocol

**Decision**: MQTTS (MQTT over TLS) on port 8883
**Rationale**: Secure communication, spec mandates TLS for all external connections
**Alternatives Considered**:
- Plain MQTT: Security risk
- HTTP/REST: Not suitable for real-time telemetry

### 12. Worker Architecture

**Decision**: Separate worker containers per responsibility
**Rationale**: Constitution principle IV (Separation of Concerns) - independent scaling and deployment
**Alternatives Considered**:
- Monolithic worker: Violates separation principle
- Serverless functions: Complexity for persistent connections

## Architecture Patterns

### Hexagonal Architecture (Ports & Adapters)

**Decision**: Domain-driven design with hexagonal architecture
**Rationale**: Constitution principles VI (Pure Domain) and IV (Separation of Concerns)
**Structure**:
- `domain/`: Pure business logic, no infrastructure dependencies
- `application/`: Use cases orchestrating domain operations
- `adapters/`: Database, API, messaging implementations

### Event-Driven Communication

**Decision**: MQTT for real-time, RabbitMQ for async processing
**Rationale**: Constitution principle II (Event-Driven Architecture)
**Flow**:
1. ESP32 → MQTT (gas/reading, gas/alert)
2. MQTT Bridge → RabbitMQ (for worker processing)
3. Workers → PostgreSQL/InfluxDB (persistence)
4. Workers → MQTT (commands back to ESP32)

### Fail-Safe Pattern

**Decision**: Local-first safety actions on ESP32
**Rationale**: Constitution principle I (Fail-Safe First)
**Implementation**:
- Valve close, buzzer, LEDs controlled locally
- Backend notification is secondary, non-blocking
- ESP32 operates autonomously during connectivity loss

## Integration Patterns

### MQTT Topics Structure

```
gas/reading          # Telemetry from ESP32 (gas, temp, humidity)
gas/alert            # Alert events from ESP32
gas/command/{id}     # Commands to specific ESP32 (valve, dissipator)
gas/status/{id}      # Status updates from ESP32
```

### RabbitMQ Exchanges & Queues

```
Exchanges:
- sensor.events (topic)    # All sensor events
- alerts.critical (direct) # High-priority alerts

Queues:
- data_collector.readings  # Telemetry storage
- gas_detection.process    # Gas level processing
- alert_handler.notify     # Notification dispatch
```

## Security Considerations

### Authentication Flow

1. User login → JWT token (24h expiry)
2. JWT includes: user_id, role, permissions, exp
3. API validates JWT on each request
4. Role-based endpoint access control

### ESP32 Security

1. Device pre-shared key for MQTT auth
2. TLS 1.3 for MQTTS connections
3. Certificate pinning (optional, future)
4. Device ID validation on backend

### Audit Logging

All critical actions logged to `audit_logs` table:
- Timestamp, user_id, role, action, sensor_id, details_json, ip_origin
- Immutable (no UPDATE/DELETE permissions)

## Performance Targets

| Metric | Target | Strategy |
|--------|--------|----------|
| Valve close time | <1s | Local ESP32 logic, no backend dependency |
| API latency p95 | <200ms | Async I/O, connection pooling |
| Alert notification | <30s | Priority queue, parallel dispatch |
| Readings throughput | 1000/sec | InfluxDB batch writes, async |
| Concurrent sensors | 50 | Horizontal worker scaling |
| Concurrent users | 100 | Stateless JWT, load balancing |

## Dependencies Summary

### Backend API (app/)
```
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
sqlalchemy[asyncio]>=2.0.25
asyncpg>=0.29.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
aiomqtt>=2.0.0
aio-pika>=9.3.0
influxdb-client[async]>=1.40.0
prometheus-client>=0.19.0
structlog>=24.1.0
```

### Workers (worker/)
```
aio-pika>=9.3.0
aiomqtt>=2.0.0
sqlalchemy[asyncio]>=2.0.25
asyncpg>=0.29.0
influxdb-client[async]>=1.40.0
pydantic>=2.5.0
structlog>=24.1.0
httpx>=0.26.0  # For push notifications
```

### Infrastructure
```
PostgreSQL 15+
InfluxDB 2.x
RabbitMQ 3.12+
Mosquitto 2.x (MQTT broker)
Nginx (reverse proxy)
Redis 7+ (optional: caching)
Prometheus + Grafana
```
