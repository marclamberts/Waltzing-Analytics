#!/usr/bin/env python3
"""Run the established Opta game-report notebook for Tunisia vs Japan."""

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NOTEBOOK = Path("/Users/marclamberts/Event data/Game_Report_Combined.ipynb")
SOURCE_DIR = Path("/Users/marclamberts/Event data/WC 2026/NEW")
MODEL_DIR = Path("/Users/marclamberts/Event data/xg_output")
REPORT_ROOT = ROOT / "output" / "postmatch"
MATCH_FILE = "2026-06-20_Tunisia - Japan.json"

sys.path.insert(0, str(ROOT / ".python_packages"))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "tmp" / "matplotlib"))

import matplotlib
matplotlib.use("Agg")


def notebook_source():
    notebook = json.loads(NOTEBOOK.read_text())
    source = "".join(notebook["cells"][0]["source"])
    replacements = {
        "JSON_DIR   = '/Users/user/XG/WC 2026'": f"JSON_DIR   = {str(SOURCE_DIR)!r}",
        "MODEL_DIR  = '/Users/user/Downloads/Danger Model/xg_output'": f"MODEL_DIR  = {str(MODEL_DIR)!r}",
        "OUT_DIR    = '/Users/user/XG/WC 2026/reports'": f"OUT_DIR    = {str(REPORT_ROOT)!r}",
        "ONLY_FILES = []": f"ONLY_FILES = [{MATCH_FILE!r}]",
        "DPI = 150": "DPI = 110",
    }
    for old, new in replacements.items():
        source = source.replace(old, new, 1)
    source = re.sub(r"^%matplotlib inline\s*$", "", source, flags=re.MULTILINE)
    source = source.replace("plt.show(); plt.close()", "plt.close()")
    source = source.replace("plt.show()\n", "")
    return source


if __name__ == "__main__":
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    code = compile(notebook_source(), str(NOTEBOOK), "exec")
    exec(code, globals(), globals())
