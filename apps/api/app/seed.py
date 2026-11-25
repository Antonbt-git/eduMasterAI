"""Datos DEMO claramente rotulados (documento maestro §8.1 y criterio de aceptación 24).

Idempotente: si la institución demo existe, no hace nada. Sustituible por datos reales sin rehacer la UI.
Uso: python -m app.seed
"""
from __future__ import annotations

import random
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, insert, select, text
from sqlalchemy.orm import Session

from .core.config import settings
from .core.events import audit
from .core.rbac import PERMISSIONS, ROLES
from .core.security import hash_password
from .db.base import SessionLocal
from .db.models import (
    Activity, Assessment, AssessmentAttempt, Certificate, Cohort, CommunityPost, CommunityThread, Course, CourseOffering,
    CourseSkill, CourseUnit, DailyMetric, Enrollment, Instructor, LearningEvent, LearningPath, Lesson, Notification,
    Organization, PathAssignment, PathStep, Permission, Recommendation, Role, Skill, SkillEvidence, Student, User,
)

SKILLS = [("IA", "Inteligencia Artificial", "#5B8CFF"), ("ML", "Machine Learning", "#7C83FF"), ("DS", "Ciencia de Datos", "#20C8F5"),
          ("WEB", "Desarrollo Web", "#C77DFF"), ("OPS", "Nube y DevOps", "#E39BFF")]
COURSES = [
    ("IA-101", "Fundamentos de Inteligencia Artificial", "basico", "IA", "#087FE5"),
    ("IA-301", "Inteligencia Artificial Avanzada", "avanzado", "IA", "#8B4DFF"),
    ("ML-101", "Machine Learning Básico", "basico", "ML", "#20C8F5"),
    ("ML-201", "Redes Neuronales con PyTorch", "intermedio", "ML", "#8B4DFF"),
    ("DS-101", "Ciencia de Datos con Python", "basico", "DS", "#00BFA6"),
    ("DS-201", "Estadística para Analítica", "intermedio", "DS", "#20C8F5"),
    ("WEB-101", "Desarrollo Web con React", "basico", "WEB", "#087FE5"),
    ("WEB-201", "APIs con FastAPI", "intermedio", "WEB", "#00BFA6"),
    ("OPS-101", "Docker y Contenedores", "basico", "OPS", "#20C8F5"),
    ("OPS-201", "Kubernetes y MLOps", "avanzado", "OPS", "#8B4DFF"),
    ("PY-101", "Python desde Cero", "basico", "DS", "#00BFA6"),
    ("PY-301", "Proyecto Final de Python", "intermedio", "ML", "#087FE5"),
]
UNITS = ["Fundamentos", "Práctica guiada", "Proyecto aplicado"]
LESSONS = ["Introducción", "Conceptos clave", "Laboratorio", "Desafío"]
FIRST = ["Lucía", "Mateo", "Valentina", "Santiago", "Camila", "Sebastián", "Isabella", "Diego", "Sofía", "Nicolás", "Mariana", "Joaquín",
         "Daniela", "Gabriel", "Renata", "Tomás", "Antonella", "Emiliano", "Martina", "Leonardo", "Ximena", "Andrés", "Paula", "Bruno",
         "Fernanda", "Rodrigo", "Elena", "Iván", "Carla", "Héctor", "Julia", "Pablo", "Noa", "Adrián", "Abril", "Kenji", "Amara", "Liam"]
LAST = ["Fernández", "Quispe", "García", "Rojas", "Mendoza", "Torres", "Flores", "Vargas", "Castillo", "Ramírez", "Chávez", "Huamán",
        "Morales", "Silva", "Gutiérrez", "Ríos", "Paredes", "Salazar", "Navarro", "Campos", "Tanaka", "Okafor", "Müller", "Smith"]
REGIONS = ["América del Norte", "América del Sur", "Europa", "Asia", "África", "Oceanía"]
REGION_P = [0.28, 0.3, 0.2, 0.13, 0.05, 0.04]


def avatar(seed: str) -> str:
    return f"https://api.dicebear.com/9.x/notionists/svg?seed={seed}&backgroundColor=0d2b52,0a1f3d,123a6b"


def ensure_rbac(db: Session) -> dict[str, Role]:
    perms = {p.code: p for p in db.scalars(select(Permission))}
    for code, desc in PERMISSIONS.items():
        if code not in perms:
            perms[code] = Permission(code=code, description=desc)
            db.add(perms[code])
    roles = {r.code: r for r in db.scalars(select(Role))}
    for code, spec in ROLES.items():
        r = roles.get(code) or Role(code=code, name=spec["name"])
        r.permissions = [perms[p] for p in spec["permissions"]]
        db.add(r)
        roles[code] = r
    db.flush()
    return roles


