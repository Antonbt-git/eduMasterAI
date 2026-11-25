# Model Card — EduMaster Multi-Task Network v1.0.1

> **DEMO**: entrenado con dataset sintético. Las cifras NO son resultados educativos reales.

| Campo | Valor |
|---|---|
| Clave | `edumaster_mtl` |
| Tarea | multitask |
| Dataset | demo-v1 (`1353f1887e59…`) |
| Esquema de features | 1.0 |
| Parámetros | 13,131 |
| Métrica principal (composite) | 0.7057 |
| Baseline | 0.6763 |
| ¿Supera baseline? | Sí |
| Temperatura de calibración | 1.000 |
| Checksum artefacto | `a81686d3b64cd6ca…` |

## Arquitectura

| Capa | Operación | Neuronas | Tensor |
|---|---|---|---|
| Entrada tabular | Normalización | 9 | `[B, 9]` |
| Secuencia de eventos | Ventana 8 semanas | 6 | `[B, 8, 6]` |
| Dense tabular | Linear + ReLU | 64 | `[B, 64]` |
| Rama temporal GRU | GRU (h=32) | 32 | `[B, 32]` |
| Dense tabular 2 | Linear + ReLU | 32 | `[B, 32]` |
| Fusión compartida | Concat → Linear → LayerNorm → Dropout | 64 | `[B, 64]` |
| A · Finalización | Sigmoid | 1 | `[B, 1]` |
| B · Dominio | Softmax ordinal | 5 | `[B, 5]` |
| C · Riesgo | Sigmoid | 1 | `[B, 1]` |
| D · Ranking | Scores de ranking | 24 | `[B, 24]` |

## Métricas de prueba (cohorte más reciente)

```json
{
 "completion": {
  "roc_auc": 0.9598277698863636,
  "pr_auc": 0.8739215593937482,
  "f1": 0.8263888888888888,
  "recall": 0.9296875,
  "precision": 0.74375,
  "brier": 0.07658133655786514,
  "ece": 0.06246094927385759,
  "false_positive_rate": 0.11647727272727272,
  "prevalence": 0.2666666805744171
 },
 "risk": {
  "roc_auc": 0.9125270200720534,
  "pr_auc": 0.8566939503310944,
  "f1": 0.7665505226480837,
  "recall": 0.7586206896551724,
  "precision": 0.7746478873239436,
  "brier": 0.10522709041833878,
  "ece": 0.04904660784328977,
  "false_positive_rate": 0.0955223880597015,
  "prevalence": 0.3020833432674408
 },
 "mastery": {
  "macro_f1": 0.6109268740637759,
  "balanced_accuracy": 0.6113003840755598,
  "mae_ordinal": 0.4081081081081081,
  "confusion_matrix": [
   [
    80,
    14,
    4,
    0,
    0
   ],
   [
    19,
    20,
    17,
    5,
    0
   ],
   [
    4,
    12,
    35,
    21,
    0
   ],
   [
    0,
    3,
    16,
    40,
    6
   ],
   [
    0,
    0,
    0,
    14,
    60
   ]
  ]
 },
 "rank": {
  "ndcg@5": 0.3952732123879144,
  "recall@5": 0.41302083333333334,
  "coverage": 1.0,
  "diversity": 0.44125000000000003
 },
 "primary": 0.7056804516672871
}
```

## Evaluación segmentada

```json
{
 "course_level": {
  "0": 0.6932,
  "1": 0.7171,
  "2": 0.6757
 },
 "region": {
  "Am\u00e9rica del Norte": 0.7013,
  "Am\u00e9rica del Sur": 0.6913,
  "Asia": 0.7009,
  "Europa": 0.7118
 }
}
```

## Uso previsto y límites
- Apoyo a docentes y coordinadores; **no** sanciona, excluye ni califica oficialmente.
- Una probabilidad es una estimación, no certeza ni diagnóstico.
- No usa variables sensibles ni proxies injustificados (sin género, edad, etnia, ubicación individual).
- Requiere revisión humana y aprobación antes de producción; rollback disponible a la versión anterior.
- Población de entrenamiento: cohortes DEMO; niveles de dominio: Principiante, Elemental, Intermedio, Avanzado, Experto.