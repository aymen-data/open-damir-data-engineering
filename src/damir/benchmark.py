"""Même échantillon, même agrégation exacte, processus isolés et ordre alterné."""
import csv
import json
import os
import platform
import random
import statistics
import subprocess
import sys
import threading
import time
from decimal import Decimal
from pathlib import Path

import psutil

from .common import sha256, utcnow, write_json

MODES = ["python_csv", "polars_csv", "polars_parquet", "duckdb_csv", "duckdb_parquet"]
COLS = ["BEN_RES_REG", "PRS_NAT", "FLT_REM_MNT", "FLT_PAI_MNT"]


def worker(folder, mode):
    # Imports hors chronométrage, processus neuf pour chaque répétition.
    if mode.startswith("polars"):
        import polars as pl
    elif mode.startswith("duckdb"):
        import duckdb
    process = psutil.Process()
    peak = [process.memory_info().rss]
    stop = threading.Event()

    def sample_memory():
        while not stop.wait(0.01):
            peak[0] = max(peak[0], process.memory_info().rss)

    thread = threading.Thread(target=sample_memory, daemon=True)
    thread.start()
    started = time.perf_counter()
    folder = Path(folder)
    if mode == "python_csv":
        groups = {}
        with (folder / "sample.csv").open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                key = row["BEN_RES_REG"]
                count, total = groups.get(key, (0, Decimal(0)))
                groups[key] = (count + 1, total + Decimal(row["FLT_REM_MNT"]))
        result = [(key, count, total) for key, (count, total) in groups.items()]
    elif mode.startswith("polars"):
        frame = (pl.scan_parquet(folder / "sample.parquet") if mode.endswith("parquet") else
                 pl.scan_csv(folder / "sample.csv", schema_overrides={
                     "BEN_RES_REG": pl.String, "PRS_NAT": pl.String,
                     "FLT_REM_MNT": pl.Decimal(24, 6), "FLT_PAI_MNT": pl.Decimal(24, 6)}))
        result = (frame.group_by("BEN_RES_REG").agg(pl.len().alias("n"), pl.col("FLT_REM_MNT").sum())
                  .collect(engine="streaming").rows())
    else:
        con = duckdb.connect()
        con.execute("SET threads=4")
        con.execute("SET memory_limit='2GB'")
        if mode.endswith("parquet"):
            relation = con.read_parquet(str(folder / "sample.parquet"))
        else:
            relation = con.read_csv(str(folder / "sample.csv"), header=True, delimiter=",",
                                    dtype={"BEN_RES_REG": "VARCHAR", "PRS_NAT": "VARCHAR",
                                           "FLT_REM_MNT": "DECIMAL(24,6)", "FLT_PAI_MNT": "DECIMAL(24,6)"})
        relation.create_view("sample")
        result = con.execute("SELECT BEN_RES_REG, count(*), sum(FLT_REM_MNT) FROM sample GROUP BY BEN_RES_REG").fetchall()
        con.close()
    canonical = sorted([[str(k), int(n), format(total, ".6f")] for k, n, total in result])
    elapsed = time.perf_counter() - started
    peak[0] = max(peak[0], process.memory_info().rss)
    stop.set()
    thread.join()
    return {"mode": mode, "seconds": elapsed, "peak_rss_mib": peak[0] / 1024**2, "result": canonical}


def benchmark(root, rows=1_000_000, repeats=3):
    import polars as pl
    import duckdb
    if rows < 1 or repeats < 1:
        raise ValueError("rows et repeats doivent être positifs")
    root = Path(root).resolve()
    folder = root / "data/benchmark"
    folder.mkdir(parents=True, exist_ok=True)
    files = sorted((root / "data/curated").glob("month=*/part-000.parquet"))
    if not files:
        raise ValueError("Aucune partition pour le benchmark")
    sample = pl.scan_parquet(files).select(COLS).head(rows).collect(engine="streaming")
    if sample.height == 0 or sample["FLT_REM_MNT"].null_count():
        raise ValueError("Le benchmark exige des remboursements renseignés et des lignes")
    sample.write_csv(folder / "sample.csv")
    sample.write_parquet(folder / "sample.parquet", compression="zstd", compression_level=3)
    sample_rows = sample.height
    del sample
    reference = None
    measurements = []
    environment = os.environ.copy()
    environment["POLARS_MAX_THREADS"] = "4"
    rng = random.Random(42)
    # Une passe d'échauffement par mode, puis répétitions dans un ordre mélangé fixe.
    for repeat in range(-1, repeats):
        order = MODES.copy()
        rng.shuffle(order)
        for mode in order:
            completed = subprocess.run([sys.executable, "-m", "damir.benchmark", str(folder), mode],
                                       check=False, capture_output=True, text=True, env=environment)
            if completed.returncode:
                raise RuntimeError(f"Benchmark {mode} en échec : {completed.stderr}")
            measurement = json.loads(completed.stdout)
            if reference is None:
                reference = measurement["result"]
            if measurement["result"] != reference:
                raise AssertionError(f"Résultats non équivalents pour {mode}")
            if repeat >= 0:
                measurement.pop("result")
                measurement["repeat"] = repeat + 1
                measurements.append(measurement)
    summary = [{"mode": mode,
                "median_seconds": statistics.median(m["seconds"] for m in measurements if m["mode"] == mode),
                "min_seconds": min(m["seconds"] for m in measurements if m["mode"] == mode),
                "max_seconds": max(m["seconds"] for m in measurements if m["mode"] == mode),
                "max_rss_mib": max(m["peak_rss_mib"] for m in measurements if m["mode"] == mode)} for mode in MODES]
    report = {"created_at": utcnow(), "rows": sample_rows, "columns": COLS, "repeats": repeats,
              "scope": "premières lignes des partitions triées ; échantillon technique non représentatif",
              "query": "GROUP BY BEN_RES_REG, COUNT(*), SUM(FLT_REM_MNT)",
              "equivalent_results": True, "reference_result": reference,
              "files": {f: {"bytes": (folder / f).stat().st_size, "sha256": sha256(folder / f)}
                        for f in ["sample.csv", "sample.parquet"]},
              "environment": {"platform": platform.platform(), "python": platform.python_version(),
                              "polars": pl.__version__, "duckdb": duckdb.__version__,
                              "logical_cpus": os.cpu_count(), "threads_per_engine": 4,
                              "ram_gib": psutil.virtual_memory().total / 1024**3},
              "limitations": ["Caches disque non vidés ; mesures après échauffement.",
                              "Imports et préparation des fichiers exclus ; lecture, parsing et agrégation inclus.",
                              "RSS totale du processus échantillonnée toutes les 10 ms ; pic bref possiblement manqué.",
                              "Python CSV mono-thread ; moteurs autorisés à utiliser 4 threads.",
                              "Pas de preuve de traitement au-delà de la RAM ni de calcul distribué."],
              "summary": summary, "measurements": measurements}
    write_json(root / "reports/benchmark.json", report)
    with (root / "reports/benchmark.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    return report


if __name__ == "__main__":
    print(json.dumps(worker(sys.argv[1], sys.argv[2])))
