# Model Card — Disengagement Risk Transformer v1.0.2

> **DEMO**: entrenado con dataset sintético. Las cifras NO son resultados educativos reales.

| Campo | Valor |
|---|---|
| Clave | `risk_transformer` |
| Tarea | binary:risk |
| Dataset | demo-v1 (`1353f1887e59…`) |
| Esquema de features | 1.0 |
| Parámetros | 18,945 |
| Métrica principal (pr_auc) | 0.8534 |
| Baseline | 0.8499 |
| ¿Supera baseline? | Sí |
| Temperatura de calibración | 1.082 |
| Checksum artefacto | `23c7d3c7a3ebb872…` |

## Arquitectura

| Capa | Operación | Neuronas | Tensor |
|---|---|---|---|
| Secuencia semanal | 8 semanas × 6 señales | 6 | `[B, 8, 6]` |
| Contexto tabular | Normalización | 9 | `[B, 9]` |
| Embedding temporal | Linear + posicional | 32 | `[B, 8, 32]` |
| Self-Attention 1 | MHA 4 cabezas + FFN | 32 | `[B, 8, 32]` |
| Self-Attention 2 | MHA 4 cabezas + FFN | 32 | `[B, 8, 32]` |
| Cabeza densa | Pool + Concat + Linear + ReLU | 32 | `[B, 32]` |
| Riesgo de desconexión | Sigmoid / T | 1 | `[B, 1]` |

## Métricas de prueba (cohorte más reciente)

```json
{
 "risk": {
  "roc_auc": 0.9031600617601647,
  "pr_auc": 0.8533785582684725,
  "f1": 0.752411575562701,
  "recall": 0.8068965517241379,
  "precision": 0.7048192771084337,
  "brier": 0.11971203982830048,
  "ece": 0.0945702695598205,
  "false_positive_rate": 0.14626865671641792,
  "prevalence": 0.3020833432674408
 },
 "primary": 0.8533785582684725
}
```

## Evaluación segmentada

```json
{
 "course_level": {
  "0": 0.8778,
  "1": 0.8733,
  "2": 0.7452
 },
 "region": {
  "Am\u00e9rica del Norte": 0.8544,
  "Am\u00e9rica del Sur": 0.8487,
  "Asia": 0.7368,
  "Europa": 0.8711
 }
}
```

## Uso previsto y límites
- Apoyo a docentes y coordinadores; **no** sanciona, excluye ni califica oficialmente.
- Una probabilidad es una estimación, no certeza ni diagnóstico.
- No usa variables sensibles ni proxies injustificados (sin género, edad, etnia, ubicación individual).
- Requiere revisión humana y aprobación antes de producción; rollback disponible a la versión anterior.
- Población de entrenamiento: cohortes DEMO; niveles de dominio: Principiante, Elemental, Intermedio, Avanzado, Experto.