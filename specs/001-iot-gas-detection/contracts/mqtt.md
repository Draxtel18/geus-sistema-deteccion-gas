# MQTT Contract: Sistema IoT de Detección de Fugas de Gas

**Feature**: 001-iot-gas-detection | **Date**: 2026-05-11

## Connection Details

| Parameter | Value |
|-----------|-------|
| Protocol | MQTTS (MQTT over TLS 1.3) |
| Port | 8883 |
| Broker | Mosquitto 2.x |
| QoS | 1 (at least once) for telemetry, 2 (exactly once) for commands |
| Keep Alive | 60 seconds |
| Clean Session | false (persistent sessions) |

## Authentication

ESP32 devices authenticate using:
- **Username**: `device_{device_id}`
- **Password**: Pre-shared key (PSK) configured during device registration
- **Client ID**: `esp32_{device_id}`

## Topic Structure

```
gas/                          # Root namespace
├── reading/{device_id}       # Telemetry from ESP32 (ESP32 → Broker)
├── alert/{device_id}         # Alerts from ESP32 (ESP32 → Broker)
├── status/{device_id}        # Status updates (ESP32 → Broker)
├── command/{device_id}       # Commands to ESP32 (Broker → ESP32)
└── ack/{device_id}           # Command acknowledgments (ESP32 → Broker)
```

## Topics Detail

### 1. `gas/reading/{device_id}` (ESP32 → Backend)

Telemetry readings published every 1 second.

**Direction**: ESP32 publishes, Backend subscribes  
**QoS**: 1  
**Retain**: false

**Payload Schema**:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["device_id", "timestamp", "gas_ppm", "temperature_c", "humidity_percent"],
  "properties": {
    "device_id": {
      "type": "string",
      "maxLength": 64,
      "description": "Unique ESP32 identifier"
    },
    "timestamp": {
      "type": "integer",
      "description": "Unix timestamp in milliseconds"
    },
    "gas_ppm": {
      "type": "number",
      "minimum": 0,
      "maximum": 10000,
      "description": "Gas concentration in parts per million"
    },
    "temperature_c": {
      "type": "number",
      "minimum": -40,
      "maximum": 85,
      "description": "Temperature in Celsius"
    },
    "humidity_percent": {
      "type": "number",
      "minimum": 0,
      "maximum": 100,
      "description": "Relative humidity percentage"
    },
    "wifi_signal": {
      "type": "integer",
      "minimum": -100,
      "maximum": 0,
      "description": "WiFi signal strength in dBm"
    }
  }
}
```

**Example**:
```json
{
  "device_id": "esp32_001",
  "timestamp": 1715472000000,
  "gas_ppm": 150.5,
  "temperature_c": 25.3,
  "humidity_percent": 65.2,
  "wifi_signal": -45
}
```

---

### 2. `gas/alert/{device_id}` (ESP32 → Backend)

Alert events when gas levels exceed thresholds.

**Direction**: ESP32 publishes, Backend subscribes  
**QoS**: 2 (exactly once - critical)  
**Retain**: true (last alert state)

**Payload Schema**:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["device_id", "timestamp", "alert_type", "gas_ppm", "severity"],
  "properties": {
    "device_id": {
      "type": "string",
      "maxLength": 64
    },
    "timestamp": {
      "type": "integer",
      "description": "Unix timestamp in milliseconds"
    },
    "alert_type": {
      "type": "string",
      "enum": ["gas_detected", "gas_cleared"],
      "description": "Type of alert event"
    },
    "gas_ppm": {
      "type": "number",
      "minimum": 0,
      "maximum": 10000
    },
    "severity": {
      "type": "string",
      "enum": ["warning", "critical", "safe"],
      "description": "warning: 200-500ppm, critical: >500ppm, safe: <200ppm"
    },
    "actions_taken": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": ["valve_closed", "dissipator_on", "buzzer_on", "led_on"]
      },
      "description": "Local actions executed by ESP32"
    }
  }
}
```

**Example - Gas Detected**:
```json
{
  "device_id": "esp32_001",
  "timestamp": 1715472000000,
  "alert_type": "gas_detected",
  "gas_ppm": 550.0,
  "severity": "critical",
  "actions_taken": ["valve_closed", "dissipator_on", "buzzer_on", "led_on"]
}
```

