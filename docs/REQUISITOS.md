# Requisitos, historias de usuario y glosario

## Historias principales
| Rol | Historia | Criterio de aceptación |
|---|---|---|
| Estudiante | Quiero ver mi avance y qué hacer después | Dashboard personal con progreso, competencias (validado vs IA) y recomendaciones con motivo |
| Estudiante | Quiero responder evaluaciones y ver mi nota | Respeta intentos y plazos; nota oficial separada de estimaciones IA |
| Docente | Quiero detectar a quién apoyar | Señal de riesgo explicada, solo de estudiantes de mis cursos |
| Docente | Quiero calificar entregas | Revisión de intentos con nota y retroalimentación auditadas |
| Coordinador | Quiero asignar rutas a cohortes | Publicación validada y asignación con fecha objetivo |
| Administrador | Quiero exportar indicadores | XLSX/CSV/PDF con fecha y filtros, auditado |
| ML Engineer | Quiero entrenar y comparar versiones | Entrenamiento asíncrono visible en vivo, métricas vs baseline |
| Administrador | Quiero aprobar o revertir modelos | Aprobación con nota, promoción, rollback |
| Auditor | Quiero verificar que nada fue alterado | Verificación de la cadena hash completa |

## Glosario
- **DEMO**: dato sintético rotulado, solo para demostración.
- **Baseline**: modelo interpretable de referencia (regresión logística, popularidad).
- **Outbox**: tabla de eventos escrita en la misma transacción que el cambio de negocio.
- **Sinapsis**: partícula animada que recorre una conexión real entre neuronas durante una inferencia o retropropagación real.
- **ABAC**: autorización por atributos (institución, curso asignado, propiedad del registro).
