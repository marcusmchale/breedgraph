class NoResultFoundError(Exception):
    pass


class IllegalOperationError(Exception):
    pass


class IdentityExistsError(IllegalOperationError):
    pass

class RelationshipExistsError(IllegalOperationError):
    pass

class ProtectedNodeError(IllegalOperationError):
    pass


class ProtectedRelationshipError(IllegalOperationError):
    pass


class UnauthorisedOperationError(IllegalOperationError):
    pass


class ExistingUniqueRelationship(IllegalOperationError):
    pass

class InconsistentStateError(IllegalOperationError):
    """Raised when the system detects an inconsistent state that prevents safe operation completion."""
    pass


class LicenceNotAcceptedError(Exception):
    """
    Data that needs its study's licence accepted, asked for without an acceptance of the licence's current text
    (docs/licences.md §5): accept it with licencesAccept
    """
    pass
