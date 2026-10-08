from typing import Any

from .base import Command

class RequestAnalysis(Command):
    agent_id: int
    analysis: dict[str, Any]  # AnalysisInput with snake_case keys, stored as an exact mirror
