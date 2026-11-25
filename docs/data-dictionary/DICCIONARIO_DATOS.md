# Diccionario de datos

Generado desde los modelos SQLAlchemy (fuente de verdad de las migraciones Alembic). Todas las marcas de tiempo son UTC (`timestamptz`); los identificadores internos son UUID salvo secuencias de auditoría/outbox.

## `activities`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| organization_id | CHAR(32) | no |  | organizations.id |
| actor_id | CHAR(32) | sí |  | users.id |
| subject_user_id | CHAR(32) | sí |  | users.id |
| type | VARCHAR(40) | no |  |  |
| title | VARCHAR(240) | no |  |  |
| visibility | VARCHAR(20) | no |  |  |
| id | CHAR(32) | no | PK |  |
| created_at | DATETIME | no |  |  |

Índices: `ix_activity_org_time`, `ix_activities_subject_user_id`

## `assessment_attempts`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| assessment_id | CHAR(32) | no |  | assessments.id |
| student_id | CHAR(32) | no |  | students.id |
| answers | JSON | no |  |  |
| score | FLOAT | sí |  |  |
| late | BOOLEAN | no |  |  |
| status | VARCHAR(20) | no |  |  |
| feedback | TEXT | sí |  |  |
| graded_by | CHAR(32) | sí |  | users.id |
| submitted_at | DATETIME | no |  |  |
| id | CHAR(32) | no | PK |  |

Índices: `ix_attempt_student_assessment`, `ix_assessment_attempts_assessment_id`, `ix_assessment_attempts_student_id`

## `assessments`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| course_id | CHAR(32) | no |  | courses.id |
| organization_id | CHAR(32) | no |  | organizations.id |
| title | VARCHAR(200) | no |  |  |
| type | VARCHAR(30) | no |  |  |
| max_score | FLOAT | no |  |  |
| weight | FLOAT | no |  |  |
| due_at | DATETIME | sí |  |  |
| attempts_allowed | INTEGER | no |  |  |
| passing_score | FLOAT | no |  |  |
| grading_rule | VARCHAR(20) | no |  |  |
| instructions | TEXT | no |  |  |
| rubric | JSON | no |  |  |
| questions | JSON | no |  |  |
| skill_id | CHAR(32) | sí |  | skills.id |
| status | VARCHAR(20) | no |  |  |
| id | CHAR(32) | no | PK |  |
| created_at | DATETIME | no |  |  |

Restricciones CHECK: `max_score > 0`

Índices: `ix_assessments_organization_id`, `ix_assessments_course_id`

## `audit_logs`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| id | BIGINT | no | PK |  |
| organization_id | CHAR(32) | sí |  |  |
| actor_id | CHAR(32) | sí |  |  |
| actor_email | VARCHAR(254) | sí |  |  |
| action | VARCHAR(60) | no |  |  |
| resource | VARCHAR(60) | no |  |  |
| resource_id | VARCHAR(80) | sí |  |  |
| occurred_at | DATETIME | no |  |  |
| ip | VARCHAR(64) | sí |  |  |
| correlation_id | VARCHAR(64) | sí |  |  |
| details | JSON | no |  |  |
| prev_hash | VARCHAR(64) | sí |  |  |
| hash | VARCHAR(64) | no |  |  |

Índices: `ix_audit_org_time`

## `certificates`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| organization_id | CHAR(32) | no |  | organizations.id |
| student_id | CHAR(32) | no |  | students.id |
| course_id | CHAR(32) | no |  | courses.id |
| folio | VARCHAR(40) | no |  |  |
| verification_code | VARCHAR(40) | no |  |  |
| template | VARCHAR(40) | no |  |  |
| status | VARCHAR(20) | no |  |  |
| issued_at | DATETIME | sí |  |  |
| expires_at | DATETIME | sí |  |  |
| issued_by | CHAR(32) | sí |  | users.id |
| revoked_reason | TEXT | sí |  |  |
| final_score | FLOAT | sí |  |  |
| id | CHAR(32) | no | PK |  |
| created_at | DATETIME | no |  |  |

Índices: `ix_certificates_student_id`, `ix_certificates_organization_id`

## `cohorts`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| organization_id | CHAR(32) | no |  | organizations.id |
| code | VARCHAR(40) | no |  |  |
| name | VARCHAR(120) | no |  |  |
| program | VARCHAR(120) | no |  |  |
| start_date | DATE | no |  |  |
| id | CHAR(32) | no | PK |  |
| created_at | DATETIME | no |  |  |

