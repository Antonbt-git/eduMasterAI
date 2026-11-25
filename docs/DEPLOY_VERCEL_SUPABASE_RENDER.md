# Guía de despliegue — EduMaster.ai (edición Nebula) en Supabase + Render + Vercel

> Plantilla sin secretos. Genera los valores con `./scripts/gen-secrets.sh` y guárdalos fuera del repositorio.

## Qué va en cada plataforma

| Plataforma | Qué aloja | Plan |
|---|---|---|
| **Supabase** | PostgreSQL (39 tablas, RLS, auditoría inmutable) | Gratuito sirve para empezar |
| **Render** | `edumaster-nebula-api` (FastAPI), `edumaster-nebula-ml` (inferencia + entrenamiento PyTorch con disco), `edumaster-nebula-redis` (Key Value) | API: gratuito o de pago. ML: **de pago obligatorio** (Render no permite discos en instancias gratuitas). Se recomienda 2 GB de RAM para PyTorch |
| **Vercel** | Frontend React | Hobby (gratuito) |

Esta edición usa la paleta Nebula en el frontend y **credenciales nuevas, distintas de la edición anterior**. Despliégala como un proyecto aparte (nuevo proyecto de Supabase, nuevo Blueprint en Render y nuevo proyecto en Vercel); no reutilices los secretos anteriores.

Orden obligatorio: **1 Supabase → 2 Render → 3 Vercel → 4 volver a Render a poner el dominio de Vercel.**

---

## Tus credenciales generadas

Genera valores aleatorios con `./scripts/gen-secrets.sh`.

| Variable | Valor | Dónde va |
|---|---|---|
| `JWT_SECRET` | `<JWT_SECRET: ./scripts/gen-secrets.sh>` | Render → `edumaster-nebula-api` |
| `INTERNAL_SERVICE_TOKEN` | `<INTERNAL_SERVICE_TOKEN: ./scripts/gen-secrets.sh>` | Render → `edumaster-nebula-api` **y** `edumaster-nebula-ml` (el mismo valor en ambos) |
| `DEMO_PASSWORD` | `<DEMO_PASSWORD>` | Render → `edumaster-nebula-api` (contraseña de las 10 cuentas demo) |
| Contraseña sugerida para la base de Supabase | `<DB_PASSWORD>` | Supabase, al crear el proyecto (sin símbolos, así no hay que codificarla en la URL) |

### Cuentas para entrar a la aplicación (contraseña: `<DEMO_PASSWORD>`)

| Rol | Correo |
|---|---|
| Superadministrador | superadmin@edumaster.ai |
| Administrador | admin@edumaster.ai |
| Coordinador | coordinador@edumaster.ai |
| Docente | docente@edumaster.ai |
| Estudiante | estudiante@edumaster.ai |
| Analista | analista@edumaster.ai |
| ML Engineer | ml@edumaster.ai |
| Auditor | auditor@edumaster.ai |
| Otra institución | admin@andino.edu · estudiante@andino.edu |

Las credenciales de **Supabase, Render y Vercel** no puedo crearlas yo: salen de tus cuentas. Abajo indico exactamente dónde copiarlas.

---

## 0. Subir el código a GitHub

```bash
unzip EduMaster-AI-Nebula.zip && cd edumaster-ai-nebula
git init && git add . && git commit -m "EduMaster.ai"
git branch -M main
git remote add origin https://github.com/<tu-usuario>/edumaster-ai-nebula.git
git push -u origin main
```
El `.gitignore` ya excluye `.env`. **No subas esta guía** al repositorio.

---

## 1. Supabase (base de datos)

1. Entra a https://supabase.com/dashboard → **New project**.
   - Name: `edumaster-nebula`
   - Database password: `<DB_PASSWORD>`
   - Region: la más cercana a la región que elijas en Render (por ejemplo, ambas en Estados Unidos este, o ambas en Frankfurt).
2. Cuando termine, pulsa **Connect** (arriba) → pestaña **Connection string** → elige **Session pooler** (puerto **5432**). No uses el *Transaction pooler* (puerto 6543): no es compatible con SQLAlchemy.
3. Copia la cadena. Tendrá esta forma:
   ```
   postgresql://postgres.<PROJECT_REF>:[YOUR-PASSWORD]@aws-0-<REGION>.pooler.supabase.com:5432/postgres
   ```
