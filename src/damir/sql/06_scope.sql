-- TOP_PS5_TRG=1 est le périmètre de la statistique mensuelle décrit dans le dictionnaire.
SELECT FLX_ANN_MOI AS mois_traitement, TOP_PS5_TRG AS top_perimetre,
       count(*) AS lignes_agregees,
       sum(FLT_REM_MNT) AS remboursement_part_legale_eur,
       sum(FLT_PAI_MNT) AS depense_prefiltree_eur
FROM remboursements GROUP BY FLX_ANN_MOI, TOP_PS5_TRG
ORDER BY mois_traitement, top_perimetre;
