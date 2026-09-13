import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def validate_month(month):
    if len(month) != 6 or not month.isdigit():
        raise ValueError("Mois attendu au format AAAAMM")
    datetime.strptime(month, "%Y%m")
    if int(month[:4]) < 2015:
        raise ValueError("Cette version prend en charge les fichiers A, à partir de 2015")
    return month
