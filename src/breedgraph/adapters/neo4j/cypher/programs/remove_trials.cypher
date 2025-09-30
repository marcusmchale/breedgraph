MATCH  (trial: Trial) where trial.id in $trial_ids
DETACH DELETE trial