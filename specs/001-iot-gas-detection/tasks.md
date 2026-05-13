# Tasks: Sistema IoT de Detección de Fugas de Gas

**Input**: Design documents from `specs/001-iot-gas-detection/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: No tests explicitly requested. Test tasks are NOT included.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: User story label (US1, US2, US3, US4)
- Paths based on hexagonal architecture from plan.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependencies, and Docker configuration

- [ ] T001 Create project directory structure per plan.md in app/, worker/, tests/
- [ ] T002 [P] Initialize app/requirements.txt with FastAPI, SQLAlchemy 2.0, aio-pika, aiomqtt, influxdb-client dependencies
- [ ] T003 [P] Initialize worker/requirements.txt with aio-pika, aiomqtt, pydantic, structlog dependencies
- [ ] T004 [P] Create .env.example with all environment variables from quickstart.md
- [ ] T005 [P] Configure docker-compose.yml with postgres, influxdb, rabbitmq, mosquitto, redis services
- [ ] T006 [P] Create app/dockerfile with Python 3.11 base image
- [ ] T007 [P] Create worker/dockerfile with Python 3.11 base image
- [ ] T008 [P] Configure mosquitto/mosquitto.conf with TLS and authentication settings
- [ ] T009 [P] Create pyproject.toml with linting (ruff) and formatting (black) configuration

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Domain Layer (Pure DDD)

- [ ] T010 [P] Create app/domain/shared/value_objects.py with SensorId, UserId, GasLevel, Timestamp
- [ ] T011 [P] Create app/domain/shared/events.py with DomainEvent base class
- [ ] T012 [P] Create app/domain/shared/exceptions.py with domain exceptions (SensorNotFound, InvalidGasLevel, etc.)
- [ ] T013 [P] Create app/domain/sensor/entities.py with Sensor, Valve, Dissipator entities
- [ ] T014 [P] Create app/domain/sensor/repository.py with ISensorRepository abstract interface
- [ ] T015 [P] Create app/domain/alert/entities.py with Alert entity and AlertSeverity, AlertStatus enums
- [ ] T016 [P] Create app/domain/alert/repository.py with IAlertRepository abstract interface
- [ ] T017 [P] Create app/domain/user/entities.py with User entity and UserRole, UserStatus enums
- [ ] T018 [P] Create app/domain/user/repository.py with IUserRepository abstract interface

### Database Infrastructure

- [ ] T019 Create app/infrastructure/database/connection.py with async SQLAlchemy 2.0 engine and session
- [ ] T020 [P] Create app/infrastructure/database/models/sensor.py with Sensor, Valve, Dissipator SQLAlchemy models
- [ ] T021 [P] Create app/infrastructure/database/models/alert.py with Alert SQLAlchemy model
- [ ] T022 [P] Create app/infrastructure/database/models/user.py with User, UserSensorAssignment SQLAlchemy models
- [ ] T023 [P] Create app/infrastructure/database/models/audit.py with AuditLog SQLAlchemy model
- [ ] T024 [P] Create app/infrastructure/database/models/config.py with GlobalConfig SQLAlchemy model
- [ ] T025 Create alembic.ini and app/infrastructure/database/migrations/env.py for Alembic setup
- [ ] T026 Create app/infrastructure/database/migrations/versions/001_initial_schema.py with all tables
- [ ] T027 Create app/infrastructure/database/migrations/versions/002_seed_global_config.py with default thresholds

### Telemetry Infrastructure (InfluxDB)

- [ ] T028 Create app/infrastructure/telemetry/influx_client.py with async InfluxDB client for readings

### Messaging Infrastructure

- [ ] T029 [P] Create app/infrastructure/messaging/rabbitmq_client.py with aio-pika connection and exchanges
- [ ] T030 [P] Create app/infrastructure/messaging/mqtt_client.py with aiomqtt client for ESP32 communication
- [ ] T031 Create worker/shared/messaging.py with shared RabbitMQ and MQTT utilities
- [ ] T032 [P] Create worker/shared/schemas.py with Pydantic schemas for MQTT message validation

### API Infrastructure

- [ ] T033 Create app/main.py with FastAPI application, lifespan, and CORS middleware
- [ ] T034 [P] Create app/infrastructure/api/dependencies.py with dependency injection for repositories
- [ ] T035 [P] Create app/infrastructure/api/middleware/logging.py with structured JSON logging middleware
- [ ] T036 [P] Create app/infrastructure/api/middleware/auth.py with JWT authentication middleware
- [ ] T037 Create app/infrastructure/api/routes/health.py with /health and /health/ready endpoints

### Worker Infrastructure

- [ ] T038 Create worker/main.py with worker entrypoint and graceful shutdown

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Detección de Gas y Cierre Automático de Válvula (Priority: P1) 🎯 MVP

**Goal**: ESP32 detects dangerous gas levels and automatically closes valve locally, then notifies backend

**Independent Test**: Simulate gas readings via MQTT, verify valve state changes in database and alert is created

### Domain Services for US1

- [ ] T039 [US1] Create app/domain/safety/entities.py with SafetyProtocol, EmergencyAction entities
- [ ] T040 [US1] Create app/domain/safety/services.py with GasLevelAnalyzer service (threshold logic)
- [ ] T041 [US1] Create app/domain/sensor/services.py with SensorStateManager service

### Application Layer for US1

- [ ] T042 [US1] Create app/application/sensor/process_reading.py use case for handling incoming readings
- [ ] T043 [US1] Create app/application/alert/create_alert.py use case for creating alerts from gas detection

### Infrastructure Adapters for US1

- [ ] T044 [US1] Create app/infrastructure/database/repositories/sensor_repository.py implementing ISensorRepository
- [ ] T045 [US1] Create app/infrastructure/database/repositories/alert_repository.py implementing IAlertRepository

### Worker: Data Collector for US1

- [ ] T046 [US1] Create worker/data_collector/validator.py with MQTT message schema validation
- [ ] T047 [US1] Create worker/data_collector/storage.py with InfluxDB batch writer for telemetry
- [ ] T048 [US1] Create worker/data_collector/consumer.py subscribing to gas/reading/{device_id} topics

### Worker: Gas Detection for US1

- [ ] T049 [US1] Create worker/gas_detection/processor.py with gas level analysis and threshold detection
- [ ] T050 [US1] Create worker/gas_detection/publisher.py to publish alerts to RabbitMQ
- [ ] T051 [US1] Create worker/gas_detection/consumer.py consuming readings from RabbitMQ

### Worker: Alert Handler for US1

- [ ] T052 [US1] Create worker/alert_handler/safety_logic.py with valve/dissipator command logic
- [ ] T053 [US1] Create worker/alert_handler/consumer.py consuming alerts from RabbitMQ
- [ ] T054 [US1] Implement MQTT command publishing in worker/alert_handler/ for valve_close commands

### API Endpoints for US1

- [ ] T055 [US1] Create app/infrastructure/api/routes/sensors.py with GET /sensors/{id} endpoint
- [ ] T056 [US1] Create app/infrastructure/api/routes/alerts.py with GET /alerts (active alerts) endpoint

**Checkpoint**: US1 complete - Gas detection and automatic valve close functional. Backend receives alerts.

---

## Phase 4: User Story 2 - Control del Disipador desde App y Activación Automática (Priority: P2)

**Goal**: Users can control dissipator manually via API, but ESP32 overrides during gas alerts

**Independent Test**: Send dissipator command via API, verify MQTT command published. Simulate alert and verify dissipator locks.

### Domain Services for US2

- [ ] T057 [US2] Create app/domain/sensor/services.py extension with DissipatorController service

### Application Layer for US2

- [ ] T058 [US2] Create app/application/sensor/control_dissipator.py use case for manual dissipator control
- [ ] T059 [US2] Create app/application/sensor/get_sensor_status.py use case for current sensor state

### API Endpoints for US2

- [ ] T060 [US2] Create app/infrastructure/api/routes/commands.py with POST /commands/dissipator/{sensor_id}
- [ ] T061 [US2] Add dissipator lock validation in commands.py (reject OFF during active alert)

### Worker Updates for US2

- [ ] T062 [US2] Update worker/alert_handler/safety_logic.py to publish dissipator_on command during alerts
- [ ] T063 [US2] Update worker/gas_detection/processor.py to set dissipator locked_by_alert flag

### Integration for US2

- [ ] T064 [US2] Add MQTT command acknowledgment handling in worker/shared/messaging.py

**Checkpoint**: US2 complete - Dissipator controllable via API with automatic override during alerts

---

## Phase 5: User Story 3 - Monitoreo en Tiempo Real y Alertas (Priority: P3)

**Goal**: Operators can monitor sensors in real-time via API and receive notifications for critical alerts

**Independent Test**: Query /sensors/{id}/current and verify latest reading. Trigger alert and verify notification sent.

### Domain Services for US3

- [ ] T065 [US3] Create app/domain/alert/services.py with AlertManager service

### Application Layer for US3

- [ ] T066 [US3] Create app/application/sensor/get_current_reading.py use case for latest telemetry
- [ ] T067 [US3] Create app/application/sensor/list_sensors.py use case for listing all sensors
- [ ] T068 [US3] Create app/application/alert/acknowledge_alert.py use case
- [ ] T069 [US3] Create app/application/alert/resolve_alert.py use case

### Infrastructure for US3

- [ ] T070 [US3] Create app/infrastructure/telemetry/reading_repository.py for InfluxDB queries

### API Endpoints for US3

- [ ] T071 [US3] Add GET /sensors endpoint in app/infrastructure/api/routes/sensors.py
- [ ] T072 [US3] Add GET /sensors/{id}/current endpoint in app/infrastructure/api/routes/sensors.py
- [ ] T073 [US3] Add POST /alerts/{id}/acknowledge endpoint in app/infrastructure/api/routes/alerts.py
- [ ] T074 [US3] Add POST /alerts/{id}/resolve endpoint in app/infrastructure/api/routes/alerts.py

### Worker: Notifications for US3

- [ ] T075 [US3] Create worker/alert_handler/notifier.py with push notification and email sending
- [ ] T076 [US3] Update worker/alert_handler/consumer.py to dispatch notifications for critical alerts

**Checkpoint**: US3 complete - Real-time monitoring and notification system functional

---

## Phase 6: User Story 4 - Histórico de Datos y Dashboard (Priority: P4)

**Goal**: Operators can query historical readings and statistics for analysis and audit

**Independent Test**: Insert historical data, query /sensors/{id}/readings with date range, verify pagination works

### Application Layer for US4

- [ ] T077 [US4] Create app/application/sensor/get_readings_history.py use case with date range filtering
- [ ] T078 [US4] Create app/application/sensor/get_sensor_stats.py use case for aggregations (min, max, avg)
- [ ] T079 [US4] Create app/application/alert/list_alerts.py use case with filtering

### Infrastructure for US4

- [ ] T080 [US4] Update app/infrastructure/telemetry/reading_repository.py with range queries and aggregations

### API Endpoints for US4

- [ ] T081 [US4] Add GET /sensors/{id}/readings endpoint with start, end, page, limit params
- [ ] T082 [US4] Add GET /sensors/{id}/stats endpoint with period param (1h, 6h, 24h, 7d, 30d, 1y)
- [ ] T083 [US4] Add filtering to GET /alerts endpoint (sensor_id, status, severity, date range)

**Checkpoint**: US4 complete - Historical data and statistics accessible via API

---

## Phase 7: RBAC & User Management (Cross-Cutting)

**Goal**: Implement role-based access control with 4 roles (admin, operator, technician, auditor)

### Domain for RBAC

- [ ] T084 Create app/domain/user/services.py with PermissionChecker service

### Application Layer for RBAC

- [ ] T085 [P] Create app/application/user/authenticate.py use case with JWT token generation
- [ ] T086 [P] Create app/application/user/create_user.py use case (admin only)
- [ ] T087 [P] Create app/application/user/update_user.py use case (admin only)
- [ ] T088 Create app/application/user/assign_sensors.py use case for operator sensor assignment

### Infrastructure for RBAC

- [ ] T089 Create app/infrastructure/database/repositories/user_repository.py implementing IUserRepository
- [ ] T090 Update app/infrastructure/api/middleware/auth.py with role-based permission checks

### API Endpoints for RBAC

- [ ] T091 Create app/infrastructure/api/routes/auth.py with POST /auth/login, POST /auth/refresh
- [ ] T092 Create app/infrastructure/api/routes/users.py with CRUD endpoints (admin only)
- [ ] T093 Add PUT /users/{id}/sensors endpoint for sensor assignment

### Role-Specific Endpoints

- [ ] T094 Add GET /sensors/{id}/health endpoint for technicians in sensors.py
- [ ] T095 Add POST /commands/test-mode/{sensor_id} endpoint for technicians in commands.py
- [ ] T096 Add POST /commands/valve/{sensor_id} endpoint with panic close option in commands.py

**Checkpoint**: RBAC complete - All 4 roles functional with appropriate permissions

---

## Phase 8: Audit & Security (Cross-Cutting)

**Goal**: Implement audit logging and security features for compliance

### Domain for Audit

- [ ] T097 Create app/domain/audit/entities.py with AuditLog entity
- [ ] T098 Create app/domain/audit/repository.py with IAuditRepository interface

### Application Layer for Audit

- [ ] T099 Create app/application/audit/log_action.py use case for recording actions
- [ ] T100 Create app/application/audit/query_logs.py use case for auditor queries
- [ ] T101 Create app/application/audit/export_data.py use case for forensic export

### Infrastructure for Audit

- [ ] T102 Create app/infrastructure/database/repositories/audit_repository.py (append-only)
- [ ] T103 Create audit logging decorator in app/infrastructure/api/middleware/audit.py

### API Endpoints for Audit

- [ ] T104 Create app/infrastructure/api/routes/audit.py with GET /audit/logs (auditor only)
- [ ] T105 Add POST /audit/export endpoint for data export (auditor only)
- [ ] T106 Add GET /audit/security endpoint with security metrics (auditor only)

### Global Configuration

- [ ] T107 Create app/infrastructure/api/routes/config.py with GET/PATCH /config (admin only)

**Checkpoint**: Audit system complete - All critical actions logged, auditor access functional

---

## Phase 9: Polish & Production Readiness

**Purpose**: Final improvements for production deployment

### Documentation

- [ ] T108 [P] Update README.md with project overview, architecture, and quickstart
- [ ] T109 [P] Create docs/api.md with API usage examples
- [ ] T110 [P] Create docs/deployment.md with VPS deployment instructions

### Monitoring & Observability

- [ ] T111 [P] Add Prometheus metrics endpoint in app/infrastructure/api/routes/metrics.py
- [ ] T112 [P] Create grafana/ directory with dashboard JSON configurations
- [ ] T113 Update docker-compose.yml with prometheus and grafana services

### Performance & Reliability

- [ ] T114 Add connection pooling configuration in app/infrastructure/database/connection.py
- [ ] T115 Add retry logic with exponential backoff in worker/shared/messaging.py
- [ ] T116 Add graceful shutdown handling in app/main.py and worker/main.py

### Security Hardening

- [ ] T117 Add rate limiting middleware in app/infrastructure/api/middleware/rate_limit.py
- [ ] T118 Add input sanitization in app/infrastructure/api/middleware/sanitize.py
- [ ] T119 Review and secure all .env variables, ensure no hardcoded secrets

### Validation

- [ ] T120 Run quickstart.md validation - verify all setup steps work
- [ ] T121 Validate API contract against specs/001-iot-gas-detection/contracts/api.yaml

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup) ─────────────────────────────────────┐
                                                     │
Phase 2 (Foundational) ◄─────────────────────────────┘
         │
         ├── BLOCKS ALL USER STORIES
         │
         ▼
┌────────┴────────┬────────────────┬────────────────┐
│                 │                │                │
▼                 ▼                ▼                ▼
Phase 3 (US1)    Phase 4 (US2)   Phase 5 (US3)   Phase 6 (US4)
P1 - MVP 🎯      P2              P3               P4
│                 │                │                │
└────────┬────────┴────────┬───────┴────────┬───────┘
         │                 │                │
         ▼                 ▼                ▼
     Phase 7 (RBAC) ◄──────┴────────────────┘
         │
         ▼
     Phase 8 (Audit)
         │
         ▼
     Phase 9 (Polish)
```

