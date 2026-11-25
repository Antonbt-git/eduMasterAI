# Matriz de trazabilidad

Cómo se cumple cada requisito de *Documentación EduMaster AI Enterprise* (DM) y del *Manual de funcionamiento y procedimientos* (MF).

## Módulos funcionales (DM §4)
| Requisito | Implementación | Ubicación |
|---|---|---|
| 4.1 Dashboard ejecutivo con KPIs, fuente, fecha y variación | `/dashboard/summary` + `KpiCard` con tooltip de fuente/actualización; filtros periodo/curso/cohorte/región | `analytics.py`, `DashboardPage.tsx` |
| 4.2 Rutas con objetivos, prerrequisitos, criterios, asignación | CRUD, publicación con validación, asignación a cohorte/estudiante con excepción | `academic.py`, `PathsPage.tsx` |
| 4.3 Cursos con versionado, importación/exportación | Crear, editar, unidades/lecciones, publicar/archivar, CSV idempotente (`Idempotency-Key`) | `academic.py`, `CoursesPage.tsx` |
| 4.4 Analítica con definiciones | Tabla por curso con definiciones documentadas, exportación XLSX/CSV/PDF auditada | `AnalyticsPage.tsx` |
| 4.5 IA Tutor | Contexto minimizado + Anthropic/OpenAI opcional + reglas | `tutor.py`, `TutorPage.tsx` |
| 4.6 Evaluaciones | Tipos, intentos, plazos, regla mejor/último/promedio, autocalificación, revisión docente | `academic.py`, `AssessmentsPage.tsx` |
| 4.7 Certificados | Folio único, PDF con QR, verificación pública mínima, anulación y reemisión | `certificates.py` |
| 4.8 Comunidad | Anuncios, debates, respuestas, reportes, moderación, escape XSS | `community.py` |
| 4.9 Dominio de habilidades | Validado (evaluación/docente) separado de estimación IA | `SkillsPage.tsx` |
| 4.10 Arquitectura neuronal animada | 5 redes con topología real, pesos, activaciones, sinapsis, controles | `NeuralNetworkCanvas.tsx`, `NeuralPage.tsx` |
| 4.11 Recomendaciones | Modelo → reglas → explicación; aceptar/descartar/útil; métricas de aceptación | `recommendations.py` |
| 4.12 Actividad y notificaciones | Feed cursor-based, centro de notificaciones, preferencias | `notifications.py` |

## Diseño (DM §5)
**Edición Nebula:** por decisión del cliente se sustituyó la paleta azul del documento (§5.1) por la paleta Nebula, conservando el resto de la especificación visual.

| Token | Original | Nebula |
|---|---|---|
| Fondo | #06152B | #0D0A1E |
| Superficies | #0A1F3D / #0D2B52 | #16112E / #21194A |
| Principal | #087FE5 | #7C5CFF (índigo eléctrico) |
| Acento | #20C8F5 | #FF5FD2 (magenta neón) |
| Secundario / retropropagación | #8B4DFF | #FF9F43 (naranja) |
| Éxito | #00BFA6 | #2DE2A6 (menta) |

El mapeo completo está en `scripts/palette-nebula.py` (re-ejecutable). Se mantienen paneles de 14 px con borde translúcido, Sora + Inter, glow solo en paneles destacados, `prefers-reduced-motion`, foco visible, responsive hasta 390 px y simulación rotulada.

## Datos, ML y MLOps (DM §7–9, MF §8–9)
| Requisito | Implementación |
|---|---|
| UUID, FK, CHECK, índices compuestos, UTC | `db/models.py`, migración `0001` |
| Pipeline de 10 pasos | `datasets/pipeline.py` (ingesta → publicación con datasheet) |
| Sin fuga temporal; split por cohorte; métrica en estudiantes no vistos | ventanas de 8 semanas, test = cohorte más reciente |
| Reconstrucción con mismo checksum (CA 28) | `test_dataset_reproducible_checksum` |
| Red MTL con 4 cabezas y pérdida enmascarada | `EduMasterMTL` |
| Baselines interpretables y puerta de publicación | `evaluation/baselines.py`, `beats_baseline` |
| Calibración, métricas por tarea, segmentación | temperature scaling, ECE, Brier, macro-F1, NDCG@5, segmentos por nivel/región |
| Registro, aprobación, promoción, rollback (CA 29) | `ml.py`, `ModelRegistry` en UI |
| Model card y datasheet | `docs/model-cards/`, `docs/data-dictionary/DATASHEET_demo-v1.md` |
| Drift | `monitoring/drift.py` (PSI) |
| Nunca entrenar en el hilo HTTP | Worker RQ; la API responde 503 si no hay worker |

## Tiempo real (DM §10)
Outbox transaccional, SSE por institución con filtro por rol/usuario, ticket de un solo uso, replay por `Last-Event-ID`, backoff exponencial, `schema_version` en cada evento (CA 26).

## Seguridad (DM §11) y pruebas de autorización (CA 30)
bcrypt, JWT de 15 min + refresh rotatorio, revocación global, rate limiting, RBAC + ABAC, 404 entre instituciones, seudonimización para analistas, auditoría con hash encadenado e inmutable en BD, RLS en Supabase, cabeceras CSP/HSTS-ready, validación de archivos. Pruebas: `apps/api/tests/test_security.py`.

## Criterios de aceptación global (DM §13.1)
| # | Estado | Evidencia |
|---|---|---|
| 22 Módulos con rutas, permisos, formularios, validación, persistencia y estados | ✔ | 14 rutas protegidas; `QueryState` (carga/error/vacío) |
| 23 Botones y filtros con acciones reales y confirmación/error | ✔ | Toaster + errores normalizados con `correlation_id` |
| 24 DEMO rotulado y sustituible | ✔ | `DemoBadge`, `label=DEMO`, `SEED_DEMO_DATA` |
| 25 Fuente y fecha por KPI | ✔ | `kpis.*.source/updated_at` |
| 26 Actualización sin recarga y recuperación tras reconexión | ✔ | SSE + `Last-Event-ID` |
| 27 Visualización refleja backend; simulación rotulada | ✔ | estados entrenando/validando/publicado/error desde `model_runs` |
| 28 Dataset reconstruible | ✔ | prueba de checksum |
| 29 Modelo con ficha, métricas, versión, aprobación y rollback | ✔ | registro de modelos |
| 30 Sin acceso a otra institución/estudiante | ✔ | pruebas de aislamiento |
| 31 Documentación de despliegue, variables, backup, restauración | ✔ | `README`, `.env.example`, `docs/runbooks/` |

## Limitaciones honestas
- Las métricas de los modelos provienen de datos sintéticos DEMO; no permiten afirmar validez educativa.
- El frontend usa SSE (no WebSocket); cumple el mismo contrato de eventos.
- Las pruebas E2E se realizaron con Playwright de forma manual durante el desarrollo; no hay suite E2E automatizada en CI.
- No pude construir las imágenes Docker en el entorno de desarrollo (sin acceso a Docker Hub); la pila se verificó ejecutando cada servicio de forma nativa contra PostgreSQL 16 y Redis 7.
