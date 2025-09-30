MATCH  (program: Program) where program.id in $program_ids
DETACH DELETE program