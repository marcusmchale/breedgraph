CREATE FULLTEXT INDEX referenceDescription IF NOT EXISTS FOR (reference:Reference) ON EACH [reference.description, reference.filename, reference.url, reference.external_id]
