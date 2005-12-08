# -*- test-case-name: axiom.test -*-

from epsilon import hotfix
hotfix.require('twisted', 'filepath_copyTo')

import os

from zope.interface import implements

from twisted.python import filepath
from twisted.python.components import registerAdapter

from epsilon.extime import Time

from axiom.slotmachine import Attribute as inmemory

from axiom.errors import NoCrossStoreReferences

from axiom.iaxiom import IComparison, IOrdering

_NEEDS_FETCH = object()         # token indicating that a value was not found

__metaclass__ = type

class Comparable:
    """ Helper for a thing that can be compared like an SQLAttribute (or is in fact
    an SQLAttribute).  Requires that 'self' have 'type' (Item-subclass) and
    'columnName' (str) attributes, as well as an 'infilter' method in the
    spirit of SQLAttribute, documented below.
    """

    def compare(self, other, sqlop):
        # interim: maybe we want objects later?  right now strings should be fine
        a = []
        tables = [self.type]
        if isinstance(other, Comparable):
            sql = ('(%s.%s %s %s.%s)' % (self.type.getTableName(),
                                         self.columnName,
                                         sqlop,
                                         other.type.getTableName(),
                                         other.columnName))
            tables.append(other.type)
        elif other is None:
            col = (self.type.getTableName(), self.columnName)
            if sqlop == '=':
                sql = '%s.%s IS NULL' % col
            elif sqlop == '!=':
                sql = '%s.%s NOT NULL' % col
            else:
                raise TypeError(
                    "None/NULL does not work with %s comparison" % (sqlop,))
        else:
            # convert to constant usable in the database
            sql = ('(%s.%s %s ?)' % (self.type.getTableName(),
                                     self.columnName,
                                     sqlop))
            a.append(other)
        return AttributeComparison(sql, a, tables, self)

    def oneOf(self, seq):
        """
        Choose items whose attributes are in a fixed set.

        X.oneOf([1, 2, 3])

        Implemented with the SQL 'in' statement.
        """
        nseq = list(seq)
        return AttributeComparison(('%s.%s IN (%s)' % (
                    self.type.getTableName(),
                    self.columnName,
                    ', '.join(['?'] * len(nseq)))),
                                   nseq,
                                   [self.type],
                                   self)

    def __eq__(self, other):
        return self.compare(other, '=')


    def __ne__(self, other):
        return self.compare(other, '!=')


    def __gt__(self, other):
        return self.compare(other, '>')


    def __lt__(self, other):
        return self.compare(other, '<')


    def __ge__(self, other):
        return self.compare(other, '>=')


    def __le__(self, other):
        return self.compare(other, '<=')


    _likeOperators = ('LIKE', 'NOT LIKE')
    def _like(self, op, *others):
        if op.upper() not in self._likeOperators:
            raise ValueError, 'LIKE-style operators are: %s' % self._likeOperators
        if not others:
            raise ValueError, 'Must pass at least one expression to _like'

        sqlParts = []
        sqlArgs = []

        tables = [self.type]

        for other in others:
            if isinstance(other, Comparable):
                sqlParts.append('%s.%s' % (other.type.getTableName(),
                                           other.columnName))
                tables.append(other.type)
            elif other is None:
                # LIKE NULL is a silly condition, but it's allowed.
                sqlParts.append('NULL')
            else:
                sqlParts.append('?')
                sqlArgs.append(other)

        sql = '(%s.%s %s (%s))' % (self.type.getTableName(),
                                   self.columnName,
                                   op, ' || '.join(sqlParts))
        return AttributeComparison(sql, sqlArgs, tables, self)

    def like(self, *others):
        return self._like('LIKE', *others)


    def not_like(self, *others):
        return self._like('NOT LIKE', *others)


    def startswith(self, other):
        return self._like('LIKE', other, '%')


    def endswith(self, other):
        return self._like('LIKE', '%', other)


    # XXX TODO: improve error reporting

    def _asc(self):
        return SimpleOrdering(self, ASC)

    def _desc(self):
        return SimpleOrdering(self, DESC)

    descending = property(_desc)
    ascending = property(_asc)
    asc = ascending
    desc = descending

ASC = 'ASC'
DESC = 'DESC'

