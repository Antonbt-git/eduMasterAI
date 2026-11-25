# Datasheet — edumaster-learning-demo (demo-v1)

> **ETIQUETA: DEMO** — dataset sintético para probar interfaz, pipeline y entrenamiento técnico.
> No permite afirmar validez educativa (documento maestro §8.1).

| Campo | Valor |
|---|---|
| Versión de pipeline | 1.0.0 |
| Esquema de features | 1.0 |
| Semilla | 42 |
| Checksum (sha256) | `1353f1887e59061ddcf9f9b5640727cd5bf70b8d09717c81c87e8ea74dc328c8` |
| Filas ingestadas | 255976 |
| Duplicados eliminados | 1273 |
| Filas en cuarentena | 507 |
| Completitud campos críticos | 100.00% |
| Duplicados tras deduplicación | 0 |
| Split (train/val/test) | {'train': 1920, 'validation': 480, 'test': 480} |

## Motivación
Probar de extremo a extremo la plataforma EduMaster.ai antes de disponer de datos institucionales autorizados.

## Composición
Eventos `session_started`, `lesson_viewed`, `activity_completed`, `assessment_submitted`, `course_completed`
por matrícula, 6 cohortes mensuales, 12 cursos y 5 competencias. Identificadores seudonimizados (sha256 con sal por versión).

## Proceso de etiquetado
- `target_completion_30d`: evento `course_completed` en la ventana futura.
- `target_mastery_level`: rúbrica sobre evaluaciones futuras (0–4). Sin evidencia ⇒ pérdida enmascarada.
- `target_dropout_risk`: sin actividad en las 3 últimas semanas de la ventana futura **y** sin completar (no ausencia aislada).

## Prevención de fuga
Features calculadas solo con semanas 0–7. Split temporal por cohorte; métricas adicionales en estudiantes no vistos.

## Limitaciones
Datos sintéticos; distribuciones simplificadas; no representativos de ninguna institución real.
