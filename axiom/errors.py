
from twisted.cred.error import UnauthorizedLogin

class BadCredentials(UnauthorizedLogin):
    pass

class NoSuchUser(UnauthorizedLogin):
    pass

class DuplicateUser(Exception):
    pass

class NoCrossStoreReferences(AttributeError):
    """
    References are not allowed between items within different Stores.
    """

class SQLError(RuntimeError):
    """
    Axiom internally generated some bad SQL.
    """

class SQLWarning(Warning):
    """
    Axiom internally generated some CREATE TABLE SQL that ... probably wasn't bad
    """
