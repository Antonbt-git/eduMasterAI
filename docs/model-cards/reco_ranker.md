# Model Card — Neural Recommender (Two-Tower) v1.0.1

> **DEMO**: entrenado con dataset sintético. Las cifras NO son resultados educativos reales.

| Campo | Valor |
|---|---|
| Clave | `reco_ranker` |
| Tarea | ranking:resources |
| Dataset | demo-v1 (`1353f1887e59…`) |
| Esquema de features | 1.0 |
| Parámetros | 1,693 |
| Métrica principal (ndcg@5) | 0.9882 |
| Baseline | 0.2627 |
| ¿Supera baseline? | Sí |
| Temperatura de calibración | 1.000 |
| Checksum artefacto | `2f9635684c20d309…` |

## Arquitectura

| Capa | Operación | Neuronas | Tensor |
|---|---|---|---|
| Perfil del estudiante | Tabular + competencia | 9 | `[B, 9+4]` |
| Catálogo de recursos | IDs de recurso | 24 | `[R=24]` |
| Torre estudiante | Linear + ReLU | 32 | `[B, 32]` |
| Embedding de recursos | Embedding | 16 | `[R, 16]` |
| Embedding estudiante | Linear | 16 | `[B, 16]` |
| Interacción u⊙v | Hadamard + Linear + ReLU | 16 | `[B, R, 16]` |
| Ranking de recursos | Score + sesgo | 24 | `[B, 24]` |

## Métricas de prueba (cohorte más reciente)

```json
{
 "rank": {
  "ndcg@5": 0.9882290433336444,
  "recall@5": 1.0,
  "coverage": 1.0,
  "diversity": 0.2345833333333334
 },
 "primary": 0.9882290433336444
}
```

## Evaluación segmentada

```json
{
 "course_level": {
  "0": 0.9884,
  "1": 0.9867,
  "2": 0.9907
 },
 "region": {
  "Am\u00e9rica del Norte": 0.9879,
  "Am\u00e9rica del Sur": 0.9881,
  "Asia": 0.9842,
  "Europa": 0.9901
 }
}
```

## Uso previsto y límites
- Apoyo a docentes y coordinadores; **no** sanciona, excluye ni califica oficialmente.
- Una probabilidad es una estimación, no certeza ni diagnóstico.
- No usa variables sensibles ni proxies injustificados (sin género, edad, etnia, ubicación individual).
- Requiere revisión humana y aprobación antes de producción; rollback disponible a la versión anterior.
- Población de entrenamiento: cohortes DEMO; niveles de dominio: Principiante, Elemental, Intermedio, Avanzado, Experto.