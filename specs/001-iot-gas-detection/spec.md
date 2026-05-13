# Especificación de Característica: Sistema IoT de Detección de Fugas de Gas - MVP

**Rama de Característica**: `001-iot-gas-detection`
**Creada**: 2026-05-03
**Estado**: Borrador
**Entrada**: Descripción del usuario: "genera un spec para comenzar a construir el proyecto"

## Escenarios de Usuario y Pruebas *(obligatorio)*

### Historia de Usuario 1 - Detección de Gas y Cierre Automático de Válvula (Prioridad: P1)

Cuando el sensor de gas detecta un nivel peligroso, el sistema debe cerrar automáticamente la válvula de gas localmente para prevenir accidentes, independientemente de la conexión al backend. El ESP32 activa el servomotor para cerrar la válvula, enciende automáticamente el disipador/ventilador de extracción para ayudar a evacuar el gas, activa una alarma audible (buzzer) y LEDs de alerta, luego notifica al sistema backend.

**Por qué esta prioridad**: Esta es la función de seguridad crítica del sistema. Sin ella, el sistema no puede proteger contra fugas de gas, lo cual es el propósito principal del proyecto. Es el MVP mínimo viable que entrega valor de seguridad inmediato.

**Prueba Independiente**: Puede probarse completamente simulando lecturas de gas peligroso en el ESP32 y verificando que: (1) la válvula se cierre físicamente, (2) el buzzer y LEDs se activen, y (3) se publique un evento MQTT de alerta. No requiere backend funcional para validar la seguridad física.

**Escenarios de Aceptación**:

1. **Dado** que el sistema está operando normalmente, **cuando** el sensor MQ-6 detecta gas > 500 ppm, **entonces** el ESP32 debe cerrar la válvula dentro de 1 segundo, activar el buzzer, y publicar evento `gas/alert` en MQTT
2. **Dado** que el sistema detectó gas crítico, **cuando** el nivel de gas baja a < 200 ppm, **entonces** el sistema debe permitir reabrir la válvula manualmente o mediante comando autorizado
3. **Dado** que el backend no está disponible, **cuando** se detecta gas crítico, **entonces** el ESP32 debe cerrar la válvula y activar alertas locales sin dependencia de la conexión

---

### Historia de Usuario 2 - Control del Disipador desde la App y Activación Automática (Prioridad: P2)

Los usuarios autorizados deben poder activar o desactivar el disipador/ventilador de extracción desde la aplicación móvil para ventilar el ambiente de forma manual cuando lo consideren necesario. Sin embargo, cuando el ESP32 detecte gas peligroso o crítico, el disipador debe activarse automáticamente de forma local, sin depender de la app, backend o conexión a internet.

**Por qué esta prioridad**: El disipador reduce la concentración de gas en el ambiente y complementa el cierre automático de la válvula. No debe depender solo de la decisión del usuario, porque ante una fuga real la respuesta debe ser inmediata y automática.

**Prueba Independiente**: Puede probarse enviando un comando autorizado desde la app/backend para activar el disipador y verificando que el ESP32 cambia el estado del actuador. También puede probarse simulando lecturas de gas peligroso y verificando que el disipador se activa automáticamente aunque no exista conexión con el backend.

**Escenarios de Aceptación**:

1. **Dado** que el sistema está operando normalmente, **cuando** un usuario autorizado activa el disipador desde la app, **entonces** el backend debe enviar el comando al ESP32 y el disipador debe encenderse
2. **Dado** que el disipador fue activado desde la app, **cuando** el usuario autorizado lo desactiva, **entonces** el sistema debe apagarlo solo si no existe una alerta activa de gas peligroso o crítico
3. **Dado** que el sensor MQ-6 detecta gas peligroso o crítico, **cuando** el nivel de gas supera el umbral configurado, **entonces** el ESP32 debe encender el disipador automáticamente sin depender del backend
4. **Dado** que existe una alerta activa de gas, **cuando** un usuario intenta apagar el disipador desde la app, **entonces** el sistema debe rechazar la acción y mantener el disipador encendido hasta que el nivel de gas vuelva a un rango seguro

---

### Historia de Usuario 3 - Monitoreo en Tiempo Real y Alertas (Prioridad: P3)

