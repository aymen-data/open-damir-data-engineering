import csv
import gzip
import json
from decimal import Decimal

import polars as pl
import pytest

from damir.analysis import analyze
from damir.benchmark import benchmark
from damir.common import sha256, validate_month, write_json
from damir.pipeline import NUMERIC, REQUIRED, cleaned_scan, transform


def row(**overrides):
    value = dict.fromkeys(REQUIRED, "0")
    value.update(FLX_ANN_MOI="202501", BEN_RES_REG="11", AGE_BEN_SNDS="30", BEN_SEX_COD="1",
                 PRS_NAT="0011", PRS_REM_TYP="0", SOI_ANN="2024", SOI_MOI="12", TOP_PS5_TRG="1",
                 FLT_REM_MNT="10.20", PRS_REM_MNT="10.20", FLT_PAI_MNT="15.50")
    value.update(overrides)
    return value


def source(root, rows):
    folder = root / "data/raw"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "A202501.csv.gz"
    with gzip.open(path, "wt", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[*REQUIRED, ""], delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    write_json(path.with_suffix(path.suffix + ".json"), {"sha256": sha256(path)})
    return path


@pytest.mark.parametrize("month", ["202500", "202513", "../202501", "20251", "201401"])
def test_invalid_month(month):
    with pytest.raises(ValueError):
        validate_month(month)


def test_round_trip_exact_money_negative_null_and_codes(tmp_path):
    source(tmp_path, [row(), row(FLT_REM_MNT="-.20", PRS_REM_MNT="-.20", PRS_ACT_NBR="", BEN_RES_REG="99")])
    meta = transform(tmp_path, "202501")
    assert meta["rows"] == 2
    data = pl.read_parquet(tmp_path / "data/curated/month=202501/part-000.parquet")
    assert data["FLT_REM_MNT"].sum() == Decimal("10.00")
    assert data["PRS_NAT"].to_list() == ["0011", "0011"]
    assert data["PRS_ACT_NBR"].null_count() == 1
    assert set(data.columns) == set(REQUIRED)
    report = json.loads((tmp_path / "reports/quality/202501.json").read_text())
    assert report["metrics"]["negative_reimbursement_rows"] == 1
    assert report["status"] == "passed"


def test_replay_does_not_duplicate_or_rewrite(tmp_path):
    source(tmp_path, [row()])
    first = transform(tmp_path, "202501")
    output = tmp_path / "data/curated/month=202501/part-000.parquet"
    before = output.stat().st_mtime_ns
    second = transform(tmp_path, "202501")
    assert first == second
    assert output.stat().st_mtime_ns == before


def test_failed_revision_preserves_previous_partition(tmp_path):
    source(tmp_path, [row()])
    transform(tmp_path, "202501")
    output = tmp_path / "data/curated/month=202501/part-000.parquet"
    before = sha256(output)
    source(tmp_path, [row(FLX_ANN_MOI="202502")])
    with pytest.raises(ValueError, match="Qualité bloquante"):
        transform(tmp_path, "202501")
    assert sha256(output) == before


def test_bad_number_not_silently_discarded(tmp_path):
    source(tmp_path, [row(FLT_REM_MNT="erreur")])
    with pytest.raises(pl.exceptions.InvalidOperationError):
        transform(tmp_path, "202501")
    assert not (tmp_path / "data/curated/month=202501/part-000.parquet").exists()


def test_excess_precision_rejected_instead_of_truncated(tmp_path):
    source(tmp_path, [row(FLT_REM_MNT="0.1234567")])
    with pytest.raises(pl.exceptions.InvalidOperationError):
        transform(tmp_path, "202501")


def test_decimal_comma_and_spaces(tmp_path):
    source(tmp_path, [row(FLT_REM_MNT=" 10,20 ", PRS_REM_MNT=" 10,20 ")])
    meta = transform(tmp_path, "202501")
    assert meta["rows"] == 1


def test_missing_column_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("FLX_ANN_MOI;BEN_RES_REG\n202501;11\n")
    with pytest.raises(ValueError, match="Colonnes obligatoires"):
        cleaned_scan(path)


def test_modified_archive_rejected(tmp_path):
    path = source(tmp_path, [row()])
    with path.open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(ValueError, match="SHA-256"):
        transform(tmp_path, "202501")


def test_prefilter_mapping_is_checked(tmp_path):
    source(tmp_path, [row(PRS_REM_TYP="5")])
    with pytest.raises(ValueError, match="Qualité bloquante"):
        transform(tmp_path, "202501")


def test_unknown_type_preserves_published_filtered_indicator(tmp_path):
    source(tmp_path, [row(PRS_REM_TYP="99", PRS_REM_MNT="11", FLT_REM_MNT="10")])
    transform(tmp_path, "202501")
    report = json.loads((tmp_path / "reports/quality/202501.json").read_text())
    assert report["metrics"]["unknown_reimbursement_type_rows"] == 1
    assert report["metrics"]["filtered_reimbursement_mismatch_rows"] == 0


def test_unknown_new_type_blocks(tmp_path):
    source(tmp_path, [row(PRS_REM_TYP="999")])
    with pytest.raises(ValueError, match="Qualité bloquante"):
        transform(tmp_path, "202501")


def test_sql_uses_prefiltered_amounts(tmp_path):
    source(tmp_path, [row(), row(PRS_REM_TYP="5", PRS_REM_MNT="3", FLT_REM_MNT="0", FLT_PAI_MNT="0")])
    transform(tmp_path, "202501")
    results = analyze(tmp_path)
    assert results["01_monthly"][0]["remboursement_part_legale_eur"] == Decimal("10.20")
    assert results["01_monthly"][0]["lignes_agregees"] == 2
    assert results["07_prestations_labels"][0]["libelle_prestation"] == "Libellé non disponible"


def test_sql_left_join_preserves_totals(tmp_path):
    source(tmp_path, [row(), row(PRS_NAT="0099")])
    transform(tmp_path, "202501")
    write_json(tmp_path / "references/modalites.json", {"PRS_NAT": {"0011": "Exemple fictif"}})
    results = analyze(tmp_path)["07_prestations_labels"]
    assert len(results) == 2
    assert sum(r["remboursement_part_legale_eur"] for r in results) == Decimal("20.40")
    assert {r["libelle_prestation"] for r in results} == {"Exemple fictif", "Libellé non disponible"}


def test_benchmark_engine_equivalence(tmp_path, monkeypatch):
    from pathlib import Path
    import os
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[1] / "src") + os.pathsep + os.environ.get("PYTHONPATH", ""))
    source(tmp_path, [row(), row(BEN_RES_REG="99", FLT_REM_MNT="-1.25", PRS_REM_MNT="-1.25")])
    transform(tmp_path, "202501")
    result = benchmark(tmp_path, rows=10, repeats=1)
    assert result["rows"] == 2
    assert result["equivalent_results"]
    assert len(result["measurements"]) == 5


def test_report_renders_exact_decimal_results(tmp_path):
    from damir.report import render_report
    source(tmp_path, [row()])
    transform(tmp_path, "202501")
    analyze(tmp_path)
    render_report(tmp_path)
    assert (tmp_path / "reports/rapport.html").read_text(encoding="utf-8").startswith("<!doctype html>")
    assert "10,20 EUR" in (tmp_path / "reports/RESULTATS.md").read_text(encoding="utf-8")
