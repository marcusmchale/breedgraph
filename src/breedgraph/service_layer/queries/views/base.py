from abc import ABC, abstractmethod
from typing import AsyncGenerator
from src.breedgraph.domain.model.accounts import UserOutput
from src.breedgraph.domain.model.controls import Access
from .regions import AbstractRegionsViews
from .accounts import AbstractAccountsViews

class AbstractViewsHolder(ABC):
    regions: AbstractRegionsViews
    accounts: AbstractAccountsViews
