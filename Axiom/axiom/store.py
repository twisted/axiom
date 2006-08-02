# -*- test-case-name: axiom.test -*-

from epsilon import hotfix
hotfix.require('twisted', 'filepath_copyTo')

import time
import os
import itertools
import warnings
import sys

from zope.interface import implements

from twisted.python import log
from twisted.python.failure import Failure
from twisted.python import filepath
from twisted.internet import defer
from twisted.python.reflect import namedAny, qual
from twisted.python.util import unsignedID
from twisted.application.service import IService, IServiceCollection

from epsilon.pending import PendingEvent
from epsilon.cooperator import SchedulingService

from axiom import _schema, attributes, upgrade, _fincache, iaxiom, errors, batch

# Doing this in a slightly awkward way so Pyflakes won't complain; it really
# doesn't like conditional imports.
if attributes.USING_APSW:
    backendName = 'axiom._apsw.Connection'
else:
    backendName = 'axiom._pysqlite2.Connection'

Connection = namedAny(backendName)


from axiom.item import \
    _typeNameToMostRecentClass, declareLegacyItem,\
    _legacyTypes, Empowered, serviceSpecialCase, _StoreIDComparer

IN_MEMORY_DATABASE = ':memory:'

tempCounter = itertools.count()

class NoEmptyItems(Exception):
    """You must define some attributes on every item.
    """

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
    if st._axiom_service is not None:
        # not new, don't add twice.
        return st._axiom_service

    collection = serviceSpecialCase(st, pups)

    st._upgradeService.setServiceParent(collection)

    if st.dbdir is not None:
        batcher = batch.BatchProcessingControllerService(st)
        batcher.setServiceParent(collection)

    return collection


def _typeIsTotallyUnknown(typename, version):
    return ((typename not in _typeNameToMostRecentClass)
            and ((typename, version) not in _legacyTypes))

class BaseQuery:
    implements(iaxiom.IQuery)

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
        self.sort = iaxiom.IOrdering(sort)
        self._computeFromClause()


    def _computeFromClause(self):
        """
        Generate the SQL string which follows the "FROM" string and before the
        "WHERE" string in the final SQL statement.
        """
        # SQL and arguments
        if self.comparison is not None:
            tables = self.comparison.getInvolvedTables()
            self.args = self.comparison.getArgs(self.store)
        else:
            tables = set()
            self.args = []
        tables.add(self.tableClass)
        tables.update(self.sort.getInvolvedTables())

        tableAliases = []
        fromClauseParts = []
        for table in sorted(tables):
            # The indirect calls to store.getTableName() will create the tables
            # if needed. (XXX That's bad, actually.  They should get created
            # some other way if necessary.  -exarkun)
            tableName = table.getTableName(self.store)
            tableAlias = table.getTableAlias(self.store, tuple(tableAliases))
            if tableAlias is None:
                fromClauseParts.append(tableName)
            else:
                tableAliases.append(tableAlias)
                fromClauseParts.append('%s AS %s' % (tableName, tableAlias))
        self.fromClause = ', '.join(fromClauseParts)
        self.sortClause = self.sort.orderSQL(self.store)


    def _sqlAndArgs(self, verb, subject):

        # Generate the WHERE clause separately from determining the tables
        # which are involved so that the loop over those tables above has a
        # chance to call getTableAlias, which may have side-effects.
        if self.comparison is not None:
            where = 'WHERE ' + self.comparison.getQuery(self.store)
        else:
            where = ''

        limitClause = []
        if self.limit is not None:
            # XXX LIMIT and OFFSET used to be using ?, but they started
            # generating syntax errors in places where generating the whole SQL
            # statement does not.  this smells like a bug in sqlite's parser to
            # me, but I don't know my SQL syntax standards well enough to be
            # sure -glyph
            if not isinstance(self.limit, (int, long)):
                raise TypeError("limit must be an integer: %r" % (self.limit,))
            limitClause.append('LIMIT')
            limitClause.append(str(self.limit))
            if self.offset is not None:
                if not isinstance(self.offset, (int, long)):
                    raise TypeError("offset must be an integer: %r" % (self.offset,))
                limitClause.append('OFFSET')
                limitClause.append(str(self.offset))
        else:
            assert self.offset is None, 'Offset specified without limit'

        sqlstr = ' '.join(
            filter(
                None,
                [verb, subject, 'FROM', self.fromClause,
                 where, self.sortClause,
                 ' '.join(limitClause)]))
        return (sqlstr, self.args)


    def _runQuery(self, verb, subject):
        # XXX ideally this should be creating an SQL cursor and iterating
        # through that so we don't have to load the whole query into memory,
        # but right now Store's interface to SQL is all through one cursor.
        # I'm not sure how to do this and preserve the chokepoint so that we
        # can do, e.g. transaction fallbacks.
        t= time.time()
        if not self.store.autocommit:
            self.store.checkpoint()
        tnsv = (self.tableClass.typeName,
                self.tableClass.schemaVersion)
        sqlstr, sqlargs = self._sqlAndArgs(verb, subject)
        sqlResults = self.store.querySQL(sqlstr, sqlargs)
        cs = self.locateCallSite()
        log.msg(interface=iaxiom.IStatEvent, querySite=cs, queryTime=time.time()-t, querySQL=sqlstr)
        return sqlResults

    def locateCallSite(self):
        i = 3
        frame = sys._getframe(i)
        while frame.f_code.co_filename == __file__:
            #let's not get stuck in findOrCreate, etc
            i += 1
            frame = sys._getframe(i)
        return (frame.f_code.co_filename, frame.f_lineno)

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
        self._queryTarget = (
            self.tableClass.storeID.getColumnName(self.store) + ', ' + (
                ', '.join(
                    [attrobj.getColumnName(self.store)
                     for name, attrobj in self.tableClass.getSchema()
                     ])))

    def _massageData(self, row):
        result = self.store._loadedItem(self.tableClass, row[0], row[1:])
        assert result.store is not None, "result %r has funky store" % (result,)
        return result

    def getColumn(self, attributeName, raw=False):
        attr = getattr(self.tableClass, attributeName)
        return AttributeQuery(self.store,
                              self.tableClass,
                              self.comparison,
                              self.limit,
                              self.offset,
                              self.sort,
                              attr,
                              raw)
    def count(self):
        rslt = self._runQuery(
            'SELECT',
            'COUNT(' + self.tableClass.storeID.getColumnName(self.store)
            + ')')
        assert len(rslt) == 1, 'more than one result: %r' % (rslt,)
        return rslt[0][0] or 0


    def deleteFromStore(self):
        """
        Delete all the Items which are found by this query.
        """
        # XXX Improve this by using DELETE FROM instead of SELECT+DELETE loop;
        # also, make sure to do some magical introspection to take the slow
        # path if the user has overridden the 'deleted' notification on Item,
        # but don't bother to call it if it's Item's (no-op) implementation.
        for item in self:
            item.deleteFromStore()


