from .base import Command

class AddCountry(Command):
    admin: int
    name: str
    code: str
