
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


class TableCreationConcurrencyError(RuntimeError):
    """
    Woah, this is really bad.  If you can get this please tell us how.
    """

class DuplicateUniqueItem(KeyError):
    """
    Found 2 or more of an item which is supposed to be unique.
    """

class ItemNotFound(KeyError):
    """
    Did not find even 1 of an item which was supposed to exist.
    """
