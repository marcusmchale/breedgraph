import os

# The largest query the API answers, so that no request has it build an answer of any size
# (entrypoints/fastapi/graphql/query_limits.py): how deep its fields nest, how many fields it asks for (each use of a
# fragment counted, as aliases repeat a field), and how many lists nest, each multiplying what is asked below it.
# BreedView asks at most 9 deep, 705 fields and 4 lists; the standard introspection query 15 deep.
MAX_QUERY_DEPTH = int(os.environ.get('MAX_QUERY_DEPTH', 15))
MAX_QUERY_FIELDS = int(os.environ.get('MAX_QUERY_FIELDS', 2000))
MAX_QUERY_LISTS = int(os.environ.get('MAX_QUERY_LISTS', 6))
