"""
Test cases for APSW-specific parts of the backend.
"""

from apsw import LockedError

from twisted.trial.unittest import TestCase

from axiom._apsw import Connection
from axiom.test.cursortest import ConnectionTestCaseMixin, StubConnection

class APSWStubConnection(StubConnection):
    def setbusytimeout(self, n):
        self.busytimeout = n


    def timeout(self):
        # XXX I don't really know how apsw works.
        raise LockedError()


class ConnectionTestCase(ConnectionTestCaseMixin, TestCase):
    skip = "APSW is dumb."

    expectedUnderlyingExceptionClass = LockedError

    def createStubConnection(self, *a, **kw):
        return APSWStubConnection(*a, **kw)


    def createAxiomConnection(self, underlyingConnection, *a, **kw):
        return Connection(underlyingConnection, *a, **kw)
