"""Catálogo RBAC (documento maestro §3 — matriz de permisos)."""
from __future__ import annotations

PERMISSIONS: dict[str, str] = {
    "orgs:manage": "Gestionar instituciones (tenants)",
    "users:read": "Consultar usuarios",
    "users:write": "Crear/editar usuarios y roles",
    "courses:read": "Consultar cursos",
    "courses:write": "Crear/editar/publicar cursos",
    "paths:read": "Consultar rutas de aprendizaje",
    "paths:write": "Crear/asignar rutas",
    "assessments:read": "Consultar evaluaciones",
    "assessments:write": "Crear/calificar evaluaciones",
    "attempts:submit": "Responder evaluaciones",
    "grades:read_all": "Ver calificaciones de toda la institución",
    "events:ingest": "Registrar eventos de aprendizaje",
    "analytics:read": "Consultar analítica",
    "analytics:export": "Exportar reportes",
    "recommendations:read": "Ver recomendaciones",
    "recommendations:review": "Revisar recomendaciones del grupo",
    "certificates:read": "Ver certificados",
    "certificates:issue": "Emitir/anular certificados",
    "community:read": "Leer comunidad",
    "community:write": "Publicar en comunidad",
    "community:moderate": "Moderar comunidad",
    "notifications:read": "Centro de notificaciones",
    "datasets:read": "Consultar datasets seudonimizados",
    "datasets:build": "Preparar/versionar datasets",
    "datasets:approve": "Aprobar acceso/publicación de datasets",
    "ml:read": "Consultar modelos y métricas",
    "ml:train": "Lanzar entrenamientos y registrar modelos",
    "ml:approve": "Aprobar publicación/rollback de modelos",
    "ml:predict": "Solicitar inferencia",
    "audit:read": "Consultar auditoría",
    "audit:read_own": "Consultar actividad propia",
    "settings:write": "Configuración institucional",
}

_ALL = list(PERMISSIONS)
_STAFF_READ = ["courses:read", "paths:read", "assessments:read", "analytics:read", "recommendations:read",
               "certificates:read", "community:read", "community:write", "notifications:read", "ml:read", "audit:read_own"]

ROLES: dict[str, dict] = {
    "superadmin": {"name": "Superadministrador", "permissions": _ALL},
    "admin": {"name": "Administrador institucional", "permissions": [p for p in _ALL if p not in ("orgs:manage", "ml:train", "datasets:build")]},
    "coordinator": {"name": "Director / coordinador", "permissions": _STAFF_READ + ["paths:write", "users:read", "grades:read_all", "analytics:export", "recommendations:review", "ml:predict", "certificates:issue"]},
    "instructor": {"name": "Docente / instructor", "permissions": _STAFF_READ + ["assessments:write", "recommendations:review", "community:moderate", "ml:predict", "analytics:export"]},
    "student": {"name": "Estudiante", "permissions": ["courses:read", "paths:read", "assessments:read", "attempts:submit", "events:ingest", "recommendations:read", "certificates:read", "community:read", "community:write", "notifications:read", "audit:read_own"]},
    "analyst": {"name": "Analista de datos", "permissions": ["analytics:read", "analytics:export", "datasets:read", "datasets:build", "courses:read", "ml:read", "notifications:read", "audit:read_own"]},
    "ml_engineer": {"name": "Científico de datos / ML Engineer", "permissions": ["ml:read", "ml:train", "ml:predict", "datasets:read", "datasets:build", "analytics:read", "notifications:read", "audit:read_own"]},
    "auditor": {"name": "Auditor", "permissions": ["audit:read", "audit:read_own", "ml:read", "datasets:read", "analytics:read", "courses:read", "notifications:read"]},
}

STAFF_ROLES = {"superadmin", "admin", "coordinator", "instructor", "analyst", "ml_engineer", "auditor"}
