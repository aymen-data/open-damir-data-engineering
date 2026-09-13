"""Transformation progressive, conservation des codes et contrôles avant publication."""
import csv
import gzip
import json
import logging
import os
import time
from pathlib import Path

import polars as pl

from .common import sha256, utcnow, validate_month, write_json

LOG = logging.getLogger(__name__)
PIPELINE_VERSION = "3"
KNOWN_REM_TYPES = ["0", "1", "2", "3", "4", "5", "6", "7", "10", "11", "12", "13"]
MONEY = ["PRS_DEP_MNT", "PRS_PAI_MNT", "PRS_REM_BSE", "PRS_REM_MNT",
         "FLT_PAI_MNT", "FLT_DEP_MNT", "FLT_REM_MNT"]
VOLUMES = ["PRS_ACT_COG", "PRS_ACT_NBR", "PRS_ACT_QTE", "FLT_ACT_COG", "FLT_ACT_NBR", "FLT_ACT_QTE"]
NUMERIC = MONEY + VOLUMES + ["PRS_REM_TAU"]
REQUIRED = ["FLX_ANN_MOI", "BEN_RES_REG", "AGE_BEN_SNDS", "BEN_SEX_COD",
            "PRS_NAT", "PRS_REM_TYP", "SOI_ANN", "SOI_MOI", "TOP_PS5_TRG", *NUMERIC]
DECIMAL = pl.Decimal(precision=24, scale=6)


def csv_scan(path):
    # Tous les codes restent des chaînes : les zéros et modalités 99 sont conservés.
    return pl.scan_csv(path, separator=";", infer_schema=False, encoding="utf8",
                       null_values=[""], raise_if_empty=True)


def cleaned_scan(path):
    frame = csv_scan(path)
    return clean_frame(frame)


def clean_frame(frame):
    names = frame.collect_schema().names()
    missing = sorted(set(REQUIRED) - set(names))
    if missing:
        raise ValueError(f"Colonnes obligatoires absentes : {missing}")
    # Le CSV officiel a un séparateur terminal : sa colonne sans nom doit être vide.
    empty_column = "" if "" in names else "__empty_column__" if "__empty_column__" in names else None
    if empty_column is not None:
        count = frame.select(pl.col(empty_column).is_not_null().sum()).collect(engine="streaming").item()
        if count:
            raise ValueError("Colonne sans nom non vide : dérive de structure")
        frame = frame.drop(empty_column)
        names.remove(empty_column)
    frame = frame.with_columns(pl.col(pl.String).str.strip_chars().replace("", None))
    # Une valeur numérique illisible provoque un arrêt ; aucune coercition silencieuse.
    expressions = []
    for name in NUMERIC:
        text = pl.col(name).str.replace_all(",", ".", literal=True)
        valid = text.str.contains(r"^[+-]?(?:\d+(?:\.\d{0,6})?|\.\d{1,6})$") | text.is_null()
        expressions.append(pl.when(valid).then(text).otherwise(pl.lit("INVALID_NUMBER_OR_PRECISION"))
                           .cast(DECIMAL, strict=True).alias(name))
    frame = frame.with_columns(expressions)
    return frame, names


def convert_batches(csv_path, candidate):
    import pyarrow as pa
    import pyarrow.csv as pacsv
    import pyarrow.parquet as pq
    with Path(csv_path).open(encoding="utf-8", newline="") as stream:
        header = next(csv.reader(stream, delimiter=";"))
    if len(set(header)) != len(header):
        raise ValueError("Noms de colonnes dupliqués")
    if "__empty_column__" in header:
        raise ValueError("Nom de colonne réservé au parseur")
    reader = pacsv.open_csv(csv_path, read_options=pacsv.ReadOptions(block_size=8 * 1024 * 1024),
                           parse_options=pacsv.ParseOptions(delimiter=";"),
                           convert_options=pacsv.ConvertOptions(column_types={c: pa.string() for c in header},
                                                                strings_can_be_null=True, null_values=[""]))
    writer = None
    total = 0
    last_log = time.monotonic()
    try:
        for batch in reader:
            batch = batch.rename_columns([name or "__empty_column__" for name in header])
            frame, columns = clean_frame(pl.from_arrow(batch).lazy())
            clean = frame.collect()
            table = clean.to_arrow()
            if writer is None:
                writer = pq.ParquetWriter(candidate, table.schema, compression="zstd", compression_level=3)
            writer.write_table(table, row_group_size=131_072)
            total += clean.height
            if time.monotonic() - last_log > 15:
                LOG.info("Conversion par blocs : %s lignes", total)
                last_log = time.monotonic()
        if writer is None:
            raise ValueError("Fichier sans données")
    finally:
        reader.close()
        if writer is not None:
            writer.close()
    return columns


