# -*- test-case-name: axiom.test -*-

import os

from twisted.python.filepath import FilePath

from axiom.slotmachine import Attribute as inmemory
from axiom.extime import Time

_NEEDS_FETCH = object()         # token indicating that a value was not found

class SQLAttribute(inmemory):
    """
    Abstract superclass of all attributes.

    _Not_ an attribute itself.
    """
    def coercer(self, value):
        """
        must return a value equivalent to the data being passed in for it to be
        considered valid for a value of this attribute.  for example, 'int' or
        'str'.
        """

        raise NotImplementedError()

    sqltype = None

    def __init__(self, doc='', indexed=False):
        inmemory.__init__(self, doc)
        self.indexed = indexed


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

    prefix = "_atop_memory_"
    dbprefix = "_atop_store_"

    def requiredSlots(self, modname, classname, attrname):
        self.modname = modname
        self.classname = classname
        self.attrname = attrname
        self.columnName = attrname
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
                raise AttributeError(self.attrname)
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
        st = oself.store
        dbval = self.infilter(pyval, oself)
        oself.__dirty__[self.attrname] = dbval
        oself.touch()
        setattr(oself, self.underlying, pyval)
        if st is not None and st.autocommit:
            oself.checkpoint()

class ColumnComparer:
    def __init__(self, atr, typ):
        self.attribute = atr
        self.type = typ
        self.compared = False   # not yet activated
        self.otherComp = None

    def compare(self, other, sqlop):
        assert not self.compared # activation time
        self.compared = True
        # interim: maybe we want objects later?  right now strings should be fine
        if isinstance(other, ColumnComparer):
            self.otherComp = other
            self.sql = ('(%s.%s %s %s.%s)' % (self.type.getTableName(),
                                            self.attribute.columnName,
                                            sqlop,
                                            other.type.getTableName(),
                                            other.attribute.columnName))
            self.preArgs = []
        else:
            # convert to constant usable in the database
            self.sql = ('(%s.%s %s ?)' % (self.type.getTableName(),
                                        self.attribute.columnName,
                                        sqlop))
            self.preArgs = [other]
            sql = '?'
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

    # XXX TODO: improve error reporting
    def getQuery(self):
        return self.sql

    def getArgsFor(self, store):
        return [self.attribute.infilter(arg, None) for arg in self.preArgs]

    def getTableNames(self):
        names = [self.type.getTableName()]
        if self.otherComp is not None:
            names.append(self.otherComp.type.getTableName())
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

class AND:
    def __init__(self, a, b):
        self.a = a
        self.b = b

    def getQuery(self):
        return ' '.join(['(',
                         self.a.getQuery(),
                         self.__class__.__name__,
                         self.b.getQuery(),
                         ')'])

    def getArgsFor(self, store):
        return self.a.getArgsFor(store) + self.b.getArgsFor(store)

    def getTableNames(self):
        return (self.a.getTableNames() + self.b.getTableNames())

class OR(AND):
    pass

class integer(SQLAttribute):
    sqltype = 'INTEGER'
    def infilter(self, pyval, oself):
        if pyval is None:
            return None
        return int(pyval)

class bytes(SQLAttribute):
    """
    Attribute representing a sequence of bytes; this is represented in memory
    as a Python 'str'.
    """

    sqltype = 'BLOB'

    def infilter(self, pyval, oself):
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

    def __init__(self, doc='', indexed=False, caseSensitive=False):
        SQLAttribute.__init__(self, doc, indexed)
        if caseSensitive:
            self.sqltype = 'TEXT'
        else:
            self.sqltype = 'TEXT COLLATE NOCASE'
        self.caseSensitive = caseSensitive

    def infilter(self, pyval, oself):
        if not isinstance(pyval, unicode) or '\x00' in pyval:
            raise TypeError("attribute [%s.%s = text()] must be (unicode string without NULL bytes); not %r" %
                            (self.classname, self.attrname, type(pyval).__name__,))
        return pyval

    def outfilter(self, dbval, oself):
        return dbval

class path(text):

    def infilter(self, pyval, oself):
        mypath = unicode(pyval.path)
        storepath = oself.store.filesdir
        if not mypath.startswith(storepath):
            raise InvalidPathError('%s not in %s' % (mypath, storepath))
        p = mypath[len(storepath):]
        if p.startswith('/'):
            p = p[1:]
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
        return int(pyval.asPOSIXTimestamp() * MICRO)

    def outfilter(self, dbval, oself):
        if dbval is None:
            return None
        return Time.fromPOSIXTimestamp(dbval / MICRO)

class reference(integer):
    def __init__(self, doc='', indexed=True, reftype=None):
        integer.__init__(self, doc, indexed)
        self.reftype = reftype

    def infilter(self, pyval, oself):
        if pyval is None:
            return None
        if oself is None:
            return pyval.storeID
        if oself.store != pyval.store:
            raise AttributeError(
                "You can't establish references to items in other stores.")
        if oself.store is None:
            raise AttributeError(
                "TODO: Setting references on items outside of stores is "
                "currently unsupported.  Set .store first.")
        return pyval.storeID

    def outfilter(self, dbval, oself):
        if dbval is None:
            return None
        return oself.store.getItemByID(dbval, autoUpgrade=not oself.__legacy__)

# promotions
