"""Régénère les JSON depuis le classeur officiel joint (pip install openpyxl==3.1.5)."""
import json
from pathlib import Path

import openpyxl

root = Path(__file__).resolve().parents[1] / "references"
workbook = openpyxl.load_workbook(root / "dictionnaire-officiel.xlsx", read_only=True, data_only=True)
definitions = {str(r[0]).strip(): {"label": r[1], "category": r[2], "comment": r[3]}
               for r in list(workbook["OPEN DAMIR"].values)[4:] if r[0]}
modalities = {}
current = None
for row in workbook["MOD OPEN DAMIR"].values:
    code, label = row[:2]
    if isinstance(code, str) and code.strip() in definitions:
        current = code.strip()
        modalities[current] = {}
    elif current is not None and code is not None:
        modalities[current][str(code).strip()] = str(label or "").strip()
for filename, content in [("variables.json", definitions), ("modalites.json", modalities)]:
    (root / filename).write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"{len(definitions)} définitions, {len(modalities)} nomenclatures")