Los operadores del sistema deben poder monitorear en tiempo real los niveles de gas, temperatura y humedad de todos los sensores conectados, y recibir alertas inmediatas cuando se detecten niveles peligrosos. El sistema debe proporcionar una API para consultar el estado actual y un sistema de notificaciones para alertas críticas.

**Por qué esta prioridad**: Después de garantizar la seguridad física, la visibilidad en tiempo real es esencial para que los operadores respondan adecuadamente a incidentes. Permite monitoreo continuo y respuesta proactiva, pero no es crítico para la seguridad inmediata (el hardware ya protege localmente).

**Prueba Independiente**: Puede probarse enviando lecturas simuladas de sensores vía MQTT y verificando que: (1) la API retorna el estado actual correctamente, (2) las alertas se generan y publican en RabbitMQ, y (3) los workers de notificación procesan las alertas. No requiere UI de dashboard.

**Escenarios de Aceptación**:

1. **Dado** que sensores están publicando lecturas, **cuando** un operador consulta la API `/api/v1/sensors/{id}/current`, **entonces** debe recibir la última lectura de gas, temperatura y humedad con timestamp
2. **Dado** que se recibe una alerta de gas crítico, **cuando** el worker de alertas procesa el evento, **entonces** debe enviar notificación push y email a los operadores registrados dentro de 30 segundos
3. **Dado** que múltiples sensores están activos, **cuando** se consulta `/api/v1/sensors`, **entonces** debe retornar el estado de todos los sensores con sus últimas lecturas

---

### Historia de Usuario 4 - Histórico de Datos y Dashboard (Prioridad: P4)

Los operadores deben poder ver el historial de lecturas de sensores y alertas para análisis de tendencias, identificación de patrones y auditoría de incidentes. El sistema debe almacenar todas las lecturas y proporcionar endpoints para consultar rangos temporales.

**Por qué esta prioridad**: El análisis histórico es valioso para mantenimiento predictivo y cumplimiento, pero no es esencial para la operación diaria ni la seguridad inmediata. Es una mejora de funcionalidad que puede entregarse después de que el sistema core esté operativo.

**Prueba Independiente**: Puede probarse insertando lecturas históricas en la base de datos y verificando que: (1) la API retorna datos correctos para rangos de tiempo especificados, (2) los datos incluyen todos los atributos necesarios (gas, temperatura, humedad, timestamp), y (3) las consultas son eficientes para rangos grandes. No requiere visualización UI.

**Escenarios de Aceptación**:

1. **Dado** que se han almacenado lecturas por 30 días, **cuando** se consulta `/api/v1/sensors/{id}/readings?start=2026-04-01&end=2026-04-30`, **entonces** debe retornar todas las lecturas en ese rango paginadas
2. **Dado** que ocurrió una alerta crítica, **cuando** se consulta `/api/v1/alerts?sensor_id={id}`, **entonces** debe retornar el historial de alertas con detalles de nivel de gas y timestamp
3. **Dado** que se requieren estadísticas, **cuando** se consulta `/api/v1/sensors/{id}/stats?period=24h`, **entonces** debe retornar promedios, máximos y mínimos de gas, temperatura y humedad en el periodo

---

### Casos Límite

- ¿Qué sucede cuando el sensor MQ-6 devuelve lecturas inválidas o fuera de rango?
- ¿Cómo maneja el sistema desconexiones temporales del broker MQTT?
- ¿Qué pasa si el ESP32 pierde conexión WiFi mientras hay una alerta activa?
- ¿Cómo se maneja el escenario donde múltiples sensores detectan gas simultáneamente?
- ¿Qué ocurre si la válvula física está atascada y no puede cerrarse?
- ¿Cómo se gestiona la pérdida de conexión con RabbitMQ durante una alerta crítica?
- ¿Qué sucede cuando la base de datos no está disponible para almacenar lecturas?
- ¿Cómo se manejan mensajes MQTT malformados o con schema incorrecto?
- ¿Qué ocurre si el certificado SSL expira y no se renueva automáticamente?
- ¿Cómo maneja el ESP32 la reconexión WiFi con reintentos y backoff exponencial?
- ¿Qué sucede si el proxy inverso Nginx falla o se reinicia?
- ¿Cómo se gestionan las actualizaciones de firmware del ESP32 sin interrumpir el monitoreo?
- ¿Qué pasa si un técnico olvida desactivar el "Modo Prueba" y se produce una fuga real?
- ¿Cómo se previene que un usuario operador intente acceder a sensores que no le pertenecen?
- ¿Qué sucede si un administrador elimina accidentalmente un sensor que tiene alertas activas?
- ¿Cómo se audita si un auditor intenta modificar logs (debe ser imposible)?
- ¿Qué ocurre si se alcanza el límite de usuarios concurrentes durante una emergencia?