Índices: `ix_cohorts_organization_id`

## `community_posts`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| thread_id | CHAR(32) | no |  | community_threads.id |
| author_id | CHAR(32) | no |  | users.id |
| body | TEXT | no |  |  |
| status | VARCHAR(20) | no |  |  |
| id | CHAR(32) | no | PK |  |
| created_at | DATETIME | no |  |  |

Índices: `ix_community_posts_thread_id`

## `community_threads`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| organization_id | CHAR(32) | no |  | organizations.id |
| course_id | CHAR(32) | sí |  | courses.id |
| author_id | CHAR(32) | no |  | users.id |
| kind | VARCHAR(20) | no |  |  |
| title | VARCHAR(200) | no |  |  |
| body | TEXT | no |  |  |
| status | VARCHAR(20) | no |  |  |
| pinned | BOOLEAN | no |  |  |
| id | CHAR(32) | no | PK |  |
| created_at | DATETIME | no |  |  |

Índices: `ix_community_threads_course_id`, `ix_community_threads_organization_id`

## `content_reports`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| organization_id | CHAR(32) | no |  | organizations.id |
| thread_id | CHAR(32) | sí |  | community_threads.id |
| post_id | CHAR(32) | sí |  | community_posts.id |
| reporter_id | CHAR(32) | no |  | users.id |
| reason | VARCHAR(300) | no |  |  |
| status | VARCHAR(20) | no |  |  |
| resolved_by | CHAR(32) | sí |  | users.id |
| id | CHAR(32) | no | PK |  |
| created_at | DATETIME | no |  |  |

Índices: `ix_content_reports_organization_id`

## `course_offerings`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| course_id | CHAR(32) | no |  | courses.id |
| instructor_id | CHAR(32) | sí |  | instructors.id |
| cohort_id | CHAR(32) | sí |  | cohorts.id |
| period | VARCHAR(20) | no |  |  |
| starts_at | DATE | sí |  |  |
| ends_at | DATE | sí |  |  |
| id | CHAR(32) | no | PK |  |
| created_at | DATETIME | no |  |  |

Índices: `ix_course_offerings_instructor_id`, `ix_offering_course_period`, `ix_course_offerings_course_id`

## `course_skills`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| course_id | CHAR(32) | no | PK | courses.id |
| skill_id | CHAR(32) | no | PK | skills.id |
| weight | FLOAT | no |  |  |

## `course_units`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| course_id | CHAR(32) | no |  | courses.id |
| title | VARCHAR(200) | no |  |  |
| position | INTEGER | no |  |  |
| id | CHAR(32) | no | PK |  |

Índices: `ix_course_units_course_id`

## `courses`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| organization_id | CHAR(32) | no |  | organizations.id |
| code | VARCHAR(40) | no |  |  |
| title | VARCHAR(200) | no |  |  |
| description | TEXT | no |  |  |
| level | VARCHAR(20) | no |  |  |
| status | VARCHAR(20) | no |  |  |
| tags | JSON | no |  |  |
| duration_hours | INTEGER | no |  |  |
| version | INTEGER | no |  |  |
| cover_color | VARCHAR(9) | no |  |  |
| updated_at | DATETIME | no |  |  |
| updated_by | CHAR(32) | sí |  | users.id |
| id | CHAR(32) | no | PK |  |
| created_at | DATETIME | no |  |  |

Restricciones CHECK: `level IN ('basico','intermedio','avanzado')`; `status IN ('draft','published','archived')`

Índices: `ix_courses_organization_id`

## `daily_metrics`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| organization_id | CHAR(32) | no | PK | organizations.id |
| day | DATE | no | PK |  |
| course_id | CHAR(32) | no | PK |  |
| region | VARCHAR(40) | no | PK |  |
| events | INTEGER | no |  |  |
| learning_seconds | BIGINT | no |  |  |
| active_students | INTEGER | no |  |  |
| assessments | INTEGER | no |  |  |
| completions | INTEGER | no |  |  |
| computed_at | DATETIME | no |  |  |

