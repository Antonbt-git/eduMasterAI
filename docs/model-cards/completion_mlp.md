# Model Card — Completion Predictor v1.0.3

> **DEMO**: entrenado con dataset sintético. Las cifras NO son resultados educativos reales.

| Campo | Valor |
|---|---|
| Clave | `completion_mlp` |
| Tarea | binary:completion |
| Dataset | demo-v1 (`1353f1887e59…`) |
| Esquema de features | 1.0 |
| Parámetros | 1,005 |
| Métrica principal (roc_auc) | 0.9639 |
| Baseline | 0.9617 |
| ¿Supera baseline? | Sí |
| Temperatura de calibración | 1.167 |
| Checksum artefacto | `efc50899dd46ecb7…` |

## Arquitectura

| Capa | Operación | Neuronas | Tensor |
|---|---|---|---|
| Variables de aprendizaje | Normalización + embedding nivel | 9 | `[B, 9+4]` |
| Oculta 1 | Linear + ReLU + Dropout | 32 | `[B, 32]` |
| Oculta 2 | Linear + ReLU | 16 | `[B, 16]` |
| Finalización | Sigmoid / T | 1 | `[B, 1]` |

## Métricas de prueba (cohorte más reciente)

```json
{
 "completion": {
  "roc_auc": 0.9638893821022727,
  "pr_auc": 0.8921118136386867,
  "f1": 0.8316151202749141,
  "recall": 0.9453125,
  "precision": 0.7423312883435583,
  "brier": 0.07550732046365738,
  "ece": 0.07323078137123956,
  "false_positive_rate": 0.11931818181818182,
  "prevalence": 0.2666666805744171
 },
 "primary": 0.9638893821022727
}
```

## Evaluación segmentada

```json
{
 "course_level": {
  "0": 0.9538,
  "1": 0.9794,
  "2": 0.9629
 },
 "region": {
  "Am\u00e9rica del Norte": 0.9727,
  "Am\u00e9rica del Sur": 0.9488,
  "Asia": 0.9651,
  "Europa": 0.9655
 }
}
```

## Uso previsto y límites
- Apoyo a docentes y coordinadores; **no** sanciona, excluye ni califica oficialmente.
- Una probabilidad es una estimación, no certeza ni diagnóstico.
- No usa variables sensibles ni proxies injustificados (sin género, edad, etnia, ubicación individual).
- Requiere revisión humana y aprobación antes de producción; rollback disponible a la versión anterior.
- Población de entrenamiento: cohortes DEMO; niveles de dominio: Principiante, Elemental, Intermedio, Avanzado, Experto.