## Requisitos *(obligatorio)*

### Requisitos Funcionales

- **FR-001**: El sistema DEBE detectar niveles de gas usando el sensor MQ-6 con muestreo cada 1 segundo
- **FR-002**: El ESP32 DEBE cerrar la válvula de gas automáticamente cuando el nivel excede 500 ppm
- **FR-003**: El ESP32 DEBE activar alertas locales (buzzer, LEDs) cuando detecta gas peligroso (200-500 ppm) o crítico (>500 ppm)
- **FR-004**: El ESP32 DEBE publicar eventos MQTT en el tópico `gas/reading` con lecturas de gas, temperatura y humedad
- **FR-005**: El ESP32 DEBE publicar eventos MQTT en el tópico `gas/alert` cuando detecta niveles peligrosos
- **FR-006**: El backend DEBE consumir eventos MQTT y publicarlos en RabbitMQ para procesamiento asíncrono
- **FR-007**: El worker de recolección de datos DEBE validar y almacenar todas las lecturas en PostgreSQL
- **FR-008**: El worker de alertas DEBE procesar alertas críticas y enviar notificaciones (push + email)
- **FR-009**: La API DEBE proporcionar endpoint para consultar el estado actual de sensores
- **FR-010**: La API DEBE proporcionar endpoint para consultar historial de lecturas por rangos de tiempo
- **FR-011**: La API DEBE proporcionar endpoint para consultar historial de alertas
- **FR-012**: Todos los mensajes MQTT DEBEN validarse contra un schema estricto
- **FR-013**: El sistema DEBE operar en modo fail-safe local sin dependencia del backend para acciones críticas
- **FR-014**: El sistema DEBE mantener logs estructurados en JSON para auditoría y debugging
- **FR-015**: Todos los servicios DEBEN implementar health checks para monitoreo
- **FR-016**: El ESP32 DEBE activar automáticamente el disipador/ventilador de extracción cuando detecte gas peligroso (200-500 ppm) o crítico (>500 ppm)
- **FR-017**: La app DEBE permitir a usuarios autorizados activar o desactivar el disipador manualmente cuando no exista una alerta activa de gas
- **FR-018**: El sistema DEBE impedir el apagado manual del disipador desde la app mientras exista una alerta activa de gas peligroso o crítico
- **FR-019**: El backend DEBE exponer un endpoint o comando seguro para enviar órdenes de activación/desactivación del disipador al ESP32
- **FR-020**: El ESP32 DEBE mantener prioridad local sobre comandos remotos, de modo que una alerta de gas siempre fuerce el disipador encendido
- **FR-021**: El sistema DEBE exponer la API REST mediante HTTPS (puerto 443) usando certificados SSL válidos de Let's Encrypt
- **FR-022**: El broker MQTT DEBE soportar conexiones seguras MQTTS (puerto 8883) con encriptación TLS para comunicación con ESP32
- **FR-023**: El proxy inverso Nginx DEBE redirigir tráfico HTTP (puerto 80) a HTTPS (puerto 443) automáticamente
- **FR-024**: El ESP32 DEBE implementar reconexión WiFi automática con reintentos limitados (máximo 30 intentos) y notificación audible de estado
- **FR-025**: El sistema DEBE renovar automáticamente los certificados SSL usando Certbot antes de su expiración
- **FR-026**: El firewall del VPS DEBE permitir solo puertos necesarios: 22 (SSH), 80 (HTTP), 443 (HTTPS), 8883 (MQTTS)
- **FR-027**: El acceso SSH al VPS DEBE usar autenticación por clave pública, sin contraseñas
- **FR-028**: Todos los secretos (credenciales WiFi, tokens, API keys) DEBEN gestionarse mediante archivo .env en producción, nunca hardcodeados en el firmware
- **FR-029**: El sistema DEBE implementar control de acceso basado en roles (RBAC) con 4 roles: Administrador, Usuario/Operador, Técnico de Mantenimiento, y Auditor de Seguridad
- **FR-030**: Los Administradores DEBEN poder crear, editar, suspender y eliminar cuentas de usuarios de cualquier rol
- **FR-031**: Los Administradores DEBEN poder registrar nuevos dispositivos ESP32, asignarles ubicaciones físicas y darlos de baja
- **FR-032**: Los Administradores DEBEN poder configurar umbrales de alerta globales (ppm para gas peligroso y crítico)
- **FR-033**: Los Usuarios/Operadores DEBEN tener acceso solo a los sensores que les han sido asignados explícitamente
- **FR-034**: Los Usuarios/Operadores DEBEN poder activar manualmente el cierre de válvula mediante "Botón de Pánico" en la app
- **FR-035**: Los Usuarios/Operadores DEBEN poder ver historial de telemetría de sus dispositivos asignados (últimas 24 horas, últimas semana/semanas, último mes/meses, último año/años)
- **FR-036**: Los Técnicos de Mantenimiento DEBEN poder activar "Modo Prueba" en dispositivos ESP32 para silenciar notificaciones durante calibración
- **FR-037**: Los Técnicos de Mantenimiento DEBEN tener acceso a métricas de salud del hardware (señal WiFi, estado MQTT, uptime)
- **FR-038**: Los Técnicos de Mantenimiento DEBEN poder ajustar el factor de corrección del sensor MQ-6 remotamente sin reprogramar el ESP32
- **FR-039**: Los Auditores de Seguridad DEBEN tener acceso de solo lectura a todos los logs de auditoría del sistema
- **FR-040**: Los Auditores de Seguridad DEBEN poder monitorear intentos de conexión fallidos, latencia de red y tráfico anómalo
- **FR-041**: Los Auditores de Seguridad DEBEN poder exportar datos de telemetría y alertas para análisis forense sin capacidad de modificar o eliminar registros
- **FR-042**: El sistema DEBE registrar en logs de auditoría todas las acciones críticas con timestamp, usuario, rol y acción realizada
- **FR-043**: El "Modo Prueba" DEBE desactivarse automáticamente después de un timeout configurable (por defecto 30 minutos) para evitar olvidos

