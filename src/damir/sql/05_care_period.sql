-- Année/mois de soins distincts du mois de traitement/remboursement.
SELECT FLX_ANN_MOI AS mois_traitement, SOI_ANN AS annee_soins, SOI_MOI AS mois_soins,
       sum(FLT_REM_MNT) AS remboursement_part_legale_eur
FROM remboursements GROUP BY FLX_ANN_MOI, SOI_ANN, SOI_MOI
ORDER BY mois_traitement, annee_soins, mois_soins;