## `datasets`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| name | VARCHAR(120) | no |  |  |
| version | VARCHAR(40) | no |  |  |
| label | VARCHAR(20) | no |  |  |
| storage_uri | VARCHAR(400) | sí |  |  |
| checksum | VARCHAR(80) | sí |  |  |
| schema_version | VARCHAR(20) | no |  |  |
| status | VARCHAR(20) | no |  |  |
| quality | JSON | no |  |  |
| progress | JSON | no |  |  |
| created_by | CHAR(32) | sí |  | users.id |
| approved_by | CHAR(32) | sí |  | users.id |
| id | CHAR(32) | no | PK |  |
| created_at | DATETIME | no |  |  |

## `enrollments`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| offering_id | CHAR(32) | no |  | course_offerings.id |
| course_id | CHAR(32) | no |  | courses.id |
| student_id | CHAR(32) | no |  | students.id |
| organization_id | CHAR(32) | no |  | organizations.id |
| status | VARCHAR(20) | no |  |  |
| progress | FLOAT | no |  |  |
| enrolled_at | DATETIME | no |  |  |
| completed_at | DATETIME | sí |  |  |
| last_activity_at | DATETIME | sí |  |  |
| id | CHAR(32) | no | PK |  |

Restricciones CHECK: `progress >= 0 AND progress <= 1`

Índices: `ix_enrollments_course_id`, `ix_enrollments_offering_id`, `ix_enrollments_organization_id`, `ix_enroll_student_course`, `ix_enrollments_student_id`

## `instructors`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| user_id | CHAR(32) | no |  | users.id |
| organization_id | CHAR(32) | no |  | organizations.id |
| staff_code | VARCHAR(40) | no |  |  |
| id | CHAR(32) | no | PK |  |
| created_at | DATETIME | no |  |  |

Índices: `ix_instructors_organization_id`

## `learning_events`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| event_id | CHAR(32) | no | PK |  |
| organization_id | CHAR(32) | no |  | organizations.id |
| student_id | CHAR(32) | no |  | students.id |
| course_id | CHAR(32) | sí |  | courses.id |
| activity_id | VARCHAR(80) | sí |  |  |
| event_type | VARCHAR(40) | no |  |  |
| occurred_at | DATETIME | no |  |  |
| duration_seconds | INTEGER | no |  |  |
| payload | JSON | no |  |  |
| payload_schema_version | INTEGER | no |  |  |
| source | VARCHAR(20) | no |  |  |
| ingested_at | DATETIME | no |  |  |

Restricciones CHECK: `duration_seconds >= 0 AND duration_seconds <= 21600`

Índices: `ix_events_org_time`, `ix_events_student_course`

## `learning_paths`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| organization_id | CHAR(32) | no |  | organizations.id |
| title | VARCHAR(200) | no |  |  |
| objective | TEXT | no |  |  |
| competencies | JSON | no |  |  |
| duration_weeks | INTEGER | no |  |  |
| criteria | TEXT | no |  |  |
| version | INTEGER | no |  |  |
| status | VARCHAR(20) | no |  |  |
| id | CHAR(32) | no | PK |  |
| created_at | DATETIME | no |  |  |

Índices: `ix_learning_paths_organization_id`

## `lessons`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| unit_id | CHAR(32) | no |  | course_units.id |
| title | VARCHAR(200) | no |  |  |
| kind | VARCHAR(20) | no |  |  |
| resource_url | VARCHAR(500) | sí |  |  |
| duration_min | INTEGER | no |  |  |
| position | INTEGER | no |  |  |
| id | CHAR(32) | no | PK |  |

Índices: `ix_lessons_unit_id`

## `model_runs`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| network_key | VARCHAR(40) | no |  |  |
| experiment | VARCHAR(80) | no |  |  |
| dataset_version | VARCHAR(40) | no |  |  |
| params | JSON | no |  |  |
| metrics | JSON | no |  |  |
| history | JSON | no |  |  |
| progress | JSON | no |  |  |
| status | VARCHAR(20) | no |  |  |
| error | TEXT | sí |  |  |
| requested_by | CHAR(32) | sí |  | users.id |
| started_at | DATETIME | sí |  |  |
| finished_at | DATETIME | sí |  |  |
| id | CHAR(32) | no | PK |  |
| created_at | DATETIME | no |  |  |

Índices: `ix_model_runs_network_key`