class SimpleOrdering:
    """
    Currently this class is mostly internal.  More documentation will follow as
    its interface is finalized.
    """
    implements(IOrdering)

    # maybe this will be a useful public API, for the query something
    # something.

    isDescending = property(lambda self: self.direction == DESC)
    isAscending = property(lambda self: self.direction == ASC)

    def __init__(self, attribute, direction=''):
        self.attribute = attribute
        self.direction = direction

    def columnAndDirection(self):
        """
        'Internal' API.  Called by CompoundOrdering.
        """
        return '%s.%s %s' % (self.attribute.type.getTableName(),
                             self.attribute.columnName,
                             self.direction)

    def orderSQL(self):
        """
        'External' API.  Called by Query objects in store.py.
        """
        return 'ORDER BY ' + self.columnAndDirection()

    def __add__(self, other):
        if isinstance(other, SimpleOrdering):
            return CompoundOrdering([self, other])
        elif isinstance(other, (list, tuple)):
            return CompoundOrdering([self] + list(other))
        else:
            return NotImplemented

    def __radd__(self, other):
        if isinstance(other, SimpleOrdering):
            return CompoundOrdering([other, self])
        elif isinstance(other, (list, tuple)):
            return CompoundOrdering(list(other) + [self])
        else:
            return NotImplemented


class CompoundOrdering:
    """
    List of SimpleOrdering instances.
    """
    implements(IOrdering)

    def __init__(self, seq):
        self.simpleOrderings = list(seq)

    def __add__(self, other):
        """
        Just thinking about what might be useful from the perspective of
        introspecting on query objects... don't document this *too* thoroughly
        yet.
        """
        if isinstance(other, CompoundOrdering):
            return CompoundOrdering(self.simpleOrderings + other.simpleOrderings)
        elif isinstance(other, SimpleOrdering):
            return CompoundOrdering(self.simpleOrderings + [other])
        elif isinstance(other, (list, tuple)):
            return CompoundOrdering(self.simpleOrderings + list(other))
        else:
            return NotImplemented

    def __radd__(self, other):
        """
        Just thinking about what might be useful from the perspective of
        introspecting on query objects... don't document this *too* thoroughly
        yet.
        """
        if isinstance(other, CompoundOrdering):
            return CompoundOrdering(other.simpleOrderings + self.simpleOrderings)
        elif isinstance(other, SimpleOrdering):
            return CompoundOrdering([other] + self.simpleOrderings)
        elif isinstance(other, (list, tuple)):
            return CompoundOrdering(list(other) + self.simpleOrderings)
        else:
            return NotImplemented

    def orderSQL(self):
        return 'ORDER BY ' + (', '.join([o.columnAndDirection() for o in self.simpleOrderings]))

class UnspecifiedOrdering:
    implements(IOrdering)

    def __init__(self, null):
        pass

    def __add__(self, other):
        return IOrdering(other, NotImplemented)

    __radd__ = __add__

    def orderSQL(self):
        return ''


registerAdapter(CompoundOrdering, list, IOrdering)
registerAdapter(CompoundOrdering, tuple, IOrdering)
registerAdapter(UnspecifiedOrdering, type(None), IOrdering)
registerAdapter(SimpleOrdering, Comparable, IOrdering)

