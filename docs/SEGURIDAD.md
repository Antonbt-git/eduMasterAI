# Modelo de amenazas (STRIDE) y controles

| Amenaza | Vector | Control implementado |
|---|---|---|
| Suplantación | Robo de credenciales, fuerza bruta | bcrypt (12 rondas), rate limit de login (10/min por IP+correo), JWT de 15 min, refresh rotatorio de un solo uso, logout que revoca todas las sesiones |
| Manipulación | Alterar notas o auditoría | Calificación solo con `assessments:write` + ABAC del curso; auditoría con hash encadenado, `pg_advisory_xact_lock` y trigger que bloquea UPDATE/DELETE |
| Repudio | Negar acciones | Bitácora con actor, IP, `correlation_id` y detalle de cada acción sensible |
| Divulgación | IDOR, otro tenant, exportes | Filtro `organization_id` en toda consulta, 404 entre instituciones, verificación de propiedad, seudonimización para analistas, verificación pública con datos mínimos, RLS en Supabase |
| Denegación de servicio | Abuso de API | Rate limit por usuario (240/min), por tutor (12/min) y verificación pública (30/min); límites de tamaño de archivo |
| Elevación de privilegios | Asignar roles | Solo superadmin asigna `superadmin`; cambios de rol invalidan tokens |
| XSS | Comunidad | Contenido escapado en servidor y renderizado como texto; CSP estricta en nginx |
| Inyección SQL | Filtros | ORM con parámetros enlazados en todas las consultas |
| SSRF/archivos | Importación CSV, URLs | Solo `.csv` ≤ 2 MB, URLs solo http/https |
| Fuga en tiempo real | SSE | Ticket de un solo uso (60 s), canal por institución, filtro por rol/usuario |
| Secretos | Repositorio | `.env` ignorado, generador de secretos, la API no arranca en producción con secretos débiles |

## Privacidad de IA
El modelo no usa género, edad, etnia ni ubicación individual. La región se usa solo de forma agregada para evaluar equidad. Las predicciones son señales de apoyo humano y se rotulan como estimación.
