# Contratos API v1

Especificación completa: `openapi.json` (también en vivo en `/api/docs`). Errores normalizados: `{code, message, details, correlation_id}`.

## Identity & Access

| Método | Ruta | Resumen |
|---|---|---|
| `POST` | `/api/v1/auth/login` | Login |
| `POST` | `/api/v1/auth/refresh` | Refresh |
| `POST` | `/api/v1/auth/logout` | Logout |
| `GET` | `/api/v1/auth/me` | Me |
| `GET` | `/api/v1/users` | List Users |
| `POST` | `/api/v1/users` | Create User |
| `PATCH` | `/api/v1/users/{user_id}` | Update User |
| `GET` | `/api/v1/roles` | List Roles |
| `GET` | `/api/v1/organizations` | List Orgs |
| `GET` | `/api/v1/settings` | Get Settings  |
| `PUT` | `/api/v1/settings` | Put Settings |

## Academic Core

| Método | Ruta | Resumen |
|---|---|---|
| `GET` | `/api/v1/courses` | List Courses |
| `POST` | `/api/v1/courses` | Create Course |
| `GET` | `/api/v1/courses/export` | Export Courses |
| `POST` | `/api/v1/courses/import` | Import Courses |
| `GET` | `/api/v1/courses/{course_id}` | Get Course |
| `PATCH` | `/api/v1/courses/{course_id}` | Update Course |
| `POST` | `/api/v1/courses/{course_id}/publish` | Publish Course |
| `POST` | `/api/v1/courses/{course_id}/archive` | Archive Course |
| `POST` | `/api/v1/courses/{course_id}/units` | Add Unit |
| `POST` | `/api/v1/courses/{course_id}/units/{unit_id}/lessons` | Add Lesson |
| `DELETE` | `/api/v1/courses/{course_id}/lessons/{lesson_id}` | Delete Lesson |
| `POST` | `/api/v1/courses/{course_id}/enroll` | Enroll |
| `GET` | `/api/v1/skills` | List Skills |
| `POST` | `/api/v1/skills` | Create Skill |
| `GET` | `/api/v1/cohorts` | List Cohorts |
| `GET` | `/api/v1/instructors` | List Instructors |
| `GET` | `/api/v1/learning-paths` | List Paths |
| `POST` | `/api/v1/learning-paths` | Create Path |
| `POST` | `/api/v1/learning-paths/{path_id}/publish` | Publish Path |
| `POST` | `/api/v1/learning-paths/{path_id}/assign` | Assign Path |
| `GET` | `/api/v1/assessments` | List Assessments |
| `POST` | `/api/v1/assessments` | Create Assessment |
| `GET` | `/api/v1/assessments/{assessment_id}` | Get Assessment |
| `POST` | `/api/v1/assessments/{assessment_id}/attempts` | Submit Attempt |
| `GET` | `/api/v1/assessments/{assessment_id}/attempts` | List Attempts |
| `POST` | `/api/v1/assessments/{assessment_id}/attempts/{attempt_id}/grade` | Grade Attempt |

## Learning Tracking

| Método | Ruta | Resumen |
|---|---|---|
| `POST` | `/api/v1/learning-events` | Post Event |
| `GET` | `/api/v1/students` | List Students |
| `GET` | `/api/v1/students/{student_id}/progress` | Student Progress |
| `GET` | `/api/v1/me/progress` | My Progress |

## Analytics

| Método | Ruta | Resumen |
|---|---|---|
| `GET` | `/api/v1/dashboard/summary` | Dashboard Summary |
| `GET` | `/api/v1/analytics/progress` | Progress Series |
| `GET` | `/api/v1/analytics/geo` | Geo |
| `GET` | `/api/v1/analytics/completion` | Completion |
| `GET` | `/api/v1/analytics/skill-mastery` | Skill Mastery |
| `GET` | `/api/v1/analytics/courses` | Course Table |
| `GET` | `/api/v1/analytics/export` | Export |
| `GET` | `/api/v1/cohorts/{cohort_id}/summary` | Cohort Summary |

## Recommendation

