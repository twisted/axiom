# -*- test-case-name: axiom.test -*-

"""
PySQLite2 Connection and Cursor wrappers.

These provide a uniform interface on top of PySQLite2 for Axiom, particularly
including error handling behavior and exception types.
"""
import time

from pysqlite2 import dbapi2

from twisted.python import log

from axiom import errors, iaxiom

class Connection(object):
    def __init__(self, dbfname, timeout=10.0, isolationLevel=None):
        self._connection = dbapi2.connect(dbfname,
                                          timeout=timeout,
                                          isolation_level=isolationLevel)


    def cursor(self):
        return Cursor(self)



class Cursor(object):
    def __init__(self, connection):
        self._connection = connection
        self._cursor = connection._connection.cursor()


    def __iter__(self):
        return iter(self._cursor)


    def execute(self, sql, args=()):
        try:
            try:
                t = time.time()
                try:
                    return self._cursor.execute(sql, args)
                finally:
                    log.msg(interface=iaxiom.IStatEvent,
                            name='database',
                            stat_cursor_execute_time=time.time() - t)
            except dbapi2.OperationalError, e:
                if e.args[0] == 'database schema has changed':
                    return self._cursor.execute(sql, args)
                raise
        except (dbapi2.ProgrammingError,
                dbapi2.InterfaceError,
                dbapi2.OperationalError), e:
            raise errors.SQLError(sql, args, e)


    def lastRowID(self):
        return self._cursor.lastrowid


    def close(self):
        self._cursor.close()
