# -*- test-case-name: axiom.test -*-

import time
import os
import itertools
import warnings

from zope.interface import implements

from twisted.python.filepath import FilePath
from twisted.internet import defer
from twisted.python.reflect import namedAny
from twisted.python.util import unsignedID
from twisted.application.service import IService, MultiService

from axiom import _schema, attributes, upgrade, _fincache, iaxiom, errors

from pysqlite2 import dbapi2 as sqlite

from axiom.item import \
    _typeNameToMostRecentClass, dummyItemSubclass,\
    _legacyTypes, TABLE_NAME, Empowered

IN_MEMORY_DATABASE = ':memory:'

tempCounter = itertools.count()

class NoEmptyItems(Exception):
    """You must define some attributes on every item.
    """


class XFilePath(FilePath):
    def dirname(self):
        return os.path.dirname(self.path)

def _mkdirIfNotExists(dirname):
    if os.path.isdir(dirname):
        return False
    os.makedirs(dirname)
    return True

class AtomicFile(file):
    """I am a file which is moved from temporary to permanent storage when it
    is closed.

    After I'm closed, I will have a 'finalpath' property saying where I went.
    """

    implements(iaxiom.IAtomicFile)

    def __init__(self, tempname, destpath):
        self._destpath = destpath
        file.__init__(self, tempname, 'w+b')

    def close(self):
        now = time.time()
        try:
            file.close(self)
            _mkdirIfNotExists(self._destpath.dirname())
            self.finalpath = self._destpath
            os.rename(self.name, self.finalpath.path)
            os.utime(self.finalpath.path, (now, now))
        except:
            return defer.fail()
        return defer.succeed(self.finalpath)

    def abort(self):
        os.unlink(self.name)

_noItem = object()              # tag for optional argument to getItemByID
                                # default

