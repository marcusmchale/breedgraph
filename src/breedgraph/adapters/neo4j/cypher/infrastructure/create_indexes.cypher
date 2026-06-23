CREATE FULLTEXT INDEX referenceDescription FOR (reference:Reference) ON EACH [reference.description, reference.filename]
