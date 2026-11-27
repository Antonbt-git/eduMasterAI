#!/usr/bin/env python3
"""Convierte documentación Markdown a PDF (WeasyPrint).

Uso:
    python scripts/md2pdf.py docs/MANUAL_USO.md [otro.md ...]
    python scripts/md2pdf.py --out docs/pdf docs/MANUAL_USO.md

Genera un PDF por archivo de entrada en el directorio `--out` (por defecto,
junto al Markdown con sufijo `.pdf`). Añade portada, número de página y
estilo corporativo EduMaster.ai.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import markdown
from weasyprint import CSS, HTML

THEME = """
@page {
  size: A4;
  margin: 20mm 17mm 18mm 17mm;
  @bottom-left { content: "EduMaster.ai · Documentación interna"; font-size: 8pt; color: #7b8aa5; }
  @bottom-right { content: "Página " counter(page) " de " counter(pages); font-size: 8pt; color: #7b8aa5; }
}
@page :first { @bottom-left { content: ""; } @bottom-right { content: ""; } }

body { font-family: "DejaVu Sans", "Inter", sans-serif; font-size: 9.6pt; line-height: 1.55; color: #1b2433; }

/* --- portada --- */
.cover { page-break-after: always; padding-top: 60mm; }
.cover .mark { font-size: 15pt; letter-spacing: .16em; text-transform: uppercase; color: #087FE5; font-weight: 700; }
.cover h1 { font-size: 30pt; line-height: 1.15; color: #06152B; margin: 8mm 0 4mm; border: none; }
.cover .sub { font-size: 12.5pt; color: #4a5a72; }
.cover .rule { height: 3mm; background: linear-gradient(90deg, #087FE5, #8B4DFF 55%, #20C8F5); border-radius: 2mm; margin: 10mm 0; }
.cover .meta { margin-top: 18mm; font-size: 9.5pt; color: #5c6b83; }
.cover .meta b { color: #06152B; }

h1 { font-size: 19pt; color: #06152B; border-bottom: 2.2pt solid #087FE5; padding-bottom: 2.5mm; margin: 9mm 0 4mm; page-break-after: avoid; }
h2 { font-size: 13.5pt; color: #0A1F3D; margin: 7mm 0 3mm; padding-left: 3mm; border-left: 3pt solid #20C8F5; page-break-after: avoid; }
h3 { font-size: 11pt; color: #0D2B52; margin: 5mm 0 2mm; page-break-after: avoid; }
h4 { font-size: 10pt; color: #4a5a72; margin: 4mm 0 2mm; page-break-after: avoid; }

p { margin: 0 0 3mm; text-align: justify; }
ul, ol { margin: 0 0 3.5mm; padding-left: 6mm; }
li { margin-bottom: 1.4mm; }

a { color: #087FE5; text-decoration: none; word-break: break-all; }

code { font-family: "DejaVu Sans Mono", monospace; font-size: 8.6pt; background: #eef3fa; padding: .3mm 1.2mm; border-radius: 1mm; color: #0D2B52; }
pre { background: #0A1F3D; color: #dfe9ff; padding: 3.5mm 4mm; border-radius: 2.5mm; overflow-wrap: anywhere; white-space: pre-wrap; margin: 0 0 4mm; page-break-inside: avoid; }
pre code { background: none; color: inherit; padding: 0; font-size: 8.3pt; line-height: 1.45; }

blockquote { border-left: 3pt solid #8B4DFF; background: #f4f1ff; margin: 0 0 4mm; padding: 2.5mm 4mm; color: #3a3560; border-radius: 0 2mm 2mm 0; }
blockquote p { margin: 0; }

table { width: 100%; border-collapse: collapse; margin: 0 0 5mm; font-size: 8.7pt; page-break-inside: auto; }
thead { background: #06152B; color: #fff; }
th { text-align: left; padding: 2.2mm 2.6mm; font-weight: 600; }
td { padding: 2mm 2.6mm; border-bottom: .6pt solid #dfe5ee; vertical-align: top; }
tbody tr:nth-child(even) { background: #f5f8fc; }
tr { page-break-inside: avoid; }

hr { border: none; border-top: 1pt solid #dfe5ee; margin: 6mm 0; }
strong { color: #06152B; }
img { max-width: 100%; }
"""

COVER_RE = re.compile(r"^#\s+(.*)$", re.M)


def render(md_path: Path, out_path: Path) -> Path:
    source = md_path.read_text(encoding="utf-8")

    title = md_path.stem.replace("_", " ").replace("-", " ")
    subtitle = "Guía de referencia"
    m = COVER_RE.search(source)
    if m:
        title = m.group(1).strip()
        source = COVER_RE.sub("", source, count=1)
        lines = [ln for ln in source.splitlines() if ln.strip() and not ln.startswith("#")]
        if lines:
            # Se convierte a HTML para conservar negritas/enlaces sin marcado crudo.
            subtitle = markdown.markdown(lines[0].strip().strip("#").strip()).strip()
            if subtitle.startswith("<p>") and subtitle.endswith("</p>"):
                subtitle = subtitle[3:-4]

    body = markdown.markdown(
        source,
        extensions=["tables", "fenced_code", "sane_lists", "attr_list", "toc"],
        extension_configs={"toc": {"permalink": False}},
    )

    cover = f"""
    <div class="cover">
      <div class="mark">EduMaster.ai</div>
      <div class="rule"></div>
      <h1>{title}</h1>
      <div class="sub">{subtitle}</div>
      <div class="meta">
        <b>Tipo:</b> Documentación de proyecto<br/>
        <b>Plataforma:</b> EduMaster.ai · Aprende • Practica • Destaca<br/>
        <b>Fuente:</b> {md_path.name}<br/>
        <b>Clasificación:</b> Uso interno · datos DEMO
      </div>
    </div>
    """

    out_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=f"<html><head><meta charset='utf-8'></head><body>{cover}{body}</body></html>",
         base_url=str(md_path.parent)).write_pdf(out_path, stylesheets=[CSS(string=THEME)])
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Convierte Markdown a PDF corporativo")
    ap.add_argument("inputs", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=None, help="Directorio de salida")
    args = ap.parse_args()

    for src in args.inputs:
        if not src.exists():
            print(f"✗ no existe: {src}", file=sys.stderr)
            return 1
        dest_dir = args.out if args.out else src.parent
        out = dest_dir / (src.stem + ".pdf")
        render(src, out)
        print(f"✔ {out}  ({out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
