SELECT FLX_ANN_MOI AS mois_traitement, PRS_NAT AS code_prestation,
       sum(FLT_REM_MNT) AS remboursement_part_legale_eur,
       sum(FLT_ACT_QTE) AS quantite_prefiltree
FROM remboursements
GROUP BY FLX_ANN_MOI, PRS_NAT
ORDER BY mois_traitement, remboursement_part_legale_eur DESC;