_noDefault = object()

class AttributeQuery(BaseQuery):
    def __init__(self,
                 store,
                 tableClass,
                 comparison=None, limit=None,
                 offset=None, sort=None,
                 attribute=None,
                 raw=False):
        assert attribute.type is tableClass
        assert attribute is not None
        BaseQuery.__init__(self, store, tableClass,
                           comparison, limit,
                           offset, sort)
        self.attribute = attribute
        self.raw = raw
        self._queryTarget = attribute.getColumnName(self.store)

    # XXX: Each implementation of 'outfilter' needs to be changed to deal
    # with self being 'None' in these cases.  most of the ones we're likely
    # to use (e.g. integer) are likely to have this already.
    def _massageData(self, row):
        if self.raw:
            return row[0]
        return self.attribute.outfilter(row[0], _FakeItemForFilter(self.store))

    def sum(self):
        #XXX sqlite has a 'total()' function that always returns a
        #float.  If it was used here instead of sum(), these three
        #functions might be refactored together.
        res = self._runQuery('SELECT', 'SUM(%s)' % (self._queryTarget,)) or [(0,)]
        assert len(res) == 1, "more than one result: %r" % (res,)
        dbval = res[0][0] or 0
        return self.attribute.outfilter(dbval, _FakeItemForFilter(self.store))

    def count(self):
        rslt = self._runQuery('SELECT', 'COUNT(%s)' % (self._queryTarget,)) or [(0,)]
        assert len(rslt) == 1, 'more than one result: %r' % (rslt,)
        return rslt[0][0]

    def average(self):
        """Apply the SQL AVG() function to the results of this query."""
        rslt = self._runQuery('SELECT', 'AVG(%s)' % (self._queryTarget,)) or [(0,)]
        assert len(rslt) == 1, 'more than one result: %r' % (rslt,)
        return rslt[0][0]

    def max(self, default=_noDefault):
        return self._functionOnTarget('MAX', default)

    def min(self, default=_noDefault):
        return self._functionOnTarget('MIN', default)

    def _functionOnTarget(self, which, default):
        rslt = self._runQuery('SELECT', '%s(%s)' %
                              (which, self._queryTarget,)) or [(None,)]
        assert len(rslt) == 1, 'more than one result: %r' % (rslt,)
        dbval = rslt[0][0]
        if dbval is None:
            if default is _noDefault:
                raise ValueError, '%s() on table with no items'%(which)
            else:
                return default
        return self.attribute.outfilter(dbval, _FakeItemForFilter(self.store))

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
        IServiceCollection: storeServiceSpecialCase,
        iaxiom.IBatchService: batch.storeBatchServiceSpecialCase}

    implements(iaxiom.IBeneficiary)

    transaction = None          # current transaction object

    storeID = -1                # I have a StoreID so that things can reference
                                # me

    databaseName = 'main'       # can differ if database is attached to another
                                # database.

    dbdir = None # FilePath to the Axiom database directory, or None for
                 # in-memory Stores.
    filesdir = None # FilePath to the filesystem-storage subdirectory of the
                    # database directory, or None for in-memory Stores.

    store = property(lambda self: self) # I have a 'store' attribute because I
                                        # am 'stored' within myself; this is
                                        # also for references to use.

    def _currentlyValidAsReferentFor(self, store):
        """necessary because I can be a target of attributes.reference()
        """
        if store is self:
            return True
        else:
            return False

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

        self._attachedChildren = {} # database name => child store object

        self.statementCache = {} # non-normalized => normalized qmark SQL
                                 # statements

        self.activeTables = {}  # tables which have had items added/removed
                                # this run

        self.objectCache = _fincache.FinalizingCache()

        self.tableQueries = {}  # map typename: query string w/ storeID
                                # parameter.  a typename is a persistent
                                # database handle for what we'll call a 'FQPN',
                                # i.e. arg to namedAny.

        self.typenameAndVersionToID = {} # map database-persistent typename and
                                         # version to an oid in the types table

        self.typeToInsertSQLCache = {}
        self.typeToSelectSQLCache = {}
        self.typeToDeleteSQLCache = {}

        self.typeToTableNameCache = {}
        self.attrToColumnNameCache = {}

        self._oldTypesRemaining = [] # a list of old types which have not been
                                     # fully upgraded in this database.

        self._axiom_service = None


        if self.parent is None:
            self._upgradeService = SchedulingService()
        else:
            # Substores should hook into their parent, since they shouldn't
            # expect to have their own substore service started.
            self._upgradeService = self.parent._upgradeService


        # OK!  Everything that can be set up without touching the filesystem
        # has been done.  Let's get ready to open the actual database...

        _initialOpenFailure = None
        if dbdir is None:
            self._initdb(IN_MEMORY_DATABASE)
            self._initSchema()
        else:
            if not isinstance(dbdir, filepath.FilePath):
                dbdir = filepath.FilePath(dbdir)
                # required subdirs: files, temp, run
                # datafile: db.sqlite
            self.dbdir = dbdir
            self.filesdir = self.dbdir.child('files')

            if not dbdir.isdir():
                tempdbdir = dbdir.temporarySibling()
                tempdbdir.makedirs() # maaaaaaaybe this is a bad idea, we
                                     # probably shouldn't be doing this
                                     # automatically.
                for child in ('files', 'temp', 'run'):
                    tempdbdir.child(child).createDirectory()
                self._initdb(tempdbdir.child('db.sqlite').path)
                self._initSchema()
                self.close(_report=False)
                try:
                    tempdbdir.moveTo(dbdir)
                except:
                    _initialOpenFailure = Failure()

            try:
                self._initdb(dbdir.child('db.sqlite').path)
            except:
                if _initialOpenFailure is not None:
                    log.msg("Failed to initialize axiom database."
                            "  Possible cause of error: ")
                    log.err(_initialOpenFailure)
                raise

        self.transact(self._startup)

        # _startup may have found some things which we must now upgrade.
        if self._oldTypesRemaining:
            # Automatically upgrade when possible.
            self._upgradeComplete = PendingEvent()
            d = self._upgradeService.addIterator(self._upgradeEverything())
            def finishHim(resultOrFailure):
                self._upgradeComplete.callback(resultOrFailure)
                self._upgradeComplete = None
            d.addBoth(finishHim)
        else:
            self._upgradeComplete = None

    _childCounter = 0

    def _attachChild(self, child):
        "attach a child database, returning an identifier for it"
        self._childCounter += 1
        databaseName = 'child_db_%d' % (self._childCounter,)
        self._attachedChildren[databaseName] = child
        # ATTACH DATABASE statements can't use bind paramaters, blech.
        self.executeSQL("ATTACH DATABASE '%s' AS %s" % (
                child.dbdir.child('db.sqlite').path,
                databaseName,))
        return databaseName

    attachedToParent = False

    def attachToParent(self):
        assert self.parent is not None, 'must have a parent to attach'
        assert self.transaction is None, "can't attach within a transaction"

        self.close()

        self.attachedToParent = True
        self.databaseName = self.parent._attachChild(self)
        self.connection = self.parent.connection
        self.cursor = self.parent.cursor

