"""Modelo de datos (documento maestro §7). UUID internos, organization_id en entidades
multi-institución, FKs, CHECK, índices compuestos y timestamps UTC."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, JSONType, Timestamps, UUIDPk, utcnow

FK = lambda t, **kw: ForeignKey(f"{t}.id", ondelete=kw.pop("ondelete", "CASCADE"), **kw)  # noqa: E731

# --------------------------------------------------------------------------- Identity & Access
role_permissions = Table(
    "role_permissions", Base.metadata,
    Column("role_id", Uuid, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Uuid, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)
user_roles = Table(
    "user_roles", Base.metadata,
    Column("user_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Uuid, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class Organization(UUIDPk, Timestamps, Base):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(40), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    timezone: Mapped[str] = mapped_column(String(64), default="America/Lima")
    settings: Mapped[dict] = mapped_column(JSONType, default=dict)


class Permission(UUIDPk, Base):
    __tablename__ = "permissions"
    code: Mapped[str] = mapped_column(String(60), unique=True)
    description: Mapped[str] = mapped_column(String(200), default="")


class Role(UUIDPk, Base):
    __tablename__ = "roles"
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(200), default="")
    permissions: Mapped[list[Permission]] = relationship(secondary=role_permissions, lazy="selectin")


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("organization_id", "email", name="uq_users_org_email"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(FK("organizations"), index=True)
    email: Mapped[str] = mapped_column(String(254))
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="active")
    avatar_url: Mapped[str | None] = mapped_column(String(400))
    title: Mapped[str | None] = mapped_column(String(80))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    roles: Mapped[list[Role]] = relationship(secondary=user_roles, lazy="selectin")
    organization: Mapped[Organization] = relationship(lazy="joined")


class Student(UUIDPk, Timestamps, Base):
    __tablename__ = "students"
    user_id: Mapped[uuid.UUID] = mapped_column(FK("users"), unique=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(FK("organizations"), index=True)
    external_code: Mapped[str] = mapped_column(String(40))
    enrollment_status: Mapped[str] = mapped_column(String(20), default="active")
    region: Mapped[str] = mapped_column(String(40), default="América del Sur")
    user: Mapped[User] = relationship(lazy="joined")


class Instructor(UUIDPk, Timestamps, Base):
    __tablename__ = "instructors"
    user_id: Mapped[uuid.UUID] = mapped_column(FK("users"), unique=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(FK("organizations"), index=True)
    staff_code: Mapped[str] = mapped_column(String(40))
    user: Mapped[User] = relationship(lazy="joined")


# --------------------------------------------------------------------------- Academic Core
class Cohort(UUIDPk, Timestamps, Base):
    __tablename__ = "cohorts"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(FK("organizations"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    program: Mapped[str] = mapped_column(String(120), default="General")
    start_date: Mapped[date] = mapped_column(Date)


class Skill(UUIDPk, Base):
    __tablename__ = "skills"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(FK("organizations"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    parent_skill_id: Mapped[uuid.UUID | None] = mapped_column(FK("skills", ondelete="SET NULL"))
    color: Mapped[str] = mapped_column(String(9), default="#20C8F5")


class Course(UUIDPk, Timestamps, Base):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_courses_org_code"),
        CheckConstraint("level IN ('basico','intermedio','avanzado')", name="level_valid"),
        CheckConstraint("status IN ('draft','published','archived')", name="status_valid"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(FK("organizations"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    level: Mapped[str] = mapped_column(String(20), default="basico")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    tags: Mapped[list] = mapped_column(JSONType, default=list)
    duration_hours: Mapped[int] = mapped_column(Integer, default=20)
    version: Mapped[int] = mapped_column(Integer, default=1)
    cover_color: Mapped[str] = mapped_column(String(9), default="#087FE5")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(FK("users", ondelete="SET NULL"))
    skills: Mapped[list["CourseSkill"]] = relationship(lazy="selectin", cascade="all, delete-orphan")
    units: Mapped[list["CourseUnit"]] = relationship(lazy="selectin", cascade="all, delete-orphan", order_by="CourseUnit.position")


class CourseSkill(Base):
    __tablename__ = "course_skills"
    course_id: Mapped[uuid.UUID] = mapped_column(FK("courses"), primary_key=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(FK("skills"), primary_key=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    skill: Mapped[Skill] = relationship(lazy="joined")


class CourseUnit(UUIDPk, Base):
    __tablename__ = "course_units"
    course_id: Mapped[uuid.UUID] = mapped_column(FK("courses"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer, default=0)
    lessons: Mapped[list["Lesson"]] = relationship(lazy="selectin", cascade="all, delete-orphan", order_by="Lesson.position")


class Lesson(UUIDPk, Base):
    __tablename__ = "lessons"
    unit_id: Mapped[uuid.UUID] = mapped_column(FK("course_units"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20), default="lesson")  # lesson|resource|link|file|activity
    resource_url: Mapped[str | None] = mapped_column(String(500))
    duration_min: Mapped[int] = mapped_column(Integer, default=15)
    position: Mapped[int] = mapped_column(Integer, default=0)


class CourseOffering(UUIDPk, Timestamps, Base):
    __tablename__ = "course_offerings"
    __table_args__ = (Index("ix_offering_course_period", "course_id", "period"),)
    course_id: Mapped[uuid.UUID] = mapped_column(FK("courses"), index=True)
    instructor_id: Mapped[uuid.UUID | None] = mapped_column(FK("instructors", ondelete="SET NULL"), index=True)
    cohort_id: Mapped[uuid.UUID | None] = mapped_column(FK("cohorts", ondelete="SET NULL"))
    period: Mapped[str] = mapped_column(String(20))
    starts_at: Mapped[date | None] = mapped_column(Date)
    ends_at: Mapped[date | None] = mapped_column(Date)
    course: Mapped[Course] = relationship(lazy="joined")


class Enrollment(UUIDPk, Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("offering_id", "student_id"),
        Index("ix_enroll_student_course", "student_id", "course_id"),
        CheckConstraint("progress >= 0 AND progress <= 1", name="progress_range"),
    )
    offering_id: Mapped[uuid.UUID] = mapped_column(FK("course_offerings"), index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(FK("courses"), index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(FK("students"), index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(FK("organizations"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")  # not_started|in_progress|completed|dropped
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LearningPath(UUIDPk, Timestamps, Base):
    __tablename__ = "learning_paths"
    organization_id: Mapped[uuid.UUID] = mapped_column(FK("organizations"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    objective: Mapped[str] = mapped_column(Text, default="")
    competencies: Mapped[list] = mapped_column(JSONType, default=list)
    duration_weeks: Mapped[int] = mapped_column(Integer, default=12)
    criteria: Mapped[str] = mapped_column(Text, default="Completar todos los cursos con nota ≥ 70")
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    steps: Mapped[list["PathStep"]] = relationship(lazy="selectin", cascade="all, delete-orphan", order_by="PathStep.position")


class PathStep(UUIDPk, Base):
    __tablename__ = "path_steps"
    path_id: Mapped[uuid.UUID] = mapped_column(FK("learning_paths"), index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(FK("courses"))
    position: Mapped[int] = mapped_column(Integer)
    prerequisite_course_id: Mapped[uuid.UUID | None] = mapped_column(FK("courses", ondelete="SET NULL"))
    course: Mapped[Course] = relationship(lazy="joined", foreign_keys=[course_id])


class PathAssignment(UUIDPk, Timestamps, Base):
    __tablename__ = "path_assignments"
    path_id: Mapped[uuid.UUID] = mapped_column(FK("learning_paths"), index=True)
    student_id: Mapped[uuid.UUID | None] = mapped_column(FK("students"), index=True)
    cohort_id: Mapped[uuid.UUID | None] = mapped_column(FK("cohorts"))
    target_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="active")
    exception_note: Mapped[str | None] = mapped_column(Text)


# --------------------------------------------------------------------------- Learning Tracking
class LearningEvent(Base):
    __tablename__ = "learning_events"
    __table_args__ = (
        Index("ix_events_org_time", "organization_id", "occurred_at"),
        Index("ix_events_student_course", "student_id", "course_id"),
        CheckConstraint("duration_seconds >= 0 AND duration_seconds <= 21600", name="duration_range"),
    )
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)  # idempotencia
    organization_id: Mapped[uuid.UUID] = mapped_column(FK("organizations"))
    student_id: Mapped[uuid.UUID] = mapped_column(FK("students"))
    course_id: Mapped[uuid.UUID | None] = mapped_column(FK("courses", ondelete="SET NULL"))
    activity_id: Mapped[str | None] = mapped_column(String(80))
    event_type: Mapped[str] = mapped_column(String(40))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    payload_schema_version: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[str] = mapped_column(String(20), default="web")
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DailyMetric(Base):
    """Agregado analítico (no se recalcula sobre OLTP en cada carga del dashboard)."""
    __tablename__ = "daily_metrics"
    organization_id: Mapped[uuid.UUID] = mapped_column(FK("organizations"), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    course_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    region: Mapped[str] = mapped_column(String(40), primary_key=True)
    events: Mapped[int] = mapped_column(Integer, default=0)
    learning_seconds: Mapped[int] = mapped_column(BigInteger, default=0)
    active_students: Mapped[int] = mapped_column(Integer, default=0)
    assessments: Mapped[int] = mapped_column(Integer, default=0)
    completions: Mapped[int] = mapped_column(Integer, default=0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Assessment(UUIDPk, Timestamps, Base):
    __tablename__ = "assessments"
    __table_args__ = (CheckConstraint("max_score > 0", name="max_score_pos"),)
    course_id: Mapped[uuid.UUID] = mapped_column(FK("courses"), index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(FK("organizations"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(30), default="multiple_choice")  # multiple_choice|true_false|short_answer|file|practice
    max_score: Mapped[float] = mapped_column(Float, default=100)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts_allowed: Mapped[int] = mapped_column(Integer, default=2)
    passing_score: Mapped[float] = mapped_column(Float, default=70)
    grading_rule: Mapped[str] = mapped_column(String(20), default="best")  # best|last|average
    instructions: Mapped[str] = mapped_column(Text, default="")
    rubric: Mapped[list] = mapped_column(JSONType, default=list)
    questions: Mapped[list] = mapped_column(JSONType, default=list)
    skill_id: Mapped[uuid.UUID | None] = mapped_column(FK("skills", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), default="published")


class AssessmentAttempt(UUIDPk, Base):
    __tablename__ = "assessment_attempts"
    __table_args__ = (Index("ix_attempt_student_assessment", "student_id", "assessment_id"),)
    assessment_id: Mapped[uuid.UUID] = mapped_column(FK("assessments"), index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(FK("students"), index=True)
    answers: Mapped[dict] = mapped_column(JSONType, default=dict)
    score: Mapped[float | None] = mapped_column(Float)
    late: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="graded")  # submitted|graded
    feedback: Mapped[str | None] = mapped_column(Text)
    graded_by: Mapped[uuid.UUID | None] = mapped_column(FK("users", ondelete="SET NULL"))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SkillEvidence(UUIDPk, Base):
    __tablename__ = "skill_evidence"
    __table_args__ = (CheckConstraint("score >= 0 AND score <= 1", name="score_range"),)
    student_id: Mapped[uuid.UUID] = mapped_column(FK("students"), index=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(FK("skills"), index=True)
    source_type: Mapped[str] = mapped_column(String(20))  # assessment | ai_estimate | instructor
    score: Mapped[float] = mapped_column(Float)
    level: Mapped[int] = mapped_column(Integer)  # 0..4
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    validated_by: Mapped[uuid.UUID | None] = mapped_column(FK("users", ondelete="SET NULL"))
    model_version: Mapped[str | None] = mapped_column(String(40))


# --------------------------------------------------------------------------- Recommendation
class Recommendation(UUIDPk, Timestamps, Base):
    __tablename__ = "recommendations"
    organization_id: Mapped[uuid.UUID] = mapped_column(FK("organizations"), index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(FK("students"), index=True)
    model_version: Mapped[str | None] = mapped_column(String(60))
    type: Mapped[str] = mapped_column(String(20), default="resource")  # resource|activity|path|review
    action: Mapped[str] = mapped_column(String(20), default="Repasa")
    title: Mapped[str] = mapped_column(String(200))
    rationale: Mapped[dict] = mapped_column(JSONType, default=dict)
    impact: Mapped[str] = mapped_column(String(20), default="medio")
    priority: Mapped[float] = mapped_column(Float, default=0.5)
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="new")  # new|accepted|dismissed|completed|expired
    resource_code: Mapped[str | None] = mapped_column(String(40))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(FK("users", ondelete="SET NULL"))
    review_note: Mapped[str | None] = mapped_column(Text)


class RecommendationFeedback(UUIDPk, Timestamps, Base):
    __tablename__ = "recommendation_feedback"
    recommendation_id: Mapped[uuid.UUID] = mapped_column(FK("recommendations"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(FK("users"))
    action: Mapped[str] = mapped_column(String(20))  # accepted|dismissed|completed|useful|not_useful
    useful: Mapped[bool | None] = mapped_column(Boolean)
    comment: Mapped[str | None] = mapped_column(Text)


# --------------------------------------------------------------------------- Certification
class Certificate(UUIDPk, Timestamps, Base):
    __tablename__ = "certificates"
    __table_args__ = (UniqueConstraint("folio"), UniqueConstraint("verification_code"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(FK("organizations"), index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(FK("students"), index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(FK("courses"))
    folio: Mapped[str] = mapped_column(String(40))
    verification_code: Mapped[str] = mapped_column(String(40))
    template: Mapped[str] = mapped_column(String(40), default="neon")
    status: Mapped[str] = mapped_column(String(20), default="issued")  # draft|issued|revoked|expired
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    issued_by: Mapped[uuid.UUID | None] = mapped_column(FK("users", ondelete="SET NULL"))
    revoked_reason: Mapped[str | None] = mapped_column(Text)
    final_score: Mapped[float | None] = mapped_column(Float)


# --------------------------------------------------------------------------- Notification / activity
class Notification(UUIDPk, Timestamps, Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notif_user_read", "user_id", "read_at"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(FK("organizations"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(FK("users"))
    type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str | None] = mapped_column(String(300))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    user_id: Mapped[uuid.UUID] = mapped_column(FK("users"), primary_key=True)
    muted_types: Mapped[list] = mapped_column(JSONType, default=list)
    muted_courses: Mapped[list] = mapped_column(JSONType, default=list)


class Activity(UUIDPk, Timestamps, Base):
    """Feed de actividad reciente (por usuario e institución)."""
    __tablename__ = "activities"
    __table_args__ = (Index("ix_activity_org_time", "organization_id", "created_at"),)
    organization_id: Mapped[uuid.UUID] = mapped_column(FK("organizations"))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(FK("users", ondelete="SET NULL"))
    subject_user_id: Mapped[uuid.UUID | None] = mapped_column(FK("users", ondelete="SET NULL"), index=True)
    type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(240))
    visibility: Mapped[str] = mapped_column(String(20), default="staff")  # staff|subject|org


# --------------------------------------------------------------------------- Community
class CommunityThread(UUIDPk, Timestamps, Base):
    __tablename__ = "community_threads"
    organization_id: Mapped[uuid.UUID] = mapped_column(FK("organizations"), index=True)
    course_id: Mapped[uuid.UUID | None] = mapped_column(FK("courses", ondelete="SET NULL"), index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(FK("users"))
    kind: Mapped[str] = mapped_column(String(20), default="discussion")  # announcement|discussion
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="visible")  # visible|hidden|pending
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    author: Mapped[User] = relationship(lazy="joined")


class CommunityPost(UUIDPk, Timestamps, Base):
    __tablename__ = "community_posts"
    thread_id: Mapped[uuid.UUID] = mapped_column(FK("community_threads"), index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(FK("users"))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="visible")
    author: Mapped[User] = relationship(lazy="joined")


class ContentReport(UUIDPk, Timestamps, Base):
    __tablename__ = "content_reports"
    organization_id: Mapped[uuid.UUID] = mapped_column(FK("organizations"), index=True)
    thread_id: Mapped[uuid.UUID | None] = mapped_column(FK("community_threads"))
    post_id: Mapped[uuid.UUID | None] = mapped_column(FK("community_posts"))
    reporter_id: Mapped[uuid.UUID] = mapped_column(FK("users"))
    reason: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|resolved|dismissed
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(FK("users", ondelete="SET NULL"))


# --------------------------------------------------------------------------- AI Platform
class Dataset(UUIDPk, Timestamps, Base):
    __tablename__ = "datasets"
    __table_args__ = (UniqueConstraint("name", "version"),)
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(20), default="DEMO")
    storage_uri: Mapped[str | None] = mapped_column(String(400))
    checksum: Mapped[str | None] = mapped_column(String(80))
    schema_version: Mapped[str] = mapped_column(String(20), default="1.0")
    status: Mapped[str] = mapped_column(String(20), default="building")  # building|ready|approved|failed
    quality: Mapped[dict] = mapped_column(JSONType, default=dict)
    progress: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(FK("users", ondelete="SET NULL"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(FK("users", ondelete="SET NULL"))


class ModelRun(UUIDPk, Timestamps, Base):
    __tablename__ = "model_runs"
    # NULL = ejecución de plataforma (DEMO/bootstrap), visible para todas las instituciones.
    organization_id: Mapped[uuid.UUID | None] = mapped_column(FK("organizations"), index=True)
    network_key: Mapped[str] = mapped_column(String(40), index=True)
    experiment: Mapped[str] = mapped_column(String(80))
    dataset_version: Mapped[str] = mapped_column(String(40))
    params: Mapped[dict] = mapped_column(JSONType, default=dict)
    metrics: Mapped[dict] = mapped_column(JSONType, default=dict)
    history: Mapped[list] = mapped_column(JSONType, default=list)
    progress: Mapped[dict] = mapped_column(JSONType, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|loading_data|training|validating|completed|failed
    error: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(FK("users", ondelete="SET NULL"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ModelVersion(UUIDPk, Timestamps, Base):
    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("network_key", "version"),
                      CheckConstraint("stage IN ('experimental','staging','production','archived')", name="stage_valid"))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(FK("organizations"), index=True)
    network_key: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[str] = mapped_column(String(40))
    artifact_uri: Mapped[str] = mapped_column(String(400))
    checksum: Mapped[str | None] = mapped_column(String(80))
    stage: Mapped[str] = mapped_column(String(20), default="experimental")
    approval_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|rejected
    approved_by: Mapped[uuid.UUID | None] = mapped_column(FK("users", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approval_note: Mapped[str | None] = mapped_column(Text)
    beats_baseline: Mapped[bool] = mapped_column(Boolean, default=False)
    primary_metric: Mapped[float | None] = mapped_column(Float)
    baseline_metric: Mapped[float | None] = mapped_column(Float)
    metrics: Mapped[dict] = mapped_column(JSONType, default=dict)
    dataset_version: Mapped[str | None] = mapped_column(String(40))
    run_id: Mapped[uuid.UUID | None] = mapped_column(FK("model_runs", ondelete="SET NULL"))
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Prediction(UUIDPk, Timestamps, Base):
    __tablename__ = "predictions"
    organization_id: Mapped[uuid.UUID] = mapped_column(FK("organizations"), index=True)
    student_id: Mapped[uuid.UUID | None] = mapped_column(FK("students", ondelete="SET NULL"), index=True)
    model_version_id: Mapped[uuid.UUID | None] = mapped_column(FK("model_versions", ondelete="SET NULL"))
    network_key: Mapped[str] = mapped_column(String(40))
    model_version: Mapped[str] = mapped_column(String(40))
    task: Mapped[str] = mapped_column(String(40))
    scores: Mapped[dict] = mapped_column(JSONType, default=dict)
    explanation: Mapped[list] = mapped_column(JSONType, default=list)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(FK("users", ondelete="SET NULL"))


# --------------------------------------------------------------------------- Audit & Outbox
class AuditLog(Base):
    """Bitácora con encadenamiento hash (detecta alteraciones)."""
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_org_time", "organization_id", "occurred_at"),)
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    actor_email: Mapped[str | None] = mapped_column(String(254))
    action: Mapped[str] = mapped_column(String(60))
    resource: Mapped[str] = mapped_column(String(60))
    resource_id: Mapped[str | None] = mapped_column(String(80))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ip: Mapped[str | None] = mapped_column(String(64))
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSONType, default=dict)
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (Index("ix_outbox_unpublished", "published_at"), Index("ix_outbox_org_seq", "organization_id", "seq"))
    seq: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(60))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    aggregate_id: Mapped[str | None] = mapped_column(String(80))
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    audience: Mapped[dict] = mapped_column(JSONType, default=dict)  # {"roles": [...], "user_ids": [...]}
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
