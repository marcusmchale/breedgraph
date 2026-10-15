from .base import Command


class RefreshReadModels(Command):
    """Rebuild read models in the state store from the database: those named, or all of them"""
    names: list[str] | None = None
