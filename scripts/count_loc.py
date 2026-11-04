"""Count handwritten application source lines (backend + frontend + config). Run: python scripts/count_loc.py

Counted: backend/*.py, frontend/src/**/*.{js,jsx,css}, frontend/index.html and the frontend config files.
Not counted: tests, scripts, README/docs, notebooks, datasets, node_modules, dist, caches, lock files.
Reports PHYSICAL lines (every line, blank and comment lines included: the strict number) and code lines (no blanks/comments).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    "backend (Python)": sorted((ROOT / "backend").glob("*.py")),
    "frontend (JS/JSX/CSS/HTML)": sorted([*(ROOT / "frontend/src").rglob("*.js"), *(ROOT / "frontend/src").rglob("*.jsx"), *(ROOT / "frontend/src").rglob("*.css"),
                                          ROOT / "frontend/index.html"]),
    "other config (vite/tailwind/postcss)": [ROOT / "frontend" / n for n in ("vite.config.js", "tailwind.config.js", "postcss.config.js")],
}
LIMIT = 3000


def is_code(line: str) -> bool:
    s = line.strip()
    return bool(s) and not s.startswith(("#", "//", "/*", "*", "*/", '"""'))


total_physical = total_code = 0
longest = (0, "")
for group, files in GROUPS.items():
    physical = code = 0
    for f in files:
        lines = f.read_text(encoding="utf-8").splitlines()
        physical += len(lines)
        code += sum(is_code(l) for l in lines)
        for l in lines:
            if len(l) > longest[0]:
                longest = (len(l), f"{f.relative_to(ROOT)}")
        print(f"  {len(lines):5d}  {f.relative_to(ROOT)}") if "-v" in sys.argv else None
    print(f"{group:40s} files={len(files):3d} physical={physical:5d} code={code:5d}")
    total_physical += physical
    total_code += code
print(f"{'TOTAL':40s} physical={total_physical:5d} code={total_code:5d}   limit={LIMIT}   longest line={longest[0]} chars ({longest[1]})")
print("PASS" if total_physical <= LIMIT else "OVER LIMIT", f"(physical lines {total_physical} / {LIMIT})")
sys.exit(0 if total_physical <= LIMIT else 1)