class SQLAttribute(inmemory, Comparable):
    """
    Abstract superclass of all attributes.

    _Not_ an attribute itself.

    @ivar indexed: A C{bool} indicating whether this attribute will be indexed
    in the database.

    @ivar default: The value used for this attribute, if no value is specified.
    """
    sqltype = None

    def __init__(self, doc='', indexed=False, default=None, allowNone=True):
        inmemory.__init__(self, doc)
        self.indexed = indexed
        self.default = default
        self.allowNone = allowNone


    def prepareInsert(self, oself, store):
        """
        Override this method to do something to an item to prepare for its
        insertion into a database.
        """

    def coercer(self, value):
        """
        must return a value equivalent to the data being passed in for it to be
        considered valid for a value of this attribute.  for example, 'int' or
        'str'.
        """

        raise NotImplementedError()


    def infilter(self, pyval, oself, store):
        """
        used to convert a Python value to something that lives in the database;
        so called because it is called when objects go in to the database.  It
        takes a Python value and returns an SQL value.
        """
        raise NotImplementedError()

    def outfilter(self, dbval, oself):
        """
        used to convert an SQL value to something that lives in memory; so
        called because it is called when objects come out of the database.  It
        takes an SQL value and returns a Python value.
        """
        return dbval

    # requiredSlots must be called before it's run

    prefix = "_axiom_memory_"
    dbprefix = "_axiom_store_"

    def requiredSlots(self, modname, classname, attrname):
        self.modname = modname
        self.classname = classname
        self.attrname = attrname
        self.columnName = '['+attrname+']'
        self.underlying = self.prefix + attrname
        self.dbunderlying = self.dbprefix + attrname
        yield self.underlying
        yield self.dbunderlying


    def fullyQualifiedName(self):
        return '.'.join([self.modname,
                         self.classname,
                         self.attrname])

    type = None

    def __get__(self, oself, type=None):
        if type is not None and oself is None:
            if self.type is not None:
                assert self.type == type
            else:
                self.type = type
            return self

        pyval = getattr(oself, self.underlying, _NEEDS_FETCH)
        st = getattr(oself, 'store')
        if pyval is _NEEDS_FETCH:
            dbval = getattr(oself, self.dbunderlying, _NEEDS_FETCH)
            if dbval is _NEEDS_FETCH:
                # here is what *is* happening here:

                # SQL attributes are always loaded when an Item is created by
                # loading from the database, either via a query, a getItemByID
                # or an attribute access.  If an attribute is left un-set, that
                # means that the item it is on was just created, and we fill in
                # the default value.

                # Here is what *should be*, but *is not* happening here:

                # this condition ought to indicate that a value may exist in
                # the database, but it is not currently available in memory.
                # It would then query the database immediately, loading all
                # SQL-resident attributes related to this item to minimize the
                # number of queries run (e.g. rather than one per attribute)

                # this is a more desireable condition because it means that you
                # can create items "for free", so doing, for example,
                # self.bar.storeID is a much cheaper operation than doing
                # self.bar.baz.  This particular idiom is frequently used in
                # queries and so speeding it up to avoid having to do a
                # database hit unless you actually need an item's attributes
                # would be worthwhile.

                return self.default
            # cache python value
            pyval = self.outfilter(dbval, oself)
            setattr(oself, self.underlying, pyval)
        return pyval

    def loaded(self, oself, dbval):
        setattr(oself, self.dbunderlying, dbval)
        delattr(oself, self.underlying) # member_descriptors don't raise
                                        # attribute errors; what gives?  good
                                        # for us, I guess.

    def __set__(self, oself, pyval):
        # convert to dbval later, I guess?
        if pyval is None and not self.allowNone:
            raise TypeError("attribute [%s.%s = %s()] must not be None" % (
                    self.classname, self.attrname, self.__class__.__name__))

        st = oself.store
        dbval = self.infilter(pyval, oself, st)
        oself.__dirty__[self.attrname] = self, dbval
        oself.touch()
        setattr(oself, self.underlying, pyval)
        if st is not None and st.autocommit:
            oself.checkpoint()


class AttributeComparison:
    """
    A comparison of one attribute with another in-database attribute or with a
    Python value.
    """

    implements(IComparison)

    def __init__(self,
                 sqlString,
                 sqlArguments,
                 involvedTableClasses,
                 leftAttribute):
        self.sqlString = sqlString
        self.sqlArguments = sqlArguments
        self.involvedTableClasses = involvedTableClasses
        self.leftAttribute = leftAttribute

    def getQuery(self):
        return self.sqlString

    def getArgs(self, store):
        return [self.leftAttribute.infilter(arg, None, store) for arg in self.sqlArguments]

    def getInvolvedTables(self):
        return set(self.involvedTableClasses)


class AggregateComparison:
    """
    Abstract base class for compound comparisons that aggregate other
    comparisons - currently only used for AND and OR comparisons.
    """

    implements(IComparison)
    operator = None

    def __init__(self, *conditions):
        self.conditions = conditions
        if self.operator is None:
            raise NotImplementedError, ('%s cannot be used; you want AND or OR.'
                                        % self.__class__.__name__)
        if not conditions:
            raise ValueError, ('%s condition requires at least one argument'
                               % self.operator)

    def getQuery(self):
        oper = ' %s ' % self.operator
        return '(%s)' % oper.join(
            [condition.getQuery() for condition in self.conditions])

    def getArgs(self, store):
        args = []
        for cond in self.conditions:
            args += cond.getArgs(store)
        return args

    def getInvolvedTables(self):
        tbls = set()
        # We only want to join these tables ONCE per expression
        # OR(A.foo=='bar', A.foo=='shoe') should not do "FROM foo, foo"
        for cond in self.conditions:
            tbls.update(cond.getInvolvedTables())
        return tbls

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           ', '.join(map(repr, self.conditions)))

