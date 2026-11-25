-- =====================================================================
-- EduMaster.ai — Seguridad para Supabase (Row Level Security)
-- Ejecutar DESPUÉS de 001_schema.sql (o de `alembic upgrade head`).
--
-- Modelo de seguridad:
--   * La API FastAPI se conecta con el rol propietario (postgres / service
--     role) y aplica RBAC/ABAC en el backend: ese rol omite RLS.
--   * Los roles públicos de Supabase (anon, authenticated) NO deben leer
--     tablas académicas por PostgREST. RLS activado sin políticas = acceso
--     denegado por defecto (defensa adicional, documento maestro §11).
-- =====================================================================
ALTER TABLE public.activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.activities NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.assessment_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.assessment_attempts NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.assessments NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.certificates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.certificates NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.cohorts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cohorts NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.community_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.community_posts NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.community_threads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.community_threads NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.content_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.content_reports NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.course_offerings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.course_offerings NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.course_skills ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.course_skills NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.course_units ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.course_units NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.courses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.courses NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.daily_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.daily_metrics NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.datasets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.datasets NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.enrollments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.enrollments NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.instructors ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.instructors NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.learning_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.learning_events NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.learning_paths ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.learning_paths NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.lessons ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lessons NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.model_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.model_runs NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.model_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.model_versions NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.notification_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notification_preferences NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organizations NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.outbox_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.outbox_events NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.path_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.path_assignments NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.path_steps ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.path_steps NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.permissions NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.predictions NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.recommendation_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recommendation_feedback NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recommendations NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.role_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.role_permissions NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.roles NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.skill_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.skill_evidence NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.skills ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.skills NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.students ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.students NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_roles NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso
ALTER TABLE public.alembic_version ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alembic_version NO FORCE ROW LEVEL SECURITY; -- el propietario (API) conserva acceso

-- Quitar privilegios directos a los roles expuestos por PostgREST
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated;

-- Auditoría protegida contra alteración: solo inserción para la API
CREATE OR REPLACE FUNCTION public.audit_logs_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit_logs es inmutable (operación % bloqueada)', TG_OP;
END $$;
DROP TRIGGER IF EXISTS trg_audit_logs_immutable ON public.audit_logs;
CREATE TRIGGER trg_audit_logs_immutable BEFORE UPDATE OR DELETE ON public.audit_logs
  FOR EACH ROW EXECUTE FUNCTION public.audit_logs_immutable();

-- (Opcional) Política de ejemplo si se habilita lectura directa con Supabase Auth:
-- el JWT debe incluir el claim org_id (app_metadata). Mantener comentada salvo aprobación.
-- CREATE POLICY courses_tenant_read ON public.courses FOR SELECT TO authenticated
--   USING (organization_id::text = (auth.jwt() -> 'app_metadata' ->> 'org_id'));

-- Bucket privado para artefactos de modelos, datasets y certificados (Supabase Storage)
INSERT INTO storage.buckets (id, name, public)
VALUES ('edumaster-artifacts', 'edumaster-artifacts', false)
ON CONFLICT (id) DO NOTHING;
