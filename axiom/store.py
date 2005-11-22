# -*- test-case-name: axiom.test -*-

import time
import os
import itertools
import warnings

from zope.interface import implements

from twisted.python import log
from twisted.python.failure import Failure
from twisted.python.filepath import FilePath
from twisted.internet import defer
from twisted.python.reflect import namedAny
from twisted.python.util import unsignedID
from twisted.application.service import IService, IServiceCollection, MultiService

from epsilon.pending import PendingEvent
from epsilon.cooperator import SchedulingService

from axiom import _schema, attributes, upgrade, _fincache, iaxiom, errors

from pysqlite2 import dbapi2 as sqlite

from axiom.item import \
    _typeNameToMostRecentClass, dummyItemSubclass,\
    _legacyTypes, TABLE_NAME, Empowered, serviceSpecialCase

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
        """
        Create an AtomicFile.  (Note: AtomicFiles can only be opened in
        write-binary mode.)

        @param tempname: The filename to open for temporary storage.

        @param destpath: The filename to move this file to when .close() is
        called.
        """
        self._destpath = destpath
        file.__init__(self, tempname, 'w+b')

    def close(self):
        """
        Close this file and commit it to its permanent location.

        @return: a Deferred which fires when the file has been moved (and
        backed up to tertiary storage, if necessary).
        """
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

def storeServiceSpecialCase(st, pups):
    if st.parent is not None:
        # If for some bizarre reason we're starting a substore's service, let's
        # just assume that its parent is running its upgraders, rather than
        # risk starting the upgrader run twice. (XXX: it *IS* possible to
        # figure out whether we need to or not, I just doubt this will ever
        # even happen in practice -- fix here if it does)
        return serviceSpecialCase(st, pups)
    if st.service is not None:
        # not new, don't add twice.
        return st.service
    svc = serviceSpecialCase(st, pups)
    subsvc = st._upgradeService
    subsvc.setServiceParent(svc)
    return svc


class BaseQuery:

    def __init__(self, store, tableClass,
                 comparison=None, limit=None,
                 offset=None, sort=None):
        """
        Create a generic object-oriented interface to SQL, used to implement
        Store.query.

        @param store: the store that this query is within.

        @param tableClass: a subclass of L{Item}.

        @param comparison: an implementor of L{iaxiom.IComparison}

        @param limit: an L{int} that limits the number of results that will be
        queried for, or None to indicate that all results should be returned.

        @param offset: an L{int} that specifies the offset within the query
        results to begin iterating from, or None to indicate that we should
        start at 0.

        @param sort: A sort order object.  Obtained by doing
        C{YourItemClass.yourAttribute.ascending} or C{.descending}.
        """

        self.store = store
        self.tableClass = tableClass
        self.comparison = comparison
        self.limit = limit
        self.offset = offset
        self.sort = sort

    def _sqlAndArgs(self, verb, subject):
        # SQL and arguments
        if self.comparison is not None:
            where = 'WHERE '+self.comparison.getQuery()
            tables = set(self.comparison.getTableNames())
            args = self.comparison.getArgs()
        else:
            where = ''
            tables = set()
            args = []
        tables.add(self.tableClass.getTableName())
        fromClause = ', '.join(tables)
        limitClause = []
        if self.limit is not None:
            # XXX LIMIT and OFFSET used to be using ?, but they started
            # generating syntax errors in places where generating the whole SQL
            # statement does not.  this smells like a bug in sqlite's parser to
            # me, but I don't know my SQL syntax standards well enough to be
            # sure -glyph
            limitClause.append('LIMIT')
            limitClause.append(str(self.limit))
            if self.offset is not None:
                limitClause.append('OFFSET')
                limitClause.append(str(self.offset))
        else:
            assert self.offset is None, 'Offset specified without limit'
        if self.sort is None:
            sort = ''
        else:
            sort = self.sort
        sqlstr = ' '.join([verb, subject,
                           'FROM',
                           ', '.join(tables),
                           where, sort,
                           ' '.join(limitClause)])
        return (sqlstr, args)

    def _runQuery(self, verb, subject):
        # XXX ideally this should be creating an SQL cursor and iterating
        # through that so we don't have to load the whole query into memory,
        # but right now Store's interface to SQL is all through one cursor.
        # I'm not sure how to do this and preserve the chokepoint so that we
        # can do, e.g. transaction fallbacks.
        if not self.store.autocommit:
            self.store.checkpoint()
        tnsv = (self.tableClass.typeName,
                self.tableClass.schemaVersion)
        if tnsv not in self.store.typenameAndVersionToID:
            return []
        sqlstr, sqlargs = self._sqlAndArgs(verb, subject)
        sqlResults = self.store.querySQL(sqlstr, sqlargs)
        return sqlResults

    def __iter__(self):
        """
        Iterate the results of a query object.
        """
        sqlResults = self._runQuery('SELECT', self._queryTarget)
        for row in sqlResults:
            yield self._massageData(row)

    _selfiter = None
    def next(self):
        if self._selfiter is None:
            warnings.warn(
                "Calling 'next' directly on a query is deprecated. "
                "Perhaps you want to use iter(query).next(), or something "
                "more expressive like store.findFirst or store.findOrCreate?",
                DeprecationWarning, stacklevel=2)
            self._selfiter = self.__iter__()
        return self._selfiter.next()

