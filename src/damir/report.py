"""Rapport HTML autonome, sans serveur ni dépendance externe."""
import html
import json
from decimal import Decimal
from pathlib import Path


def number(value, decimals=0):
    return f"{Decimal(str(value)):,.{decimals}f}".replace(",", " ").replace(".", ",")


def render_report(root):
    root = Path(root)
    manifests = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((root / "data/manifests").glob("*.json"))]
    if not manifests:
        raise ValueError("Aucun manifeste")
    results = json.loads((root / "reports/analyses/results.json").read_text(encoding="utf-8"))
    benchpath = root / "reports/benchmark.json"
    bench = json.loads(benchpath.read_text(encoding="utf-8")) if benchpath.exists() else None
    quality = [json.loads((root / f"reports/quality/{m['month']}.json").read_text(encoding="utf-8")) for m in manifests]
    rows = sum(m["rows"] for m in manifests)
    csv_bytes = sum(m["csv_bytes"] for m in manifests)
    parquet_bytes = sum(m["parquet_bytes"] for m in manifests)
    monthly = results["01_monthly"]
    total = sum(Decimal(r["remboursement_part_legale_eur"]) for r in monthly)
    periods = ", ".join(m["month"] for m in manifests)
    region_labels = {}
    reference = root / "references/modalites.json"
    labels = json.loads(reference.read_text(encoding="utf-8")) if reference.exists() else {}
    region_labels = labels.get("BEN_RES_REG", {})
    region_totals = {}
    for r in results["02_regions"]:
        code = r["code_region_residence"]
        region_totals[code] = region_totals.get(code, Decimal(0)) + Decimal(r["remboursement_part_legale_eur"])
    top = sorted(region_totals.items(), key=lambda pair: pair[1], reverse=True)[:10]
    largest = max((v for _, v in top), default=Decimal(1)) or Decimal(1)
    bars = "".join(f'<div class="bar-row"><div>{html.escape(region_labels.get(k, "Code " + k))}</div><div class="track"><i style="width:{max(0,float(v/largest)*100):.2f}%"></i></div><strong>{number(v/1_000_000,1)} M€</strong></div>' for k, v in top)
    negative = sum(q["metrics"]["negative_reimbursement_rows"] for q in quality)
    unknown_types = sum(q["metrics"]["unknown_reimbursement_type_rows"] for q in quality)
    missing = sum(q["metrics"]["missing_act_count_rows"] for q in quality)
    unknown = sum(q["metrics"]["region_code_99_rows"] for q in quality)
    bench_table = "<p>Benchmark non exécuté.</p>"
    if bench:
        bench_table = '<p>' + number(bench["rows"]) + ' lignes · 4 colonnes · ' + str(bench["repeats"]) + ' répétitions mesurées · résultats identiques</p><table><thead><tr><th>Méthode</th><th>Médiane</th><th>Min–max</th><th>RSS max.</th></tr></thead><tbody>'
        for row in bench["summary"]:
            bench_table += f'<tr><td>{html.escape(row["mode"])}</td><td>{number(row["median_seconds"],3)} s</td><td>{number(row["min_seconds"],3)}–{number(row["max_seconds"],3)} s</td><td>{number(row["max_rss_mib"],1)} Mio</td></tr>'
        bench_table += '</tbody></table><p class="note">Échantillon technique des premières lignes ; aucune extrapolation statistique. Caches disque non vidés. Imports et création des fichiers exclus. Python utilise un thread, les moteurs jusqu’à quatre. La mémoire est échantillonnée toutes les 10 ms.</p>'
    document = f'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Open DAMIR · Rapport du projet</title>
