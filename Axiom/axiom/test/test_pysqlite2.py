"""
Test cases for PySQLite2-specific parts of the backend.
"""

from pysqlite2.dbapi2 import OperationalError

from twisted.trial.unittest import TestCase

from axiom._pysqlite2 import Connection
from axiom.test.cursortest import ConnectionTestCaseMixin, StubConnection


class PySQLite2StubConnection(StubConnection):
    def timeout(self):
        raise OperationalError('database is locked')


class ConnectionTestCase(ConnectionTestCaseMixin, TestCase):
    expectedUnderlyingExceptionClass = OperationalError

    def createStubConnection(self, *a, **kw):
        return PySQLite2StubConnection(*a, **kw)


    def createAxiomConnection(self, underlyingConnection, *a, **kw):
        return Connection(underlyingConnection, *a, **kw)


    def createRealConnection(self):
        """
        Create a memory-backed connection for integration testing.
        """
        return Connection.fromDatabaseName(":memory:")
