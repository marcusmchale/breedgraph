MATCH  (program: Program) where program.id in $programs
DETACH DELETE program