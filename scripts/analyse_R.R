# Complément pédagogique : agrégation de remboursements en R via DuckDB.
# Installer une fois : install.packages(c("DBI", "duckdb"))
# Depuis la racine : Rscript scripts/analyse_R.R
# Dans RStudio : ouvrir le projet puis source("scripts/analyse_R.R")
# Statut initial : fourni, non exécuté ici (R absent).
if (!requireNamespace("DBI", quietly = TRUE) || !requireNamespace("duckdb", quietly = TRUE)) {
  stop("Installer DBI et duckdb : install.packages(c('DBI', 'duckdb'))")
}
run_analysis <- function() {
  args <- commandArgs(trailingOnly = TRUE)
  root <- normalizePath(if (length(args)) args[1] else ".", winslash = "/", mustWork = TRUE)
  con <- DBI::dbConnect(duckdb::duckdb())
  on.exit(DBI::dbDisconnect(con, shutdown = TRUE), add = TRUE)
  DBI::dbExecute(con, "SET threads=4")
  DBI::dbExecute(con, "SET memory_limit='2GB'")
  pattern <- paste0(root, "/data/curated/month=*/part-000.parquet")
  query <- paste0(
    "SELECT FLX_ANN_MOI AS mois_traitement, BEN_RES_REG AS code_region_residence, ",
    "CAST(SUM(FLT_REM_MNT) AS VARCHAR) AS remboursement_part_legale_eur ",
    "FROM read_parquet(", DBI::dbQuoteString(con, pattern), ", hive_partitioning=false) ",
    "GROUP BY FLX_ANN_MOI, BEN_RES_REG ORDER BY FLX_ANN_MOI, BEN_RES_REG"
  )
  result <- DBI::dbGetQuery(con, query)
  expected <- read.csv(file.path(root, "reports/analyses/02_regions.csv"), colClasses = "character")
  joined <- merge(result, expected, by = c("mois_traitement", "code_region_residence"), suffixes = c("_r", "_python"))
  if (nrow(joined) != nrow(result) || nrow(joined) != nrow(expected)) stop("Groupes différents")
  # Comparaison pédagogique en double à 0,01 EUR près ; calcul SQL fait en DECIMAL.
  difference <- abs(as.numeric(joined$remboursement_part_legale_eur_r) - as.numeric(joined$remboursement_part_legale_eur_python))
  if (anyNA(difference) || any(difference > 0.01)) stop("Résultats différents")
  write.csv(result, file.path(root, "reports/analyses/regions_R.csv"), row.names = FALSE)
  message("Résultats R concordants avec la requête Python/DuckDB à 0,01 EUR près.")
  print(result)
}
run_analysis()
