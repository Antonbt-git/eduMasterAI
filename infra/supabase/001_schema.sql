BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001

CREATE TABLE audit_logs (
    id BIGSERIAL NOT NULL, 
    organization_id UUID, 
    actor_id UUID, 
    actor_email VARCHAR(254), 
    action VARCHAR(60) NOT NULL, 
    resource VARCHAR(60) NOT NULL, 
    resource_id VARCHAR(80), 
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    ip VARCHAR(64), 
    correlation_id VARCHAR(64), 
    details JSONB NOT NULL, 
    prev_hash VARCHAR(64), 
    hash VARCHAR(64) NOT NULL, 
    CONSTRAINT pk_audit_logs PRIMARY KEY (id)
);

CREATE INDEX ix_audit_org_time ON audit_logs (organization_id, occurred_at);

CREATE TABLE organizations (
    name VARCHAR(200) NOT NULL, 
    code VARCHAR(40) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    timezone VARCHAR(64) NOT NULL, 
    settings JSONB NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_organizations PRIMARY KEY (id), 
    CONSTRAINT uq_organizations_code UNIQUE (code)
);

CREATE TABLE outbox_events (
    seq BIGSERIAL NOT NULL, 
    event_id UUID NOT NULL, 
    event_type VARCHAR(60) NOT NULL, 
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    organization_id UUID, 
    actor_id UUID, 
    aggregate_id VARCHAR(80), 
    schema_version INTEGER NOT NULL, 
    correlation_id VARCHAR(64), 
    payload JSONB NOT NULL, 
    audience JSONB NOT NULL, 
    published_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_outbox_events PRIMARY KEY (seq), 
    CONSTRAINT uq_outbox_events_event_id UNIQUE (event_id)
);

CREATE INDEX ix_outbox_org_seq ON outbox_events (organization_id, seq);

CREATE INDEX ix_outbox_unpublished ON outbox_events (published_at);

CREATE TABLE permissions (
    code VARCHAR(60) NOT NULL, 
    description VARCHAR(200) NOT NULL, 
    id UUID NOT NULL, 
    CONSTRAINT pk_permissions PRIMARY KEY (id), 
    CONSTRAINT uq_permissions_code UNIQUE (code)
);

CREATE TABLE roles (
    code VARCHAR(40) NOT NULL, 
    name VARCHAR(80) NOT NULL, 
    description VARCHAR(200) NOT NULL, 
    id UUID NOT NULL, 
    CONSTRAINT pk_roles PRIMARY KEY (id), 
    CONSTRAINT uq_roles_code UNIQUE (code)
);

CREATE TABLE cohorts (
    organization_id UUID NOT NULL, 
    code VARCHAR(40) NOT NULL, 
    name VARCHAR(120) NOT NULL, 
    program VARCHAR(120) NOT NULL, 
    start_date DATE NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_cohorts PRIMARY KEY (id), 
    CONSTRAINT fk_cohorts_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
    CONSTRAINT uq_cohorts_organization_id UNIQUE (organization_id, code)
);

CREATE INDEX ix_cohorts_organization_id ON cohorts (organization_id);

CREATE TABLE daily_metrics (
    organization_id UUID NOT NULL, 
    day DATE NOT NULL, 
    course_id UUID NOT NULL, 
    region VARCHAR(40) NOT NULL, 
    events INTEGER NOT NULL, 
    learning_seconds BIGINT NOT NULL, 
    active_students INTEGER NOT NULL, 
    assessments INTEGER NOT NULL, 
    completions INTEGER NOT NULL, 
    computed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_daily_metrics PRIMARY KEY (organization_id, day, course_id, region), 
    CONSTRAINT fk_daily_metrics_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);

CREATE TABLE learning_paths (
    organization_id UUID NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    objective TEXT NOT NULL, 
    competencies JSONB NOT NULL, 
    duration_weeks INTEGER NOT NULL, 
    criteria TEXT NOT NULL, 
    version INTEGER NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_learning_paths PRIMARY KEY (id), 
    CONSTRAINT fk_learning_paths_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);

