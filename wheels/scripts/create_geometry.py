import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.geometry_tools import ensure_directory

GEOMETRY_DIR = ROOT / "wheels" / "geometries"
OUTPUT_DIR = ROOT / "wheels" / "outputs"
FIGURE_DIR = ROOT / "wheels" / "figures"
GEOMETRY_FILE = GEOMETRY_DIR / "wheels_geometry.txt"

GEOMETRY_TEMPLATE = """\
Wheels geometry placeholder
===========================

Replace this file with generated geometry content for the wheels study.
"""


def main() -> None:
    for directory in (GEOMETRY_DIR, OUTPUT_DIR, FIGURE_DIR):
        ensure_directory(directory)

    if not GEOMETRY_FILE.exists():
        GEOMETRY_FILE.write_text(GEOMETRY_TEMPLATE, encoding="utf-8")
        print(f"Created {GEOMETRY_FILE.relative_to(ROOT)}")
    else:
        print(f"Keeping existing {GEOMETRY_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
