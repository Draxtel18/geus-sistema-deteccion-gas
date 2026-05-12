# Data Model: Sistema IoT de Detección de Fugas de Gas

**Feature**: 001-iot-gas-detection | **Date**: 2026-05-11

## Entity Diagram

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│    User     │       │   Sensor    │       │   Reading   │
├─────────────┤       ├─────────────┤       ├─────────────┤
│ id          │       │ id          │◄──────│ sensor_id   │
│ email       │       │ location    │       │ gas_ppm     │
│ role        │──────►│ status      │       │ temperature │
│ sensors[]   │       │ last_reading│       │ humidity    │
└─────────────┘       └──────┬──────┘       │ timestamp   │
                             │              └─────────────┘
                             │                    ▲
                             ▼                    │ (InfluxDB)
                      ┌─────────────┐             │
                      │    Valve    │      ┌──────┴──────┐
                      ├─────────────┤      │             │
                      │ sensor_id   │      │  Telemetry  │
                      │ state       │      │   Storage   │
                      │ last_change │      │             │
                      └─────────────┘      └─────────────┘
                             │
                      ┌──────┴──────┐
                      │  Dissipator │
                      ├─────────────┤
                      │ sensor_id   │
                      │ state       │
                      │ mode        │
                      └─────────────┘
                             │
                      ┌──────┴──────┐
                      │    Alert    │
                      ├─────────────┤
                      │ sensor_id   │
                      │ gas_level   │
                      │ severity    │
                      │ status      │
                      └─────────────┘
                             │
                      ┌──────┴──────┐
                      │  AuditLog   │
                      ├─────────────┤
                      │ user_id     │
                      │ action      │
                      │ timestamp   │
                      └─────────────┘
