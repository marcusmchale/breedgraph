CREATE FULLTEXT INDEX referenceDescription FOR (reference:Reference) ON EACH [reference.description, reference.filename, reference.url, reference.external_id]
