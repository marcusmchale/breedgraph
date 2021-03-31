from typing import Optional
from pydantic import BaseModel
from accounts import Account, AffiliationLevel


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None
    affiliation_level: AffiliationLevel
