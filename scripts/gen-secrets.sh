#!/usr/bin/env bash
# Genera secretos aleatorios fuertes.
#   ./scripts/gen-secrets.sh            → imprime los valores
#   ./scripts/gen-secrets.sh --write    → crea/actualiza .env reemplazando los marcadores
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - "$@" <<'PY'
import re, secrets, shutil, sys, pathlib
vals = {"JWT_SECRET": secrets.token_urlsafe(48), "INTERNAL_SERVICE_TOKEN": secrets.token_urlsafe(32),
        "POSTGRES_PASSWORD": secrets.token_urlsafe(24), "GRAFANA_PASSWORD": secrets.token_urlsafe(18),
        "MINIO_ROOT_PASSWORD": secrets.token_urlsafe(24)}
if "--write" not in sys.argv:
    print("\n".join(f"{k}={v}" for k, v in vals.items())); sys.exit()
env = pathlib.Path(".env")
if not env.exists():
    shutil.copy(".env.example", env)
text = env.read_text()
for k, v in vals.items():
    text = re.sub(rf"^{k}=(cambia.*)?$", f"{k}={v}", text, flags=re.M)
env.write_text(text)
print(".env listo con secretos aleatorios (los valores ya personalizados se conservan).")
PY
