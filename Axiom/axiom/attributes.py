# -*- test-case-name: axiom.test.test_attributes -*-

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

USING_APSW = False

_NEEDS_FETCH = object()         # token indicating that a value was not found

__metaclass__ = type

class Comparable:
    """
    Helper for a thing that can be compared like an SQLAttribute (or is in fact
    an SQLAttribute).  Requires that 'self' have 'type' (Item-subclass) and
    'columnName' (str) attributes, as well as an 'infilter' method in the
    spirit of SQLAttribute, documented below.
    """

    def compare(self, other, sqlop):
        # interim: maybe we want objects later?  right now strings should be fine
        a = []
        tables = [self.type]
        if isinstance(other, Comparable):
            return TwoAttributeComparison(self, sqlop, other)
        elif other is None:
            if sqlop == '=':
                negate = False
            elif sqlop == '!=':
                negate = True
            else:
                raise TypeError(
                    "None/NULL does not work with %s comparison" % (sqlop,))
            return NullComparison(self, negate)
        else:
            # convert to constant usable in the database
            return AttributeValueComparison(self, sqlop, other)

    def oneOf(self, seq, negate=False):
        """
        Choose items whose attributes are in a fixed set.

        X.oneOf([1, 2, 3])

        Implemented with the SQL 'in' statement.
        """
        return SequenceComparison(self, list(seq), negate)

    def notOneOf(self, seq):
        return self.oneOf(seq, negate=True)

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
    def _like(self, negate, *others):
        if not others:
            raise ValueError, 'Must pass at least one expression to _like'

        likeParts = []

        for other in others:
            if isinstance(other, Comparable):
                likeParts.append(LikeColumn(other))
            elif other is None:
                # LIKE NULL is a silly condition, but it's allowed.
                likeParts.append(LikeNull())
            else:
                likeParts.append(LikeValue(other))

        return LikeComparison(self, negate, likeParts)

    def like(self, *others):
        return self._like(False, *others)


    def notLike(self, *others):
        return self._like(True, *others)


    def startswith(self, other):
        return self._like(False, other, '%')


    def endswith(self, other):
        return self._like(False, '%', other)


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

    def columnAndDirection(self, store):
        """
        'Internal' API.  Called by CompoundOrdering.
        """
        return '%s %s' % (self.attribute.getColumnName(store),
                          self.direction)

    def orderSQL(self, store):
        """
        'External' API.  Called by Query objects in store.py.
        """
        return 'ORDER BY ' + self.columnAndDirection(store)

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

    def orderSQL(self, store):
        return 'ORDER BY ' + (', '.join([o.columnAndDirection(store) for o in self.simpleOrderings]))

class UnspecifiedOrdering:
    implements(IOrdering)

    def __init__(self, null):
        pass

    def __add__(self, other):
        return IOrdering(other, NotImplemented)

    __radd__ = __add__

    def orderSQL(self, store):
        return ''


registerAdapter(CompoundOrdering, list, IOrdering)
registerAdapter(CompoundOrdering, tuple, IOrdering)
registerAdapter(UnspecifiedOrdering, type(None), IOrdering)
registerAdapter(SimpleOrdering, Comparable, IOrdering)

def compoundIndex(*columns):
    for column in columns:
        column.compoundIndexes.append(columns)

class SQLAttribute(inmemory, Comparable):
    """
    Abstract superclass of all attributes.

    _Not_ an attribute itself.

    @ivar indexed: A C{bool} indicating whether this attribute will be indexed
    in the database.

    @ivar default: The value used for this attribute, if no value is specified.
    """
    sqltype = None

    def __init__(self, doc='', indexed=False, default=None, allowNone=True, defaultFactory=None):
        inmemory.__init__(self, doc)
        self.indexed = indexed
        self.compoundIndexes = []
        self.allowNone = allowNone
        self.default = default
        self.defaultFactory = defaultFactory
        if default is not None and defaultFactory is not None:
            raise ValueError("You may specify only one of default "
                             "or defaultFactory, not both")

    def getColumnName(self, st):
        return self.type.getTableName(st) + '.' + self.columnName

    def computeDefault(self):
        if self.defaultFactory is not None:
            return self.defaultFactory()
        return self.default

    def reprFor(self, oself):
        return repr(self.__get__(oself))


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

    def __repr__(self):
        return '<%s %s>' % ( self.__class__.__name__, self.fullyQualifiedName())

    def type():
        def get(self):
            if self._type is None:
                from twisted.python.reflect import namedAny
                self._type = namedAny(self.modname+'.'+self.classname)
            return self._type
        return get,
    _type = None
    type = property(*type())

    def __get__(self, oself, type=None):
        if type is not None and oself is None:
            if self._type is not None:
                assert self._type == type
            else:
                self._type = type
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


class TwoAttributeComparison:
    implements(IComparison)
    def __init__(self, leftAttribute, operationString, rightAttribute):
        self.leftAttribute = leftAttribute
        self.operationString = operationString
        self.rightAttribute = rightAttribute

    def getQuery(self, store):
        sql = ('(%s %s %s)' % (self.leftAttribute.getColumnName(store),
                               self.operationString,
                               self.rightAttribute.getColumnName(store)))
        return sql

    def getInvolvedTables(self):
        return set([self.leftAttribute.type, self.rightAttribute.type])

    def getArgs(self, store):
        return []


