# Model Card — Skill Mastery Ordinal v1.0.1

> **DEMO**: entrenado con dataset sintético. Las cifras NO son resultados educativos reales.

| Campo | Valor |
|---|---|
| Clave | `mastery_ordinal` |
| Tarea | ordinal:mastery |
| Dataset | demo-v1 (`1353f1887e59…`) |
| Esquema de features | 1.0 |
| Parámetros | 2,281 |
| Métrica principal (macro_f1) | 0.6415 |
| Baseline | 0.6308 |
| ¿Supera baseline? | Sí |
| Temperatura de calibración | 1.000 |
| Checksum artefacto | `6cdf96281d7fd64b…` |

## Arquitectura

| Capa | Operación | Neuronas | Tensor |
|---|---|---|---|
| Evidencias y actividad | Tabular + embedding competencia + media temporal | 9 | `[B, 9+4+6]` |
| Oculta 1 | Linear + GELU | 48 | `[B, 48]` |
| Oculta 2 | Linear + GELU | 24 | `[B, 24]` |
| Nivel de dominio | Softmax ordinal | 5 | `[B, 5]` |
| Umbrales acumulados | P(nivel ≥ k) | 4 | `[B, 4]` |

## Métricas de prueba (cohorte más reciente)

```json
{
 "mastery": {
  "macro_f1": 0.6415484466645792,
  "balanced_accuracy": 0.6470757546284479,
  "mae_ordinal": 0.37027027027027026,
  "confusion_matrix": [
   [
    81,
    13,
    4,
    0,
    0
   ],
   [
    19,
    22,
    13,
    7,
    0
   ],
   [
    1,
    13,
    37,
    20,
    1
   ],
   [
    0,
    2,
    11,
    40,
    12
   ],
   [
    0,
    0,
    0,
    6,
    68
   ]
  ]
 },
 "primary": 0.6415484466645792
}
```

## Evaluación segmentada

```json
{
 "course_level": {
  "0": 0.6338,
  "1": 0.6288,
  "2": 0.6337
 },
 "region": {
  "Am\u00e9rica del Norte": 0.6058,
  "Am\u00e9rica del Sur": 0.6563,
  "Asia": 0.6085,
  "Europa": 0.6974
 }
}
```

## Uso previsto y límites
- Apoyo a docentes y coordinadores; **no** sanciona, excluye ni califica oficialmente.
- Una probabilidad es una estimación, no certeza ni diagnóstico.
- No usa variables sensibles ni proxies injustificados (sin género, edad, etnia, ubicación individual).
- Requiere revisión humana y aprobación antes de producción; rollback disponible a la versión anterior.
- Población de entrenamiento: cohortes DEMO; niveles de dominio: Principiante, Elemental, Intermedio, Avanzado, Experto.