"""

Classes responsible for reconstructing typed domain inputs from serialized
representations (e.g. JSON payloads, Redis event payloads, external imports).

Most command/event flows enforce types at the application boundary, but
asynchronous workflows that serialize payloads for later processing can lose
that validation/coercion step. Importers provide the boundary where these
payloads are validated and hydrated into structured input types before
entering domain processing.

These are primarily used for complex domain inputs where a simple primitive
coercion is insufficient (e.g. datasets containing nested records).

"""
from .dataset import DatasetImport, DatasetUpdateImport, RecordImport
from .analysis import AnalysisImport, AnalysisVariableImport, InteractionTermImport