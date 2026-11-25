# Metodología de IA — EduMaster.ai

## Pipeline de datos
1. Ingesta de eventos de aprendizaje (seudonimizados).
2. Validación de completitud crítica ≥ 98 %, deduplicación, cuarentena de rango y
   consistencia temporal (≤ 5 %).
3. Split por estudiante (train/validation/test) sin fuga de grupo.
4. Etiquetado a 30 días con horizonte fijo.

## Modelos
- Red neuronal multitarea (completion, mastery, dropout risk, ranking).
- Baselines interpretables: regresión logística y Gradient Boosting; se selecciona el
  mejor por ROC-AUC/PR-AUC (binarios) y macro-F1 (maestría).
- Una versión solo se publica si supera el baseline o con justificación auditada.

## Monitoreo
- Drift de features por PSI (estable < 0.1, moderado < 0.25, drift ≥ 0.25).
- Reentrenamiento trimestral o ante drift significativo.

## Privacidad
- Ley 29733 (Perú): seudonimización antes del entrenamiento, sin identificadores
  directos en el contexto del tutor, consentimiento y derecho de supresión.