### Entidades Clave

- **Sensor**: Dispositivo ESP32 que representa una ubicación física de monitoreo. Atributos: identificador único, ubicación, estado (online/offline), última lectura timestamp
- **Reading**: Medición individual de un sensor en un punto en el tiempo. Atributos: sensor_id, nivel_gas_ppm, temperatura_c, humedad_percent, timestamp, calidad_señal
- **Alert**: Notificación de nivel de gas peligroso que requiere atención. Atributos: alerta_id, sensor_id, nivel_gas, severidad (peligroso/crítico), timestamp, estado (activo/resuelto), notificaciones_enviadas
- **Valve**: Actuador físico para corte de gas controlado por el ESP32. Atributos: valve_id, sensor_id, estado (abierto/cerrado), ultimo_cambio_timestamp, estado_mecanico
- **Disipador**: Actuador físico de ventilación/extracción controlado por el ESP32. Atributos: disipador_id, sensor_id, estado (encendido/apagado), modo_activacion (manual/automático), ultimo_cambio_timestamp, estado_mecanico
- **User**: Usuario del sistema con rol específico. Atributos: user_id, nombre, email, rol (admin/operador/tecnico/auditor), notificaciones_enabled, dispositivos_notificacion, sensores_asignados (solo para operadores), fecha_creacion, estado (activo/suspendido), ultimo_acceso
- **Rol**: Define permisos y capacidades de un usuario. Atributos: rol_id, nombre (admin/operador/tecnico/auditor), permisos (lista de acciones permitidas), descripcion
- **AuditLog**: Registro de auditoría de acciones críticas. Atributos: log_id, timestamp, user_id, rol, accion (ej: "cerrar_valvula_manual", "activar_modo_prueba"), sensor_id, detalles_json, ip_origen
- **VPS**: Servidor virtual en la nube que aloja todos los servicios backend. Atributos: ip_publica, dominio, proveedor (DigitalOcean), region, estado_firewall, certificados_ssl_expiracion
- **ProxyInverso**: Componente Nginx que maneja enrutamiento, SSL/TLS y redirecciones. Atributos: configuracion_dominios, certificados_activos, estado_servicio, logs_acceso

