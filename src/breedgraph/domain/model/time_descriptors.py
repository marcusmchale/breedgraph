from pydantic import BaseModel, field_validator


class TimeDescriptor(BaseModel):
    pass

class Season(TimeDescriptor):
    name: str
    year: int  # 4 digit

    @field_validator('year')
    def validate_year(cls, v):
        if not len(str(v)) == 4:
            raise ValueError('Year must be 4 digits')

class SeasonStored(Season):
    id: int

