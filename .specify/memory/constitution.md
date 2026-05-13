<!--
INFORME DE IMPACTO DE SINCRONIZACIÓN
Cambio de versión: 1.3.0 → 1.4.0 (sincronización con spec y roles RBAC)
Principios modificados: N/A
Secciones añadidas: N/A
Secciones sincronizadas: Roles RBAC (4 roles), Entidades (incluye Disipador, AuditLog)
Documentos verificados:
  ✅ spec.md - 43 requisitos funcionales, 15 criterios éxito, 4 roles
  ✅ specify-rules.md - Bounded contexts y entidades alineados
  ✅ prompts/constitution.md - Estructura actualizada a hexagonal, MQ-6, disipador
  ✅ checklists/requirements.md - Actualizado con 4 historias de usuario
  ⚠ README.md - Vacío, necesita documentación del proyecto
TODOs de seguimiento: Documentar flujos de comunicación entre bounded contexts
-->

# Constitución del Sistema IoT de Detección de Fugas de Gas

## Principios Fundamentales

### I. Fail-Safe Primero (Seguridad ante Todo)

El hardware DEBE actuar de forma autónoma sin dependencia del backend. Las acciones de seguridad críticas (ej. cierre de válvula) se ejecutan localmente en el ESP32 antes de cualquier comunicación con el backend. Racional: Los fallos de red o caídas del backend no deben comprometer nunca la seguridad física.

### II. Arquitectura Orientada a Eventos

Todos los componentes se comunican mediante eventos asíncronos (MQTT para tiempo real, RabbitMQ para procesamiento asíncrono). Los servicios DEBEN estar desacoplados y comunicarse a través de brokers de mensajes, no mediante llamadas directas. El hardware ESP32 DEBE ser controlado exclusivamente vía MQTT, nunca mediante comunicación directa con workers. Racional: Permite escalado independiente, aislamiento de fallos y acoplamiento débil entre hardware, API y workers.

### III. Asíncrono por Defecto

Todas las operaciones de I/O DEBEN usar patrones asíncronos (asyncio, aio-pika). Las llamadas bloqueantes están prohibidas en los manejadores de solicitudes y workers. Racional: Garantiza alto rendimiento bajo carga y previene el agotamiento del pool de hilos.

### IV. Separación de Responsabilidades

La capa API, los workers y la infraestructura de mensajería están estrictamente separados. La API expone endpoints y publica eventos pero no procesa lógica de negocio. Los workers manejan tareas asíncronas específicas. El broker MQTT maneja telemetría en tiempo real y comandos de hardware. Los workers NUNCA comunican directamente con hardware físico. Racional: Los límites claros permiten despliegue, pruebas y escalado independientes de cada responsabilidad.

### V. Escalable por Diseño

La arquitectura DEBE soportar escalado horizontal. La ausencia de estado es obligatoria para las instancias de API y workers. Cada bounded context y worker puede escalar independientemente. Racional: El sistema debe manejar crecientes cantidades de dispositivos y volumen de mensajes sin cambios arquitectónicos.

### VI. Dominio Puro (DDD)

El dominio DEBE estar libre de dependencias de infraestructura. Las reglas de negocio, entidades y servicios del dominio DEBEN ser agnósticos a bases de datos, APIs y frameworks. Los adapters implementan los ports del dominio. Racional: Protege la lógica de negocio de cambios tecnológicos y facilita las pruebas.

### VII. Comunicación Indirecta con Hardware

El control de hardware físico (ESP32) DEBE realizarse exclusivamente mediante mensajes MQTT. Los workers DEBEN publicar comandos en tópicos MQTT específicos, nunca mediante comunicación directa. El ESP32 DEBE suscribirse a tópicos de control y ejecutar acciones localmente. Racional: Mantiene el principio fail-safe y elimina dependencias directas entre workers y hardware.

### VIII. Separación de Almacenamiento

Los datos DEBEN separarse por tipo y frecuencia de acceso. Datos estructurados (usuarios, configuración, alertas) DEBEN almacenarse en PostgreSQL con SQLAlchemy 2.0. Telemetría masiva (lecturas de sensores) DEBEN almacenarse en InfluxDB con cliente nativo. Racional: Optimiza rendimiento y costos según características de los datos.

### IX. Patrones de Persistencia

Para datos relacionales DEBE usarse SQLAlchemy 2.0 con patrón Data Mapper. Los modelos de base de datos viven exclusivamente en la capa de adapters. Para telemetría DEBE usarse cliente nativo InfluxDB sin ORM. Racional: Mantiene dominio puro y maximiza throughput para datos de alta frecuencia.

## Estándares de Código