class AttributeValueComparison:
    implements(IComparison)
    def __init__(self, attribute, operationString, value):
        self.attribute = attribute
        self.operationString = operationString
        self.value = value

    def getQuery(self, store):
        return ('(%s %s ?)' % (self.attribute.getColumnName(store),
                               self.operationString))

    def getArgs(self, store):
        return [self.attribute.infilter(self.value, None, store)]

    def getInvolvedTables(self):
        return set([self.attribute.type])

    def __repr__(self):
        return ' '.join((self.attribute.fullyQualifiedName(),
                         self.operationString,
                         repr(self.value)))

class NullComparison:
    implements(IComparison)
    def __init__(self, attribute, negate=False):
        self.attribute = attribute
        self.negate = negate

    def getQuery(self, store):
        if self.negate:
            op = 'NOT'
        else:
            op = 'IS'
        return ('(%s %s NULL)' % (self.attribute.getColumnName(store),
                                  op))

    def getArgs(self, store):
        return []

    def getInvolvedTables(self):
        return set([self.attribute.type])

class LikeFragment:
    def getLikeArgs(self):
        return []

    def getLikeQuery(self, st):
        raise NotImplementedError()

    def getLikeTables(self):
        return []

class LikeNull(LikeFragment):
    def getLikeQuery(self, st):
        return "NULL"

class LikeValue(LikeFragment):
    def __init__(self, value):
        self.value = value

    def getLikeQuery(self, st):
        return "?"

    def getLikeArgs(self):
        return [self.value]

class LikeColumn(LikeFragment):
    def __init__(self, attribute):
        self.attribute = attribute

    def getLikeQuery(self, st):
        return self.attribute.getColumnName(st)

    def getLikeTables(self):
        return [self.attribute.type]


class LikeComparison:
    implements(IComparison)
    # Not AggregateComparison or AttributeValueComparison because there is a
    # different, optimized syntax for 'or'.  WTF is wrong with you, SQL??

    def __init__(self, attribute, negate, likeParts):
        self.negate = negate
        self.attribute = attribute
        self.likeParts = likeParts

    def getInvolvedTables(self):
        tbls = set()
        for lf in self.likeParts:
            tbls.update(lf.getLikeTables())
        return tbls

    def getQuery(self, store):
        if self.negate:
            op = 'NOT LIKE'
        else:
            op = 'LIKE'
        sqlParts = [lf.getLikeQuery(store) for lf in self.likeParts]
        sql = '(%s %s (%s))' % (self.attribute.getColumnName(store),
                                op, ' || '.join(sqlParts))
        return sql

    def getArgs(self, store):
        l = []
        for lf in self.likeParts:
            for pyval in lf.getLikeArgs():
                l.append(
                    self.attribute.infilter(
                        pyval, None, store))
        return l



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

    def getQuery(self, store):
        oper = ' %s ' % self.operator
        return '(%s)' % oper.join(
            [condition.getQuery(store) for condition in self.conditions])

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

class SequenceComparison:
    def __init__(self, attribute, seq, negate):
        self.attribute = attribute
        self.seq = seq
        self.negate = negate

    def getQuery(self, store):
        return '%s %sIN (%s)' % (
            self.attribute.getColumnName(store),
            self.negate and 'NOT ' or '',
            ', '.join(['?'] * len(self.seq)))

    def getArgs(self, store):
        return [self.attribute.infilter(pyval, None, store) for pyval in self.seq]

    def getInvolvedTables(self):
        return set([self.attribute.type])

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
        if pyval is None:
            return None
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

    if USING_APSW:
        def outfilter(self, dbval, oself):
            if type(dbval) is str:
                return unicode(dbval, 'ascii')
            return dbval
    else:
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

_cascadingDeletes = {}

class reference(integer):
    NULLIFY = object()
    DISALLOW = object()
    CASCADE = object()

    def __init__(self, doc='', indexed=True, allowNone=True, reftype=None,
                 whenDeleted=NULLIFY):
        integer.__init__(self, doc, indexed, None, allowNone)
        assert whenDeleted in (reference.NULLIFY,
                               reference.CASCADE,
                               reference.DISALLOW),(
            "whenDeleted must be one of: "
            "reference.NULLIFY, reference.CASCADE, reference.DISALLOW")
        self.reftype = reftype
        self.whenDeleted = whenDeleted
        if whenDeleted is reference.CASCADE:
            # Note; this list is technically in a slightly inconsistent state
            # as things are being built.
            _cascadingDeletes.setdefault(reftype, []).append(self)

    def reprFor(self, oself):
        sid = getattr(oself, self.dbunderlying, None)
        if sid is None:
            return 'None'
        return 'reference(%d)' % (sid,)

    def __get__(self, oself, type=None):
        rv = super(reference, self).__get__(oself, type)
        if rv is self:
            # If it's an attr lookup on the class, just do that.
            return self
        if rv is None:
            return rv
        if not rv._currentlyValidAsReferentFor(oself.store):
            # Make sure it's currently valid, i.e. it's not going to be deleted
            # this transaction or it hasn't been deleted.

            # XXX TODO: drop cached in-memory referent if it's been deleted /
            # no longer valid.
            assert self.whenDeleted is reference.NULLIFY, (
                "not sure what to do if not...")
            return None
        return rv

    def prepareInsert(self, oself, store):
        oitem = super(reference, self).__get__(oself) # bypass NULLIFY
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