4. Conviértela así (cambia el inicio y añade SSL):
   ```
   postgresql+psycopg://postgres.<PROJECT_REF>:<DB_PASSWORD>@aws-0-<REGION>.pooler.supabase.com:5432/postgres?sslmode=require
   ```
   Esta es tu **`DATABASE_URL`**. Si usaste otra contraseña con símbolos (`@ : / # ?`), codifícalos en la URL (por ejemplo, `@` → `%40`).
5. *(Opcional)* **Project Settings → API**: copia `Project URL` (`SUPABASE_URL`) y la clave `anon` (`SUPABASE_ANON_KEY`). Solo se necesitan si vas a usar Supabase Auth; la aplicación funciona sin ellas.

No hace falta crear tablas a mano: la API ejecuta las migraciones al arrancar en Render. La seguridad (RLS) se aplica en el paso 5.

---

## 2. Render (API, ML y Redis)

1. Entra a https://dashboard.render.com → **New** → **Blueprint**.
2. Conecta GitHub y elige el repositorio `edumaster-ai-nebula`. Render detecta `render.yaml` y propone 3 recursos: `edumaster-nebula-redis`, `edumaster-nebula-api`, `edumaster-nebula-ml`.
3. Render te pedirá los valores marcados como secretos. Rellena:

### `edumaster-nebula-api`
| Variable | Valor |
|---|---|
| `DATABASE_URL` | la URL del paso 1.4 |
| `JWT_SECRET` | `<JWT_SECRET: ./scripts/gen-secrets.sh>` |
| `INTERNAL_SERVICE_TOKEN` | `<INTERNAL_SERVICE_TOKEN: ./scripts/gen-secrets.sh>` |
| `DEMO_PASSWORD` | `<DEMO_PASSWORD>` |
| `PUBLIC_WEB_URL` | `https://edumaster-nebula.vercel.app` *(provisional; lo corriges en el paso 4)* |
| `CORS_ORIGINS` | `https://edumaster-nebula.vercel.app` *(provisional)* |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET` | déjalos vacíos si no usas Supabase Auth |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | vacío (opcional, ver paso 6) |

### `edumaster-nebula-ml`
| Variable | Valor |
|---|---|
| `INTERNAL_SERVICE_TOKEN` | `<INTERNAL_SERVICE_TOKEN: ./scripts/gen-secrets.sh>` (idéntico al de la API) |

`REDIS_URL`, `ML_SERVICE_URL` y `API_INTERNAL_URL` los conecta Render solo, por la red privada.

4. Pulsa **Apply**. La primera construcción tarda unos minutos (la imagen de ML descarga PyTorch).
5. Cuando `edumaster-nebula-api` esté *Live*, copia su URL pública, por ejemplo `https://edumaster-nebula-api.onrender.com`.
6. Comprueba:
   ```
   https://edumaster-nebula-api.onrender.com/health/ready
   ```
   Debe responder `"database":"ok"`, `"redis":"ok"` y `"ml_service":"ok"`.

En el primer arranque la API crea las tablas, carga los datos DEMO y manda entrenar las 5 redes al servicio ML (1–3 minutos). Como `ENVIRONMENT=production`, las versiones entrenadas **no se publican solas**: hay que aprobarlas (paso 7).

> Si dejas la API en plan gratuito, Render la duerme tras un rato sin tráfico; la primera visita tarda en despertar y el simulador de actividad en vivo se pausa mientras duerme.

---

## 3. Vercel (frontend)

1. Entra a https://vercel.com/new → **Import** el repositorio `edumaster-ai-nebula`.
2. **Root Directory**: `apps/web` (botón *Edit*). Framework: Vite (se detecta solo por `vercel.json`).
3. **Environment Variables**:
   | Variable | Valor |
   |---|---|
   | `VITE_API_URL` | `https://edumaster-nebula-api.onrender.com/api/v1` (tu URL del paso 2.5 + `/api/v1`) |
   | `VITE_DEMO_PASSWORD` | `<DEMO_PASSWORD>` *(opcional: solo si quieres que el login muestre y rellene la contraseña demo; omítelo en producción real)* |
4. **Deploy**. Copia el dominio final, por ejemplo `https://edumaster-nebula-xyz.vercel.app`.