class _FakeItemForFilter:
    __legacy__ = False
    def __init__(self, store):
        self.store = store

class ItemQuery(BaseQuery):
    def __init__(self, *a, **k):
        BaseQuery.__init__(self, *a, **k)
        self._queryTarget = (self.tableClass.getTableName()+'.oid, ' +
                             self.tableClass.getTableName()+'.*')

    def _massageData(self, row):
        return self.store._loadedItem(self.tableClass, row[0], row[1:])

    def getColumn(self, attributeName):
        attr = getattr(self.tableClass, attributeName)
        return AttributeQuery(self.store,
                              self.tableClass,
                              self.comparison,
                              self.limit,
                              self.offset,
                              self.sort,
                              attr)
    def count(self):
        rslt = self._runQuery('SELECT',
                              'COUNT(' + self.tableClass.getTableName() + '.oid'
                              + ')')
        if rslt:
            assert len(rslt) == 1, 'more than one result: %r' % (rslt,)
            return rslt[0][0]
        else:
            return 0


class AttributeQuery(BaseQuery):
    def __init__(self,
                 store,
                 tableClass,
                 comparison=None, limit=None,
                 offset=None, sort=None,
                 attribute=None):
        assert attribute.type is tableClass
        assert attribute is not None
        BaseQuery.__init__(self, store, tableClass,
                           comparison, limit,
                           offset, sort)
        self.attribute = attribute
        self._queryTarget = tableClass.getTableName() + '.' + attribute.columnName

    # XXX: Each implementation of 'outfilter' needs to be changed to deal
    # with self being 'None' in these cases.  most of the ones we're likely
    # to use (e.g. integer) are likely to have this already.
    def _massageData(self, row):
        return self.attribute.outfilter(row[0], _FakeItemForFilter(self.store))

    def sum(self):
        res = self._runQuery('SELECT', 'SUM(%s)' % (self._queryTarget,))
        if res:
            assert len(res) == 1, "more than one result: %r" % (res,)
            dbval = res[0][0]
        else:
            dbval = 0
        return self.attribute.outfilter(dbval, _FakeItemForFilter(self.store))

    def count(self):
        rslt = self._runQuery('SELECT', 'COUNT(%s)' % (self._queryTarget,))
        if rslt:
            assert len(rslt) == 1, 'more than one result: %r' % (rslt,)
            return rslt[0][0]
        else:
            return 0

    def distinct(self):
        """
        Iterate through the distinct values for this column.
        """
        sqlResults = self._runQuery('SELECT DISTINCT', self._queryTarget)
        for row in sqlResults:
            yield self._massageData(row)