class AND(AggregateComparison):
    """
    Combine 2 L{IComparison}s such that this is true when both are true.
    """
    operator = 'AND'

class OR(AggregateComparison):
    """
    Combine 2 L{IComparison}s such that this is true when either is true.
    """
    operator = 'OR'

class boolean(SQLAttribute):
    sqltype = 'BOOLEAN'

    def infilter(self, pyval, oself, store):
        if pyval is True:
            return 1
        elif pyval is False:
            return 0
        else:
            raise TypeError("attribute [%s.%s = boolean()] must be True or False; not %r" %
                            (self.classname, self.attrname, type(pyval).__name__,))

    def outfilter(self, dbval, oself):
        if dbval == 1:
            return True
        elif dbval == 0:
            return False
        else:
            raise ValueError(
                "attribute [%s.%s = boolean()] "
                "must have a database value of 1 or 0; not %r" %
                (self.classname, self.attrname, dbval))

TOO_BIG = (2 ** 63)-1

class ConstraintError(TypeError):
    """A type constraint was violated.
    """

    def __init__(self,
                 attributeObj,
                 requiredTypes,
                 providedValue):
        self.attributeObj = attributeObj
        self.requiredTypes = requiredTypes
        self.providedValue = providedValue
        TypeError.__init__(self,
                           "attribute [%s.%s = %s()] must be "
                           "(%s); not %r" %
                           (attributeObj.classname,
                            attributeObj.attrname,
                            attributeObj.__class__.__name__,
                            requiredTypes,
                            type(providedValue).__name__))

def requireType(attributeObj, value, typerepr, *types):
    if not isinstance(value, types):
        raise ConstraintError(attributeObj,
                              typerepr,
                              value)

inttyperepr = "integer less than %r" % (TOO_BIG,)

import warnings

class integer(SQLAttribute):
    sqltype = 'INTEGER'
    def infilter(self, pyval, oself, store):
        if pyval is None:
            return None
        requireType(self, pyval, inttyperepr, int, long)
        if pyval > TOO_BIG:
            raise ConstraintError(
                self, inttyperepr, pyval)
        return pyval

class bytes(SQLAttribute):
    """
    Attribute representing a sequence of bytes; this is represented in memory
    as a Python 'str'.
    """

    sqltype = 'BLOB'

    def infilter(self, pyval, oself, store):
        if pyval is None:
            return None
        if isinstance(pyval, unicode):
            raise ConstraintError(self, "str or other byte buffer", pyval)
        return buffer(pyval)

    def outfilter(self, dbval, oself):
        if dbval is None:
            return None
        return str(dbval)

class InvalidPathError(ValueError):
    """
    A path that could not be used with the database was attempted to be used
    with the database.
    """

class text(SQLAttribute):
    """
    Attribute representing a sequence of characters; this is represented in
    memory as a Python 'unicode'.
    """

    def __init__(self, caseSensitive=False, **kw):
        SQLAttribute.__init__(self, **kw)
        if caseSensitive:
            self.sqltype = 'TEXT'
        else:
            self.sqltype = 'TEXT COLLATE NOCASE'
        self.caseSensitive = caseSensitive

    def infilter(self, pyval, oself, store):
        if pyval is None:
            return None
        if not isinstance(pyval, unicode) or u'\0' in pyval:
            raise ConstraintError(
                self, "unicode string without NULL bytes", pyval)
        return pyval

    def outfilter(self, dbval, oself):
        return dbval

