# -*- test-case-name: axiom.test -*-

import os

from twisted.python.filepath import FilePath

from epsilon.extime import Time

from axiom.slotmachine import Attribute as inmemory

from axiom.errors import NoCrossStoreReferences

_NEEDS_FETCH = object()         # token indicating that a value was not found


class SQLAttribute(inmemory):
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


    def coercer(self, value):
        """
        must return a value equivalent to the data being passed in for it to be
        considered valid for a value of this attribute.  for example, 'int' or
        'str'.
        """

        raise NotImplementedError()


    def infilter(self, pyval, oself):
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

    def __get__(self, oself, type=None):
        if type is not None and oself is None:
            return ColumnComparer(self, type)

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
        dbval = self.infilter(pyval, oself)
        oself.__dirty__[self.attrname] = self, dbval
        oself.touch()
        setattr(oself, self.underlying, pyval)
        if st is not None and st.autocommit:
            oself.checkpoint()

class ColumnComparer:
    def __init__(self, atr, typ):
        self.attribute = atr
        self.type = typ
        self.compared = False   # not yet activated
        self.otherComps = []

    def compare(self, other, sqlop):
        assert not self.compared # activation time
        self.compared = True
        # interim: maybe we want objects later?  right now strings should be fine
        a = self.preArgs = []
        if isinstance(other, ColumnComparer):
            self.otherComps.append(other)
            self.sql = ('(%s.%s %s %s.%s)' % (self.type.getTableName(),
                                              self.attribute.columnName,
                                              sqlop,
                                              other.type.getTableName(),
                                              other.attribute.columnName))
        elif other is None:
            col = (self.type.getTableName(), self.attribute.columnName)
            if sqlop == '=':
                self.sql = '%s.%s IS NULL' % col
            elif sqlop == '!=':
                self.sql = '%s.%s NOT NULL' % col
            else:
                raise TypeError(
                    "None/NULL does not work with %s comparison" % (sqlop,))
        else:
            # convert to constant usable in the database
            self.sql = ('(%s.%s %s ?)' % (self.type.getTableName(),
                                          self.attribute.columnName,
                                          sqlop))
            a.append(other)
        return self

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
        assert not self.compared # activation time
        self.compared = True
        if op.upper() not in self._likeOperators:
            raise ValueError, 'LIKE-style operators are: %s' % self._likeOperators
        if not others:
            raise ValueError, 'Must pass at least one expression to _like'

        sqlParts = []
        self.preArgs = []

        for other in others:
            if isinstance(other, ColumnComparer):
                self.otherComps.append(other)
                sqlParts.append('%s.%s' % (other.type.getTableName(),
                                           other.attribute.columnName))
            elif other is None:
                # LIKE NULL is a silly condition, but it's allowed.
                sqlParts.append('NULL')
            else:
                self.preArgs.append(other)
                sqlParts.append('?')

        self.sql = '(%s.%s %s (%s))' % (self.type.getTableName(),
                                        self.attribute.columnName,
                                        op, ' || '.join(sqlParts))
        return self

    def like(self, *others):
        return self._like('LIKE', *others)
    def not_like(self, *others):
        return self._like('NOT LIKE', *others)
    def startswith(self, other):
        return self._like('LIKE', other, '%')
    def endswith(self, other):
        return self._like('LIKE', '%', other)


    # XXX TODO: improve error reporting
    def getQuery(self):
        return self.sql

    def getArgsFor(self, store):
        return [self.attribute.infilter(arg, None) for arg in self.preArgs]

    def getTableNames(self):
        names = [self.type.getTableName()]
        names.extend([c.type.getTableName() for c in self.otherComps])
        return names

    def _asc(self):
        return 'ORDER BY %s.%s ASC' % (self.type.getTableName(),
                                       self.attribute.columnName)

    def _desc(self):
        return 'ORDER BY %s.%s DESC' % (self.type.getTableName(),
                                        self.attribute.columnName)

    descending = property(_desc)
    ascending = property(_asc)
    asc = ascending
    desc = descending


