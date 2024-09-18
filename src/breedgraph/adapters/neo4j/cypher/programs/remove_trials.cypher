MATCH  (trial: Trial) where trial.id in $trials
DETACH DELETE trial