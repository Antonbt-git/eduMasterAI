# Accesibilidad — WCAG 2.1 AA

## Correcciones aplicadas
- `--color-dim` elevado a `#B4A8D8` (contraste ≥ 4.5:1 sobre `#0D0A1E`/`#16112E`/`#21194A`).
- Botón primario con texto oscuro sobre `#7C5CFF` (≥ 4.5:1).
- Navegación por teclado, `aria-label`, `role="tablist"`, `aria-live` en conversación del tutor.
- `prefers-reduced-motion` respetado en el canvas neuronal.

## Pendiente (auditoría formal)
- Auditoría con axe-core / Lighthouse sobre todas las rutas.
- Verificación de foco visible en todos los controles interactivos.