### Clean Code Principles
- Los nombres DEBEN ser descriptivos y revelar intención
- Las funciones DEBEN ser pequeñas y hacer una sola cosa
- Los comentarios DEBEN explicar el "porqué", no el "qué"
- El código DEBE seguir el principio DRY (Don't Repeat Yourself)

### Patrones de Escritura
- **Variables y funciones**: snake_case (ej: `gas_sensor_reading`)
- **Clases**: PascalCase (ej: `GasDetectionService`)
- **Constantes**: UPPER_CASE (ej: `MQTT_BROKER_URL`)
- **Archivos**: snake_case con extensión apropiada (ej: `gas_sensor.py`)
- **Módulos/Paquetes**: snake_case (ej: `gas_detection/`)
- **Variables privadas**: prefijo `_` (ej: `_internal_state`)
- **Métodos privados**: prefijo `_` (ej: `_validate_sensor()`)

### Principios SOLID
- **S**ingle Responsibility: Cada clase debe tener una sola razón para cambiar
- **O**pen/Closed: Abierto para extensión, cerrado para modificación
- **L**iskov Substitution: Las subclases deben poder reemplazar a sus clases base
- **I**nterface Segregation: Interfaces específicas y pequeñas
- **D**ependency Inversion: Depender de abstracciones, no de implementaciones

### Guías de Formato y Estructura
- **Indentación**: 4 espacios, sin tabs
- **Longitud máxima de línea**: 88-100 caracteres
- **Imports**: agrupar por tipo (stdlib, third-party, local)
- **Docstrings**: formato Google o NumPy consistente
- **Type hints**: obligatorios para interfaces públicas
- **Complejidad ciclomática**: máximo 10 por función

### Manejo de Errores y Logging
- **Excepciones específicas**: crear excepciones de dominio (ej: `SensorReadError`)
- **Logging estructurado**: usar JSON en producción
- **Niveles de log**: DEBUG para desarrollo, INFO para producción
- **No silenciar excepciones**: nunca usar `except: pass`

### Testing y Calidad
- **Coverage mínimo**: 80% para código crítico
- **Tests unitarios**: aislados, rápidos, sin dependencias externas
- **Tests de integración**: para flujos críticos de negocio
- **Nomenclatura de tests**: `test_[scenario]_[expected_behavior]`

## Requisitos de Seguridad

- TLS DEBE estar habilitado para todas las comunicaciones externas en producción
- Los mensajes MQTT DEBEN validarse con verificaciones estrictas de esquema
- Los secretos DEBEN gestionarse mediante variables de entorno o gestores de secretos, nunca hardcodeados
- El backend NO DEBE confiar para acciones de seguridad críticas (el fail-safe del hardware es primario)
- Todas las entradas de fuentes no confiables (dispositivos ESP32) DEBEN sanitizarse
- El control de hardware DEBE realizarse vía MQTT, nunca mediante comunicación directa
- Los workers DEBEN publicar comandos en tópicos MQTT, no ejecutar acciones de hardware

## Flujo de Desarrollo

- El desarrollo de características sigue el flujo de Spec Kit: spec → plan → tasks → implement
- Todas las características DEBEN incluir escenarios de usuario con criterios de aceptación
- La capacidad de prueba independiente es obligatoria para cada historia de usuario
- La estructura del código sigue arquitectura hexagonal con Domain-Driven Design

### Estructura de Proyecto
- **Dominio Compartido** (`domain/`): Paquete Python independiente con bounded contexts
  - `sensor/`: Entidades, repositorios, servicios de sensores
  - `safety/`: Lógica de seguridad y fail-safe
  - `alert/`: Gestión de alertas y notificaciones
  - `user/`: Usuarios, permisos y roles
  - `shared/`: Eventos base, value objects, excepciones
- **Backend API** (`app/`): Contenedor separado con adaptadores
  - `adapters/api/`: REST endpoints y middleware
  - `adapters/persistence/postgresql/`: SQLAlchemy 2.0 + Alembic
  - `adapters/persistence/influxdb/`: Cliente nativo telemetría
  - `adapters/messaging/`: RabbitMQ y MQTT
  - `application/`: Casos de uso por bounded context
  - `infrastructure/`: Configuración y DI container
- **Workers** (`workers/`): Contenedores separados por responsabilidad
  - `gas_detection/`: Procesamiento de lecturas de gas
  - `alert_handler/`: Manejo de alertas críticas
  - `data_collector/`: Recolección y validación de datos
  - `shared/`: Adaptadores reutilizables

### Comunicación y Mensajería
- **MQTT**: Tiempo real y comunicación con hardware ESP32
- **RabbitMQ**: Procesamiento asíncrono y desacoplamiento
- **PostgreSQL**: Datos estructurados con SQLAlchemy 2.0
- **InfluxDB**: Telemetría masiva con cliente nativo
- **Redis**: Cache y estado temporal
- **Docker**: Contenedorización y consistencia de despliegue

## Gobernanza

Esta constitución prevalece sobre todas las demás prácticas de desarrollo. Las enmiendas requieren:
1. Documentación del racional del cambio
2. Incremento de versión siguiendo versionado semántico (MAJOR para eliminación/redefinición de principios, MINOR para nuevos principios, PATCH para aclaraciones)
3. Propagación de cambios a plantillas dependientes (plan, spec, tasks)
4. Revisión de cumplimiento de todos los PRs contra los principios actuales

Toda complejidad más allá de estos principios DEBE justificarse explícitamente con una alternativa más simple considerada y rechazada.

**Versión**: 1.4.0 | **Ratificada**: 2026-05-03 | **Última Modificación**: 2026-05-11