## Criterios de Éxito *(obligatorio)*

### Resultados Medibles

- **SC-001**: El tiempo entre detección de gas crítico (>500 ppm) y cierre de válvula debe ser menor a 1 segundo en 99% de los casos
- **SC-002**: El sistema debe procesar y almacenar al menos 1000 lecturas por segundo sin degradación de rendimiento
- **SC-003**: Las alertas críticas deben llegar a los operadores dentro de 30 segundos en 95% de los casos
- **SC-004**: El tiempo de disponibilidad del sistema core (detección y cierre automático) debe ser mayor al 99.9%
- **SC-005**: La latencia de la API para consultas de estado actual debe ser menor a 200ms en el percentil 95
- **SC-006**: El sistema debe soportar hasta 50 sensores simultáneos sin pérdida de mensajes
- **SC-007**: Los falsos positivos (alertas sin gas real) deben ser menores al 1% del total de alertas
- **SC-008**: El disipador debe activarse automáticamente en menos de 1 segundo desde la detección de gas peligroso o crítico en 99% de los casos
- **SC-009**: Los comandos manuales de activación del disipador desde la app deben reflejarse en el ESP32 en menos de 2 segundos cuando exista conectividad
- **SC-010**: El ESP32 debe reconectarse automáticamente a WiFi en menos de 15 segundos después de una desconexión temporal
- **SC-011**: El tiempo de respuesta de la API a través del proxy inverso Nginx debe ser menor a 250ms en el percentil 95 (incluyendo overhead SSL)
- **SC-012**: Los certificados SSL deben renovarse automáticamente al menos 7 días antes de su expiración sin intervención manual
- **SC-013**: El sistema debe soportar al menos 100 usuarios concurrentes con diferentes roles sin degradación de rendimiento
- **SC-014**: Los logs de auditoría deben ser consultables en menos de 500ms para rangos de hasta 30 días
- **SC-015**: El "Modo Prueba" debe activarse en el ESP32 en menos de 3 segundos desde la solicitud del técnico

## Suposiciones

- Los sensores ESP32 tienen conexión WiFi estable en el entorno de operación (red 2.4 GHz)
- El broker MQTT y RabbitMQ están configurados con alta disponibilidad en el VPS
- Los operadores tienen dispositivos móviles con conexión a internet para recibir notificaciones push
- La válvula de gas es compatible con el servomotor seleccionado
- El disipador/ventilador de extracción puede operar de forma segura con el voltaje y corriente disponibles en el sistema
- El sistema se despliega en un VPS de DigitalOcean con acceso a energía continua y backup
- El rango de operación del sensor MQ-6 es adecuado para los tipos de gas a detectar
- PostgreSQL tiene capacidad suficiente para almacenar datos de sensores por al menos 6 meses (política de retención)
- La red local tiene ancho de banda suficiente para tráfico MQTT de sensores
- El dominio está registrado y los DNS apuntan correctamente a la IP pública del VPS
- El VPS tiene Ubuntu Server como sistema operativo con Docker y Docker Compose instalados
- El firewall UFW está habilitado y configurado correctamente en el VPS
- Las claves SSH están configuradas para acceso seguro sin contraseñas al VPS

## Clarificaciones

**Autenticación de API**: La API REST usará JWT tokens con control de acceso basado en roles (RBAC) para diferenciar entre los 4 roles del sistema: Administrador, Usuario/Operador, Técnico de Mantenimiento, y Auditor de Seguridad.

**Resolución de Alertas**: Las alertas críticas (>500 ppm) requieren resolución manual por operador con verificación humana. Las alertas peligrosas (200-500 ppm) pueden resolverse automáticamente cuando el nivel de gas baja a < 200 ppm.