| Método | Ruta | Resumen |
|---|---|---|
| `GET` | `/api/v1/recommendations` | List Recs |
| `POST` | `/api/v1/recommendations/generate` | Generate |
| `POST` | `/api/v1/recommendations/{rec_id}/feedback` | Feedback |
| `POST` | `/api/v1/recommendations/{rec_id}/review` | Review |

## Certification

| Método | Ruta | Resumen |
|---|---|---|
| `GET` | `/api/v1/certificates` | List Certs |
| `POST` | `/api/v1/certificates` | Issue Cert |
| `POST` | `/api/v1/certificates/{cert_id}/revoke` | Revoke |
| `POST` | `/api/v1/certificates/{cert_id}/reissue` | Reissue |
| `GET` | `/api/v1/certificates/{cert_id}/pdf` | Download |

## Community

| Método | Ruta | Resumen |
|---|---|---|
| `GET` | `/api/v1/community/threads` | List Threads |
| `POST` | `/api/v1/community/threads` | Create Thread |
| `GET` | `/api/v1/community/threads/{thread_id}` | Get Thread |
| `POST` | `/api/v1/community/threads/{thread_id}/posts` | Reply |
| `POST` | `/api/v1/community/threads/{thread_id}/report` | Report |
| `GET` | `/api/v1/community/reports` | Reports |
| `POST` | `/api/v1/community/threads/{thread_id}/moderate` | Moderate |

## Notification & Audit

| Método | Ruta | Resumen |
|---|---|---|
| `GET` | `/api/v1/notifications` | List Notifications |
| `POST` | `/api/v1/notifications/{notif_id}/read` | Mark Read |
| `POST` | `/api/v1/notifications/read-all` | Read All |
| `GET` | `/api/v1/notifications/preferences` | Get Prefs |
| `PUT` | `/api/v1/notifications/preferences` | Put Prefs |
| `GET` | `/api/v1/activity` | Feed |
| `GET` | `/api/v1/audit-logs` | Audit Logs |
| `GET` | `/api/v1/audit-logs/verify` | Verify Chain |

## AI Platform

| Método | Ruta | Resumen |
|---|---|---|
| `GET` | `/api/v1/ml/networks` | Networks |
| `GET` | `/api/v1/ml/networks/{key}/graph` | Graph |
| `GET` | `/api/v1/ml/examples` | Examples |
| `GET` | `/api/v1/ml/datasets` | List Datasets |
| `POST` | `/api/v1/ml/datasets` | Build Dataset |
| `POST` | `/api/v1/ml/datasets/{dataset_id}/approve` | Approve Dataset |
| `POST` | `/api/v1/ml/training-runs` | Create Run |
| `GET` | `/api/v1/ml/training-runs` | List Runs |
| `GET` | `/api/v1/ml/training-runs/{run_id}` | Get Run |
| `GET` | `/api/v1/ml/models` | List Models |
| `GET` | `/api/v1/ml/models/{model_id}` | Get Model |
| `POST` | `/api/v1/ml/models/{model_id}/approve` | Approve |
| `POST` | `/api/v1/ml/models/{model_id}/reject` | Reject |
| `POST` | `/api/v1/ml/models/{model_id}/promote` | Promote |
| `POST` | `/api/v1/ml/networks/{key}/rollback` | Rollback |
| `POST` | `/api/v1/ml/predictions` | Predict |
| `GET` | `/api/v1/ml/predictions` | List Predictions |

## Realtime

| Método | Ruta | Resumen |
|---|---|---|
| `POST` | `/api/v1/realtime/ticket` | Ticket |
| `GET` | `/api/v1/realtime/stream` | Stream |

## IA Tutor

| Método | Ruta | Resumen |
|---|---|---|
| `POST` | `/api/v1/ai-tutor/ask` | Ask |

## Público

| Método | Ruta | Resumen |
|---|---|---|
| `GET` | `/api/v1/certificates/verify/{code}` | Verify |

## Operación

| Método | Ruta | Resumen |
|---|---|---|
| `GET` | `/health/live` | Live |
| `GET` | `/health/ready` | Ready |