**Example - Gas Cleared**:
```json
{
  "device_id": "esp32_001",
  "timestamp": 1715472300000,
  "alert_type": "gas_cleared",
  "gas_ppm": 150.0,
  "severity": "safe",
  "actions_taken": []
}
```

---

### 3. `gas/status/{device_id}` (ESP32 → Backend)

Device status updates (health, connectivity, state changes).

**Direction**: ESP32 publishes, Backend subscribes  
**QoS**: 1  
**Retain**: true (last known status)

**Payload Schema**:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["device_id", "timestamp", "status"],
  "properties": {
    "device_id": {
      "type": "string",
      "maxLength": 64
    },
    "timestamp": {
      "type": "integer"
    },
    "status": {
      "type": "string",
      "enum": ["online", "offline", "maintenance"]
    },
    "uptime_seconds": {
      "type": "integer",
      "minimum": 0
    },
    "wifi_signal": {
      "type": "integer",
      "minimum": -100,
      "maximum": 0
    },
    "memory_free_bytes": {
      "type": "integer",
      "minimum": 0
    },
    "firmware_version": {
      "type": "string"
    },
    "valve_state": {
      "type": "string",
      "enum": ["open", "closed"]
    },
    "dissipator_state": {
      "type": "string",
      "enum": ["on", "off"]
    },
    "test_mode": {
      "type": "boolean"
    },
    "correction_factor": {
      "type": "number",
      "minimum": 0.5,
      "maximum": 2.0
    }
  }
}
```

**Example**:
```json
{
  "device_id": "esp32_001",
  "timestamp": 1715472000000,
  "status": "online",
  "uptime_seconds": 86400,
  "wifi_signal": -45,
  "memory_free_bytes": 150000,
  "firmware_version": "1.2.0",
  "valve_state": "open",
  "dissipator_state": "off",
  "test_mode": false,
  "correction_factor": 1.0
}
```

---

### 4. `gas/command/{device_id}` (Backend → ESP32)

Commands from backend to control ESP32 actuators.

**Direction**: Backend publishes, ESP32 subscribes  
**QoS**: 2 (exactly once - critical)  
**Retain**: false

**Payload Schema**:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["command_id", "timestamp", "command", "source"],
  "properties": {
    "command_id": {
      "type": "string",
      "format": "uuid",
      "description": "Unique command identifier for tracking"
    },
    "timestamp": {
      "type": "integer"
    },
    "command": {
      "type": "string",
      "enum": [
        "valve_open",
        "valve_close",
        "dissipator_on",
        "dissipator_off",
        "test_mode_enable",
        "test_mode_disable",
        "set_correction_factor",
        "reboot",
        "status_request"
      ]
    },
    "source": {
      "type": "string",
      "enum": ["remote", "panic"],
      "description": "remote: normal command, panic: emergency button"
    },
    "params": {
      "type": "object",
      "description": "Command-specific parameters"
    }
  }
}
```

**Command Examples**:

**Valve Close**:
```json
{
  "command_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": 1715472000000,
  "command": "valve_close",
  "source": "remote"
}
```

