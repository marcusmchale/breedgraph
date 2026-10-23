from pydantic import BaseModel


class Command(BaseModel):

    def given(self, field: str) -> bool:
        """
        Whether an update gives the field, as a value or as null (README, Updates): a field left out leaves the value as
        it is, and null clears an optional one
        """
        return field in self.model_fields_set

    def given_text(self, field: str) -> str | None:
        """An optional text field as given: empty or blank clears it, as null does"""
        value = getattr(self, field)
        return value if value is not None and value.strip() else None
