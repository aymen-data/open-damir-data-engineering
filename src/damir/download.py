"""Téléchargement par session officielle, sans jeton figé ni contournement d'accès."""
import html
import json
import logging
import os
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

from .common import sha256, utcnow, validate_month, write_json

SOURCE_PAGE = "https://www.assurance-maladie.ameli.fr/etudes-et-donnees/open-damir-depenses-sante-interregimes"
BASE = "https://open-data-assurance-maladie.ameli.fr/depenses/"
LOG = logging.getLogger(__name__)


def download(root, month, refresh=False):
    validate_month(month)
    folder = Path(root) / "data/raw"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"A{month}.csv.gz"
    metadata_path = target.with_suffix(target.suffix + ".json")
    if target.exists() and metadata_path.exists() and not refresh:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if sha256(target) != metadata["sha256"]:
            raise ValueError("Archive locale modifiée : utiliser --refresh pour la remplacer")
        LOG.info("Archive vérifiée, téléchargement ignoré : %s", target.name)
        return target
    listing = BASE + f"download.php?Annee={month[:4]}&Dir_Rep=Open_DAMIR"
    with requests.Session() as session:
        session.headers["User-Agent"] = "OpenDamirEducationalPipeline/0.1"
        response = session.get(listing, timeout=(20, 90))
        response.raise_for_status()
        links = re.findall(r"href=[\"']([^\"']+)", response.text)
        matches = [html.unescape(link) for link in links if f"A{month}.csv.gz" in link]
        if len(matches) != 1:
            raise ValueError(f"Fichier absent ou ambigu dans le catalogue officiel : {month}")
        url = urljoin(listing, matches[0])
        if urlparse(url).hostname != urlparse(BASE).hostname:
            raise ValueError("Hôte inattendu dans le catalogue")
        partial = target.with_suffix(target.suffix + ".part")
        started = last_log = time.monotonic()
        received = 0
        with session.get(url, stream=True, timeout=(20, 120)) as response:
            response.raise_for_status()
            expected = int(response.headers.get("Content-Length", 0))
            with partial.open("wb") as stream:
                for block in response.iter_content(4 * 1024 * 1024):
                    if not block:
                        continue
                    if received == 0 and block[:2] != b"\x1f\x8b":
                        raise ValueError("Le serveur n'a pas fourni un gzip. Réessayer plus tard via le catalogue officiel.")
                    stream.write(block)
                    received += len(block)
                    if time.monotonic() - last_log > 10:
                        LOG.info("Téléchargement %s : %.0f / %.0f Mo", month, received / 1e6, expected / 1e6)
                        last_log = time.monotonic()
        if received == 0 or (expected and received != expected):
            raise ValueError("Téléchargement incomplet ; fichier .part non publié")
        digest = sha256(partial)
        os.replace(partial, target)
        write_json(metadata_path, {
            "source_page": SOURCE_PAGE, "catalogue_url": listing,
            "filename": target.name, "month": month, "downloaded_at": utcnow(),
            "bytes": received, "sha256": digest,
            "seconds": round(time.monotonic() - started, 3),
            "scope": "fichier mensuel complet officiel", "license": "Licence ouverte (voir source)",
        })
    LOG.info("Archive enregistrée : %s", target)
    return target


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("month")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    download(args.root, args.month)
