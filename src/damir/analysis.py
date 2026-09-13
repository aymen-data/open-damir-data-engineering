"""Analyses SQL sur les indicateurs préfiltrés, avec libellés officiels si disponibles."""
import csv
import json
from pathlib import Path

import duckdb

from .common import write_json


def sql_string(value):
    return "'" + str(value).replace("'", "''") + "'"


def connect(root):
    root = Path(root).resolve()
    if not list((root / "data/curated").glob("month=*/part-000.parquet")):
        raise ValueError("Aucune partition publiée")
    con = duckdb.connect()
    con.execute("SET threads=4")
    con.execute("SET memory_limit='2GB'")
    temp = root / "data/duckdb_tmp"
    temp.mkdir(parents=True, exist_ok=True)
    con.execute(f"SET temp_directory={sql_string(temp.as_posix())}")
    pattern = (root / "data/curated/month=*/part-000.parquet").as_posix()
    con.execute(f"CREATE VIEW remboursements AS SELECT * FROM read_parquet({sql_string(pattern)}, union_by_name=true, hive_partitioning=false)")
    con.execute("CREATE TEMP TABLE nomenclatures(variable VARCHAR, code VARCHAR, libelle VARCHAR, PRIMARY KEY(variable, code))")
    reference = root / "references/modalites.json"
    if reference.exists():
        labels = json.loads(reference.read_text(encoding="utf-8"))
        values = [(variable, code, label) for variable, mapping in labels.items() for code, label in mapping.items()]
        if values:
            con.executemany("INSERT INTO nomenclatures VALUES (?, ?, ?)", values)
    return con


def analyze(root):
    root = Path(root)
    output = root / "reports/analyses"
    output.mkdir(parents=True, exist_ok=True)
    sql_dir = Path(__file__).parent / "sql"
    con = connect(root)
    try:
        queries = sorted(sql_dir.glob("*.sql"))
        results = {}
        for file in queries:
            cursor = con.execute(file.read_text(encoding="utf-8"))
            columns = [c[0] for c in cursor.description]
            rows = cursor.fetchall()
            with (output / f"{file.stem}.csv").open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(columns)
                writer.writerows(rows)
            results[file.stem] = [dict(zip(columns, row)) for row in rows]
        write_json(output / "results.json", results)
        return results
    finally:
        con.close()
