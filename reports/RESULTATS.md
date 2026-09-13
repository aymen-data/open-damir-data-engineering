# Résultats exécutés

Périodes : 202501.

- Lignes agrégées : 36 640 259.
- CSV : 5,921 Go ; Parquet : 1,067 Go.
- Remboursements préfiltrés, part légale : 13 342 058 546,16 EUR.
- Lignes avec remboursement préfiltré négatif : 5 600 345.

Les sommes concernent exclusivement le périmètre des fichiers chargés. Une ligne n'est pas un patient.

## Benchmark

1 000 000 lignes, 3 répétitions. Résultats exactement identiques.

| Méthode | Médiane (s) | RSS max (Mio) |
|---|---:|---:|
| python_csv | 1.514 | 20.4 |
| polars_csv | 0.046 | 97.3 |
| polars_parquet | 0.020 | 92.0 |
| duckdb_csv | 0.373 | 74.9 |
| duckdb_parquet | 0.029 | 47.8 |

Caches disque non vidés ; imports exclus ; échantillon technique non représentatif. Voir benchmark.json pour les limites.