## `model_versions`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| network_key | VARCHAR(40) | no |  |  |
| name | VARCHAR(120) | no |  |  |
| version | VARCHAR(40) | no |  |  |
| artifact_uri | VARCHAR(400) | no |  |  |
| checksum | VARCHAR(80) | sí |  |  |
| stage | VARCHAR(20) | no |  |  |
| approval_status | VARCHAR(20) | no |  |  |
| approved_by | CHAR(32) | sí |  | users.id |
| approved_at | DATETIME | sí |  |  |
| approval_note | TEXT | sí |  |  |
| beats_baseline | BOOLEAN | no |  |  |
| primary_metric | FLOAT | sí |  |  |
| baseline_metric | FLOAT | sí |  |  |
| metrics | JSON | no |  |  |
| dataset_version | VARCHAR(40) | sí |  |  |
| run_id | CHAR(32) | sí |  | model_runs.id |
| promoted_at | DATETIME | sí |  |  |
| id | CHAR(32) | no | PK |  |
| created_at | DATETIME | no |  |  |

Restricciones CHECK: `stage IN ('experimental','staging','production','archived')`

Índices: `ix_model_versions_network_key`

## `notification_preferences`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| user_id | CHAR(32) | no | PK | users.id |
| muted_types | JSON | no |  |  |
| muted_courses | JSON | no |  |  |

## `notifications`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| organization_id | CHAR(32) | no |  | organizations.id |
| user_id | CHAR(32) | no |  | users.id |
| type | VARCHAR(40) | no |  |  |
| title | VARCHAR(200) | no |  |  |
| body | TEXT | no |  |  |
| link | VARCHAR(300) | sí |  |  |
| read_at | DATETIME | sí |  |  |
| id | CHAR(32) | no | PK |  |
| created_at | DATETIME | no |  |  |

Índices: `ix_notifications_organization_id`, `ix_notif_user_read`

## `organizations`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| name | VARCHAR(200) | no |  |  |
| code | VARCHAR(40) | no |  |  |
| status | VARCHAR(20) | no |  |  |
| timezone | VARCHAR(64) | no |  |  |
| settings | JSON | no |  |  |
| id | CHAR(32) | no | PK |  |
| created_at | DATETIME | no |  |  |

## `outbox_events`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| seq | BIGINT | no | PK |  |
| event_id | CHAR(32) | no |  |  |
| event_type | VARCHAR(60) | no |  |  |
| occurred_at | DATETIME | no |  |  |
| organization_id | CHAR(32) | sí |  |  |
| actor_id | CHAR(32) | sí |  |  |
| aggregate_id | VARCHAR(80) | sí |  |  |
| schema_version | INTEGER | no |  |  |
| correlation_id | VARCHAR(64) | sí |  |  |
| payload | JSON | no |  |  |
| audience | JSON | no |  |  |
| published_at | DATETIME | sí |  |  |

Índices: `ix_outbox_org_seq`, `ix_outbox_unpublished`

## `path_assignments`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| path_id | CHAR(32) | no |  | learning_paths.id |
| student_id | CHAR(32) | sí |  | students.id |
| cohort_id | CHAR(32) | sí |  | cohorts.id |
| target_date | DATE | sí |  |  |
| status | VARCHAR(20) | no |  |  |
| exception_note | TEXT | sí |  |  |
| id | CHAR(32) | no | PK |  |
| created_at | DATETIME | no |  |  |

Índices: `ix_path_assignments_student_id`, `ix_path_assignments_path_id`

## `path_steps`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| path_id | CHAR(32) | no |  | learning_paths.id |
| course_id | CHAR(32) | no |  | courses.id |
| position | INTEGER | no |  |  |
| prerequisite_course_id | CHAR(32) | sí |  | courses.id |
| id | CHAR(32) | no | PK |  |

Índices: `ix_path_steps_path_id`

## `permissions`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| code | VARCHAR(60) | no |  |  |
| description | VARCHAR(200) | no |  |  |
| id | CHAR(32) | no | PK |  |

## `predictions`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| organization_id | CHAR(32) | no |  | organizations.id |
| student_id | CHAR(32) | sí |  | students.id |
| model_version_id | CHAR(32) | sí |  | model_versions.id |
| network_key | VARCHAR(40) | no |  |  |
| model_version | VARCHAR(40) | no |  |  |
| task | VARCHAR(40) | no |  |  |
| scores | JSON | no |  |  |
| explanation | JSON | no |  |  |
| latency_ms | FLOAT | sí |  |  |
| requested_by | CHAR(32) | sí |  | users.id |
| id | CHAR(32) | no | PK |  |
| created_at | DATETIME | no |  |  |