class Store(Empowered):

    implements(iaxiom.IBeneficiary)

    transaction = None          # current transaction object

    storeID = -1                # I have a StoreID so that things can reference
                                # me

    store = property(lambda self: self) # I have a 'store' attribute because I
                                        # am 'stored' within myself; this is
                                        # also for references to use.

    def __init__(self, dbdir=None, debug=False, parent=None, idInParent=None):
        if parent is not None or idInParent is not None:
            assert parent is not None
            assert idInParent is not None
        self.parent = parent
        self.idInParent = idInParent
        self.debug = debug
        self.autocommit = True
        self.queryTimes = []
        self.execTimes = []
        self.statementCache = {} # non-normalized => normalized qmark SQL
                                 # statements

        self.objectCache = _fincache.FinalizingCache()


        if dbdir is None:
            dbfpath = IN_MEMORY_DATABASE
        else:
            dbdir = os.path.abspath(dbdir)
            dbfpath = os.path.join(dbdir, 'db.sqlite')
            self.filesdir = os.path.join(dbdir, 'files')
            if os.path.isdir(dbdir):
                if not os.path.exists(dbfpath):
                    raise OSError(
                        "The path %r is already a directory, "
                        "but not an Axiom Store" % (dbfpath,))
            else:
                _mkdirIfNotExists(dbdir)
                _mkdirIfNotExists(self.filesdir)
                _mkdirIfNotExists(os.path.join(dbdir, 'temp'))
        self.dbdir = dbdir
        self.connection = sqlite.connect(dbfpath)
        self.cursor = self.connection.cursor()
        self.activeTables = {}  # tables which have had items added/removed
                                # this run

        # install powerups if we've never powered on before;
        create = not self.querySQL(_schema.HAS_SCHEMA_FEATURE,
                                   ['table', 'axiom_types'])[0][0]
        if create:
            for stmt in _schema.BASE_SCHEMA:
                self.executeSQL(stmt)

        # activate services if we have(?)
        # scheduler needs startup hook

        self.tableQueries = {}  # map typename: query string w/ storeID
                                # parameter.  a typename is a persistent
                                # database handle for what we'll call a 'FQPN',
                                # i.e. arg to namedAny.

        self.typenameToID = {} # map database-persistent typename to an oid in
                               # the types table

        self.typenameAndVersionToID = {} # obvious I hope

        self.idToTypename = {} # map database-persistent typeID (oid in types
                               # table) to typename

        self.service = None

        for oid, module, typename, version in self.querySQL(_schema.ALL_TYPES):
            self.typenameAndVersionToID[typename, version] = oid
            if typename not in _typeNameToMostRecentClass:
                namedAny(module)
            if version == _typeNameToMostRecentClass[typename].schemaVersion:
                self.typenameToID[typename] = oid
                self.idToTypename[oid] = typename
            else:
                self._prepareOldVersionOf(oid, typename, version)

        for typename in self.typenameToID:
            self.checkTypeSchemaConsistency(typename)


    def __repr__(self):
        d = self.dbdir
        if d is None:
            d = '(in memory)'
        else:
            d = repr(d)
        return '<Store %s@0x%x>' % (self.dbdir, unsignedID(self))


    def newFilePath(self, *path):
        return XFilePath(os.path.join(self.dbdir, 'files', *path))

    def findOrCreate(self, userItemClass, __ifnew=None, **attrs):
        """
        Usage:

            s.findOrCreate(userItemClass [, function] [, x=1, y=2, ...])

        Example:

            class YourItemType(Item):
                a = integer()
                b = text()
                c = integer()

            def f(x):
                print x, \"-- it's new!\"
            s.findOrCreate(YourItemType, f, a=1, b=u'2')

        Search for an item with columns in the database that match the passed
        set of keyword arguments, returning the first match if one is found,
        creating one with the given attributes if not.  Takes an optional
        positional argument function to call on the new item if it is new.
        """
        existingItem = self.findFirst(userItemClass, **attrs)
        if existingItem is None:
            newItem = userItemClass(store=self, **attrs)
            if __ifnew is not None:
                __ifnew(newItem)
            return newItem
        else:
            return existingItem

    def findFirst(self, userItemClass, **attrs):
        """
        Usage:

            s.findFirst(userItemClass [, x=1, y=2, ...])

        Example:

            class YourItemType(Item):
                a = integer()
                b = text()
                c = integer()

            s.findFirst(YourItemType, a=1, b=u'2')

        Search for an item with columns in the database that match the
        passed set of keyword arguments, returning the first match if
        one is found, or None if one is not found.
        """
        andargs = []
        for k, v in attrs.iteritems():
            col = getattr(userItemClass, k)
            andargs.append(col == v)

        if len(andargs) == 0:
            cond = []
        elif len(andargs) == 1:
            cond = [andargs[0]]
        else:
            cond = [attributes.AND(*andargs)]

        for result in self.query(userItemClass, *cond):
            return result
        return None

    def newFile(self, *path):
        assert self.dbdir is not None, "Cannot create files in in-memory Stores (yet)"
        tmpname = os.path.join(self.dbdir, 'temp', str(tempCounter.next())+".tmp")
        return AtomicFile(tmpname, self.newFilePath(*path))

    def newDirectory(self, *path):
        assert self.dbdir is not None, "Cannot create directories in in-memory Stores (yet)"
        return FilePath(os.path.join(self.dbdir, 'files', *path))

    def checkTypeSchemaConsistency(self, typename):
        """
        Called for all known types at database startup: make sure that what we know
        (in memory) about this type is

        """
        # make sure that both the runtime and the database both know about this
        # type; if they don't both know, we can't check that their views are
        # consistent
        assert typename in self.typenameToID
        if typename not in _typeNameToMostRecentClass:
            print 'EARLY OUT CONSISTENCY CHECK: WHAT?'
            return
        typeID = self.typenameToID[typename]
        actualType = _typeNameToMostRecentClass[typename]
        #
        inMemorySchema = [(storedAttribute.indexed, storedAttribute.sqltype,
                           storedAttribute.allowNone,
                           storedAttribute.attrname)
                          for (name, storedAttribute) in actualType.getSchema()]

        onDiskSchema = self.querySQL(_schema.IDENTIFYING_SCHEMA, [typeID])

        if inMemorySchema != onDiskSchema:
            raise RuntimeError(
                "Schema mismatch on already-loaded %r object version %d: %r != %r" %
                (actualType.typeName, actualType.schemaVersion, onDiskSchema, inMemorySchema))

        if self.querySQL(_schema.GET_TYPE_OF_VERSION,
                      [typename, actualType.schemaVersion]):
            raise RuntimeError(
                "Greater versions of database %r objects in the DB than in memory" %
                (typename,))

        # finally find old versions of the data and prepare to upgrade it.

    def _prepareOldVersionOf(self, typeID, typename, version):
        dummyItemSubclass(*self._dssargs(typeID, typename, version))

    def getOldVersionOf(self, typename, version):
        return _legacyTypes[typename, version]

    def _dssargs(self, typeID, typename, version):
        """
        Returns a 4-tuple suitable as args for dummyItemSubclass
        """

        appropriateSchema = self.querySQL(_schema.SCHEMA_FOR_TYPE, [typeID])
        # create actual attribute objects
        dummyAttributes = {}
        for indexed, pythontype, attribute, docstring in appropriateSchema:
            atr = getattr(attributes, pythontype)(indexed=indexed,
                                                  doc=docstring)
            dummyAttributes[attribute] = atr
        dummyBases = []
        retval = (typename, version, dummyAttributes, dummyBases)
        return retval


        # grab the schema for that version
        # look up upgraders which push it forward
        # insert "AutoUpgrader" class into idToTypename somehow(?)

    def query(self, *a, **k):
        """
        Return a generator of objects which match an L{IComparison} predicate.

        """
        return self._select(*a, **k)

    def count(self, *a, **k):
        """
        Retrieve a count of objects which match a particular C{IComparison}
        predicate.

        Example::
            self.store.count(MyClass,
                             MyClass.otherValue > 10)

        will return the number of instances of MyClass present in the database
        with an otherValue attribute greater than 10.

        @return: an L{int}.

        """
        try:
            resultCount = self._select(justCount=True, *a, **k).next()
        except StopIteration:
            return 0
        else:
            return resultCount

    def sum(self, summableAttribute, *a, **k):
        """
        Retrieve a sum from the database.

        Example::

            self.store.sum(MyClass.numericValue,
                           MyClass.otherValue > 10)

            # returns a sum of all numericValues from MyClass instances in
            # self.store where otherValue is greater than ten

        """
        try:
            resultSum = self._select(summableAttribute.type,
                                     sumAttribute=summableAttribute, *a, **k).next()
        except StopIteration:
            return 0
        return resultSum

    def _select(self,
                tableClass,
                comparison=None,
                limit=None, offset=None,
                sort=None,
                justCount=False,
                sumAttribute=None):
        """

        Generic object-oriented interface to 'SELECT', used to implement .query,
        .sum, and .count.

        @param tableClass: a subclass of L{Item}.

        @param comparison: an implementor of L{iaxiom.IComparison}

        @param limit: an L{int} that limits the number of results that will be
        queried for, or None to indicate that all results should be returned.

        @param offset: an L{int} that specifies the offset within the query
        results to begin iterating from, or None to indicate that we should
        start at 0.

        @param justCount: a L{bool} that specifies if we should 'just count'
        rather than returning the actual query results (interface to SELECT
        COUNT(x) WHERE ...)

        @param sumAttribute: an L{axiom.attributes.ColumnComparer} that should
        be summed and returned, rather than returning the SQL results.  (Refer
        to these using YourItemClass.attributeName.)

        """
        if not self.autocommit:
            self.checkpoint()
        if (tableClass.typeName,
            tableClass.schemaVersion) not in self.typenameAndVersionToID:
            return
        if comparison is not None:
            tables = set(comparison.getTableNames())
            where = ['WHERE', comparison.getQuery()]
            args = comparison.getArgs()
        else:
            tables = set()
            where = []
            args = []
        tables.add(tableClass.getTableName())
        query = ['SELECT']
        if justCount:
            query += ['COUNT(*)']
        elif sumAttribute is not None:
            query += ['SUM(%s)' % (sumAttribute.columnName,)]
        else:
            query += [tableClass.getTableName(), '.oid,', tableClass.getTableName(), '.*']
        query += ['FROM', ', '.join(tables)]
        query.extend(where)
        if sort is not None:
            query.append(sort)
        if limit is not None:
            # XXX LIMIT and OFFSET used to be using ?, but they started
            # generating syntax errors in places where generating the whole SQL
            # statement does not.  this smells like a bug in sqlite's parser to
            # me, but I don't know my SQL syntax standards well enough to be
            # sure -glyph
            query.append('LIMIT ')
            query.append(str(limit))
            if offset is not None:
                query.append('OFFSET ')
                query.append(str(offset))
        S = ' '.join(query)
        sqlResults = self.querySQL(S, args)
        if justCount or sumAttribute:
            assert len(sqlResults) == 1
            yield sqlResults[0][0]
            return
        for row in sqlResults:
            yield self._loadedItem(
                tableClass,
                row[0],
                row[1:])

    def _loadedItem(self, itemClass, storeID, attrs):
        if self.objectCache.has(storeID):
            result = self.objectCache.get(storeID)
            # XXX do checks on consistency between attrs and DB object, maybe?
        else:
            result = itemClass.existingInStore(self, storeID, attrs)
            if not result.__legacy__:
                self.objectCache.cache(storeID, result)
        return result

    def checkpoint(self):
        for item in self.transaction:
            # XXX: it should be possible here, using various clever hacks, to
            # automatically optimize functionally identical statements into
            # executemany.
            item.checkpoint()

    def revert(self):
        self.connection.rollback()
        for item in self.transaction:
            item.revert()

    executedThisTransaction = None

    def transact(self, f, *a, **k):
        if self.transaction is not None:
            return f(*a, **k)
        self.executedThisTransaction = []
        self.transaction = set()
        self.autocommit = False
        try:
            try:
                result = f(*a, **k)
                self.checkpoint()
            except:
                self.revert()
                raise
            else:
                self.commit()
                for committed in self.transaction:
                    committed.committed()
            return result
        finally:
            self.autocommit = True
            self.transaction = None
            self.executedThisTransaction = None

    def commit(self):
        if self.debug:
            print '*'*10, 'COMMIT', '*'*10
        self.connection.commit()

    def close(self):
        self.cursor.close()
        self.connection.close()
        self.cursor = None
        self.connection = None

        if self.debug:
            if not self.queryTimes:
                print 'no queries'
            else:
                print 'query:', self.avgms(self.queryTimes)
            if not self.execTimes:
                print 'no execs'
            else:
                print 'exec:', self.avgms(self.execTimes)

    def avgms(self, l):
        return 'count: %d avg: %dus' % (len(l), int( (sum(l)/len(l)) * 1000000.),)


    def getTypeID(self, tableClass):
        """
        """
        key = (tableClass.typeName,
               tableClass.schemaVersion)
        if key in self.typenameAndVersionToID:
            return self.typenameAndVersionToID[key]

        sqlstr = []
        sqlarg = []
        indexes = []

        # needs to be calculated including version
        tableName = tableClass.getTableName()

        sqlstr.append("CREATE TABLE %s (" % tableName)

        for nam, atr in tableClass.getSchema():
            # it's a stored attribute
            sqlarg.append("\n%s %s" %
                          (atr.columnName, atr.sqltype))
            if atr.indexed:
                indexes.append(nam)
        if len(sqlarg) == 0:
            # XXX should be raised way earlier, in the class definition or something
            raise NoEmptyItems("%r did not define any attributes" % (tableClass,))

        sqlstr.append(', '.join(sqlarg))
        sqlstr.append(')')

        if not self.autocommit:
            self.connection.rollback()

        self.createSQL(''.join(sqlstr))
        for index in indexes:
            self.createSQL('CREATE INDEX axiomidx_%s_%s ON %s([%s])'
                           % (tableName, index,
                              tableName, index))

        if not self.autocommit:
            self._reexecute()

        typeID = self.executeSQL(_schema.CREATE_TYPE, [tableClass.typeName,
                                                       tableClass.__module__,
                                                       tableClass.schemaVersion])

        for n, (name, storedAttribute) in enumerate(tableClass.getSchema()):
            self.executeSQL(
                _schema.ADD_SCHEMA_ATTRIBUTE,
                [typeID, n, storedAttribute.indexed, storedAttribute.sqltype,
                 storedAttribute.allowNone, storedAttribute.attrname,
                 storedAttribute.doc, storedAttribute.__class__.__name__])
            # XXX probably need something better for pythontype eventually,
            # when we figure out a good way to do user-defined attributes or we
            # start parameterizing references.

        self.typenameToID[tableClass.typeName] = typeID
        self.typenameAndVersionToID[key] = typeID
        self.idToTypename[typeID] = tableClass.typeName

        return typeID

    def getTableQuery(self, typename, version):
        if typename not in self.tableQueries:
            query = 'SELECT * FROM %s WHERE oid = ?' % (
                TABLE_NAME(typename, version), )
            self.tableQueries[typename, version] = query
        return self.tableQueries[typename, version]

    def getItemByID(self, storeID, default=_noItem, autoUpgrade=True):
        """
        """
        assert storeID is not None
        if storeID == -1:
            return self
        if self.objectCache.has(storeID):
            return self.objectCache.get(storeID)
        results = self.querySQL(_schema.TYPEOF_QUERY, [storeID])
        assert (len(results) in [1, 0]),\
            "Database panic: more than one result for TYPEOF!"
        if results:
            typename, module, version = results[0]
            # for the moment we're going to assume no inheritance
            attrs = self.querySQL(self.getTableQuery(typename, version),
                                  [storeID])
            assert len(attrs) == 1, "No results for known-to-be-good object"
            attrs = attrs[0]
            useMostRecent = False
            moreRecentAvailable = False
            if typename in _typeNameToMostRecentClass:
                moreRecentAvailable = True
                mostRecent = _typeNameToMostRecentClass[typename]

                if mostRecent.schemaVersion < version:
                    raise RuntimeError("%s:%d - was found in the database and most recent %s is %d" %
                                       (typename, version, typename, mostRecent.schemaVersion))
                if mostRecent.schemaVersion == version:
                    useMostRecent = True
            if useMostRecent:
                T = mostRecent
            else:
                T = self.getOldVersionOf(typename, version)
            x = T.existingInStore(self, storeID, attrs)
            if moreRecentAvailable and (not useMostRecent) and autoUpgrade:
                # upgradeVersion will do caching as necessary, we don't have to
                # cache here.  (It must, so that app code can safely call
                # upgradeVersion and get a consistent object out of it.)
                x = upgrade.upgradeAllTheWay(x, typename, x.schemaVersion)
            elif not x.__legacy__:
                # We loaded the most recent version of an object
                self.objectCache.cache(storeID, x)
            return x
        if default is _noItem:
            raise KeyError(storeID)
        return default

    def _normalizeSQL(self, sql):
        assert "'" not in sql, "Strings are _NOT ALLOWED_"
        if sql not in self.statementCache:
            accum = []
            lines = sql.split('\n')
            for line in lines:
                line = line.split('--')[0]         # remove comments
                words = line.strip().split()
                accum.extend(words)
            normsql = ' '.join(accum)   # your SQL should never have any
                                        # significant whitespace in it, right?
            self.statementCache[sql] = normsql
        return self.statementCache[sql]


    def querySQL(self, sql, args=()):
        """For use with SELECT (or SELECT-like PRAGMA) statements.
        """
        sql = self._normalizeSQL(sql)
        if self.debug:
            result = timeinto(self.queryTimes, self._queryandfetch, sql, args)
        else:
            result = self._queryandfetch(sql, args)
        return result

    def _queryandfetch(self, sql, args):
        if self.debug:
            print '**', sql, '--', ', '.join(map(str, args))
        try:
            self.cursor.execute(sql, args)
        except (sqlite.ProgrammingError, sqlite.OperationalError, sqlite.InterfaceError), oe:
            raise errors.SQLError("SQL: %r(%r) caused exception: %s:%s" %(
                    sql, args, oe.__class__, oe))
        result = self.cursor.fetchall()
        if self.autocommit:
            self.commit()
        if self.debug:
            print '  lastrow:', self.cursor.lastrowid
            print '  result:', result
        return result

    def createSQL(self, sql, args=()):
        """ For use with auto-committing statements such as CREATE TABLE or CREATE
        INDEX.
        """
        try:
            self._execSQL(sql, args)
        except errors.SQLError, se:
            warnings.warn(
                "(Probably harmless) error during table or index creation: "+str(se),
                errors.SQLWarning)

    def _execSQL(self, sql, args):
        sql = self._normalizeSQL(sql)
        if self.debug:
            rows = timeinto(self.execTimes, self._queryandfetch, sql, args)
        else:
            rows = self._queryandfetch(sql, args)
        assert not rows
        return sql

    def executeSQL(self, sql, args=()):
        """
        For use with UPDATE or INSERT statements.
        """
        sql = self._execSQL(sql, args)
        result = self.cursor.lastrowid
        if self.executedThisTransaction is not None:
            self.executedThisTransaction.append((result, sql, args))
        return result

    def _reexecute(self):
        assert self.executedThisTransaction is not None
        for resultLastTime, sql, args in self.executedThisTransaction:
            self._execSQL(sql, args)
            resultThisTime = self.cursor.lastrowid
            if resultLastTime != resultThisTime:
                raise errors.TableCreationConcurrencyError(
                    "Expected to get %s as a result "
                    "of %r:%r, got %s" % (
                        resultLastTime,
                        sql, args,
                        resultThisTime))


def timeinto(l, f, *a, **k):
    then = time.time()
    try:
        return f(*a, **k)
    finally:
        now = time.time()
        elapsed = now - then
        l.append(elapsed)

queryTimes = []
execTimes = []


class StorageService(MultiService):

    def __init__(self, *a, **k):
        MultiService.__init__(self)
        self.a = a
        self.k = k
        self.store = None

    def privilegedStartService(self):
        self.store = Store(*self.a, **self.k)
        def reallyStart():
            IService(self.store).setServiceParent(self)
            MultiService.privilegedStartService(self)
        self.store.transact(reallyStart)

    def close(self, ignored=None):
        # final close method, called after the service has been stopped
        self.store.close()
        self.store = None
        return ignored

    def stopService(self):
        return defer.maybeDeferred(
            MultiService.stopService, self).addBoth(
            self.close)
