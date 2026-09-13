-- AGE_BEN_SNDS désigne une classe, pas un âge individuel ; 99 est conservé.
SELECT FLX_ANN_MOI AS mois_traitement, AGE_BEN_SNDS AS code_tranche_age,
       sum(FLT_REM_MNT) AS remboursement_part_legale_eur,
       count(*) AS lignes_agregees
FROM remboursements GROUP BY FLX_ANN_MOI, AGE_BEN_SNDS
ORDER BY mois_traitement, code_tranche_age;