**Panic Close** (from operator's panic button):
```json
{
  "command_id": "550e8400-e29b-41d4-a716-446655440001",
  "timestamp": 1715472000000,
  "command": "valve_close",
  "source": "panic"
}
```

**Set Correction Factor**:
```json
{
  "command_id": "550e8400-e29b-41d4-a716-446655440002",
  "timestamp": 1715472000000,
  "command": "set_correction_factor",
  "source": "remote",
  "params": {
    "factor": 1.15
  }
}
```

**Enable Test Mode**:
```json
{
  "command_id": "550e8400-e29b-41d4-a716-446655440003",
  "timestamp": 1715472000000,
  "command": "test_mode_enable",
  "source": "remote",
  "params": {
    "duration_minutes": 30
  }
}
```

---

### 5. `gas/ack/{device_id}` (ESP32 → Backend)

Command acknowledgments from ESP32.

**Direction**: ESP32 publishes, Backend subscribes  
**QoS**: 1  
**Retain**: false

**Payload Schema**:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["command_id", "timestamp", "status"],
  "properties": {
    "command_id": {
      "type": "string",
      "format": "uuid",
      "description": "Original command ID being acknowledged"
    },
    "timestamp": {
      "type": "integer"
    },
    "status": {
      "type": "string",
      "enum": ["success", "failed", "rejected"],
      "description": "Command execution result"
    },
    "error_code": {
      "type": "string",
      "description": "Error code if status is failed/rejected"
    },
    "error_message": {
      "type": "string",
      "description": "Human-readable error message"
    }
  }
}
```

**Example - Success**:
```json
{
  "command_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": 1715472000500,
  "status": "success"
}
```

**Example - Failed**:
```json
{
  "command_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": 1715472000500,
  "status": "failed",
  "error_code": "VALVE_STUCK",
  "error_message": "Valve mechanical failure detected"
}
```

**Example - Rejected**:
```json
{
  "command_id": "550e8400-e29b-41d4-a716-446655440001",
  "timestamp": 1715472000500,
  "status": "rejected",
  "error_code": "ALERT_ACTIVE",
  "error_message": "Cannot disable dissipator during active gas alert"
}
```

---

## Error Codes

| Code | Description |
|------|-------------|
| `VALVE_STUCK` | Valve mechanical failure |
| `DISSIPATOR_STUCK` | Dissipator mechanical failure |
| `ALERT_ACTIVE` | Operation blocked by active alert |
| `INVALID_COMMAND` | Unrecognized command |
| `INVALID_PARAMS` | Invalid command parameters |
| `TEST_MODE_ACTIVE` | Operation blocked by test mode |
| `TIMEOUT` | Operation timed out |

---

## Last Will and Testament (LWT)

ESP32 configures LWT for offline detection:

**Topic**: `gas/status/{device_id}`  
**QoS**: 1  
**Retain**: true  
**Payload**:
```json
{
  "device_id": "{device_id}",
  "timestamp": 0,
  "status": "offline"
}
```

---

## Message Flow Diagrams

### Normal Reading Flow
```
ESP32                    MQTT Broker              Backend
  |                          |                       |
  |-- gas/reading/{id} ----->|                       |
  |                          |-- gas/reading/{id} -->|
  |                          |                       |
  |                          |                       |--> Store in InfluxDB
  |                          |                       |--> Publish to RabbitMQ
```

### Alert Flow (Fail-Safe)
```
ESP32                    MQTT Broker              Backend
  |                          |                       |
  |-- [GAS > 500ppm] --------|                       |
  |-- [CLOSE VALVE local] ---|                       |
  |-- [TURN ON DISSIPATOR] --|                       |
  |-- [BUZZER + LED ON] -----|                       |
  |                          |                       |
  |-- gas/alert/{id} ------->|                       |
  |                          |-- gas/alert/{id} ---->|
  |                          |                       |
  |                          |                       |--> Create Alert
  |                          |                       |--> Send Notifications
```

### Command Flow
```
Backend                  MQTT Broker              ESP32
  |                          |                       |
  |-- gas/command/{id} ----->|                       |
  |                          |-- gas/command/{id} -->|
  |                          |                       |
  |                          |                       |--> Execute command
  |                          |                       |
  |                          |<-- gas/ack/{id} ------|
  |<-- gas/ack/{id} ---------|                       |
  |                          |                       |
  |--> Update command status |                       |
```

---

## Validation Rules

1. **All messages MUST include `device_id` and `timestamp`**
2. **Timestamps MUST be Unix milliseconds**
3. **Gas readings MUST be validated**: 0 ≤ ppm ≤ 10000
4. **Temperature MUST be validated**: -40°C ≤ temp ≤ 85°C
5. **Humidity MUST be validated**: 0% ≤ humidity ≤ 100%
6. **Commands MUST include `command_id` for tracking**
7. **Alerts MUST specify severity based on gas level**

---

## Reconnection Strategy

ESP32 implements exponential backoff:

| Attempt | Delay |
|---------|-------|
| 1 | 1s |
| 2 | 2s |
| 3 | 4s |
| 4 | 8s |
| 5 | 16s |
| 6+ | 30s (max) |

After 30 failed attempts, ESP32 emits long buzzer tone and restarts.
