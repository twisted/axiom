# -*- test-case-name: axiom.test.test_pysqlite2 -*-

"""
Test code for any cursor implementation which is to work with Axiom.

This probably isn't complete.
"""

from axiom.errors import TimeoutError, TableAlreadyExists, SQLError, CursorLeftOpen, CursorClosed

CREATE_FOO = "CREATE TABLE foo (bar INTEGER)"
SELECT_FOO = "SELECT * FROM foo"
INSERT_FOO = "INSERT INTO foo VALUES (?)"

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


    def next(self):
        """
        Stub cursor tests never expect any results, so this always raises
        StopIteration.
        """
        raise StopIteration()



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


    def test_commitTransactionSQL(self):
        """
        BEGIN and COMMIT statements should be issued on a dedicated transaction
        cursor.
        """
        stub = self.createStubConnection()
        con = self.createAxiomConnection(stub)
        con.begin()
        self.assertEquals(len(stub.cursors), 1)
        self.assertEquals(stub.cursors[0].statements,
                          ["BEGIN IMMEDIATE TRANSACTION"])
        stub.cursors[0].statements.pop()
        con.commit()
        self.assertEquals(len(stub.cursors), 1)
        self.assertEquals(stub.cursors[0].statements, ["COMMIT"])


    def test_commitWithoutBegin(self):
        """
        The 'commit' method should raise an exception if there is no
        corresponding 'begin' call.
        """
        con = self.createRealConnection()
        # Commit shouldn't work if a transaction isn't in progress.
        self.assertRaises(SQLError, con.commit)
        con.begin()
        con.commit()


    def test_rollbackTransaction(self):
        """
        L{Connection.rollback} will revert any changes to the database since
        the last L{Connection.begin} call.
        """
        con = self.createRealConnection()
        cur = con.cursor()
        cur.execute(CREATE_FOO)
        cur.execute(INSERT_FOO, [7])
        cur.execute(INSERT_FOO, [8])
        con.begin()
        cur.execute(INSERT_FOO, [9])
        con.rollback()
        self.assertEquals(list(cur.execute(SELECT_FOO)), [(7,), (8,)])


    def test_executeResult(self):
        """
        The 'execute' method will return the cursor itself.
        """
        con = self.createRealConnection()
        cur = con.cursor()
        self.assertIdentical(cur.execute(CREATE_FOO), cur)
        self.assertIdentical(cur.execute(SELECT_FOO), cur)


    def test_dontInvalidateNoResults(self):
        """
        If an operation with no results is performed before a transaction
        begins, for example a 'CREATE TABLE', the cursor won't be invalidated
        by the L{Connection.begin} call, even if its results haven't been
        explicitly exhausted.
        """
        con = self.createRealConnection()
        cur = con.cursor()
        cur.execute(CREATE_FOO)
        cur.execute(INSERT_FOO, [1])
        con.begin()
        self.assertEquals(list(cur.execute(SELECT_FOO)), [(1,)])
        con.commit()


    def test_transactionInvalidatesCursors(self):
        """
        Normally, SQLite will prohibit a transaction from being started or
        stopped while a cursor is still outstanding on a given connection that
        has more results.

        However, in Axiom we don't want to care if a user has lazily forgotten
        to fully exhaust a lazy query: transactions should always start or stop
        as requested.
        """
        con = self.createRealConnection()
        transactionCursor = con.cursor()
        transactionCursor.execute(CREATE_FOO)
        for x in range(4):
            transactionCursor.execute(INSERT_FOO, [x])
        dataCursor = con.cursor()
        dataCursor.execute(SELECT_FOO)
        results = iter(dataCursor)
        con.begin()
        self.assertRaises(CursorLeftOpen, results.next)
        self.assertRaises(CursorLeftOpen, dataCursor.execute, SELECT_FOO)
        con.commit()


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
        axiomConnection = self.createAxiomConnection(
            stubConnection, timeout=self.TIMEOUT)
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


    def test_closedCursor(self):
        """
        All operations on closed cursors should raise exceptions.  Due to a bug
        in pysqlite2, this was not always the case, but we should consistently
        provide that behavior.

        @see: U{http://oss.itsystementwicklung.de/trac/pysqlite/ticket/250}
        """
        con = self.createRealConnection()
        cur = con.cursor()
        cur.execute(CREATE_FOO)
        cur.execute(INSERT_FOO, [1])
        cur.execute(SELECT_FOO)
        cur.close()
        self.assertRaises(CursorClosed, cur.next)
