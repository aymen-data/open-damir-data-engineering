import argparse
import logging
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Open DAMIR : pipeline sur données publiques réelles")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Racine des données et rapports")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ["fetch", "transform", "run"]:
        p = sub.add_parser(command)
        p.add_argument("--months", nargs="+", required=True, help="Exemple : 202501 202502")
        if command in ["fetch", "run"]:
            p.add_argument("--refresh", action="store_true", help="Récupérer une révision de la source")
        if command == "run":
            p.add_argument("--benchmark-rows", type=int, default=1_000_000)
            p.add_argument("--repeats", type=int, default=3)
    sub.add_parser("analyze")
    sub.add_parser("report")
    p = sub.add_parser("benchmark")
    p.add_argument("--rows", type=int, default=1_000_000)
    p.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    os.environ.setdefault("POLARS_MAX_THREADS", "4")
    logs = args.root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(logs / "pipeline.log", encoding="utf-8")])
    from .download import download
    from .pipeline import transform
    from .analysis import analyze
    from .benchmark import benchmark
    from .report import render_report
    try:
        if args.command in ["fetch", "run"]:
            for month in dict.fromkeys(args.months):
                download(args.root, month, args.refresh)
        if args.command in ["transform", "run"]:
            for month in dict.fromkeys(args.months):
                transform(args.root, month)
        if args.command in ["analyze", "run"]:
            logging.info("Analyses SQL DuckDB")
            analyze(args.root)
        if args.command in ["benchmark", "run"]:
            logging.info("Benchmark en processus isolés")
            benchmark(args.root, args.benchmark_rows if args.command == "run" else args.rows, args.repeats)
        if args.command in ["report", "run"]:
            render_report(args.root)
        logging.info("Terminé : %s", args.command)
    except Exception:
        logging.exception("Échec : %s. Consulter les logs ; les fichiers .part/.pending ne sont pas publiés.", args.command)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