Las variables `VITE_*` se incrustan al compilar: si las cambias, hay que volver a desplegar en Vercel.

---

## 4. Conectar Vercel con Render (CORS)

En Render → `edumaster-nebula-api` → **Environment**, cambia al dominio real de Vercel:

| Variable | Valor |
|---|---|
| `PUBLIC_WEB_URL` | `https://edumaster-nebula-xyz.vercel.app` |
| `CORS_ORIGINS` | `https://edumaster-nebula-xyz.vercel.app` |

Si añades un dominio propio, ponlos separados por coma: `https://edumaster-nebula-xyz.vercel.app,https://app.tudominio.com`. Guarda (Render redespliega solo).

---

## 5. Seguridad en Supabase (RLS)

En Supabase → **SQL Editor** → **New query**, pega el contenido de `infra/supabase/002_rls_security.sql` y pulsa **Run**. Esto:
- activa RLS en todas las tablas y quita el acceso de `anon`/`authenticated` (nadie puede leer datos con la clave pública);
- hace la tabla de auditoría imposible de editar o borrar;
- crea el bucket privado `edumaster-artifacts`.

Ejecútalo **después** de que la API haya arrancado una vez (las tablas deben existir). La API sigue funcionando porque se conecta como propietaria de la base.

---

## 6. IA Tutor con API externa (opcional)

En Render → `edumaster-nebula-api` → Environment:

| Proveedor | Variables |
|---|---|
| Anthropic | `AI_TUTOR_PROVIDER=anthropic`, `ANTHROPIC_API_KEY=<tu clave de console.anthropic.com>` |
| OpenAI o compatible | `AI_TUTOR_PROVIDER=openai`, `OPENAI_API_KEY=<clave>`, opcional `OPENAI_BASE_URL` y `OPENAI_MODEL` |

Sin clave, el tutor responde con reglas y las recomendaciones de la red propia.

---

## 7. Primer uso

1. Abre tu dominio de Vercel y entra como `ml@edumaster.ai`. En **Redes neuronales** verás las 5 redes entrenando en vivo.
2. Entra como `admin@edumaster.ai` → **Redes neuronales** → **Registro de modelos** → en cada red: **Revisar** → escribe una nota → **Aprobar** → **Publicar**.
3. Con los modelos publicados se activan la inferencia real, las sinapsis en el visualizador, las recomendaciones generadas por IA y el KPI «Calidad del modelo».

---

## 8. Verificación final

- [ ] `https://edumaster-nebula-api.onrender.com/health/ready` → todo `ok`
- [ ] Login con las cuentas demo desde Vercel
- [ ] Chip «En vivo» en verde arriba a la izquierda (tiempo real funcionando)
- [ ] Las 5 redes aparecen con estado «publicado» tras aprobarlas
- [ ] Un certificado se verifica en `https://<vercel>/verificar/<código>`
- [ ] En Supabase, el SQL de RLS se ejecutó sin errores

## Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| El login muestra «Failed to fetch» | `VITE_API_URL` mal escrito o CORS | Revisa el paso 3.3 y el paso 4; redespliega Vercel si cambiaste `VITE_API_URL` |
| `/health/ready` muestra error de base de datos | URL de Supabase | Debe empezar con `postgresql+psycopg://`, puerto **5432** (Session pooler) y `?sslmode=require` |
| `ml_service` «no disponible» | El servicio ML aún está construyendo o despertando | Espera a que esté *Live* en Render |
| Entrenamientos en cola sin avanzar | Token interno distinto | `INTERNAL_SERVICE_TOKEN` debe ser idéntico en API y ML |
| La API no arranca: «Secretos inseguros» | Valores débiles en producción | Usa los secretos de esta guía |
| «Sin conexión» en el chip de tiempo real | API dormida (plan gratuito) | Recarga; pasa la API a un plan de pago para que no duerma |

## Rotar credenciales
```bash
./scripts/gen-secrets.sh        # imprime nuevos valores
```
Cambia `JWT_SECRET` (cierra todas las sesiones) o `INTERNAL_SERVICE_TOKEN` (en API y ML a la vez) en Render. Para la base, cambia la contraseña en Supabase → Project Settings → Database y actualiza `DATABASE_URL`.
