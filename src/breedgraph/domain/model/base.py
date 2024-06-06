from pydantic import BaseModel, Field, computed_field
from abc import ABC, abstractmethod
from typing import List, Dict
from src.breedgraph.domain.events.accounts import Event

class Entity(BaseModel):
    id: int = Field(frozen=True)

    def __hash__(self):
        return hash(self.id)



class Aggregate(ABC, BaseModel):
    events: List[Event] = list()

    @property
    @abstractmethod
    def root(self) -> Entity:
        raise NotImplementedError

    @property
    @abstractmethod
    def protected(self) -> str|None:
        # Return a string describing why this aggregate is protected
        # or None/empty string if safe to delete
        raise NotImplementedError

    def __hash__(self) -> int:
        return hash(self.root.id)

class Member(BaseModel):
    name: str
    parent: int|None = None

class MemberStored(Member, Entity):

    children: List[int] = Field()
    pass

class MappedHierarchy(Aggregate):
    root_id: int
    members: Dict[int, Member | MemberStored] = dict()

    @classmethod
    def from_list(cls, members_list: List[BaseModel]):
        root_id = None
        members = dict()
        for m in members_list:
            members[m.id] = m
            if m.parent is None:
                root_id = m.id
        return cls(root_id=root_id, members=members)

    @property
    def root(self) -> MemberStored:
        return self.members[self.root_id]

    @property
    def protected(self) -> str|None:
        if self.root.children:
            return "Cannot delete an organisation while its root has children"

    def add_member(self, member: Member) -> int:  # returns the temporary ID in case it is needed
        if not member.parent in self.members:
            raise ValueError("Member is not in this hierarchy")
        for mid in self.members[member.parent].children:
            if self.members[mid].name.casefold() == member.name.casefold():
                raise ValueError("The parent member already has a child with this name")
        temp_id = -len(self.members) - 1
        self.members[temp_id] = member
        self.members[member.parent].children.append(temp_id)
        return temp_id

    def remove_member(self, member_id):
        member = self.members[member_id]
        if member.children:
            raise ValueError("Cannot remove a member with children")
        if member.parent is not None:
            self.members[member.parent].children.remove(member_id)
        self.members.pop(member_id)

    def get_member(self, member_id: int=None, name: str=None, parent_id: None|int = None) -> Member:
        if member_id is not None:
            return self.members[member_id]
        elif name is None:
            raise ValueError("Either a member ID or name is required")

        if parent_id is None:
            if name.casefold == self.root.name.casefold():
                return self.root
            else:
                members = [m for m in self.members.values() if m.name.casefold() == name.casefold()]
                if len(members) == 1:
                    return members[0]
                else:
                    raise ValueError("More than one member with a matching name, try specifying the parent")
        elif name is not None:
            parent = self.members[parent_id]
            for m in parent.children:
                member = self.members[m]
                if member.name.casefold() == name.casefold():
                    return member
