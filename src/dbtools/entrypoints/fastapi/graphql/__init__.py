
import logging

logger = logging.getLogger(__name__)
logger.info("Start GraphQL service")

from . import resolvers  # need to import these here as using decorators