class Store(Empowered):
    """
    I am a database that Axiom Items can be stored in.

    Store an item in me by setting its 'store' attribute to be me.

    I can be created one of two ways:

        Store()                      # Create an in-memory database

        Store("/path/to/file.axiom") # create an on-disk database in the
                                     # directory /path/to/file.axiom
    """

    aggregateInterfaces = {
        IService: storeServiceSpecialCase,
        IServiceCollection: storeServiceSpecialCase}

    implements(iaxiom.IBeneficiary)

    transaction = None          # current transaction object

    storeID = -1                # I have a StoreID so that things can reference
                                # me

    store = property(lambda self: self) # I have a 'store' attribute because I
                                        # am 'stored' within myself; this is
                                        # also for references to use.

    def __init__(self, dbdir=None, debug=False, parent=None, idInParent=None):
        """
        Create a store.

        @param dbdir: A name of an existing Axiom directory, or the name of a
        directory that does not exist yet which will be created as this Store
        is instantiated.  If unspecified, this database will be kept in memory.

        @param debug: set to True if this Store should print out every SQL
        statement it sends to SQLite.

        @param parent: (internal) If this is opened using an
        L{axiom.substore.Substore}, a reference to its parent.

        @param idInParent: (internal) If this is opened using an
        L{axiom.substore.Substore}, the storeID of the item within its parent
        which opened it.
        """
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

        self._oldTypesRemaining = [] # a list of old types which have not been
                                     # fully upgraded in this database.

        self.service = None

        for oid, module, typename, version in self.querySQL(_schema.ALL_TYPES):
            self.typenameAndVersionToID[typename, version] = oid
            if typename not in _typeNameToMostRecentClass:
                namedAny(module)

            cls = _typeNameToMostRecentClass.get(typename)

            if cls is not None:
                if version == cls.schemaVersion:
                    self.typenameToID[typename] = oid
                    self.idToTypename[oid] = typename
                else:
                    self._prepareOldVersionOf(oid, typename, version)

        for typename in self.typenameToID:
            self.checkTypeSchemaConsistency(typename)

        if self.parent is None:
            self._upgradeService = SchedulingService()
        else:
            # Substores should hook into their parent, since they shouldn't
            # expect to have their own substore service started.
            self._upgradeService = self.parent._upgradeService

        if self._oldTypesRemaining:
            # Automatically upgrade when possible.
            self._upgradeComplete = PendingEvent()
            self._upgradeService.addIterator(self._upgradeEverything())
        else:
            self._upgradeComplete = None

    def __repr__(self):
        d = self.dbdir
        if d is None:
            d = '(in memory)'
        else:
            d = repr(d)
        return '<Store %s@0x%x>' % (d, unsignedID(self))


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
        """
        Open a new file somewhere in this Store's file area.

        @param path: a sequence of path segments.

        @return: an L{AtomicFile}.
        """
        assert self.dbdir is not None, "Cannot create files in in-memory Stores (yet)"
        assert len(path) > 0, "newFile requires a nonzero number of segments"
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
        """
        Note that this database contains old versions of a particular type.
        Create the appropriate dummy item subclass.
        """
        self._oldTypesRemaining.append(
            dummyItemSubclass(*self._dssargs(typeID, typename, version)))


    def _upgradeOneThing(self):
        """
        Upgrade one Item; return True if there may be more work to do, False if
        this store is definitely fully upgraded.
        """
        while self._oldTypesRemaining:
            t0 = self._oldTypesRemaining[0]
            onething = list(self.query(t0, limit=1))
            if not onething:
                self._oldTypesRemaining.pop(0)
                continue
            o = onething[0]
            self.transact(upgrade.upgradeAllTheWay, o, t0.typeName, t0.schemaVersion)
            return True
        self._upgradeComplete.callback(None)
        self._upgradeComplete = None
        return False

    def _upgradeEverything(self):
        while self._upgradeOneThing():
            yield None

    def whenFullyUpgraded(self):
        """
        Return a Deferred which fires when this Store has been fully upgraded.
        """
        if self._upgradeComplete is not None:
            return self._upgradeComplete.deferred()
        else:
            return defer.succeed(None)

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

    def findUnique(self, tableClass, comparison=None, default=_noItem):
        """
        Find an Item in the database which should be unique.  If it is found,
        return it.  If it is not found, return 'default' if it was passed,
        otherwise raise L{errors.ItemNotFound}.  If more than one item is
        found, raise L{errors.DuplicateUniqueItem}.

        @param comparison: implementor of L{iaxiom.IComparison}.

        @param default: value to use if the item is not found.
        """
        results = list(self.query(tableClass, comparison, limit=2))
        lr = len(results)

        if lr == 0:
            if default is _noItem:
                raise errors.ItemNotFound(comparison)
            else:
                return default
        elif lr == 2:
            raise errors.DuplicateUniqueItem(comparison, results)
        elif lr == 1:
            return results[0]
        else:
            raise AssertionError("limit=2 database query returned 3+ results: ",
                                 comparison, results)


    def query(self, *a, **k):
        """
        Return a generator of objects which match an L{IComparison} predicate.
        """
        return ItemQuery(self, *a, **k)

    def sum(self, summableAttribute, *a, **k):
        args = (self, summableAttribute.type) + a
        return AttributeQuery(attribute=summableAttribute,
                              *args, **k).sum()

    def count(self, *a, **k):
        return self.query(*a, **k).count()

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
                exc = Failure()
                try:
                    self.revert()
                except:
                    log.err(exc)
                    raise
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
        if not isinstance(storeID, (int, long)):
            raise TypeError("storeID *must* be an int or long, not %r" % (
                    type(storeID).__name__,))
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
                x = self.transact(upgrade.upgradeAllTheWay, x, typename, x.schemaVersion)
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
            if not str(se).endswith('already exists'):
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
