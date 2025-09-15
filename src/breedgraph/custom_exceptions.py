class NoResultFoundError(Exception):
    pass


class IllegalOperationError(Exception):
    pass


class IdentityExistsError(IllegalOperationError):
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