class _BooleanCondition:
    operator = None

    def __init__(self, *conditions):
        if self.operator is None:
            raise NotImplementedError, ('%s cannot be used; you want AND or OR.'
                                        % self.__class__.__name__)
        if not conditions:
            raise ValueError, ('%s condition requires at least one argument'
                               % self.operator)
        self.conditions = conditions

    def getQuery(self):
        oper = ' %s ' % self.operator
        return '(%s)' % oper.join(
            [condition.getQuery() for condition in self.conditions])

    def getArgsFor(self, store):
        args = []
        for cond in self.conditions:
            args += cond.getArgsFor(store)
        return args

    def getTableNames(self):
        tbls = []
        # We only want to join these tables ONCE per expression
        # OR(A.foo=='bar', A.foo=='shoe') should not do "FROM foo, foo"
        for cond in self.conditions:
            for tbl in cond.getTableNames():
                if tbl not in tbls:
                    tbls.append(tbl)
        return tbls

class AND(_BooleanCondition):
    operator = 'AND'

class OR(_BooleanCondition):
    operator = 'OR'

class boolean(SQLAttribute):
    sqltype = 'BOOLEAN'

    def infilter(self, pyval, oself):
        if pyval is True:
            return 1
        elif pyval is False:
            return 0
        else:
            raise TypeError("attribute [%s.%s = boolean()] must be True or False; not %r" %
                            (self.classname, self.attrname, type(pyval).__name__,))

    def outfilter(self, dbval, oself):
        import pdb; pdb.set_trace()
        if dbval == 1:
            return True
        elif dbval == 0:
            return False
        else:
            raise ValueError("attribute [%s.%s = boolean()] must have a database value of 1 or 0; not %r" %
                             (self.classname, self.attrname, dbval))

TOO_BIG = (2 ** 63)-1

class integer(SQLAttribute):
    sqltype = 'INTEGER'
    def infilter(self, pyval, oself):
        if pyval is None:
            return None
        bigness = int(pyval)
        if bigness > TOO_BIG:
            raise OverflowError(
                "Integers larger than %r, such as %r don't fit in the database." % (TOO_BIG, bigness))
        return bigness

class bytes(SQLAttribute):
    """
    Attribute representing a sequence of bytes; this is represented in memory
    as a Python 'str'.
    """

    sqltype = 'BLOB'

    def infilter(self, pyval, oself):
        if pyval is None:
            return None
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

    def infilter(self, pyval, oself):
        if pyval is None:
            return None
        if not isinstance(pyval, unicode) or u'\0' in pyval:
            raise TypeError("attribute [%s.%s = text()] must be (unicode string without NULL bytes); not %r" %
                            (self.classname, self.attrname, type(pyval).__name__,))
        return pyval

    def outfilter(self, dbval, oself):
        return dbval

class path(text):

    def infilter(self, pyval, oself):
        mypath = unicode(pyval.path)
        storepath = os.path.normpath(oself.store.filesdir)
        if not mypath.startswith(storepath):
            raise InvalidPathError('%s not in %s' % (mypath, storepath))
        p = mypath[len(storepath)+1:]   # +1 to include \ or /
        return super(path, self).infilter(p, oself)

    def outfilter(self, dbval, oself):
        if dbval is None:
            return None
        fp = FilePath(os.path.join(oself.store.filesdir, dbval))
        return fp


MICRO = 1000000.

class timestamp(integer):

    def infilter(self, pyval, oself):
        if pyval is None:
            return None
        return integer.infilter(self, pyval.asPOSIXTimestamp() * MICRO, oself)

    def outfilter(self, dbval, oself):
        if dbval is None:
            return None
        return Time.fromPOSIXTimestamp(dbval / MICRO)

class reference(integer):
    def __init__(self, doc='', indexed=True, allowNone=True, reftype=None):
        integer.__init__(self, doc, indexed, None, allowNone)
        self.reftype = reftype

    def infilter(self, pyval, oself):
        if pyval is None:
            return None
        if oself is None:
            return pyval.storeID
        if oself.store is None:
            return pyval.storeID
        if oself.store != pyval.store:
            raise NoCrossStoreReferences(
                "You can't establish references to items in other stores.")

        return integer.infilter(self, pyval.storeID, oself)

    def outfilter(self, dbval, oself):
        if dbval is None:
            return None
        return oself.store.getItemByID(dbval, autoUpgrade=not oself.__legacy__)
