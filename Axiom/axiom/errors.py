
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
    def __init__(self, sql, args, underlying):
        RuntimeError.__init__(self, sql, args, underlying)
        self.sql, self.args, self.underlying = self.args

    def __str__(self):
        return "<SQLError: %r(%r) caused %s: %s>" % (
            self.sql, self.args,
            self.underlying.__class__, self.underlying)



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