class path(text):
    """
    Attribute representing a pathname in the filesystem.  If 'relative=True',
    the default, the representative pathname object must be somewhere inside
    the store, and will migrate with the store.

    I expect L{twisted.python.filepath.FilePath} or compatible objects as my
    values.
    """

    def __init__(self, relative=True, **kw):
        text.__init__(self, **kw)
        self.relative = True

    def prepareInsert(self, oself, store):
        """
        Prepare for insertion into the database by making the dbunderlying
        attribute of the item a relative pathname with respect to the store
        rather than an absolute pathname.
        """
        if self.relative:
            fspath = self.__get__(oself)
            oself.__dirty__[self.attrname] = self, self.infilter(fspath, oself, store)

    def infilter(self, pyval, oself, store):
        if pyval is None:
            return None
        mypath = unicode(pyval.path)
        if store is None:
            store = oself.store
        if store is None:
            return None
        if self.relative:
            # XXX add some more filepath APIs to make this kind of checking easier.
            storepath = os.path.normpath(store.filesdir.path)
            mysegs = mypath.split(os.sep)
            storesegs = storepath.split(os.sep)
            if len(mysegs) <= len(storesegs) or mysegs[:len(storesegs)] != storesegs:
                raise InvalidPathError('%s not in %s' % (mypath, storepath))
            # In the database we use '/' to separate paths for portability.
            # This databaes could have relative paths created on Windows, then
            # be moved to Linux for deployment, and what *was* the native
            # os.sep (backslash) will not be friendly to Linux's filesystem.
            # However, this is only for relative paths, since absolute or UNC
            # pathnames on a Windows system are inherently unportable and it's
            # not reasonable to calculate relative paths outside the store.
            p = '/'.join(mysegs[len(storesegs):])
        else:
            p = mypath          # we already know it's absolute, it came from a
                                # filepath.
        return super(path, self).infilter(p, oself, store)

    def outfilter(self, dbval, oself):
        if dbval is None:
            return None
        if self.relative:
            fp = oself.store.filesdir
            for segment in dbval.split('/'):
                fp = fp.child(segment)
        else:
            fp = filepath.FilePath(dbval)
        return fp


MICRO = 1000000.

class timestamp(integer):
    """
    An in-database representation of date and time.

    To make formatting as easy as possible, this is represented in Python as an
    instance of L{epsilon.extime.Time}; see its documentation for more details.
    """
    def infilter(self, pyval, oself, store):
        if pyval is None:
            return None
        return integer.infilter(self,
                                int(pyval.asPOSIXTimestamp() * MICRO), oself,
                                store)

    def outfilter(self, dbval, oself):
        if dbval is None:
            return None
        return Time.fromPOSIXTimestamp(dbval / MICRO)

class reference(integer):
    def __init__(self, doc='', indexed=True, allowNone=True, reftype=None):
        integer.__init__(self, doc, indexed, None, allowNone)
        self.reftype = reftype


    def prepareInsert(self, oself, store):
        oitem = self.__get__(oself)
        if oitem is not None and oitem.store is not store:
            raise NoCrossStoreReferences(
                "Trying to insert item: %r into store: %r, "
                "but it has a reference to other item: .%s=%r "
                "in another store: %r" % (
                    oself, store,
                    self.attrname, oitem,
                    oitem.store))

    def infilter(self, pyval, oself, store):
        if pyval is None:
            return None
        if oself is None:
            return pyval.storeID
        if oself.store is None:
            return pyval.storeID
        if oself.store != pyval.store:
            raise NoCrossStoreReferences(
                "You can't establish references to items in other stores.")

        return integer.infilter(self, pyval.storeID, oself, store)

    def outfilter(self, dbval, oself):
        if dbval is None:
            return None
        return oself.store.getItemByID(dbval, autoUpgrade=not oself.__legacy__)

class ieee754_double(SQLAttribute):
    """
    From the SQLite documentation:

        'Each value stored in an SQLite database (or manipulated by the
        database engine) has one of the following storage classes: (...)
        REAL. The value is a floating point value, stored as an 8-byte IEEE
        floating point number.'

    This attribute type implements IEEE754 double-precision binary
    floating-point storage.  Some people call this 'float', and think it is
    somehow related to numbers.  This assumption can be misleading when working
    with certain types of data.

    This attribute name has an unweildy name on purpose.  You should be aware
    of the caveats related to binary floating point math before using this
    type.  It is particularly ill-advised to use it to store values
    representing large amounts of currency as rounding errors may be
    significant enough to introduce accounting discrepancies.

    Certain edge-cases are not handled properly.  For example, INF and NAN are
    considered by SQLite to be equal to everything, rather than the Python
    interpretation where INF is equal only to itself and greater than
    everything, and NAN is equal to nothing, not even itself.
    """

    sqltype = 'REAL'

    def infilter(self, pyval, oself, store):
        if pyval is None:
            return None
        requireType(self, pyval, 'float', float)
        return pyval

    def outfilter(self, dbval, oself):
        return dbval
