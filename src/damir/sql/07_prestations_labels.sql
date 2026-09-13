-- Agréger avant de joindre réduit le volume de la jointure.
-- LEFT JOIN conserve aussi les codes absents de la nomenclature de référence.
WITH totals AS (
    SELECT FLX_ANN_MOI AS mois_traitement, PRS_NAT AS code_prestation,
           sum(FLT_REM_MNT) AS remboursement_part_legale_eur
    FROM remboursements
    GROUP BY FLX_ANN_MOI, PRS_NAT
)
SELECT t.*, coalesce(n.libelle, 'Libellé non disponible') AS libelle_prestation
FROM totals AS t
LEFT JOIN nomenclatures AS n ON n.variable='PRS_NAT' AND n.code=t.code_prestation
ORDER BY mois_traitement, remboursement_part_legale_eur DESC;