**Política de Retención de Datos**: Los datos históricos de lecturas se eliminarán después de 6 meses. No se requiere archivo opcional para MVP.

**Encriptación de Datos**: Se requiere encriptación de datos en reposo usando encriptación nativa de PostgreSQL o a nivel de filesystem para proteger datos sensibles.

**Stack de Monitoreo**: Se implementará Prometheus + Grafana para métricas, monitoreo y alertas del sistema, complementando el logging estructurado en JSON.

**Control Manual del Disipador**: El disipador puede activarse desde la app por usuarios autorizados. Sin embargo, durante una alerta de gas peligroso o crítico, el control local del ESP32 tiene prioridad y el disipador permanecerá encendido hasta que el nivel de gas vuelva a un rango seguro.

**Infraestructura Cloud y Despliegue**: El sistema se desplegará en un VPS de DigitalOcean accesible mediante dominio público. Nginx actuará como proxy inverso manejando SSL/TLS termination con certificados de Let's Encrypt (renovación automática vía Certbot). El firewall UFW permitirá solo puertos esenciales: 22 (SSH con clave pública), 80/443 (HTTP/HTTPS para API web), y 8883 (MQTTS para ESP32). El acceso se realizará mediante SSH con autenticación por clave pública sin contraseñas.

**Firmware ESP32**: El firmware base implementa conexión WiFi con reintentos limitados (máximo 30 intentos), notificación audible mediante buzzer para estados de conexión (1 pitido corto = conectado, 3 pitidos = error, pitido largo = desconectado), y reconexión automática en caso de pérdida de WiFi. Las credenciales WiFi y otros secretos deben migrarse de hardcoded a gestión segura mediante variables de entorno o archivo de configuración separado.

**Seguridad de Comunicaciones**: Toda comunicación entre ESP32 y backend usará MQTTS (MQTT sobre TLS) en puerto 8883. La API REST será accesible solo mediante HTTPS con redirección automática desde HTTP. Los certificados SSL se renovarán automáticamente antes de expiración usando Certbot integrado con Nginx.

**Sistema de Roles y Permisos (RBAC)**:

1. **Administrador (Admin/SuperUser)**: Gestión completa del sistema a nivel macro. Capacidades: crear/editar/suspender/eliminar usuarios de cualquier rol, registrar y dar de baja dispositivos ESP32, asignar ubicaciones físicas a sensores, configurar umbrales de alerta globales (ppm para gas peligroso y crítico).

2. **Usuario/Operador (Residente)**: Consumidor final con acceso limitado a sensores asignados. Capacidades: monitorear estado actual (gas, temperatura, humedad) solo de sus sensores asignados, recibir notificaciones push de alertas, activar "Botón de Pánico" para cierre manual de válvula, ver historial de telemetría de sus dispositivos (últimas 24 horas, últimas semana/semanas, último mes/meses, último año/años).

3. **Técnico de Mantenimiento (Técnico/Instalador)**: Rol especializado para mantenimiento y calibración de hardware. Capacidades: activar "Modo Prueba" en ESP32 (silencia notificaciones temporalmente durante calibración), acceder a métricas de salud del hardware (señal WiFi, estado MQTT, uptime), ajustar factor de corrección del sensor MQ-6 remotamente sin reprogramar firmware. El "Modo Prueba" se desactiva automáticamente después de 30 minutos por seguridad.

4. **Auditor de Seguridad (Auditor/Analista)**: Rol de solo lectura enfocado en ciberseguridad y análisis. Capacidades: acceso completo a logs de auditoría (quién hizo qué y cuándo), monitorear intentos de conexión fallidos al broker MQTT, analizar latencia de red y tráfico anómalo, exportar masivamente datos de telemetría y alertas para análisis forense. Sin capacidad de modificar o eliminar registros.

**Logs de Auditoría**: Todas las acciones críticas se registran con timestamp, user_id, rol, acción realizada, sensor_id afectado, detalles en JSON e IP de origen. Ejemplos de acciones auditadas: cierre manual de válvula, activación de modo prueba, cambio de umbrales, creación/eliminación de usuarios, asignación de sensores.