CREATE INDEX ix_learning_paths_organization_id ON learning_paths (organization_id);

CREATE TABLE role_permissions (
    role_id UUID NOT NULL, 
    permission_id UUID NOT NULL, 
    CONSTRAINT pk_role_permissions PRIMARY KEY (role_id, permission_id), 
    CONSTRAINT fk_role_permissions_permission_id_permissions FOREIGN KEY(permission_id) REFERENCES permissions (id) ON DELETE CASCADE, 
    CONSTRAINT fk_role_permissions_role_id_roles FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE
);

CREATE TABLE skills (
    organization_id UUID NOT NULL, 
    code VARCHAR(40) NOT NULL, 
    name VARCHAR(120) NOT NULL, 
    parent_skill_id UUID, 
    color VARCHAR(9) NOT NULL, 
    id UUID NOT NULL, 
    CONSTRAINT pk_skills PRIMARY KEY (id), 
    CONSTRAINT fk_skills_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
    CONSTRAINT fk_skills_parent_skill_id_skills FOREIGN KEY(parent_skill_id) REFERENCES skills (id) ON DELETE SET NULL, 
    CONSTRAINT uq_skills_organization_id UNIQUE (organization_id, code)
);

CREATE INDEX ix_skills_organization_id ON skills (organization_id);

CREATE TABLE users (
    organization_id UUID NOT NULL, 
    email VARCHAR(254) NOT NULL, 
    full_name VARCHAR(200) NOT NULL, 
    password_hash VARCHAR(200), 
    status VARCHAR(20) NOT NULL, 
    avatar_url VARCHAR(400), 
    title VARCHAR(80), 
    last_login_at TIMESTAMP WITH TIME ZONE, 
    token_version INTEGER NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_users PRIMARY KEY (id), 
    CONSTRAINT fk_users_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
    CONSTRAINT uq_users_org_email UNIQUE (organization_id, email)
);

CREATE INDEX ix_users_organization_id ON users (organization_id);

