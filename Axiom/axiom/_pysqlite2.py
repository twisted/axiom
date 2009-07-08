# -*- test-case-name: axiom.test.test_pysqlite2 -*-

"""
PySQLite2 Connection and Cursor wrappers.

These provide a uniform interface on top of PySQLite2 for Axiom, particularly
including error handling behavior and exception types.
"""
import time

from weakref import WeakValueDictionary

from pysqlite2 import dbapi2
# import sqlite3 as dbapi2

from twisted.python import log

from axiom import errors
from axiom.iaxiom import IStatEvent

class Connection(object):
    """
    This is a wrapper around a connection object from pysqlite2, adding a thin
    layer of transaction and timeout management that works the way Axiom wants.

    The transaction management allows us to track all open cursors with results
    and close them when a transaction begins or ends, to allow us to begin and
    end transactions.  This allows commit() and rollback() to always succeed.
    pysqlite2 2.5.0 and later attempt to implement this but still have some
    issues; earlier versions (which we still support) do not.

    This L{Connection} also has transactions with an explicit begin(), so that
    cursors which executed queries before the I{start} of the transaction are
    also invalidated, to prevent properly transaction-isolated results from
    being mingled with other results.

    SQLite3 uses something like exponential backoff when trying to acquire a
    database lock.  This means that even for very long timeouts, it may only
    attempt to acquire the lock a handful of times.  Another process which is
    executing frequent, short-lived transactions may acquire and release the
    lock many times between any two attempts by this one to acquire it.  If
    this process gets unlucky just a few times, this execute may fail to
    acquire the lock within the specified timeout.  Processes started by
    L{axiom.batch} behave exactly like this, so an axiom server with a busy
    batch process, using SQLite3's default timeout logic will frequently have
    exceptions in its log.

    Since attempting to acquire the lock is a fairly cheap operation, we take
    another route.  SQLite3 is always told to use a timeout of 0 - ie, acquire
    it on the first try or fail instantly.  We will keep doing this at a fixed
    interval, until the user-specified timeout actual timeout expires.
    """

    _transactionCursor = None

    def __init__(self, connection, timeout=None):
        self._connection = connection
        self._timeout = timeout
        self._cursors = WeakValueDictionary()


    @classmethod
    def fromDatabaseName(cls, dbFilename, timeout=None, isolationLevel=None):
        """
        Create a L{Connection} from a database name; i.e. the path name of a
        sqlite database file on the file system, or a string that's special to
        the sqlite library, such as ':memory:' for an in-memory database.
        """
        return cls(dbapi2.connect(dbFilename, timeout=0,
                                  isolation_level=isolationLevel))


    def begin(self):
        """
        Immediately begin a transaction, acquiring a database lock.

        @raise errors.TimeoutError: if the database lock takes longer than
        C{self._timeout} seconds to acquire.
        """
        for cur in self._cursors.values():
            cur._transactionPrepare()
        self._rootExecute("BEGIN IMMEDIATE TRANSACTION")


    def rollback(self):
        """
        Roll back the currently-executing transaction, reverting all database
        changes executed since L{Cursor.begin} was called.
        """
        self._rootExecute("ROLLBACK")


    def commit(self):
        """
        Commit the currently-executing transaction.
        """
        self._rootExecute("COMMIT")


    def _rootExecute(self, sql):
        """
        Execute some SQL on a dedicated transaction cursor.  There should be no
        results; this is used only internally for BEGIN/COMMIT/ROLLBACK.
        """
        if self._transactionCursor is None:
            self._transactionCursor = self.cursor()
        self._transactionCursor.execute(sql)


    def cursor(self):
        cur = Cursor(self, self._timeout)
        self._cursors[id(cur)] = cur
        return cur


    def identifySQLError(self, sql, args, e):
        """
        Identify an appropriate SQL error object for the given message for the
        supported versions of sqlite.

        Since pysqlite2 only gives us strings, rather than error constants, we
        have to do this by looking at error messages.

        @return: an SQLError
        """
        message = e.args[0]
        if message.startswith("table") and message.endswith("already exists"):
            return errors.TableAlreadyExists(sql, args, e)
        if message == 'database is locked':
            return errors.DatabaseLocked(sql, args, e)
        return errors.SQLError(sql, args, e)



class Cursor(object):
    """
    A wrapper around a L{pysqlite2.dbapi2.Cursor} that performs error
    translation and more useful timeout logic.
    """
    def __init__(self, connection, timeout):
        self._connection = connection
        self._cursor = connection._connection.cursor()
        self.timeout = timeout
        self._closed = None


    def __iter__(self):
        """
        Return this L{Cursor}, as it is iterable.
        """
        return self


    def _transactionPrepare(self):
        """
        A transaction is about to begin or commit; close this cursor.  If this
        cursor has results, invalidate it so that it can no longer be used, as
        its results won't be valid.
        """
        try:
            self._cursor.next()
        except StopIteration:
            pass
        else:
            self.close(errors.CursorLeftOpen)


    def next(self):
        """
        Get the next result from my cursor.

        @raise errors.CursorLeftOpen: if this cursor had results before a
            transaction started or stopped.
        """
        self._checkClosed()
        return self._cursor.next()


    def time(self):
        """
        Return the current wallclock time as a float representing seconds
        from an fixed but arbitrary point.
        """
        return time.time()


    def sleep(self, seconds):
        """
        Block for the given number of seconds.

        (This may be replaced by tests to simulate the passage of time.)

        @type seconds: C{float}
        """
        time.sleep(seconds)


    def execute(self, sql, args=()):
        """
        Execute the given sql statement with the given arguments on my
        underlying database cursor, performing error translation in the
        process.

        @raise errors.SQLError: if the issued SQL is invalid.

        @raise errors.TableAlreadyExists: if the SQL statement is a 'CREATE
            TABLE' statment which creates a table.

        @raise errors.TimeoutError: if acquiring the database lock takes too
            long.

        @return: this L{Cursor}, to support the 'for record in
            cursor.execute():' idiom.
        """
        self._checkClosed()
        blockedTime = 0.0
        t = self.time()
        try:
            while 1:
                try:
                    try:
                        self._cursor.execute(sql, args)
                    except (dbapi2.ProgrammingError,
                            dbapi2.InterfaceError,
                            dbapi2.OperationalError), e:
                        raise self._connection.identifySQLError(sql, args, e)
                    break
                except errors.DatabaseLocked, e:
                    now = self.time()
                    if self.timeout is not None:
                        if (now - t) > self.timeout:
                            raise errors.TimeoutError(sql, self.timeout, e.underlying)
                    self.sleep(0.1)
                    blockedTime = self.time() - t
        finally:
            txntime = self.time() - t
            if txntime - blockedTime > 2.0:
                log.msg('Extremely long execute: %s' % (txntime - blockedTime,))
                log.msg(sql)
            log.msg(interface=IStatEvent,
                    stat_cursor_execute_time=txntime,
                    stat_cursor_blocked_time=blockedTime)
        return self


    def lastRowID(self):
        """
        Return the last ID of the last row that this cursor created.
        """
        return self._cursor.lastrowid


    def _checkClosed(self):
        """
        Check if this cursor is closed.  If it is, raise the appropriate
        exception.
        """
        if self._closed is not None:
            raise self._closed


    def close(self, exception=errors.CursorClosed):
        """
        Close this cursor, causing all future operations on it to raise
        L{CursorClosed}.
        """
        self._cursor.close()
        self._closed = exception
