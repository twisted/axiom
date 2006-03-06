# -*- test-case-name: axiom.test -*-


"""
APSW Connection and Cursor wrappers.

These provide a uniform interface on top of APSW for Axiom, particularly
including error handling behavior and exception types.
"""

import gc

import apsw

from axiom import errors

class Connection(object):
    def __init__(self, dbfname, timeout=10.0):
        self._connection = apsw.Connection(dbfname)
        self._connection.setbusytimeout(int(timeout * 1000))


    def cursor(self):
        return Cursor(self)


    def _close(self):
        self._connection = None

        # This is necessary because APSW does not provide .close() methods for
        # the connection or cursor objects - they are managed as resources and
        # explicitly closed in tp_del.  Here we tell the garbage collector to
        # MAKE SURE that those objects are finalized, because there may be
        # application-level requirements to require that the store is closed so
        # that, for example, we may unlink some disk files related to it.

        gc.collect()



class Cursor(object):
    def __init__(self, connection):
        self._connection = connection
        self._cursor = connection.cursor()


    def __iter__(self):
        return iter(self._cursor)


    def execute(self, sql, args=()):
        try:
            return self._cursor.execute(sql, args)
        except apsw.Error, e:
            raise errors.SQLError(sql, args, e)


    def lastRowID(self):
        return self._connection.last_insert_rowid()


    def close(self):
        self._cursor = None
        self._connection._close()
        self._connection = None