### User Story Dependencies

| Story | Depends On | Can Start After |
|-------|------------|-----------------|
| US1 (P1) | Phase 2 | Foundational complete |
| US2 (P2) | US1 (shares alert logic) | US1 T052 complete |
| US3 (P3) | Phase 2 | Foundational complete |
| US4 (P4) | US3 (shares reading repo) | US3 T070 complete |

### Parallel Opportunities

**Phase 1 (Setup)**: T002-T009 all parallelizable
**Phase 2 (Foundational)**: T010-T018, T020-T024, T029-T032, T034-T036 parallelizable
**User Stories**: US1 and US3 can start in parallel after Phase 2

---

## Parallel Example: Phase 2 Foundation

```bash
# Launch domain entities in parallel:
Task: T010 "Create value_objects.py"
Task: T011 "Create events.py"
Task: T012 "Create exceptions.py"
Task: T013 "Create sensor entities"
Task: T014 "Create sensor repository interface"
Task: T015 "Create alert entities"
Task: T016 "Create alert repository interface"
Task: T017 "Create user entities"
Task: T018 "Create user repository interface"

# Launch SQLAlchemy models in parallel:
Task: T020 "Create sensor models"
Task: T021 "Create alert model"
Task: T022 "Create user models"
Task: T023 "Create audit model"
Task: T024 "Create config model"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T009)
2. Complete Phase 2: Foundational (T010-T038)
3. Complete Phase 3: User Story 1 (T039-T056)
4. **STOP and VALIDATE**: 
   - Send simulated MQTT readings
   - Verify alerts created in database
   - Verify valve state tracked
5. Deploy/demo if ready - **Core safety functionality operational**

### Incremental Delivery

| Increment | Phases | Value Delivered |
|-----------|--------|-----------------|
| MVP | 1 + 2 + 3 | Gas detection, automatic valve close, basic API |
| +Dissipator | + 4 | Manual/automatic dissipator control |
| +Monitoring | + 5 | Real-time monitoring, notifications |
| +History | + 6 | Historical data, statistics, trends |
| +RBAC | + 7 | Multi-user with role permissions |
| +Audit | + 8 | Compliance, forensics, security |
| Production | + 9 | Monitoring, docs, hardening |

### Suggested MVP Scope

**Minimum deployable**: Phases 1-3 (US1 only) = **56 tasks**
- Provides core safety value (gas detection + valve close)
- Backend receives and stores alerts
- Basic API for monitoring

---

## Summary

| Metric | Value |
|--------|-------|
| **Total Tasks** | 121 |
| **Phase 1 (Setup)** | 9 tasks |
| **Phase 2 (Foundational)** | 29 tasks |
| **US1 (P1) - MVP** | 18 tasks |
| **US2 (P2)** | 8 tasks |
| **US3 (P3)** | 12 tasks |
| **US4 (P4)** | 7 tasks |
| **RBAC** | 13 tasks |
| **Audit** | 11 tasks |
| **Polish** | 14 tasks |
| **Parallelizable** | ~45% of tasks |

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story
- Each user story independently completable after Foundational phase
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- FR-035 updated: Operators can view telemetry history for 24h, weeks, months, years (implemented in US4 T082)
