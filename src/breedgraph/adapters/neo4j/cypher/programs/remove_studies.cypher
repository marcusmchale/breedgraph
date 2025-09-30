MATCH  (study: Study) where study.id in $study_ids
DETACH DELETE study