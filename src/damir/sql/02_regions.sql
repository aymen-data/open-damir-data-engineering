SELECT FLX_ANN_MOI AS mois_traitement, BEN_RES_REG AS code_region_residence,
       count(*) AS lignes_agregees,
       sum(FLT_REM_MNT) AS remboursement_part_legale_eur,
       sum(FLT_PAI_MNT) AS depense_prefiltree_eur
FROM remboursements
GROUP BY FLX_ANN_MOI, BEN_RES_REG
ORDER BY mois_traitement, remboursement_part_legale_eur DESC;
