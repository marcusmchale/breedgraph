MATCH  (study: Study) where study.id in $studies
DETACH DELETE study