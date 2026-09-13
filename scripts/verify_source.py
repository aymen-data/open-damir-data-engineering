"""Contrôle indépendant CSV → Parquet avec DuckDB, sans réutiliser le nettoyage Polars."""
import argparse
import json
from pathlib import Path

import duckdb

from damir.common import utcnow, write_json
from damir.pipeline import MONEY

parser = argparse.ArgumentParser()
parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
args = parser.parse_args()
con = duckdb.connect()
con.execute("SET threads=4")
con.execute("SET memory_limit='2GB'")
results = []
for path in sorted((args.root / "data/manifests").glob("*.json")):
    metadata = json.loads(path.read_text(encoding="utf-8"))
    month = metadata["month"]
    csv_path = args.root / f"data/raw/A{month}.csv"
    parquet_path = args.root / f"data/curated/month={month}/part-000.parquet"
    raw_sums = ", ".join(f"sum(CAST(replace(trim({c}), ',', '.') AS DECIMAL(24,6)))" for c in MONEY)
    clean_sums = ", ".join(f"sum({c})" for c in MONEY)
    raw = con.execute(f"SELECT count(*), {raw_sums} FROM read_csv(?, delim=';', header=true, all_varchar=true)", [str(csv_path)]).fetchone()
    clean = con.execute(f"SELECT count(*), {clean_sums} FROM read_parquet(?)", [str(parquet_path)]).fetchone()
    if raw != clean or raw[0] != metadata["rows"]:
        raise AssertionError(f"Conservation des lignes/montants incorrecte : {month}")
    results.append({"month": month, "rows": raw[0], "equal": True,
                    "sums": dict(zip(MONEY, raw[1:]))})
con.close()
if not results:
    raise ValueError("Aucun manifeste publié")
write_json(args.root / "reports/source_verification.json", {
    "checked_at": utcnow(), "method": "DuckDB lit indépendamment CSV brut et Parquet, compte les lignes et compare exactement sept sommes monétaires",
    "results": results,
})
print(json.dumps(results, default=str))
