"""Mapeo de la paleta original (azul) a la paleta Nebula. Ejecutar desde apps/web para re-aplicar o ajustar."""
import pathlib, re, sys

HEX = {  # original → Nebula
    "#06152B": "#0D0A1E", "#020A17": "#07050F", "#0A1F3D": "#16112E", "#0D2B52": "#21194A", "#16406F": "#3B2E78",
    "#0E3466": "#261C55", "#1C5A9C": "#4A3A94",
    "#087FE5": "#7C5CFF", "#1B8FF0": "#9177FF", "#0A5FC0": "#5B3FE0", "#5FB2FF": "#A996FF",
    "#20C8F5": "#FF5FD2", "#78BEFF": "#FF96E6",
    "#8B4DFF": "#FF9F43", "#9A63FF": "#FFB06A", "#9B5CFF": "#FF8F3A", "#B794FF": "#FFC48A", "#C9B0FF": "#FFD2A8", "#D662FF": "#FF9F43",
    "#6E6EFF": "#B57CFF", "#00BFA6": "#2DE2A6", "#00D6AA": "#2DE2A6", "#7FF0DD": "#9FF5D6",
    "#EAF4FF": "#F3EEFF", "#8FA8C8": "#A99CC9", "#5D7AA0": "#7A6CA3", "#C5D6EE": "#D8CFF0", "#D7E6FA": "#E4DCF7", "#CFE0F5": "#DED5F2",
    "#0A2A6B": "#211A4A", "#1747C9": "#4B2FA8", "#3C5BFF": "#7C5CFF", "#E59BFF": "#FF8FE0", "#FF8A65": "#6E7BFF",
}
RGB = {
    (6, 21, 43): (13, 10, 30), (10, 31, 61): (22, 17, 46), (13, 43, 82): (33, 25, 74),
    (8, 127, 229): (124, 92, 255), (32, 140, 245): (124, 92, 255), (32, 160, 245): (140, 100, 255), (64, 150, 255): (150, 110, 255),
    (32, 200, 245): (255, 95, 210), (120, 190, 255): (255, 150, 230), (139, 77, 255): (255, 159, 67), (214, 98, 255): (255, 159, 67),
    (110, 110, 255): (181, 124, 255), (190, 120, 255): (255, 180, 120), (190, 110, 255): (255, 170, 110), (0, 214, 170): (45, 226, 166),
    (234, 244, 255): (243, 238, 255), (220, 235, 255): (236, 228, 255), (143, 168, 200): (169, 156, 201),
}

def conv(text: str) -> str:
    text = re.sub(r"#[0-9A-Fa-f]{6}\b", lambda m: HEX.get(m.group(0).upper(), m.group(0)), text)
    def rgb(m):
        k = tuple(int(x) for x in m.group(2, 3, 4))
        if k not in RGB:
            return m.group(0)
        sep = ", " if ", " in m.group(0) else ","
        return f"{m.group(1)}{sep.join(map(str, RGB[k]))}"
    text = re.sub(r"(rgba?\()(\d+), ?(\d+), ?(\d+)", rgb, text)
    text = re.sub(r"\[(\d+), (\d+), (\d+)\]", lambda m: str(list(RGB[k])).replace(",", ",") if (k := tuple(map(int, m.groups()))) in RGB else m.group(0), text)
    return text

changed = 0
for p in [*pathlib.Path("src").rglob("*.ts*"), *pathlib.Path("src").rglob("*.css"), pathlib.Path("index.html"), pathlib.Path("public/favicon.svg")]:
    s = p.read_text(); n = conv(s)
    if n != s:
        p.write_text(n); changed += 1
print("archivos actualizados:", changed)
