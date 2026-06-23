from .commands import (
    accounts as accounts_commands,
    arrangements,
    blocks,
    datasets,
    ontologies,
    organisations,
    people,
    regions,
    setup,
    controls
)
from .events import (
    accounts as accounts_events,
    analysis as analysis_events,
    datasets as datasets_events,
    references as references_events
)
from .registry import handlers