def mk_user(db, org, roles, email, name, role_codes, title=None, pw=None):
    u = User(organization_id=org.id, email=email, full_name=name, title=title, password_hash=pw or hash_password(settings.demo_password),
             roles=[roles[r] for r in role_codes], avatar_url=avatar(email.split("@")[0]))
    db.add(u)
    db.flush()
    return u


def _demo_complete(db: Session) -> bool:
    """El demo está completo solo si tiene institución, staff, estudiantes, eventos y matrículas."""
    org = db.scalar(select(Organization).where(Organization.code == "EMA"))
    if not org:
        return False
    checks = (
        select(User.id).where(User.organization_id == org.id, User.email == "admin@edumaster.ai"),
        select(Student.id).where(Student.organization_id == org.id),
        select(LearningEvent.event_id).where(LearningEvent.organization_id == org.id),
        select(Enrollment.id).where(Enrollment.organization_id == org.id),
    )
    return all(db.scalar(q.limit(1)) is not None for q in checks)


def seed(db: Session) -> None:
    # Mantener objetos cargados entre commits por fases (evita round-trips de recarga).
    db.expire_on_commit = False
    # En Postgres/Supabase el pooler impone un statement_timeout corto; el seed
    # es una tarea batch y necesita más margen.
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(text("SET statement_timeout = 0"))
        db.commit()
    if _demo_complete(db):
        print("[seed] datos demo ya existen — omitido")
        ensure_rbac(db)
        db.commit()
        return
    if db.scalar(select(Organization.id).where(Organization.code == "EMA")):
        print("[seed] datos demo incompletos — reiniciando desde cero")
        db.execute(delete(Organization).where(Organization.code == "EMA"))
        db.commit()
    rnd = random.Random(2026)
    roles = ensure_rbac(db)
    now = datetime.now(timezone.utc)
    pw = hash_password(settings.demo_password)

    org = Organization(name="EduMaster Academy", code="EMA", timezone="America/Lima", settings={"demo": True, "demo_simulator": True})
    org2 = Organization(name="Instituto Andino de Tecnología", code="IAT", timezone="America/Lima", settings={"demo": True, "demo_simulator": False})
    db.add_all([org, org2])
    db.flush()

    staff = {
        "superadmin": mk_user(db, org, roles, "superadmin@edumaster.ai", "Super Administrador", ["superadmin"], "Superadministrador", pw),
        "admin": mk_user(db, org, roles, "admin@edumaster.ai", "Dra. Ana López", ["admin"], "Administrador", pw),
        "coordinator": mk_user(db, org, roles, "coordinador@edumaster.ai", "Mg. Rosa Paredes", ["coordinator"], "Coordinadora académica", pw),
        "instructor": mk_user(db, org, roles, "docente@edumaster.ai", "Ing. Carlos Ruiz", ["instructor"], "Docente", pw),
        "instructor2": mk_user(db, org, roles, "docente2@edumaster.ai", "Dra. Elena Vega", ["instructor"], "Docente", pw),
        "analyst": mk_user(db, org, roles, "analista@edumaster.ai", "Lic. Jorge Salas", ["analyst"], "Analista de datos", pw),
        "ml": mk_user(db, org, roles, "ml@edumaster.ai", "Ing. Kenji Tanaka", ["ml_engineer"], "ML Engineer", pw),
        "auditor": mk_user(db, org, roles, "auditor@edumaster.ai", "CPC. Marta Ríos", ["auditor"], "Auditora", pw),
    }
    ins1 = Instructor(user_id=staff["instructor"].id, organization_id=org.id, staff_code="IN-001")
    ins2 = Instructor(user_id=staff["instructor2"].id, organization_id=org.id, staff_code="IN-002")
    db.add_all([ins1, ins2])

    skills = {}
    for code, name, color in SKILLS:
        skills[code] = Skill(organization_id=org.id, code=code, name=name, color=color)
        db.add(skills[code])
    cohorts = []
    for m in range(6):
        d = date(2026, 1 + m, 5)
        c = Cohort(organization_id=org.id, code=f"C2026-{m + 1:02d}", name=f"Cohorte {d:%B %Y}".replace("January", "Enero").replace("February", "Febrero")
                   .replace("March", "Marzo").replace("April", "Abril").replace("May", "Mayo").replace("June", "Junio"), program="Tecnología e IA", start_date=d)
        cohorts.append(c)
        db.add(c)
    db.flush()

    courses, lesson_ids, offerings, assessments = [], {}, {}, defaultdict(list)
    for i, (code, title, level, sk, color) in enumerate(COURSES):
        c = Course(organization_id=org.id, code=code, title=title, level=level, status="published" if i < 11 else "draft", cover_color=color,
                   description=f"Curso {level} de {skills[sk].name}: teoría, laboratorios guiados y un proyecto aplicado.",
                   tags=[sk.lower(), level], duration_hours=[20, 32, 48][["basico", "intermedio", "avanzado"].index(level)], updated_by=staff["admin"].id,
                   created_at=now - timedelta(days=400 - i * 9))
        c.skills = [CourseSkill(skill_id=skills[sk].id, weight=1.0)]
        db.add(c)
        db.flush()
        lids = []
        for u_i, ut in enumerate(UNITS):
            unit = CourseUnit(course_id=c.id, title=f"Unidad {u_i + 1}: {ut}", position=u_i)
            unit.lessons = [Lesson(title=f"{lt} — {ut.lower()}", kind=["lesson", "resource", "activity", "activity"][l_i],
                                   resource_url=None, duration_min=[15, 20, 40, 45][l_i], position=l_i) for l_i, lt in enumerate(LESSONS)]
            db.add(unit)
            db.flush()
            lids += [str(l.id) for l in unit.lessons]
        lesson_ids[c.id] = lids
        off = CourseOffering(course_id=c.id, instructor_id=(ins1 if i % 2 == 0 else ins2).id, cohort_id=cohorts[i % 6].id, period="2026", starts_at=date(2026, 1, 5))
        db.add(off)
        db.flush()
        offerings[c.id] = off
        for k, (atitle, atype) in enumerate([("Evaluación parcial", "multiple_choice"), ("Proyecto práctico", "practice")]):
            a = Assessment(course_id=c.id, organization_id=org.id, title=f"{atitle}: {title}", type=atype, max_score=100, passing_score=70,
                           due_at=now + timedelta(days=7 + k * 14), attempts_allowed=3, skill_id=skills[sk].id, grading_rule="best",
                           instructions="Responde con cuidado. Se considera el mejor intento.",
                           rubric=[{"criterio": "Precisión", "peso": 0.6}, {"criterio": "Aplicación", "peso": 0.4}],
                           questions=[
                               {"prompt": f"¿Qué describe mejor el objetivo de {title}?", "options": ["Memorizar sin practicar", "Aplicar conceptos a problemas reales", "Evitar evaluaciones"], "answer": "Aplicar conceptos a problemas reales", "points": 10},
                               {"prompt": "Una red neuronal ajusta sus pesos mediante…", "options": ["Retropropagación del error", "Azar puro", "Copiar respuestas"], "answer": "Retropropagación del error", "points": 10},
                               {"prompt": "Verdadero o falso: una probabilidad estimada por IA es un diagnóstico definitivo.", "options": ["Verdadero", "Falso"], "answer": "Falso", "points": 10},
                           ] if atype == "multiple_choice" else [])
            db.add(a)
            db.flush()
            assessments[c.id].append(a)
        courses.append(c)

    # --------------------------------------------------------- estudiantes
    students = []
    main_user = mk_user(db, org, roles, "estudiante@edumaster.ai", "Lucía Fernández", ["student"], "Estudiante", pw)
    main = Student(user_id=main_user.id, organization_id=org.id, external_code="ST-0001", region="América del Sur")
    db.add(main)
    students.append(main)
    used = {"estudiante@edumaster.ai"}
    for n in range(2, 361):
        f, l = rnd.choice(FIRST), rnd.choice(LAST)
        email = f"{f.lower()}.{l.lower()}{n}@alumnos.edumaster.ai".encode("ascii", "ignore").decode()
        if email in used:
            continue
        used.add(email)
        uid = uuid.uuid4()
        u = User(id=uid, organization_id=org.id, email=email, full_name=f"{f} {l}", password_hash=pw, roles=[roles["student"]],
                 avatar_url=avatar(email.split("@")[0]), title="Estudiante")
        db.add(u)
        st = Student(id=uuid.uuid4(), user_id=uid, organization_id=org.id, external_code=f"ST-{n:04d}",
                     region=rnd.choices(REGIONS, REGION_P)[0])
        db.add(st)
        students.append(st)
    db.flush()
    db.commit()  # fase 1: estructura académica persistida (libera locks)

    # --------------------------------------------------------- matrículas + eventos + intentos
    events, attempts, evidence, enrollments = [], [], [], []
    published = [c for c in courses if c.status == "published"]
    lat = {s.id: (rnd.gauss(0, 1), rnd.gauss(0, 1)) for s in students}
    for st in students:
        ability, motivation = lat[st.id]
        k = rnd.choice([1, 2, 2, 3, 3, 4]) if st is not main else 4
        chosen = rnd.sample(published, k) if st is not main else [c for c in published if c.code in ("PY-101", "ML-101", "IA-301", "DS-101")]
        for c in chosen:
            start = now - timedelta(days=rnd.randint(5, 330)) if st is not main else now - timedelta(days=rnd.randint(30, 120))
            weeks = min(12, max(1, (now - start).days // 7))
            lids = lesson_ids[c.id]
            seen, completed_acts = set(), 0
            drop_week = rnd.randint(2, 11) if rnd.random() < 1 / (1 + 2.7 ** (1.2 * motivation + 0.3)) else 99
            last_at = None
            for w in range(weeks):
                if w >= drop_week:
                    break
                for _ in range(max(0, int(rnd.gauss(2.2 + 0.8 * motivation, 1)))):
                    t = start + timedelta(days=7 * w + rnd.random() * 7)
                    if t > now:
                        continue
                    events.append(dict(event_id=uuid.uuid4(), organization_id=org.id, student_id=st.id, course_id=c.id, event_type="session_started",
                                       occurred_at=t, duration_seconds=rnd.randint(600, 5400), activity_id=None, payload={"label": "DEMO"}, source="import"))
                    for _ in range(rnd.randint(1, 3)):
                        lid = lids[min(len(lids) - 1, len(seen) + rnd.randint(0, 1))]
                        seen.add(lid)
                        etype = "activity_completed" if rnd.random() < 0.45 else "lesson_viewed"
                        completed_acts += etype == "activity_completed"
                        events.append(dict(event_id=uuid.uuid4(), organization_id=org.id, student_id=st.id, course_id=c.id, event_type=etype,
                                           occurred_at=t + timedelta(minutes=rnd.randint(2, 50)), duration_seconds=rnd.randint(120, 2400),
                                           activity_id=lid, payload={"label": "DEMO"}, source="import"))
                    last_at = t
            best = {}
            for a in assessments[c.id]:
                if len(seen) < 4 or rnd.random() < 0.15:
                    continue
                for _ in range(rnd.randint(1, 2)):
                    score = max(5, min(100, 100 / (1 + 2.7 ** (-(1.1 * ability + 0.4 * motivation + 0.9 + rnd.gauss(0, 0.6)))) ))
                    at = min(now - timedelta(hours=1), start + timedelta(days=rnd.randint(7, 7 * max(2, weeks))))
                    attempts.append(dict(id=uuid.uuid4(), assessment_id=a.id, student_id=st.id, score=round(score, 1), late=rnd.random() < 0.2,
                                         status="graded", submitted_at=at, answers={}))
                    best[a.id] = max(best.get(a.id, 0), score)
                    evidence.append(dict(id=uuid.uuid4(), student_id=st.id, skill_id=a.skill_id, source_type="assessment",
                                         score=round(score / 100, 3), level=min(4, int(score / 100 * 5)), observed_at=at))
            lesson_ratio = len(seen) / len(lids)
            passed = sum(1 for v in best.values() if v >= 70)
            progress = round(min(1.0, 0.6 * lesson_ratio + 0.4 * passed / len(assessments[c.id])), 4)
            if drop_week == 99 and weeks >= 10 and passed == len(assessments[c.id]) and rnd.random() < 0.85:
                progress = 1.0
            status = "completed" if progress >= 0.999 else ("in_progress" if progress > 0 else "not_started")
            enrollments.append(dict(id=uuid.uuid4(), offering_id=offerings[c.id].id, course_id=c.id, student_id=st.id, organization_id=org.id,
                                    status=status, progress=progress, enrolled_at=start, last_activity_at=last_at,
                                    completed_at=(start + timedelta(days=7 * weeks)) if status == "completed" else None))
    # Lucía: uno completado reciente (Python) para mostrar certificado/actividad
    for e in enrollments:
        if e["student_id"] == main.id and e["course_id"] == next(c.id for c in courses if c.code == "PY-101"):
            e.update(status="completed", progress=1.0, completed_at=now - timedelta(hours=2))
    for chunk in range(0, len(events), 5000):
        db.execute(insert(LearningEvent), events[chunk:chunk + 5000])
        db.commit()  # fase 2: commits por lote de eventos (progreso persistente)
    db.execute(insert(Enrollment), enrollments)
    if attempts:
        db.execute(insert(AssessmentAttempt), attempts)
    if evidence:
        db.execute(insert(SkillEvidence), evidence)
    # Algunas validaciones docentes de nivel (separadas de la estimación IA)
    db.execute(insert(SkillEvidence), [dict(id=uuid.uuid4(), student_id=ev["student_id"], skill_id=ev["skill_id"], source_type="instructor",
                                            score=ev["score"], level=ev["level"], observed_at=ev["observed_at"], validated_by=staff["instructor"].id)
                                       for ev in evidence[::7]])
    db.commit()

    # --------------------------------------------------------- agregados diarios
    region_of = {s.id: s.region for s in students}
    agg = defaultdict(lambda: {"events": 0, "secs": 0, "students": set(), "assess": 0, "comp": 0})
    for e in events:
        k = (e["occurred_at"].date(), e["course_id"], region_of[e["student_id"]])
        agg[k]["events"] += 1
        agg[k]["secs"] += e["duration_seconds"]
        agg[k]["students"].add(e["student_id"])
    for a in attempts:
        cid = next(c for c, lst in assessments.items() if any(x.id == a["assessment_id"] for x in lst))
        agg[(a["submitted_at"].date(), cid, region_of[a["student_id"]])]["assess"] += 1
    for e in enrollments:
        if e["completed_at"]:
            agg[(e["completed_at"].date(), e["course_id"], region_of[e["student_id"]])]["comp"] += 1
    db.execute(insert(DailyMetric), [dict(organization_id=org.id, day=k[0], course_id=k[1], region=k[2], events=v["events"], learning_seconds=v["secs"],
                                          active_students=len(v["students"]), assessments=v["assess"], completions=v["comp"], computed_at=now)
                                     for k, v in agg.items()])
    db.commit()  # fase 3: agregados diarios

    # --------------------------------------------------------- certificados
    seq = 0
    for e in sorted([e for e in enrollments if e["status"] == "completed"], key=lambda x: x["completed_at"]):
        if rnd.random() < 0.8 or e["student_id"] == main.id:
            seq += 1
            db.add(Certificate(organization_id=org.id, student_id=e["student_id"], course_id=e["course_id"], folio=f"EMA-{e['completed_at'].year}-{seq:06d}",
                               verification_code=uuid.uuid4().hex[:12].upper(), status="issued", issued_at=e["completed_at"] + timedelta(minutes=30),
                               expires_at=e["completed_at"] + timedelta(days=1095), issued_by=staff["admin"].id, final_score=100.0))

    # --------------------------------------------------------- rutas
    by_code = {c.code: c for c in courses}
    paths = [
        ("Ruta de Ciencia de Datos", "Dominar análisis de datos con Python y estadística aplicada.", ["PY-101", "DS-101", "DS-201", "ML-101"], ["Ciencia de Datos", "Machine Learning"]),
        ("Ruta de IA Aplicada", "Construir y desplegar modelos de IA responsables.", ["IA-101", "ML-101", "ML-201", "IA-301"], ["Inteligencia Artificial", "Machine Learning"]),
        ("Ruta Full-Stack + DevOps", "Desarrollar APIs y frontends y operarlos en la nube.", ["WEB-101", "WEB-201", "OPS-101", "OPS-201"], ["Desarrollo Web", "Nube y DevOps"]),
    ]
    for title, obj, codes, comps in paths:
        lp = LearningPath(organization_id=org.id, title=title, objective=obj, competencies=comps, duration_weeks=16, status="published")
        lp.steps = [PathStep(course_id=by_code[cd].id, position=i, prerequisite_course_id=by_code[codes[i - 1]].id if i else None) for i, cd in enumerate(codes)]
        db.add(lp)
        db.flush()
        db.add(PathAssignment(path_id=lp.id, cohort_id=cohorts[0].id, target_date=date(2026, 12, 15)))
        db.add(PathAssignment(path_id=lp.id, student_id=main.id, target_date=date(2026, 12, 15)))

    # --------------------------------------------------------- recomendaciones de arranque (reglas, rotuladas)
    for i, (act, cd, imp) in enumerate([("Repasa", "IA-301", "alto"), ("Completa", "ML-101", "alto"), ("Sigue", "DS-201", "medio"),
                                         ("Realiza", "PY-301", "medio"), ("Explora", "ML-201", "bajo")]):
        db.add(Recommendation(organization_id=org.id, student_id=main.id, model_version="reglas-arranque-v1", type="resource", action=act,
                              title=f"{act}: {by_code[cd].title}", impact=imp, priority=1 - i * 0.15, confidence=None, status="new",
                              rationale={"competency": by_code[cd].skills[0].skill.name if by_code[cd].skills else "", "reasons": ["Regla de arranque: brecha de competencia en la ruta asignada"],
                                         "objective": "Avanzar en la ruta asignada", "disclaimer": "Generada por reglas antes de publicar el modelo."},
                              expires_at=now + timedelta(days=30)))

    # --------------------------------------------------------- comunidad
    th = [
        (staff["instructor"], "announcement", "Bienvenidos a Redes Neuronales con PyTorch", "Esta semana veremos backpropagation. Revisen el visualizador neuronal antes de la clase.", by_code["ML-201"].id),
        (main_user, "discussion", "¿Cómo elegir la tasa de aprendizaje?", "Mi loss oscila mucho con lr=0.1. ¿Algún consejo práctico?", by_code["ML-101"].id),
        (staff["coordinator"], "announcement", "Nueva Ruta Full-Stack + DevOps disponible", "Ya pueden inscribirse en la nueva ruta. Inicio: próximo lunes.", None),
        (staff["instructor2"], "discussion", "Comparte tu proyecto de Docker", "Publiquen el enlace a su repositorio y comenten el de un compañero.", by_code["OPS-101"].id),
    ]
    for i, (au, kind, title, body, cid) in enumerate(th):
        t = CommunityThread(organization_id=org.id, course_id=cid, author_id=au.id, kind=kind, title=title, body=body, pinned=kind == "announcement",
                            created_at=now - timedelta(hours=30 - i * 6))
        db.add(t)
        db.flush()
        if i == 1:
            db.add(CommunityPost(thread_id=t.id, author_id=staff["instructor"].id, body="Prueba con un scheduler (ReduceLROnPlateau) y empieza en 1e-3.",
                                 created_at=now - timedelta(hours=20)))

    # --------------------------------------------------------- actividad y notificaciones (como la referencia)
    for title, typ, hours, subj in [("Curso de Python completado", "course_completed", 2, main_user.id),
                                    ("Certificado emitido correctamente", "certificate_issued", 3, main_user.id),
                                    ("Nuevo curso iniciado", "enrollment", 5, main_user.id),
                                    ("Examen de Machine Learning aprobado", "assessment_graded", 24, main_user.id),
                                    ("Meta de aprendizaje alcanzada (90%)", "goal", 26, main_user.id)]:
        db.add(Activity(organization_id=org.id, type=typ, title=title, subject_user_id=subj, visibility="org", created_at=now - timedelta(hours=hours)))
    for u in [staff["admin"], main_user, staff["instructor"]]:
        db.add(Notification(organization_id=org.id, user_id=u.id, type="welcome", title="Bienvenido a EduMaster.ai",
                            body="Entorno DEMO con datos sintéticos rotulados.", link="/"))

    # --------------------------------------------------------- segunda institución (pruebas de aislamiento)
    a2 = mk_user(db, org2, roles, "admin@andino.edu", "Mg. Pedro Andrade", ["admin"], "Administrador", pw)
    s2u = mk_user(db, org2, roles, "estudiante@andino.edu", "Rocío Mamani", ["student"], "Estudiante", pw)
    db.add(Student(user_id=s2u.id, organization_id=org2.id, external_code="AN-0001", region="América del Sur"))
    db.add(Course(organization_id=org2.id, code="AN-101", title="Introducción a la Programación (Andino)", level="basico", status="published", updated_by=a2.id))
    for code, name, color in SKILLS:
        db.add(Skill(organization_id=org2.id, code=code, name=name, color=color))

    audit(db, None, "system.seeded", "organization", org.id, {"label": "DEMO", "students": len(students), "events": len(events)}, org_id=org.id, actor_email="system@seed")
    db.commit()
    print(f"[seed] DEMO creado: {len(students)} estudiantes, {len(events)} eventos, {len(attempts)} intentos, {len(enrollments)} matrículas")


def main():
    with SessionLocal() as db:
        seed(db)


if __name__ == "__main__":
    main()