```

## Entities

### Sensor (PostgreSQL)

Representa un dispositivo ESP32 físico en una ubicación de monitoreo.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Identificador único del sensor |
| device_id | VARCHAR(64) | UNIQUE, NOT NULL | ID del hardware ESP32 |
| location | VARCHAR(255) | NOT NULL | Ubicación física descriptiva |
| status | ENUM | NOT NULL | `online`, `offline`, `maintenance` |
| wifi_signal | INTEGER | NULL | Señal WiFi en dBm (-100 a 0) |
| mqtt_connected | BOOLEAN | DEFAULT false | Estado conexión MQTT |
| uptime_seconds | INTEGER | DEFAULT 0 | Tiempo activo desde último reinicio |
| test_mode | BOOLEAN | DEFAULT false | Modo prueba activo |
| test_mode_expires_at | TIMESTAMP | NULL | Expiración automática modo prueba |
| correction_factor | FLOAT | DEFAULT 1.0 | Factor corrección sensor MQ-6 |
| last_reading_at | TIMESTAMP | NULL | Timestamp última lectura recibida |
| created_at | TIMESTAMP | NOT NULL | Fecha registro |
| updated_at | TIMESTAMP | NOT NULL | Última modificación |

**Validaciones**:
- `wifi_signal` debe estar entre -100 y 0
- `correction_factor` debe estar entre 0.5 y 2.0
- `test_mode_expires_at` debe ser futuro cuando se activa

**Índices**:
- `idx_sensor_device_id` en `device_id`
- `idx_sensor_status` en `status`

---

### Reading (InfluxDB)

Medición individual de telemetría en un punto en el tiempo.

| Field | Type | Tags/Fields | Description |
|-------|------|-------------|-------------|
| time | TIMESTAMP | - | Timestamp de la medición (nanoseconds) |
| sensor_id | STRING | TAG | ID del sensor (para filtrado) |
| gas_ppm | FLOAT | FIELD | Nivel de gas en partes por millón |
| temperature_c | FLOAT | FIELD | Temperatura en Celsius |
| humidity_percent | FLOAT | FIELD | Humedad relativa (0-100) |
| wifi_signal | INTEGER | FIELD | Señal WiFi en dBm |

**Measurement**: `sensor_readings`
**Retention Policy**: 180 días (6 meses)
**Downsampling**: Promedios horarios después de 30 días

**Validaciones**:
- `gas_ppm` debe estar entre 0 y 10000
- `temperature_c` debe estar entre -40 y 85
- `humidity_percent` debe estar entre 0 y 100

---

### Alert (PostgreSQL)

Notificación de nivel de gas peligroso que requiere atención.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Identificador único de alerta |
| sensor_id | UUID | FK → Sensor, NOT NULL | Sensor que generó la alerta |
| gas_level_ppm | FLOAT | NOT NULL | Nivel de gas detectado |
| severity | ENUM | NOT NULL | `warning` (200-500ppm), `critical` (>500ppm) |
| status | ENUM | NOT NULL | `active`, `acknowledged`, `resolved` |
| triggered_at | TIMESTAMP | NOT NULL | Momento de detección |
| acknowledged_at | TIMESTAMP | NULL | Momento de reconocimiento |
| acknowledged_by | UUID | FK → User, NULL | Usuario que reconoció |
| resolved_at | TIMESTAMP | NULL | Momento de resolución |
| resolved_by | UUID | FK → User, NULL | Usuario que resolvió |
| auto_resolved | BOOLEAN | DEFAULT false | Resolución automática (gas < 200ppm) |
| notifications_sent | JSONB | DEFAULT '[]' | Log de notificaciones enviadas |
| created_at | TIMESTAMP | NOT NULL | Fecha creación registro |

**Validaciones**:
- `severity = 'warning'` cuando `gas_level_ppm` entre 200 y 500
- `severity = 'critical'` cuando `gas_level_ppm` > 500
- `resolved_at` solo si `status = 'resolved'`
- Alertas críticas requieren `resolved_by` (no auto-resolución)

**Índices**:
- `idx_alert_sensor_id` en `sensor_id`
- `idx_alert_status` en `status`
- `idx_alert_triggered_at` en `triggered_at`

**State Transitions**:
```
active → acknowledged → resolved
active → resolved (solo warning, auto)
```

---

### Valve (PostgreSQL)

Actuador físico para corte de gas controlado por ESP32.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Identificador único |
| sensor_id | UUID | FK → Sensor, UNIQUE, NOT NULL | Sensor asociado |
| state | ENUM | NOT NULL | `open`, `closed` |
| last_state_change | TIMESTAMP | NOT NULL | Último cambio de estado |
| mechanical_status | ENUM | DEFAULT 'ok' | `ok`, `stuck`, `unknown` |
| last_command_source | ENUM | NULL | `local`, `remote`, `panic` |
| created_at | TIMESTAMP | NOT NULL | Fecha registro |
| updated_at | TIMESTAMP | NOT NULL | Última modificación |

**Validaciones**:
- Un sensor solo puede tener una válvula asociada
- `mechanical_status = 'stuck'` si el cambio de estado falla

---

### Dissipator (PostgreSQL)

Actuador de ventilación/extracción controlado por ESP32.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Identificador único |
| sensor_id | UUID | FK → Sensor, UNIQUE, NOT NULL | Sensor asociado |
| state | ENUM | NOT NULL | `on`, `off` |
| activation_mode | ENUM | NOT NULL | `manual`, `automatic` |
| last_state_change | TIMESTAMP | NOT NULL | Último cambio de estado |
| mechanical_status | ENUM | DEFAULT 'ok' | `ok`, `stuck`, `unknown` |
| locked_by_alert | BOOLEAN | DEFAULT false | Bloqueado por alerta activa |
| created_at | TIMESTAMP | NOT NULL | Fecha registro |
| updated_at | TIMESTAMP | NOT NULL | Última modificación |

**Validaciones**:
- No se puede apagar si `locked_by_alert = true`
- `activation_mode = 'automatic'` cuando gas > 200ppm

---

### User (PostgreSQL)

Usuario del sistema con rol y permisos específicos.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Identificador único |
| email | VARCHAR(255) | UNIQUE, NOT NULL | Email (login) |
| password_hash | VARCHAR(255) | NOT NULL | Hash bcrypt |
| name | VARCHAR(255) | NOT NULL | Nombre completo |
| role | ENUM | NOT NULL | `admin`, `operator`, `technician`, `auditor` |
| status | ENUM | NOT NULL | `active`, `suspended` |
| notifications_enabled | BOOLEAN | DEFAULT true | Recibir notificaciones |
| notification_devices | JSONB | DEFAULT '[]' | Tokens push notification |
| last_login_at | TIMESTAMP | NULL | Último acceso |
| last_login_ip | INET | NULL | IP último acceso |
| created_at | TIMESTAMP | NOT NULL | Fecha creación |
| updated_at | TIMESTAMP | NOT NULL | Última modificación |

**Índices**:
- `idx_user_email` en `email`
- `idx_user_role` en `role`
- `idx_user_status` en `status`

---

### UserSensorAssignment (PostgreSQL)

Relación N:M entre operadores y sensores asignados.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Identificador único |
| user_id | UUID | FK → User, NOT NULL | Usuario (solo operadores) |
| sensor_id | UUID | FK → Sensor, NOT NULL | Sensor asignado |
| assigned_at | TIMESTAMP | NOT NULL | Fecha asignación |
| assigned_by | UUID | FK → User, NOT NULL | Admin que asignó |

**Constraints**:
- UNIQUE (`user_id`, `sensor_id`)
- Solo usuarios con `role = 'operator'` pueden tener asignaciones

---

### AuditLog (PostgreSQL)

Registro inmutable de acciones críticas del sistema.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Identificador único |
| timestamp | TIMESTAMP | NOT NULL | Momento de la acción |
| user_id | UUID | FK → User, NULL | Usuario que ejecutó (NULL para sistema) |
| user_role | ENUM | NULL | Rol al momento de la acción |
| action | VARCHAR(100) | NOT NULL | Tipo de acción |
| sensor_id | UUID | FK → Sensor, NULL | Sensor afectado (si aplica) |
| details | JSONB | DEFAULT '{}' | Detalles adicionales |
| ip_origin | INET | NULL | IP de origen |
| created_at | TIMESTAMP | NOT NULL | Fecha registro |

**Acciones auditadas**:
- `valve_close_manual`, `valve_close_auto`, `valve_open`
- `dissipator_on_manual`, `dissipator_on_auto`, `dissipator_off`
- `test_mode_enable`, `test_mode_disable`
- `alert_acknowledge`, `alert_resolve`
- `user_create`, `user_update`, `user_suspend`, `user_delete`
- `sensor_register`, `sensor_update`, `sensor_decommission`
- `threshold_update`, `correction_factor_update`
- `login_success`, `login_failed`

**Índices**:
- `idx_audit_timestamp` en `timestamp`
- `idx_audit_user_id` en `user_id`
- `idx_audit_action` en `action`
- `idx_audit_sensor_id` en `sensor_id`

**Nota**: Esta tabla es append-only. No se permiten UPDATE ni DELETE.

---

### GlobalConfig (PostgreSQL)

Configuración global del sistema.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Identificador único |
| key | VARCHAR(100) | UNIQUE, NOT NULL | Clave de configuración |
| value | JSONB | NOT NULL | Valor de configuración |
| updated_at | TIMESTAMP | NOT NULL | Última modificación |
| updated_by | UUID | FK → User | Admin que modificó |

**Configuraciones clave**:
- `gas_threshold_warning`: 200 (ppm)
- `gas_threshold_critical`: 500 (ppm)
- `test_mode_timeout_minutes`: 30
- `alert_notification_timeout_seconds`: 30
- `data_retention_days`: 180

## Enums

```python
class SensorStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"

