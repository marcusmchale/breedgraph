from pydantic import BaseModel, field_validator, ValidationError, Field, computed_field
from src.breedgraph.adapters.repositories.base import Entity, Aggregate, AggregateRoot

from typing import List


class Position(BaseModel):
    x: float | int | str | None = None
    y: float | int | str | None = None
    z: float | int | str | None = None

class Layout(BaseModel):
    type: int  # ref to LayoutTypeStored
    description: str

    parent: int|None = None
    position: Position | None = None
    # when a layout has a parent layout, position relates this element to that parent.

    children: List[int | None] = None
    positions: List[Position | None] = None #
    position_min: Position|None = None
    position_max: Position|None = None

    used: bool = False  # can't be deleted if used, store true if this is referenced

    @field_validator('position')
    def position_validator(cls, input_value, other_values):
        if input_value is None and other_values['parent'] is None:
            pass
        else:
            raise ValidationError("If a parent layout is specified, a position must also be defined")

    def is_valid_position(self, position: Position):
        if self.positions:
            if position in self.positions:
                return True
            else:
                return False
        elif self.position_min and self.position_max:
            for attr in Position.model_fields.keys():
                value = getattr(position, attr)
                min_value = getattr(self.position_min, attr)
                max_value = getattr(self.position_max, attr)
                if value is None:
                    if not all([min_value is None, max_value is None]):
                        raise ValueError(f"Position is missing attribute: {attr}")
                elif all([min_value is not None, max_value is not None]):
                    if not min_value <= value <= max_value:
                        raise ValueError(f"Position for {attr} must be equal to or between {min_value} and {max_value}")
                elif self.position_min is None:
                    if not value <= self.position_max:
                        raise ValueError(f"Position for {attr} must be less than or equal to {max_value}")
                elif self.position_max is None:
                    if not value >= self.position_min:
                        raise ValueError(f"Position for {attr} must be greater than or equal to {min_value}")

class LayoutStored(Layout, Entity):
    pass

class Arrangement(Aggregate):
    layouts: List[Layout|LayoutStored]

    @property
    def root(self) -> Layout:
        if self.layouts[0].parent is not None:
            raise ValueError("Root layout should have no parents")
        return self.layouts[0]

    @property
    def protected(self) -> str | False:
        for layout in self.layouts:
            if layout.used:
                return "This arrangement is used to define existing records and so cannot be removed"

        return False