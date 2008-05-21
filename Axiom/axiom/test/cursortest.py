# -*- test-case-name: axiom.test.test_pysqlite2 -*-

"""
Test code for any cursor implementation which is to work with Axiom.

This probably isn't complete.
"""

from axiom.errors import TimeoutError, TableAlreadyExists, SQLError

class StubCursor(object):
    """
    Stand in for an actual database-backed cursor.  Used by tests to assert the
    right calls are made to execute and to make sure errors from execute are
    handled correctly.

    @ivar statements: A list of SQL strings which have been executed.
    @ivar connection: A reference to the L{StubConnection} which created this
    cursor.
    """
    def __init__(self, connection):
        self.connection = connection
        self.statements = []


    def execute(self, statement, args=()):
        """
        Capture some SQL for later inspection.
        """
        self.statements.append(statement)



class StubConnection(object):
    """
    Stand in for an actual database-backed connection.  Used by tests to create
    L{StubCursors} to easily test behavior of code which interacts with cursors.

    @ivar cursors: A list of all cursors ever created with this connection.
    """
    def __init__(self):
        self.cursors = []


    def cursor(self):
        """
        Create and return a new L{StubCursor}.
        """
        self.cursors.append(StubCursor(self))
        return self.cursors[-1]


    def timeout(self):
        """
        Induce behavior indicative of a database-level transient failure which
        might lead to a timeout.
        """
        raise NotImplementedError



class ConnectionTestCaseMixin:

    # The number of seconds we will allow for timeouts in this test suite.
    TIMEOUT = 5.0

    # The amount of time beyond the specified timeout we will allow Axiom to
    # waste sleeping.  This number shouldn't be changed very often, if ever.
    # We're testing a particular performance feature which we should be able to
    # rely on.
    ALLOWED_SLOP = 0.2


    def createAxiomConnection(self):
        raise NotImplementedError("Cannot create Axiom Connection instance.")


    def createStubConnection(self):
        raise NotImplementedError("Cannot create Axiom Connection instance.")


    def createRealConnection(self):
        """
        Create a memory-backed database connection for integration testing.
        """
        raise NotImplementedError("Real connection creation not implemented.")


    def test_identifyTableCreationError(self):
        """
        When the same table is created twice, we should get a TableAlreadyExists
        exception.
        """
        con = self.createRealConnection()
        cur = con.cursor()
        CREATE_TABLE = "create table foo (bar integer)"
        cur.execute(CREATE_TABLE)
        e = self.assertRaises(TableAlreadyExists, cur.execute, CREATE_TABLE)


    def test_identifyGenericError(self):
        """
        When invalid SQL is issued, we should get a SQLError exception.
        """
        con = self.createRealConnection()
        cur = con.cursor()
        INVALID_STATEMENT = "not an SQL string"
        e = self.assertRaises(SQLError, cur.execute, INVALID_STATEMENT)


    def test_cursor(self):
        """
        Test that the cursor method can actually create a cursor object.
        """
        stubConnection = self.createStubConnection()
        axiomConnection = self.createAxiomConnection(stubConnection)
        axiomCursor = axiomConnection.cursor()

        self.assertEquals(len(stubConnection.cursors), 1)
        statement = "SELECT foo FROM bar"
        axiomCursor.execute(statement)
        self.assertEquals(len(stubConnection.cursors[0].statements), 1)
        self.assertEquals(stubConnection.cursors[0].statements[0], statement)


    def test_timeoutExceeded(self):
        """
        Test that the timeout we pass to the Connection is respected.
        """
        clock = [0]
        def time():
            return clock[0]
        def sleep(n):
            clock[0] += n

        stubConnection = self.createStubConnection()
        axiomConnection = self.createAxiomConnection(stubConnection, timeout=self.TIMEOUT)
        axiomCursor = axiomConnection.cursor()

        axiomCursor.time = time
        axiomCursor.sleep = sleep

        def execute(statement, args=()):
            if time() < self.TIMEOUT * 2:
                return stubConnection.timeout()
            return object()

        stubConnection.cursors[0].execute = execute

        statement = 'SELECT foo FROM bar'
        timeoutException = self.assertRaises(
            TimeoutError,
            axiomCursor.execute, statement)

        self.failUnless(
            self.TIMEOUT <= time() <= self.TIMEOUT + self.ALLOWED_SLOP,
            "Wallclock duration of execute() call out of bounds.")

        self.assertEquals(timeoutException.statement, statement)
        self.assertEquals(timeoutException.timeout, self.TIMEOUT)
        self.failUnless(isinstance(
                timeoutException.underlying,
                self.expectedUnderlyingExceptionClass))