def quality(path, month):
    frame = pl.scan_parquet(path)
    columns = frame.collect_schema().names()
    metrics = [pl.len().alias("rows"),
               (pl.col("FLX_ANN_MOI").is_null() | (pl.col("FLX_ANN_MOI") != month)).sum().alias("wrong_month"),
               pl.col("FLT_REM_MNT").lt(0).sum().alias("negative_reimbursement_rows"),
               pl.col("FLT_PAI_MNT").lt(0).sum().alias("negative_expense_rows"),
               pl.col("BEN_RES_REG").eq("99").sum().alias("region_code_99_rows"),
               pl.col("AGE_BEN_SNDS").eq("99").sum().alias("age_code_99_rows"),
               pl.col("PRS_ACT_NBR").is_null().sum().alias("missing_act_count_rows"),
               pl.col("PRS_REM_TYP").eq("99").sum().alias("unknown_reimbursement_type_rows"),
               (~pl.col("PRS_REM_TYP").fill_null("").is_in(KNOWN_REM_TYPES + ["99"])).sum().alias("unexpected_reimbursement_type_rows"),
               (~pl.col("SOI_MOI").fill_null("").str.contains(r"^(0?[1-9]|1[0-2])$")).sum().alias("unusual_care_month_rows"),
               *[pl.col(c).is_null().sum().alias(f"null__{c}") for c in columns],
               *[pl.col(c).sum().alias(f"sum__{c}") for c in MONEY],
               # Le dictionnaire fournit des indicateurs FLT préfiltrés : contrôle indépendant.
               (pl.col("PRS_REM_TYP").is_in(KNOWN_REM_TYPES) & (pl.col("FLT_REM_MNT").fill_null(0) !=
                pl.when(pl.col("PRS_REM_TYP").is_in(["0", "1"]))
                .then(pl.col("PRS_REM_MNT").fill_null(0)).otherwise(pl.lit(0)))).sum().alias("filtered_reimbursement_mismatch_rows")]
    values = frame.select(metrics).collect(engine="streaming").to_dicts()[0]
    sample = frame.head(100_000).collect(engine="streaming")
    # Purement diagnostique : pas d'identifiant de patient ni de clé métier déclarée.
    values["duplicate_audit"] = {"scope": "premières 100000 lignes au maximum", "rows": sample.height,
                                 "exact_duplicate_excess": sample.height - sample.unique().height,
                                 "action": "aucune suppression automatique"}
    errors = []
    if not values["rows"]:
        errors.append("Fichier sans ligne")
    if values["wrong_month"]:
        errors.append("Période absente ou incompatible avec le fichier")
    for c in ["FLT_REM_MNT", "FLT_PAI_MNT", "PRS_NAT", "BEN_RES_REG"]:
        if values[f"null__{c}"]:
            errors.append(f"Valeurs manquantes dans une colonne analytique requise : {c}")
    if values["filtered_reimbursement_mismatch_rows"]:
        errors.append("Incohérence FLT_REM_MNT avec le filtre légal du dictionnaire")
    if values["unexpected_reimbursement_type_rows"]:
        errors.append("Type de remboursement absent de la nomenclature validée")
    return {"checked_at": utcnow(), "month": month, "status": "failed" if errors else "passed",
            "blocking_errors": errors, "metrics": values,
            "policy": "Négatifs, valeurs inconnues et nombres d'actes absents conservés et décrits ; pas d'imputation."}


def decompress(archive, target):
    started = time.monotonic()
    tmp = target.with_suffix(".csv.part")
    # La lecture jusqu'au bout vérifie aussi le CRC gzip.
    with gzip.open(archive, "rb") as source, tmp.open("wb") as destination:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
            destination.write(block)
    os.replace(tmp, target)
    LOG.info("Décompression : %.1f Go en %.1f s", target.stat().st_size / 1e9, time.monotonic() - started)


def transform(root, month):
    validate_month(month)
    root = Path(root)
    archive = root / f"data/raw/A{month}.csv.gz"
    metadata_path = archive.with_suffix(archive.suffix + ".json")
    if not archive.exists() or not metadata_path.exists():
        raise ValueError("Archive et manifeste requis : exécuter fetch d'abord")
    source_meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    digest = sha256(archive)
    if digest != source_meta["sha256"]:
        raise ValueError("SHA-256 de l'archive incorrect")
    partition = root / f"data/curated/month={month}"
    partition.mkdir(parents=True, exist_ok=True)
    output = partition / "part-000.parquet"
    manifest_path = root / f"data/manifests/{month}.json"
    quality_path = root / f"reports/quality/{month}.json"
    if output.exists() and manifest_path.exists() and quality_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (previous["source_sha256"] == digest and previous["pipeline_version"] == PIPELINE_VERSION
                and sha256(output) == previous["parquet_sha256"]):
            LOG.info("Partition %s déjà vérifiée : aucune duplication", month)
            return previous
    csv_path = root / f"data/raw/A{month}.csv"
    # Toujours recréer le CSV depuis l'archive vérifiée si une transformation est nécessaire.
    decompress(archive, csv_path)
    started = time.monotonic()
    candidate = partition / "part-000.parquet.pending"
    LOG.info("Conversion Polars par blocs Arrow de %s", month)
    columns = convert_batches(csv_path, candidate)
    transform_seconds = time.monotonic() - started
    LOG.info("Contrôles sur le Parquet candidat")
    report = quality(candidate, month)
    if report["status"] != "passed":
        write_json(root / f"reports/quality/{month}.failed.json", report)
        raise ValueError(f"Qualité bloquante : {report['blocking_errors']}. Ancienne partition conservée.")
    parquet_digest = sha256(candidate)
    os.replace(candidate, output)
    write_json(quality_path, report)
    metadata = {"month": month, "pipeline_version": PIPELINE_VERSION, "source_sha256": digest,
                "parquet_sha256": parquet_digest, "source_columns": columns, "rows": report["metrics"]["rows"],
                "csv_bytes": csv_path.stat().st_size, "gzip_bytes": archive.stat().st_size,
                "parquet_bytes": output.stat().st_size, "transform_seconds": round(transform_seconds, 3),
                "completed_at": utcnow(), "polars_version": pl.__version__}
    write_json(manifest_path, metadata)
    LOG.info("Partition publiée : %s lignes", metadata["rows"])
    return metadata