#     def detachFromParent(self):
#         pass


    def _initSchema(self):
        # No point in even attempting to transactionalize this:
        # every single statement is a CREATE TABLE or a CREATE
        # INDEX and those commit transactions silently anyway.
        for stmt in _schema.BASE_SCHEMA:
            self.executeSchemaSQL(stmt)


    def _startup(self):
        """
        Called during __init__.  Check consistency of schema in database with
        classes in memory.  Load all Python modules for stored items, and load
        version information for upgrader service to run later.
        """
        typesToCheck = []
        for oid, module, typename, version in self.querySchemaSQL(_schema.ALL_TYPES):
            if self.debug:
                print
                print 'SCHEMA:', oid, module, typename, version
            self.typenameAndVersionToID[typename, version] = oid
            if typename not in _typeNameToMostRecentClass:
                try:
                    namedAny(module)
                except ValueError, err:
                    raise ImportError('cannot find module ' + module, str(err))

            cls = _typeNameToMostRecentClass.get(typename)

            if cls is not None:
                if version != cls.schemaVersion:
                    typesToCheck.append(
                        self._prepareOldVersionOf(oid, typename, version))
                else:
                    typesToCheck.append(cls)

        for cls in typesToCheck:
            self.checkTypeSchemaConsistency(cls)

        # Schema is consistent!  Now, if I forgot to create any indexes last
        # time I saw this table, do it now...
        for cls in typesToCheck:
            self._createIndexesFor(cls)

        cantUpgradeErrors = []
        for oldVersion in self._oldTypesRemaining:
            # We have to be able to get from oldVersion.schemaVersion to
            # the most recent type.

            currentType = _typeNameToMostRecentClass.get(
                oldVersion.typeName, None)

            if currentType is None:
                # There isn't a current version of this type; it's entirely
                # legacy, will be upgraded by deleting and replacing with
                # something else.
                continue

            typeInQuestion = oldVersion.typeName
            upgver = oldVersion.schemaVersion

            while upgver < currentType.schemaVersion:
                # Do we have enough of the schema present to upgrade?
                if ((typeInQuestion, upgver, upgver+1)
                    not in upgrade._upgradeRegistry):
                    cantUpgradeErrors.append(
                        "No upgrader present for %s (%s) from %d to %d" % (
                            typeInQuestion, qual(currentType), upgver,
                            upgver + 1))

                # Is there a type available for each upgrader version?
                if upgver+1 != currentType.schemaVersion:
                    if (typeInQuestion, upgver+1) not in _legacyTypes:
                        cantUpgradeErrors.append(
                            "Type schema required for upgrade missing:"
                            " %s version %d" % (
                                typeInQuestion, upgver+1))
                upgver += 1
        if cantUpgradeErrors:
            raise errors.NoUpgradePathAvailable('\n    '.join(cantUpgradeErrors))


    def _initdb(self, dbfname):
        self.connection = Connection.fromDatabaseName(dbfname)
        self.cursor = self.connection.cursor()


    def __repr__(self):
        d = self.dbdir
        if d is None:
            d = '(in memory)'
        else:
            d = repr(d)
        return '<Store %s@0x%x>' % (d, unsignedID(self))

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
        newItem = userItemClass(store=self, **attrs)
        if __ifnew is not None:
            __ifnew(newItem)
        return newItem

    def newFilePath(self, *path):
        p = self.filesdir
        for subdir in path:
            p = p.child(subdir)
        return p

    def newTemporaryFilePath(self, *path):
        p = self.dbdir.child('temp')
        for subdir in path:
            p = p.child(subdir)
        return p

    def newFile(self, *path):
        """
        Open a new file somewhere in this Store's file area.

        @param path: a sequence of path segments.

        @return: an L{AtomicFile}.
        """
        assert self.dbdir is not None, "Cannot create files in in-memory Stores (yet)"
        assert len(path) > 0, "newFile requires a nonzero number of segments"
        tmpname = self.dbdir.child('temp').child(str(tempCounter.next()) + ".tmp")
        return AtomicFile(tmpname.path, self.newFilePath(*path))

    def newDirectory(self, *path):
        assert self.dbdir is not None, "Cannot create directories in in-memory Stores (yet)"
        p = self.filesdir
        for subdir in path:
            p = p.child(subdir)
        return p

    def checkTypeSchemaConsistency(self, actualType):
        """
        Called for all known types at database startup: make sure that what we know
        (in memory) about this type is

        """
        # make sure that both the runtime and the database both know about this
        # type; if they don't both know, we can't check that their views are
        # consistent

        inMemorySchema = [(#storedAttribute.indexed,
                           storedAttribute.sqltype,
                           #storedAttribute.allowNone,
                           storedAttribute.attrname)
                          for (name, storedAttribute) in actualType.getSchema()]

        # getTypeID is the wrong thing to do here because it's recursive!
        typeID = self.typenameAndVersionToID[actualType.typeName,
                                             actualType.schemaVersion]

        onDiskSchema = [(ondisksqltype, ondiskattrname) for
                        (ondiskindexed,
                         ondisksqltype,
                         ondiskallownone,
                         ondiskattrname) in
                        self.querySchemaSQL(_schema.IDENTIFYING_SCHEMA,
                                           [typeID])]

        if inMemorySchema != onDiskSchema:
            raise RuntimeError(
                "Schema mismatch on already-loaded %r <%r> object version %d: %r != %r" %
                (actualType, actualType.typeName, actualType.schemaVersion,
                 onDiskSchema, inMemorySchema))


        if actualType.__legacy__:
            return

        if self.querySchemaSQL(_schema.GET_GREATER_VERSIONS_OF_TYPE,
                               [actualType.typeName,
                                actualType.schemaVersion]):
            raise RuntimeError(
                "Greater versions of database %r objects in the DB than in memory" %
                (actualType.typeName,))

        # finally find old versions of the data and prepare to upgrade it.

    def _prepareOldVersionOf(self, typeID, typename, version):
        """
        Note that this database contains old versions of a particular type.
        Create the appropriate dummy item subclass.
        """

        appropriateSchema = self.querySchemaSQL(_schema.SCHEMA_FOR_TYPE, [typeID])
        # create actual attribute objects
        dummyAttributes = {}
        for indexed, pythontype, attribute, docstring in appropriateSchema:
            atr = getattr(attributes, pythontype)(indexed=indexed,
                                                  doc=docstring)
            dummyAttributes[attribute] = atr
        dummyBases = []
        dis = declareLegacyItem(typename, version, dummyAttributes, dummyBases)
        self._oldTypesRemaining.append(dis)
        return dis


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
        return False

    def _upgradeEverything(self):
        didAny = False
        while self._upgradeOneThing():
            if not didAny:
                didAny = True
                log.msg("Beginning upgrade...")
            yield None
        if didAny:
            log.msg("Upgrade complete.")

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



        # grab the schema for that version
        # look up upgraders which push it forward

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


    def findFirst(self, tableClass, comparison=None,
                  offset=None, sort=None, default=None):
        """
        Usage:

            s.findFirst(tableClass [, query arguments except 'limit'])

        Example:

            class YourItemType(Item):
                a = integer()
                b = text()
                c = integer()
            ...
            it = s.findFirst(YourItemType,
                             AND(YourItemType.a == 1,
                                 YourItemType.b == u'2'),
                                 sort=YourItemType.c.descending)

        Search for an item with columns in the database that match the passed
        comparison, offset and sort, returning the first match if one is found,
        or the passed default (None if none is passed) if one is not found.
        """

        limit = 1
        for item in self.query(tableClass, comparison, limit, offset, sort):
            return item
        return default

    def query(self, tableClass, comparison=None,
              limit=None, offset=None, sort=None):
        """
        Return a generator of instances of C{tableClass}.

        Example::

            fastCars = s.query(Vehicle,
                axiom.attributes.AND(
                    Vehicle.wheels == 4,
                    Vehicle.maxKPH > 200),
                limit=100,
                sort=Vehicle.maxKPH.descending)


        @param tableClass: a subclass of Item to look for instances of.

        @param comparison: a provider of L{IComparison}, or None, to match all
        items available in the store.

        @param limit: an int to limit the total length of the results, or None
        for all available results.

        @param offset: an int to specify a starting point within the available
        results, or None to start at 0.

        @param sort: an L{ISort}, something that comes from an SQLAttribute's
        'ascending' or 'descending' attribute.

        @return: an L{ItemQuery} object, which is an iterable of items.
        """
        return ItemQuery(self, tableClass, comparison, limit, offset, sort)

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

    executedThisTransaction = None
    tablesCreatedThisTransaction = None

    def transact(self, f, *a, **k):
        if self.transaction is not None:
            return f(*a, **k)
        if self.attachedToParent:
            return self.parent.transact(f, *a, **k)
        try:
            self._begin()
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
                self._commit()
            return result
        finally:
            self._cleanupTxnState()

    # The following three methods are necessary...

    # - in PySQLite: because PySQLite has some buggy transaction handling which
    #   makes it impossible to issue explicit BEGIN statements - which we
    #   _need_ to do to provide guarantees for read/write transactions.

    # - in APSW: because there are no .commit() or .rollback() methods.

    def _begin(self):
        if self.debug:
            print '<'*10, 'BEGIN', '>'*10
        self.cursor.execute("BEGIN IMMEDIATE TRANSACTION")
        self._setupTxnState()

    def _setupTxnState(self):
        self.executedThisTransaction = []
        self.tablesCreatedThisTransaction = []
        if self.attachedToParent:
            self.transaction = self.parent.transaction
        else:
            self.transaction = set()
        self.autocommit = False
        for sub in self._attachedChildren.values():
            sub._setupTxnState()

    def _commit(self):
        if self.debug:
            print '*'*10, 'COMMIT', '*'*10
        # self.connection.commit()
        self.cursor.execute("COMMIT")
        log.msg(interface=iaxiom.IStatEvent, stat_commits=1)
        self._postCommitHook()

    def _postCommitHook(self):
        for committed in self.transaction:
            committed.committed()

    def _rollback(self):
        if self.debug:
            print '>'*10, 'ROLLBACK', '<'*10
        # self.connection.rollback()
        self.cursor.execute("ROLLBACK")
        log.msg(interface=iaxiom.IStatEvent, stat_rollbacks=1)


    def revert(self):
        self._rollback()
        self._inMemoryRollback()


    def _inMemoryRollback(self):
        for item in self.transaction:
            item.revert()
        self.transaction.clear()
        for tableClass in self.tablesCreatedThisTransaction:
            del self.typenameAndVersionToID[tableClass.typeName,
                                            tableClass.schemaVersion]
            # Clear all cache related to this table
            for cache in (self.typeToInsertSQLCache,
                          self.typeToDeleteSQLCache,
                          self.typeToSelectSQLCache,
                          self.typeToTableNameCache) :
                if tableClass in cache:
                    del cache[tableClass]
            if tableClass.storeID in self.attrToColumnNameCache:
                del self.attrToColumnNameCache[tableClass.storeID]
            for name, attr in tableClass.getSchema():
                if attr in self.attrToColumnNameCache:
                    del self.attrToColumnNameCache[attr]
            
        for sub in self._attachedChildren.values():
            sub._inMemoryRollback()


    def _cleanupTxnState(self):
        self.autocommit = True
        self.transaction = None
        self.executedThisTransaction = None
        self.tablesCreatedThisTransaction = []
        for sub in self._attachedChildren.values():
            sub._cleanupTxnState()

    def close(self, _report=True):
        self.cursor.close()
        self.cursor = self.connection = None
        if self.debug and _report:
            if not self.queryTimes:
                print 'no queries'
            else:
                print 'query:', self.avgms(self.queryTimes)
            if not self.execTimes:
                print 'no execs'
            else:
                print 'exec:', self.avgms(self.execTimes)

    def avgms(self, l):
        return 'count: %d avg: %dus' % (len(l),
                                        int( (sum(l)/len(l)) * 1000000.),)

    def _indexNameOf(self, tableClass, attrname):
        return "%s.axiomidx_%s_v%d_%s" % (self.databaseName,
                                          tableClass.typeName,
                                          tableClass.schemaVersion,
                                          '_'.join(attrname))

    def _tableNameFor(self, typename, version):
        return "%s.item_%s_v%d" % (self.databaseName, typename, version)

    def getTableName(self, tableClass):
        """
        Retrieve the fully qualified name of the table holding items
        of a particular class in this store.  If the table does not
        exist in the database, it will be created as a side-effect.

        @param tableClass: an Item subclass

        @raises L{axiom.errors.ItemClassesOnly}: if an object other than a subclass of Item is passed.

        @return: a string
        """
        from axiom import item
        if not (isinstance(tableClass, type) and issubclass(tableClass, item.Item)):
            raise errors.ItemClassesOnly("Only subclasses of Item have table names.")

        if tableClass not in self.typeToTableNameCache:
            self.typeToTableNameCache[tableClass] = self._tableNameFor(tableClass.typeName, tableClass.schemaVersion)
            # make sure the table exists
            self.getTypeID(tableClass)
        return self.typeToTableNameCache[tableClass]

    def getShortColumnName(self, attribute):
        """
        Retreive the column name for a particular attribute in this
        store.  The attribute must be bound to an Item subclass (its
        type must be valid). If the underlying table does not exist in
        the database, it will be created as a side-effect.

        @param tableClass: an Item subclass

        @return: a string

        XXX: The current implementation does not really match the
        description, which is actually more restrictive. But it will
        be true soon, so I guess it is ok for now.  The reason is
        that this method is used during table creation.
        """
        if isinstance(attribute, _StoreIDComparer):
            return 'oid'
        return '[' + attribute.attrname + ']'


    def getColumnName(self, attribute):
        """
        Retreive the fully qualified column name for a particular
        attribute in this store.  The attribute must be bound to an
        Item subclass (its type must be valid). If the underlying
        table does not exist in the database, it will be created as a
        side-effect.

        @param tableClass: an Item subclass

        @return: a string
        """
        if attribute not in self.attrToColumnNameCache:
            self.attrToColumnNameCache[attribute] = '.'.join(
                (self.getTableName(attribute.type),
                 self.getShortColumnName(attribute)))
        return self.attrToColumnNameCache[attribute]


    def getTypeID(self, tableClass):
        """
        Retrieve the typeID associated with a particular table in the
        in-database schema for this Store.  A typeID is an opaque integer
        representing the Item subclass, and the associated table in this
        Store's SQLite database.

        @param tableClass: a subclass of Item

        @return: an integer
        """
        key = (tableClass.typeName,
               tableClass.schemaVersion)
        if key in self.typenameAndVersionToID:
            return self.typenameAndVersionToID[key]

        # We may need to create a table.  Although we don't have a memory of
        # this table from the last time we called "_startup()", another process
        # may have updated the schema since then.  Let's give it a chance to
        # update the in-memory schema if it has changed on disk.
        self._startup()

        if key in self.typenameAndVersionToID:
            return self.typenameAndVersionToID[key]
        return self.transact(self._actualTableCreation, tableClass, key)

    def _actualTableCreation(self, tableClass, key):
        """
        In the event that an Item subclass which has never before been added to
        the schema of our SQLite database, create the table, update the schema,
        and return the typeID.  This is internal to the implementation of
        getTypeID.  It must be run in a transaction.

        @param tableClass: an Item subclass
        @param key: a 2-tuple of the tableClass's typeName and schemaVersion

        @return: a typeID
        """
        sqlstr = []
        sqlarg = []

        # needs to be calculated including version
        tableName = self._tableNameFor(tableClass.typeName, tableClass.schemaVersion)

        sqlstr.append("CREATE TABLE %s (" % tableName)

        for nam, atr in tableClass.getSchema():
            # it's a stored attribute
            sqlarg.append("\n%s %s" %
                          (atr.getShortColumnName(self), atr.sqltype))

        if len(sqlarg) == 0:
            # XXX should be raised way earlier, in the class definition or something
            raise NoEmptyItems("%r did not define any attributes" % (tableClass,))

        sqlstr.append(', '.join(sqlarg))
        sqlstr.append(')')

        self.createSQL(''.join(sqlstr))

        typeID = self.executeSchemaSQL(_schema.CREATE_TYPE,
                                       [tableClass.typeName,
                                        tableClass.__module__,
                                        tableClass.schemaVersion])

        self.typenameAndVersionToID[key] = typeID
        
        if self.tablesCreatedThisTransaction is not None:
            self.tablesCreatedThisTransaction.append(tableClass)

        self._createIndexesFor(tableClass)

        for n, (name, storedAttribute) in enumerate(tableClass.getSchema()):
            self.executeSchemaSQL(
                _schema.ADD_SCHEMA_ATTRIBUTE,
                [typeID, n, storedAttribute.indexed, storedAttribute.sqltype,
                 storedAttribute.allowNone, storedAttribute.attrname,
                 storedAttribute.doc, storedAttribute.__class__.__name__])
            # XXX probably need something better for pythontype eventually,
            # when we figure out a good way to do user-defined attributes or we
            # start parameterizing references.

        return typeID

    def _createIndexesFor(self, tableClass):
        indexes = set()
        for nam, atr in tableClass.getSchema():
            if atr.indexed:
                indexes.add(((atr.getShortColumnName(self),), (atr.attrname,)))
            for compound in atr.compoundIndexes:
                indexes.add((tuple(inatr.getShortColumnName(self) for inatr in compound),
                             tuple(inatr.attrname for inatr in compound)))

        # _ZOMFG_ SQL is such a piece of _shit_: you can't fully qualify the
        # table name in CREATE INDEX statements because the _INDEX_ is fully
        # qualified!

        indexColumnPrefix = '.'.join(self.getTableName(tableClass).split(".")[1:])

        for (indexColumns, indexAttrs) in indexes:
            csql = ('CREATE INDEX %s ON %s(%s)' %
                    (self._indexNameOf(tableClass, indexAttrs),
                     indexColumnPrefix,
                     ', '.join(indexColumns)))
            try:
                self.createSQL(csql)
            except errors.SQLError, sqle:
                # Ignore duplicate indexes.
                if "already exists" not in str(sqle):
                    raise

    def getTableQuery(self, typename, version):
        if (typename, version) not in self.tableQueries:
            query = 'SELECT * FROM %s WHERE oid = ?' % (
                self._tableNameFor(typename, version), )
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
        log.msg(interface=iaxiom.IStatEvent, stat_cache_misses=1, key=storeID)
        results = self.querySchemaSQL(_schema.TYPEOF_QUERY, [storeID])
        assert (len(results) in [1, 0]),\
            "Database panic: more than one result for TYPEOF!"
        if results:
            typename, module, version = results[0]
            # for the moment we're going to assume no inheritance
            attrs = self.querySQL(self.getTableQuery(typename, version),
                                  [storeID])
            if len(attrs) != 1:
                raise errors.ItemNotFound("No results for known-to-be-good object")
            attrs = attrs[0]
            useMostRecent = False
            moreRecentAvailable = False

            # The schema may have changed since the last time I saw the
            # database.  Let's look to see if this is suspiciously broken...

            if _typeIsTotallyUnknown(typename, version):
                # Another process may have created it - let's re-up the schema
                # and see what we get.
                self._startup()

                # OK, all the modules have been loaded now, everything
                # verified.
                if _typeIsTotallyUnknown(typename, version):

                    # If there is STILL no inkling of it anywhere, we are
                    # almost certainly boned.  Let's tell the user in a
                    # structured way, at least.
                    raise errors.UnknownItemType(
                        "cannot load unknown schema/version pair: %r %r - id: %r" %
                        (typename, version, storeID))

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
        # It turns out that "ATTACH DATABASE" *requires* string interpolation,
        # since it syntactically does not support bind parameters.  It takes a
        # string as a parameter though.  Considering that this assertion was
        # never tripped before I don't feel too bad commenting it out, but I
        # wish there were a way to preserve 'paranoid mode'

        # assert "'" not in sql, "Strings are _NOT ALLOWED_"
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

    def querySchemaSQL(self, sql, args=()):
        sql = sql.replace("*DATABASE*", self.databaseName)
        return self.querySQL(sql, args)

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
        self.cursor.execute(sql, args)
        before = time.time()
        result = list(self.cursor)
        after = time.time()
        if after - before > 2.0:
            log.msg('Extremely long list(cursor): %s' % (after - before,))
            log.msg(sql)
            # import traceback; traceback.print_stack()
        if self.debug:
            print '  lastrow:', self.cursor.lastRowID()
            print '  result:', result
        return result


    def createSQL(self, sql, args=()):
        """
        For use with auto-committing statements such as CREATE TABLE or CREATE
        INDEX.
        """
        before = time.time()
        self._execSQL(sql, args)
        after = time.time()
        if after - before > 2.0:
            log.msg('Extremely long CREATE: %s' % (after - before,))
            log.msg(sql)
            # import traceback; traceback.print_stack()


    def _execSQL(self, sql, args):
        sql = self._normalizeSQL(sql)
        if self.debug:
            rows = timeinto(self.execTimes, self._queryandfetch, sql, args)
        else:
            rows = self._queryandfetch(sql, args)
        assert not rows
        return sql

    def executeSchemaSQL(self, sql, args=()):
        sql = sql.replace("*DATABASE*", self.databaseName)
        return self.executeSQL(sql, args)

    def executeSQL(self, sql, args=()):
        """
        For use with UPDATE or INSERT statements.
        """
        sql = self._execSQL(sql, args)
        result = self.cursor.lastRowID()
        if self.executedThisTransaction is not None:
            self.executedThisTransaction.append((result, sql, args))
        return result

# This isn't actually useful any more.  It turns out that the pysqlite
# documentation is confusingly worded; it's perfectly possible to create tables
# within transactions, but PySQLite's automatic transaction management (which
# we turn off) breaks that.  However, a function very much like it will be
# useful for doing nested transactions without support from the database
# itself, so I'm keeping it here commented out as an example.

#     def _reexecute(self):
#         assert self.executedThisTransaction is not None
#         self._begin()
#         for resultLastTime, sql, args in self.executedThisTransaction:
#             self._execSQL(sql, args)
#             resultThisTime = self.cursor.lastRowID()
#             if resultLastTime != resultThisTime:
#                 raise errors.TableCreationConcurrencyError(
#                     "Expected to get %s as a result "
#                     "of %r:%r, got %s" % (
#                         resultLastTime,
#                         sql, args,
#                         resultThisTime))


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
