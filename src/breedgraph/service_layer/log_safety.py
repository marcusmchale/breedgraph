"""
Helpers to keep personal data out of application logs. See docs/person.md §5.
Log IDs and actions, not message contents or input values.
"""
from pydantic import BaseModel, ValidationError


def _is_id_field(name: str) -> bool:
    return name == 'id' or name.endswith('_id') or name.endswith('_ids') or name in ('write_team', 'team', 'teams')


def loggable(message: BaseModel) -> str:
    """A command or event as its class name and ID fields only"""
    ids = {
        name: value for name, value in message.__dict__.items()
        if _is_id_field(name) and value is not None
    }
    return f"{message.__class__.__name__}({', '.join(f'{name}={value}' for name, value in ids.items())})"


def describe_exception(exception: BaseException) -> str:
    """An exception for logging. Validation errors are described without the input values they contain."""
    if isinstance(exception, ValidationError):
        errors = '; '.join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exception.errors(include_input=False, include_url=False)
        )
        return f"{exception.__class__.__name__} for {exception.title}: {errors}"
    return f"{exception.__class__.__name__}: {exception}"
