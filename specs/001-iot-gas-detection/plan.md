# Implementation Plan: Sistema IoT de Detección de Fugas de Gas

**Branch**: `001-iot-gas-detection` | **Date**: 2026-05-11 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/001-iot-gas-detection/spec.md`

## Summary

Sistema IoT de detección de fugas de gas con arquitectura event-driven y fail-safe local. El ESP32 ejecuta acciones críticas de seguridad (cierre de válvula, activación de disipador) de forma autónoma sin dependencia del backend. El backend proporciona monitoreo en tiempo real, histórico de datos, notificaciones y control remoto mediante arquitectura hexagonal con FastAPI, PostgreSQL, InfluxDB, MQTT y RabbitMQ.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: FastAPI 0.110+, SQLAlchemy 2.0, aio-pika, aiomqtt, influxdb-client  
**Storage**: PostgreSQL 15+ (structured), InfluxDB 2.x (telemetry)  
**Testing**: pytest + pytest-asyncio  
**Target Platform**: Linux server (DigitalOcean VPS), ESP32 (firmware)  
**Project Type**: IoT backend (web-service + workers)  
**Performance Goals**: 1000 readings/sec, <1s valve close, <30s alert notification  
**Constraints**: <200ms API p95, 99.9% uptime, offline-capable ESP32  
**Scale/Scope**: 50 sensors, 100 concurrent users, 6 months data retention

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Fail-Safe First | ✅ PASS | ESP32 executes valve close locally, no backend dependency |
| II. Event-Driven Architecture | ✅ PASS | MQTT for real-time, RabbitMQ for async processing |
| III. Async by Default | ✅ PASS | FastAPI + asyncio, aio-pika, aiomqtt |
| IV. Separation of Concerns | ✅ PASS | API, workers, messaging strictly separated |
| V. Scalable by Design | ✅ PASS | Stateless API/workers, horizontal scaling |
| VI. Pure Domain (DDD) | ✅ PASS | Hexagonal architecture, domain free of infra |
| VII. Indirect Hardware Communication | ✅ PASS | Workers publish to MQTT, never direct ESP32 |
| VIII. Storage Separation | ✅ PASS | PostgreSQL (structured) + InfluxDB (telemetry) |
| IX. Persistence Patterns | ✅ PASS | SQLAlchemy 2.0 Data Mapper, native InfluxDB client |

## Project Structure

### Documentation (this feature)

```text
specs/001-iot-gas-detection/
├── plan.md              # This file
├── research.md          # Phase 0: Technical decisions
├── data-model.md        # Phase 1: Entity definitions
├── quickstart.md        # Phase 1: Development setup
├── contracts/           # Phase 1: API & MQTT contracts
│   ├── api.yaml         # OpenAPI 3.0 specification
│   └── mqtt.md          # MQTT topics and payloads
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
app/                              # Backend API container
├── domain/                       # Pure domain (DDD)
│   ├── sensor/                   # Sensor bounded context
│   │   ├── entities.py
│   │   ├── repository.py
│   │   └── services.py
│   ├── safety/                   # Safety & fail-safe logic
│   │   ├── entities.py
│   │   └── services.py
│   ├── alert/                    # Alert management
│   │   ├── entities.py
│   │   ├── repository.py
│   │   └── services.py
│   ├── user/                     # Users & RBAC
│   │   ├── entities.py
│   │   ├── repository.py
│   │   └── services.py
│   └── shared/                   # Shared value objects, events
│       ├── events.py
│       ├── value_objects.py
│       └── exceptions.py
├── application/                  # Use cases
│   ├── sensor/
│   ├── alert/
│   └── user/
├── infrastructure/               # Adapters
│   ├── api/                      # FastAPI endpoints
│   │   ├── routes/
│   │   ├── middleware/
│   │   └── dependencies.py
│   ├── database/                 # PostgreSQL adapters
│   │   ├── models/
│   │   ├── repositories/
│   │   └── migrations/
│   ├── messaging/                # MQTT & RabbitMQ
│   │   ├── mqtt_client.py
│   │   └── rabbitmq_client.py
│   └── telemetry/                # InfluxDB adapter
│       └── influx_client.py
├── main.py                       # FastAPI entrypoint
├── requirements.txt
└── dockerfile

worker/                           # Worker containers
├── data_collector/               # Telemetry storage worker
│   ├── consumer.py
│   ├── storage.py
│   └── validator.py
├── gas_detection/                # Gas processing worker
│   ├── consumer.py
│   ├── processor.py
│   └── publisher.py
├── alert_handler/                # Alert notification worker
│   ├── consumer.py
│   ├── notifier.py
│   └── safety_logic.py
├── shared/                       # Shared worker utilities
│   ├── messaging.py
│   ├── models.py
│   └── schemas.py
├── main.py                       # Worker entrypoint
├── requirements.txt
└── dockerfile

mosquitto/                        # MQTT broker config
└── mosquitto.conf

tests/                            # Test suite
├── unit/
│   ├── domain/
│   └── application/
├── integration/
│   ├── api/
│   └── workers/
└── contract/
    └── mqtt/

docker-compose.yml                # Local development stack
```

**Structure Decision**: IoT backend with separated API and workers following hexagonal architecture. The existing directory structure (`app/`, `worker/`, `mosquitto/`) is preserved and expanded with bounded contexts per constitution.

## Complexity Tracking

> No constitution violations identified. All principles satisfied.