CREATE TABLE activities (
    organization_id UUID NOT NULL, 
    actor_id UUID, 
    subject_user_id UUID, 
    type VARCHAR(40) NOT NULL, 
    title VARCHAR(240) NOT NULL, 
    visibility VARCHAR(20) NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_activities PRIMARY KEY (id), 
    CONSTRAINT fk_activities_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT fk_activities_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
    CONSTRAINT fk_activities_subject_user_id_users FOREIGN KEY(subject_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_activities_subject_user_id ON activities (subject_user_id);

CREATE INDEX ix_activity_org_time ON activities (organization_id, created_at);

CREATE TABLE courses (
    organization_id UUID NOT NULL, 
    code VARCHAR(40) NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    description TEXT NOT NULL, 
    level VARCHAR(20) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    tags JSONB NOT NULL, 
    duration_hours INTEGER NOT NULL, 
    version INTEGER NOT NULL, 
    cover_color VARCHAR(9) NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_by UUID, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_courses PRIMARY KEY (id), 
    CONSTRAINT ck_courses_level_valid CHECK (level IN ('basico','intermedio','avanzado')), 
    CONSTRAINT ck_courses_status_valid CHECK (status IN ('draft','published','archived')), 
    CONSTRAINT fk_courses_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
    CONSTRAINT fk_courses_updated_by_users FOREIGN KEY(updated_by) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT uq_courses_org_code UNIQUE (organization_id, code)
);

CREATE INDEX ix_courses_organization_id ON courses (organization_id);

CREATE TABLE datasets (
    name VARCHAR(120) NOT NULL, 
    version VARCHAR(40) NOT NULL, 
    label VARCHAR(20) NOT NULL, 
    storage_uri VARCHAR(400), 
    checksum VARCHAR(80), 
    schema_version VARCHAR(20) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    quality JSONB NOT NULL, 
    progress JSONB NOT NULL, 
    created_by UUID, 
    approved_by UUID, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_datasets PRIMARY KEY (id), 
    CONSTRAINT fk_datasets_approved_by_users FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT fk_datasets_created_by_users FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT uq_datasets_name UNIQUE (name, version)
);

CREATE TABLE instructors (
    user_id UUID NOT NULL, 
    organization_id UUID NOT NULL, 
    staff_code VARCHAR(40) NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_instructors PRIMARY KEY (id), 
    CONSTRAINT fk_instructors_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
    CONSTRAINT fk_instructors_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_instructors_user_id UNIQUE (user_id)
);

CREATE INDEX ix_instructors_organization_id ON instructors (organization_id);

CREATE TABLE model_runs (
    network_key VARCHAR(40) NOT NULL, 
    experiment VARCHAR(80) NOT NULL, 
    dataset_version VARCHAR(40) NOT NULL, 
    params JSONB NOT NULL, 
    metrics JSONB NOT NULL, 
    history JSONB NOT NULL, 
    progress JSONB NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    error TEXT, 
    requested_by UUID, 
    started_at TIMESTAMP WITH TIME ZONE, 
    finished_at TIMESTAMP WITH TIME ZONE, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_model_runs PRIMARY KEY (id), 
    CONSTRAINT fk_model_runs_requested_by_users FOREIGN KEY(requested_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_model_runs_network_key ON model_runs (network_key);

CREATE TABLE notification_preferences (
    user_id UUID NOT NULL, 
    muted_types JSONB NOT NULL, 
    muted_courses JSONB NOT NULL, 
    CONSTRAINT pk_notification_preferences PRIMARY KEY (user_id), 
    CONSTRAINT fk_notification_preferences_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE notifications (
    organization_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    type VARCHAR(40) NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    body TEXT NOT NULL, 
    link VARCHAR(300), 
    read_at TIMESTAMP WITH TIME ZONE, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_notifications PRIMARY KEY (id), 
    CONSTRAINT fk_notifications_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
    CONSTRAINT fk_notifications_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_notif_user_read ON notifications (user_id, read_at);

CREATE INDEX ix_notifications_organization_id ON notifications (organization_id);

CREATE TABLE students (
    user_id UUID NOT NULL, 
    organization_id UUID NOT NULL, 
    external_code VARCHAR(40) NOT NULL, 
    enrollment_status VARCHAR(20) NOT NULL, 
    region VARCHAR(40) NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_students PRIMARY KEY (id), 
    CONSTRAINT fk_students_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
    CONSTRAINT fk_students_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_students_user_id UNIQUE (user_id)
);

CREATE INDEX ix_students_organization_id ON students (organization_id);

CREATE TABLE user_roles (
    user_id UUID NOT NULL, 
    role_id UUID NOT NULL, 
    CONSTRAINT pk_user_roles PRIMARY KEY (user_id, role_id), 
    CONSTRAINT fk_user_roles_role_id_roles FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE, 
    CONSTRAINT fk_user_roles_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE assessments (
    course_id UUID NOT NULL, 
    organization_id UUID NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    type VARCHAR(30) NOT NULL, 
    max_score FLOAT NOT NULL, 
    weight FLOAT NOT NULL, 
    due_at TIMESTAMP WITH TIME ZONE, 
    attempts_allowed INTEGER NOT NULL, 
    passing_score FLOAT NOT NULL, 
    grading_rule VARCHAR(20) NOT NULL, 
    instructions TEXT NOT NULL, 
    rubric JSONB NOT NULL, 
    questions JSONB NOT NULL, 
    skill_id UUID, 
    status VARCHAR(20) NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_assessments PRIMARY KEY (id), 
    CONSTRAINT ck_assessments_max_score_pos CHECK (max_score > 0), 
    CONSTRAINT fk_assessments_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE CASCADE, 
    CONSTRAINT fk_assessments_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
    CONSTRAINT fk_assessments_skill_id_skills FOREIGN KEY(skill_id) REFERENCES skills (id) ON DELETE SET NULL
);

CREATE INDEX ix_assessments_course_id ON assessments (course_id);

CREATE INDEX ix_assessments_organization_id ON assessments (organization_id);

CREATE TABLE certificates (
    organization_id UUID NOT NULL, 
    student_id UUID NOT NULL, 
    course_id UUID NOT NULL, 
    folio VARCHAR(40) NOT NULL, 
    verification_code VARCHAR(40) NOT NULL, 
    template VARCHAR(40) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    issued_at TIMESTAMP WITH TIME ZONE, 
    expires_at TIMESTAMP WITH TIME ZONE, 
    issued_by UUID, 
    revoked_reason TEXT, 
    final_score FLOAT, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_certificates PRIMARY KEY (id), 
    CONSTRAINT fk_certificates_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE CASCADE, 
    CONSTRAINT fk_certificates_issued_by_users FOREIGN KEY(issued_by) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT fk_certificates_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
    CONSTRAINT fk_certificates_student_id_students FOREIGN KEY(student_id) REFERENCES students (id) ON DELETE CASCADE, 
    CONSTRAINT uq_certificates_folio UNIQUE (folio), 
    CONSTRAINT uq_certificates_verification_code UNIQUE (verification_code)
);

CREATE INDEX ix_certificates_organization_id ON certificates (organization_id);

CREATE INDEX ix_certificates_student_id ON certificates (student_id);

CREATE TABLE community_threads (
    organization_id UUID NOT NULL, 
    course_id UUID, 
    author_id UUID NOT NULL, 
    kind VARCHAR(20) NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    body TEXT NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    pinned BOOLEAN NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_community_threads PRIMARY KEY (id), 
    CONSTRAINT fk_community_threads_author_id_users FOREIGN KEY(author_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT fk_community_threads_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE SET NULL, 
    CONSTRAINT fk_community_threads_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);

CREATE INDEX ix_community_threads_course_id ON community_threads (course_id);

CREATE INDEX ix_community_threads_organization_id ON community_threads (organization_id);

CREATE TABLE course_offerings (
    course_id UUID NOT NULL, 
    instructor_id UUID, 
    cohort_id UUID, 
    period VARCHAR(20) NOT NULL, 
    starts_at DATE, 
    ends_at DATE, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_course_offerings PRIMARY KEY (id), 
    CONSTRAINT fk_course_offerings_cohort_id_cohorts FOREIGN KEY(cohort_id) REFERENCES cohorts (id) ON DELETE SET NULL, 
    CONSTRAINT fk_course_offerings_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE CASCADE, 
    CONSTRAINT fk_course_offerings_instructor_id_instructors FOREIGN KEY(instructor_id) REFERENCES instructors (id) ON DELETE SET NULL
);

CREATE INDEX ix_course_offerings_course_id ON course_offerings (course_id);

CREATE INDEX ix_course_offerings_instructor_id ON course_offerings (instructor_id);

CREATE INDEX ix_offering_course_period ON course_offerings (course_id, period);

CREATE TABLE course_skills (
    course_id UUID NOT NULL, 
    skill_id UUID NOT NULL, 
    weight FLOAT NOT NULL, 
    CONSTRAINT pk_course_skills PRIMARY KEY (course_id, skill_id), 
    CONSTRAINT fk_course_skills_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE CASCADE, 
    CONSTRAINT fk_course_skills_skill_id_skills FOREIGN KEY(skill_id) REFERENCES skills (id) ON DELETE CASCADE
);

CREATE TABLE course_units (
    course_id UUID NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    position INTEGER NOT NULL, 
    id UUID NOT NULL, 
    CONSTRAINT pk_course_units PRIMARY KEY (id), 
    CONSTRAINT fk_course_units_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE CASCADE
);

CREATE INDEX ix_course_units_course_id ON course_units (course_id);

CREATE TABLE learning_events (
    event_id UUID NOT NULL, 
    organization_id UUID NOT NULL, 
    student_id UUID NOT NULL, 
    course_id UUID, 
    activity_id VARCHAR(80), 
    event_type VARCHAR(40) NOT NULL, 
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    duration_seconds INTEGER NOT NULL, 
    payload JSONB NOT NULL, 
    payload_schema_version INTEGER NOT NULL, 
    source VARCHAR(20) NOT NULL, 
    ingested_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_learning_events PRIMARY KEY (event_id), 
    CONSTRAINT ck_learning_events_duration_range CHECK (duration_seconds >= 0 AND duration_seconds <= 21600), 
    CONSTRAINT fk_learning_events_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE SET NULL, 
    CONSTRAINT fk_learning_events_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
    CONSTRAINT fk_learning_events_student_id_students FOREIGN KEY(student_id) REFERENCES students (id) ON DELETE CASCADE
);

CREATE INDEX ix_events_org_time ON learning_events (organization_id, occurred_at);

CREATE INDEX ix_events_student_course ON learning_events (student_id, course_id);

CREATE TABLE model_versions (
    network_key VARCHAR(40) NOT NULL, 
    name VARCHAR(120) NOT NULL, 
    version VARCHAR(40) NOT NULL, 
    artifact_uri VARCHAR(400) NOT NULL, 
    checksum VARCHAR(80), 
    stage VARCHAR(20) NOT NULL, 
    approval_status VARCHAR(20) NOT NULL, 
    approved_by UUID, 
    approved_at TIMESTAMP WITH TIME ZONE, 
    approval_note TEXT, 
    beats_baseline BOOLEAN NOT NULL, 
    primary_metric FLOAT, 
    baseline_metric FLOAT, 
    metrics JSONB NOT NULL, 
    dataset_version VARCHAR(40), 
    run_id UUID, 
    promoted_at TIMESTAMP WITH TIME ZONE, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_model_versions PRIMARY KEY (id), 
    CONSTRAINT ck_model_versions_stage_valid CHECK (stage IN ('experimental','staging','production','archived')), 
    CONSTRAINT fk_model_versions_approved_by_users FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT fk_model_versions_run_id_model_runs FOREIGN KEY(run_id) REFERENCES model_runs (id) ON DELETE SET NULL, 
    CONSTRAINT uq_model_versions_network_key UNIQUE (network_key, version)
);

CREATE INDEX ix_model_versions_network_key ON model_versions (network_key);

CREATE TABLE path_assignments (
    path_id UUID NOT NULL, 
    student_id UUID, 
    cohort_id UUID, 
    target_date DATE, 
    status VARCHAR(20) NOT NULL, 
    exception_note TEXT, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_path_assignments PRIMARY KEY (id), 
    CONSTRAINT fk_path_assignments_cohort_id_cohorts FOREIGN KEY(cohort_id) REFERENCES cohorts (id) ON DELETE CASCADE, 
    CONSTRAINT fk_path_assignments_path_id_learning_paths FOREIGN KEY(path_id) REFERENCES learning_paths (id) ON DELETE CASCADE, 
    CONSTRAINT fk_path_assignments_student_id_students FOREIGN KEY(student_id) REFERENCES students (id) ON DELETE CASCADE
);

CREATE INDEX ix_path_assignments_path_id ON path_assignments (path_id);

CREATE INDEX ix_path_assignments_student_id ON path_assignments (student_id);

CREATE TABLE path_steps (
    path_id UUID NOT NULL, 
    course_id UUID NOT NULL, 
    position INTEGER NOT NULL, 
    prerequisite_course_id UUID, 
    id UUID NOT NULL, 
    CONSTRAINT pk_path_steps PRIMARY KEY (id), 
    CONSTRAINT fk_path_steps_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE CASCADE, 
    CONSTRAINT fk_path_steps_path_id_learning_paths FOREIGN KEY(path_id) REFERENCES learning_paths (id) ON DELETE CASCADE, 
    CONSTRAINT fk_path_steps_prerequisite_course_id_courses FOREIGN KEY(prerequisite_course_id) REFERENCES courses (id) ON DELETE SET NULL
);

CREATE INDEX ix_path_steps_path_id ON path_steps (path_id);

CREATE TABLE recommendations (
    organization_id UUID NOT NULL, 
    student_id UUID NOT NULL, 
    model_version VARCHAR(60), 
    type VARCHAR(20) NOT NULL, 
    action VARCHAR(20) NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    rationale JSONB NOT NULL, 
    impact VARCHAR(20) NOT NULL, 
    priority FLOAT NOT NULL, 
    confidence FLOAT, 
    status VARCHAR(20) NOT NULL, 
    resource_code VARCHAR(40), 
    expires_at TIMESTAMP WITH TIME ZONE, 
    reviewed_by UUID, 
    review_note TEXT, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_recommendations PRIMARY KEY (id), 
    CONSTRAINT fk_recommendations_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
    CONSTRAINT fk_recommendations_reviewed_by_users FOREIGN KEY(reviewed_by) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT fk_recommendations_student_id_students FOREIGN KEY(student_id) REFERENCES students (id) ON DELETE CASCADE
);

CREATE INDEX ix_recommendations_organization_id ON recommendations (organization_id);

CREATE INDEX ix_recommendations_student_id ON recommendations (student_id);

CREATE TABLE skill_evidence (
    student_id UUID NOT NULL, 
    skill_id UUID NOT NULL, 
    source_type VARCHAR(20) NOT NULL, 
    score FLOAT NOT NULL, 
    level INTEGER NOT NULL, 
    observed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    validated_by UUID, 
    model_version VARCHAR(40), 
    id UUID NOT NULL, 
    CONSTRAINT pk_skill_evidence PRIMARY KEY (id), 
    CONSTRAINT ck_skill_evidence_score_range CHECK (score >= 0 AND score <= 1), 
    CONSTRAINT fk_skill_evidence_skill_id_skills FOREIGN KEY(skill_id) REFERENCES skills (id) ON DELETE CASCADE, 
    CONSTRAINT fk_skill_evidence_student_id_students FOREIGN KEY(student_id) REFERENCES students (id) ON DELETE CASCADE, 
    CONSTRAINT fk_skill_evidence_validated_by_users FOREIGN KEY(validated_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_skill_evidence_skill_id ON skill_evidence (skill_id);

CREATE INDEX ix_skill_evidence_student_id ON skill_evidence (student_id);

CREATE TABLE assessment_attempts (
    assessment_id UUID NOT NULL, 
    student_id UUID NOT NULL, 
    answers JSONB NOT NULL, 
    score FLOAT, 
    late BOOLEAN NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    feedback TEXT, 
    graded_by UUID, 
    submitted_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id UUID NOT NULL, 
    CONSTRAINT pk_assessment_attempts PRIMARY KEY (id), 
    CONSTRAINT fk_assessment_attempts_assessment_id_assessments FOREIGN KEY(assessment_id) REFERENCES assessments (id) ON DELETE CASCADE, 
    CONSTRAINT fk_assessment_attempts_graded_by_users FOREIGN KEY(graded_by) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT fk_assessment_attempts_student_id_students FOREIGN KEY(student_id) REFERENCES students (id) ON DELETE CASCADE
);

CREATE INDEX ix_assessment_attempts_assessment_id ON assessment_attempts (assessment_id);

CREATE INDEX ix_assessment_attempts_student_id ON assessment_attempts (student_id);

CREATE INDEX ix_attempt_student_assessment ON assessment_attempts (student_id, assessment_id);

CREATE TABLE community_posts (
    thread_id UUID NOT NULL, 
    author_id UUID NOT NULL, 
    body TEXT NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_community_posts PRIMARY KEY (id), 
    CONSTRAINT fk_community_posts_author_id_users FOREIGN KEY(author_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT fk_community_posts_thread_id_community_threads FOREIGN KEY(thread_id) REFERENCES community_threads (id) ON DELETE CASCADE
);

CREATE INDEX ix_community_posts_thread_id ON community_posts (thread_id);

CREATE TABLE enrollments (
    offering_id UUID NOT NULL, 
    course_id UUID NOT NULL, 
    student_id UUID NOT NULL, 
    organization_id UUID NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    progress FLOAT NOT NULL, 
    enrolled_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    last_activity_at TIMESTAMP WITH TIME ZONE, 
    id UUID NOT NULL, 
    CONSTRAINT pk_enrollments PRIMARY KEY (id), 
    CONSTRAINT ck_enrollments_progress_range CHECK (progress >= 0 AND progress <= 1), 
    CONSTRAINT fk_enrollments_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE CASCADE, 
    CONSTRAINT fk_enrollments_offering_id_course_offerings FOREIGN KEY(offering_id) REFERENCES course_offerings (id) ON DELETE CASCADE, 
    CONSTRAINT fk_enrollments_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
    CONSTRAINT fk_enrollments_student_id_students FOREIGN KEY(student_id) REFERENCES students (id) ON DELETE CASCADE, 
    CONSTRAINT uq_enrollments_offering_id UNIQUE (offering_id, student_id)
);

CREATE INDEX ix_enroll_student_course ON enrollments (student_id, course_id);

CREATE INDEX ix_enrollments_course_id ON enrollments (course_id);

CREATE INDEX ix_enrollments_offering_id ON enrollments (offering_id);

CREATE INDEX ix_enrollments_organization_id ON enrollments (organization_id);

CREATE INDEX ix_enrollments_student_id ON enrollments (student_id);

CREATE TABLE lessons (
    unit_id UUID NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    kind VARCHAR(20) NOT NULL, 
    resource_url VARCHAR(500), 
    duration_min INTEGER NOT NULL, 
    position INTEGER NOT NULL, 
    id UUID NOT NULL, 
    CONSTRAINT pk_lessons PRIMARY KEY (id), 
    CONSTRAINT fk_lessons_unit_id_course_units FOREIGN KEY(unit_id) REFERENCES course_units (id) ON DELETE CASCADE
);

CREATE INDEX ix_lessons_unit_id ON lessons (unit_id);

CREATE TABLE predictions (
    organization_id UUID NOT NULL, 
    student_id UUID, 
    model_version_id UUID, 
    network_key VARCHAR(40) NOT NULL, 
    model_version VARCHAR(40) NOT NULL, 
    task VARCHAR(40) NOT NULL, 
    scores JSONB NOT NULL, 
    explanation JSONB NOT NULL, 
    latency_ms FLOAT, 
    requested_by UUID, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_predictions PRIMARY KEY (id), 
    CONSTRAINT fk_predictions_model_version_id_model_versions FOREIGN KEY(model_version_id) REFERENCES model_versions (id) ON DELETE SET NULL, 
    CONSTRAINT fk_predictions_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
    CONSTRAINT fk_predictions_requested_by_users FOREIGN KEY(requested_by) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT fk_predictions_student_id_students FOREIGN KEY(student_id) REFERENCES students (id) ON DELETE SET NULL
);

CREATE INDEX ix_predictions_organization_id ON predictions (organization_id);

CREATE INDEX ix_predictions_student_id ON predictions (student_id);

CREATE TABLE recommendation_feedback (
    recommendation_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    action VARCHAR(20) NOT NULL, 
    useful BOOLEAN, 
    comment TEXT, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_recommendation_feedback PRIMARY KEY (id), 
    CONSTRAINT fk_recommendation_feedback_recommendation_id_recommendations FOREIGN KEY(recommendation_id) REFERENCES recommendations (id) ON DELETE CASCADE, 
    CONSTRAINT fk_recommendation_feedback_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_recommendation_feedback_recommendation_id ON recommendation_feedback (recommendation_id);

CREATE TABLE content_reports (
    organization_id UUID NOT NULL, 
    thread_id UUID, 
    post_id UUID, 
    reporter_id UUID NOT NULL, 
    reason VARCHAR(300) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    resolved_by UUID, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_content_reports PRIMARY KEY (id), 
    CONSTRAINT fk_content_reports_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE, 
    CONSTRAINT fk_content_reports_post_id_community_posts FOREIGN KEY(post_id) REFERENCES community_posts (id) ON DELETE CASCADE, 
    CONSTRAINT fk_content_reports_reporter_id_users FOREIGN KEY(reporter_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT fk_content_reports_resolved_by_users FOREIGN KEY(resolved_by) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT fk_content_reports_thread_id_community_threads FOREIGN KEY(thread_id) REFERENCES community_threads (id) ON DELETE CASCADE
);

CREATE INDEX ix_content_reports_organization_id ON content_reports (organization_id);

INSERT INTO alembic_version (version_num) VALUES ('0001') RETURNING alembic_version.version_num;

COMMIT;