class AlertSeverity(str, Enum):
    WARNING = "warning"      # 200-500 ppm
    CRITICAL = "critical"    # >500 ppm

class AlertStatus(str, Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"

class ValveState(str, Enum):
    OPEN = "open"
    CLOSED = "closed"

class DissipatorState(str, Enum):
    ON = "on"
    OFF = "off"

class ActivationMode(str, Enum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"

class MechanicalStatus(str, Enum):
    OK = "ok"
    STUCK = "stuck"
    UNKNOWN = "unknown"

class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    TECHNICIAN = "technician"
    AUDITOR = "auditor"

class UserStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"

class CommandSource(str, Enum):
    LOCAL = "local"      # ESP32 decision
    REMOTE = "remote"    # Backend command
    PANIC = "panic"      # Panic button
```

## Storage Strategy

| Entity | Storage | Rationale |
|--------|---------|-----------|
| Sensor | PostgreSQL | Structured, relational, low write frequency |
| Reading | InfluxDB | High-frequency time-series, retention policies |
| Alert | PostgreSQL | Relational (user refs), workflow state |
| Valve | PostgreSQL | Low frequency, state tracking |
| Dissipator | PostgreSQL | Low frequency, state tracking |
| User | PostgreSQL | Auth, RBAC, relational |
| AuditLog | PostgreSQL | Immutable, indexed queries |
| GlobalConfig | PostgreSQL | Low frequency, admin-only |

## Migration Strategy

Usar Alembic para PostgreSQL:
1. `001_initial_schema.py`: Crear todas las tablas
2. `002_seed_global_config.py`: Valores por defecto
3. `003_create_admin_user.py`: Usuario admin inicial

InfluxDB no requiere migraciones (schema-on-write).