Índices: `ix_predictions_organization_id`, `ix_predictions_student_id`

## `recommendation_feedback`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| recommendation_id | CHAR(32) | no |  | recommendations.id |
| user_id | CHAR(32) | no |  | users.id |
| action | VARCHAR(20) | no |  |  |
| useful | BOOLEAN | sí |  |  |
| comment | TEXT | sí |  |  |
| id | CHAR(32) | no | PK |  |
| created_at | DATETIME | no |  |  |

Índices: `ix_recommendation_feedback_recommendation_id`

## `recommendations`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| organization_id | CHAR(32) | no |  | organizations.id |
| student_id | CHAR(32) | no |  | students.id |
| model_version | VARCHAR(60) | sí |  |  |
| type | VARCHAR(20) | no |  |  |
| action | VARCHAR(20) | no |  |  |
| title | VARCHAR(200) | no |  |  |
| rationale | JSON | no |  |  |
| impact | VARCHAR(20) | no |  |  |
| priority | FLOAT | no |  |  |
| confidence | FLOAT | sí |  |  |
| status | VARCHAR(20) | no |  |  |
| resource_code | VARCHAR(40) | sí |  |  |
| expires_at | DATETIME | sí |  |  |
| reviewed_by | CHAR(32) | sí |  | users.id |
| review_note | TEXT | sí |  |  |
| id | CHAR(32) | no | PK |  |
| created_at | DATETIME | no |  |  |

Índices: `ix_recommendations_organization_id`, `ix_recommendations_student_id`

## `role_permissions`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| role_id | CHAR(32) | no | PK | roles.id |
| permission_id | CHAR(32) | no | PK | permissions.id |

## `roles`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| code | VARCHAR(40) | no |  |  |
| name | VARCHAR(80) | no |  |  |
| description | VARCHAR(200) | no |  |  |
| id | CHAR(32) | no | PK |  |

## `skill_evidence`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| student_id | CHAR(32) | no |  | students.id |
| skill_id | CHAR(32) | no |  | skills.id |
| source_type | VARCHAR(20) | no |  |  |
| score | FLOAT | no |  |  |
| level | INTEGER | no |  |  |
| observed_at | DATETIME | no |  |  |
| validated_by | CHAR(32) | sí |  | users.id |
| model_version | VARCHAR(40) | sí |  |  |
| id | CHAR(32) | no | PK |  |

Restricciones CHECK: `score >= 0 AND score <= 1`

Índices: `ix_skill_evidence_student_id`, `ix_skill_evidence_skill_id`

## `skills`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| organization_id | CHAR(32) | no |  | organizations.id |
| code | VARCHAR(40) | no |  |  |
| name | VARCHAR(120) | no |  |  |
| parent_skill_id | CHAR(32) | sí |  | skills.id |
| color | VARCHAR(9) | no |  |  |
| id | CHAR(32) | no | PK |  |

Índices: `ix_skills_organization_id`

## `students`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| user_id | CHAR(32) | no |  | users.id |
| organization_id | CHAR(32) | no |  | organizations.id |
| external_code | VARCHAR(40) | no |  |  |
| enrollment_status | VARCHAR(20) | no |  |  |
| region | VARCHAR(40) | no |  |  |
| id | CHAR(32) | no | PK |  |
| created_at | DATETIME | no |  |  |

Índices: `ix_students_organization_id`

## `user_roles`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| user_id | CHAR(32) | no | PK | users.id |
| role_id | CHAR(32) | no | PK | roles.id |

## `users`

| Columna | Tipo | Nulo | Clave | Referencia |
|---|---|---|---|---|
| organization_id | CHAR(32) | no |  | organizations.id |
| email | VARCHAR(254) | no |  |  |
| full_name | VARCHAR(200) | no |  |  |
| password_hash | VARCHAR(200) | sí |  |  |
| status | VARCHAR(20) | no |  |  |
| avatar_url | VARCHAR(400) | sí |  |  |
| title | VARCHAR(80) | sí |  |  |
| last_login_at | DATETIME | sí |  |  |
| token_version | INTEGER | no |  |  |
| id | CHAR(32) | no | PK |  |
| created_at | DATETIME | no |  |  |

Índices: `ix_users_organization_id`
