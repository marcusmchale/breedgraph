from .base import Event

class AnalysisRequested(Event):
    agent_id: int
    analysis_id: str