import os

# The data processing terms accepted when an organisation declares its legal entity.
# The terms document is hosted elsewhere; only its version is recorded with each declaration.
# Declaring a legal entity is refused while no version is configured.
DATA_PROCESSING_TERMS_VERSION = os.environ.get('DATA_PROCESSING_TERMS_VERSION') or None
DATA_PROCESSING_TERMS_URL = os.environ.get('DATA_PROCESSING_TERMS_URL') or None
