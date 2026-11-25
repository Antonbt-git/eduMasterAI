# Plan de QA y UAT — EduMaster.ai

## Alcance
Cubre los 31 casos de aceptación del documento maestro (CA-01 … CA-31) más los
endurecimientos de esta iteración (multi-tenant de modelos, idempotencia,
CSP, contrato de inferencia, puertas de calidad, estados de certificados).

## Tipos de prueba
- **Unitarias**: `apps/api/tests` (23 pasan), `apps/ml/tests`.
- **Contrato**: `tests/test_contract.py` (16 endpoints exigidos).
- **Endurecimiento**: `tests/test_hardening.py` (CSP, idempotencia, aislamiento).
- **E2E (Playwright)**: pendiente de automatizar; hoy verificación manual documentada en `docs/TRAZABILIDAD.md`.
- **Carga (k6)**: pendiente.

## Criterios de salida (DoD)
- 100 % de pruebas unitarias/contrato en verde.
- `ruff check apps/api --select E9,F63,F7,F82` sin errores.
- Trivy sin vulnerabilidades CRITICAL.
- Build de `apps/web` sin errores de tipo.
- Checklist de accesibilidad WCAG 2.1 AA (ver `docs/ACCESIBILIDAD.md`).