<style>
:root{{--ink:#172b38;--muted:#56707e;--line:#d9e4e8;--teal:#087f80;--paper:#f1f5f6}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.6 system-ui,sans-serif}}main{{max-width:1120px;margin:0 auto;padding:48px 28px}}header{{border-top:5px solid var(--teal);padding-top:24px;margin-bottom:30px}}.eyebrow{{text-transform:uppercase;letter-spacing:.15em;font-size:12px;font-weight:700;color:var(--teal)}}h1{{font-size:clamp(32px,5vw,52px);line-height:1.1;letter-spacing:-.04em;margin:14px 0}}h2{{font-size:23px;margin:0 0 14px}}p{{margin:10px 0}}.intro{{max-width:800px;color:var(--muted);font-size:18px}}.badge{{display:inline-block;padding:5px 12px;background:#d8eeea;border-radius:20px;font-size:13px}}.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:28px 0}}.card,section{{background:white;border:1px solid var(--line);border-radius:12px;padding:25px}}.card strong{{display:block;font-size:32px;letter-spacing:-.025em}}.card span,.note{{color:var(--muted);font-size:13px}}section{{margin:20px 0}}.flow{{display:flex;flex-wrap:wrap;gap:12px;align-items:center}}.flow b{{background:#ecf4f4;padding:9px 13px;border-radius:6px;font-size:14px}}.bar-row{{display:grid;grid-template-columns:260px 1fr 110px;gap:14px;align-items:center;margin:15px 0;font-size:13px}}.bar-row strong{{text-align:right}}.track{{height:12px;background:#edf3f4;border-radius:3px}}.track i{{display:block;background:var(--teal);height:100%;border-radius:3px}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{padding:13px 9px;border-bottom:1px solid var(--line);text-align:right}}th:first-child,td:first-child{{text-align:left}}th{{font-size:12px;color:var(--muted)}}ul{{padding-left:22px}}a{{color:#096769}}footer{{color:var(--muted);font-size:13px;padding:20px 0}}@media(max-width:700px){{main{{padding:24px 16px}}.cards{{grid-template-columns:1fr}}.bar-row{{grid-template-columns:1fr 85px}}.bar-row .track{{grid-column:1;grid-row:auto}}.bar-row strong{{grid-column:2;grid-row:span 2}}section{{padding:18px;overflow:auto}}table{{font-size:12px}}}}@media print{{body{{background:white}}main{{padding:0}}section,.card{{break-inside:avoid}}}}
</style></head><body><main><header><div class="eyebrow">Portfolio · Data Engineering · Projet 01</div><h1>Des remboursements bruts<br>aux données analysables.</h1><p class="intro">Un pipeline reproductible sur les fichiers publics réels de l’Assurance Maladie, avec contrôles, calculs SQL et mesures de performances.</p><span class="badge">Périodes traitées : {periods} · Source complète pour chaque mois</span></header>
<div class="cards"><div class="card"><span>LIGNES AGRÉGÉES TRAITÉES</span><strong>{number(rows)}</strong><span>Une ligne n’est ni un patient ni un acte individuel.</span></div><div class="card"><span>STOCKAGE PARQUET</span><strong>{number(parquet_bytes/1e9,2)} Go</strong><span>CSV brut : {number(csv_bytes/1e9,2)} Go · ratio CSV/Parquet : {number(csv_bytes/parquet_bytes,2)}×</span></div><div class="card"><span>REMBOURSEMENTS · PART LÉGALE</span><strong>{number(total/1_000_000_000,2)} Md€</strong><span>Somme nette FLT_REM_MNT du périmètre chargé.</span></div></div>
<section><h2>La chaîne de traitement</h2><div class="flow"><b>Source officielle + SHA-256</b><span>→</span><b>Polars · typage et contrôles</b><span>→</span><b>Parquet par mois</b><span>→</span><b>DuckDB · SQL</b></div><p class="note">Partition remplacée après validation. Une relance sur une source et une partition inchangées ne recharge pas les lignes. Les codes sont conservés en texte ; les montants sont stockés en décimal exact.</p></section>
<section><h2>Remboursements par région de résidence</h2><p class="note">Dix codes les plus élevés dans le périmètre chargé · montants nets · aucune correction par population.</p>{bars}<p class="note">Les libellés proviennent du dictionnaire officiel joint. Les codes spéciaux sont conservés.</p></section>
<section><h2>Qualité : rendre les particularités visibles</h2><ul><li><strong>{number(negative)}</strong> lignes avec remboursement préfiltré négatif : conservées, à interpréter avec le contexte de liquidation.</li><li><strong>{number(missing)}</strong> nombres d’actes bruts absents : pas de remplacement arbitraire par zéro.</li><li><strong>{number(unknown)}</strong> lignes avec le code de région 99 : conservées dans les agrégats.</li><li><strong>{number(unknown_types)}</strong> lignes avec type de remboursement inconnu : indicateur FLT conservé, filtre non reconstructible.</li><li>Contrôles bloquants : schéma minimal, conversions, période, colonnes analytiques requises et correspondance du remboursement préfiltré sur les types connus.</li><li>Doublons exacts : diagnostic limité aux 100 000 premières lignes par mois ; aucune suppression automatique.</li></ul><p class="note">Rapports détaillés : dossier <code>quality/</code>. Les contrôles réussis ne constituent pas une certification de la source.</p></section>
<section><h2>Performances mesurées</h2>{bench_table}<p><a href="benchmark.json">Mesures détaillées et environnement</a></p></section>
<section><h2>Ce que ces résultats permettent de dire</h2><p>Le projet démontre l’ingestion d’un fichier volumineux, son typage, son stockage en colonnes et des analyses reproductibles. Les requêtes utilisent les indicateurs préfiltrés du producteur pour éviter certains doubles comptes.</p><p>Les données sont agrégées : elles ne permettent pas de reconstruire un parcours individuel, de compter les patients, ni d’estimer un risque clinique. Le mois de traitement est distinct du mois de soins. Les montants présentés ne couvrent pas nécessairement l’ensemble des dépenses de santé françaises.</p><p><a href="../README.md">Guide du projet</a> · <a href="analyses/results.json">Résultats SQL</a> · <a href="../README.md">Comprendre et présenter le travail</a></p></section>
<footer>Source : <a href="https://www.assurance-maladie.ameli.fr/etudes-et-donnees/open-damir-depenses-sante-interregimes">Assurance Maladie · Open DAMIR</a>. Réutilisation sous Licence ouverte selon la page source. Projet pédagogique indépendant de la DREES et de l’Assurance Maladie.</footer></main></body></html>'''
    (root / "reports/rapport.html").write_text(document, encoding="utf-8")
    summary = f"# Résultats exécutés\n\nPériodes : {periods}.\n\n- Lignes agrégées : {number(rows)}.\n- CSV : {number(csv_bytes/1e9,3)} Go ; Parquet : {number(parquet_bytes/1e9,3)} Go.\n- Remboursements préfiltrés, part légale : {number(total,2)} EUR.\n- Lignes avec remboursement préfiltré négatif : {number(negative)}.\n\nLes sommes concernent exclusivement le périmètre des fichiers chargés. Une ligne n'est pas un patient.\n"
    if bench:
        summary += "\n## Benchmark\n\n" + f"{number(bench['rows'])} lignes, {bench['repeats']} répétitions. Résultats exactement identiques.\n\n| Méthode | Médiane (s) | RSS max (Mio) |\n|---|---:|---:|\n"
        summary += "\n".join(f"| {r['mode']} | {r['median_seconds']:.3f} | {r['max_rss_mib']:.1f} |" for r in bench["summary"])
        summary += "\n\nCaches disque non vidés ; imports exclus ; échantillon technique non représentatif. Voir benchmark.json pour les limites.\n"
    (root / "reports/RESULTATS.md").write_text(summary, encoding="utf-8")
