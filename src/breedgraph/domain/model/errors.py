from dataclasses import dataclass
from src.breedgraph.domain.model.base import SerializableMixin

@dataclass
class ItemError(SerializableMixin):
    index: int
    error: str

    def model_dump(self):
        return {
            'index': self.index,
            'error': self.error
        }