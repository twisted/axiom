# -*- test-case-name: axiom.test.test_slotmachine -*-

hyper = super

_NOSLOT = object()

class Allowed(object):
    """
    An attribute that's allowed to be set.
    """
    def __init__(self, name, default=_NOSLOT):
        self.name = name
        self.default = default

    def __get__(self, oself, otype=None):
        if otype is not None and oself is None:
            return self
        if self.name in oself.__dict__:
            return oself.__dict__[self.name]
        if self.default is not _NOSLOT:
            return self.default
        raise AttributeError("%r object did not have attribute %r" %(oself.__class__.__name__, self.name))

    def __delete__(self, oself):
        if self.name not in oself.__dict__:
            # Returning rather than raising here because that's what
            # member_descriptor does, and Axiom relies upon that behavior.
            ## raise AttributeError('%r object has no attribute %r' %
            ##                      (oself.__class__.__name__, self.name))
            return
        del oself.__dict__[self.name]

    def __set__(self, oself, value):
        oself.__dict__[self.name] = value

class _SlotMetaMachine(type):
    def __new__(meta, name, bases, dictionary):
        dictionary['__name__'] = name
        slots = list(meta.determineSchema(dictionary))
        for slot in slots:
            default = _NOSLOT
            for base in bases:
                defval = getattr(base, slot, _NOSLOT)
                if defval is not _NOSLOT:
                    break
            dictionary[slot] = Allowed(slot, defval)
        nt = type.__new__(meta, name, bases, dictionary)
        return nt

    def determineSchema(meta, dictionary):
        return dictionary.get("slots", [])

    determineSchema = classmethod(determineSchema)


class DescriptorWithDefault(object):
    def __init__(self, default, original):
        self.original = original
        self.default = default

    def __get__(self, oself, type=None):
        if type is not None:
            if oself is None:
                return self.default
        return getattr(oself, self.original, self.default)

    def __set__(self, oself, value):
        setattr(oself, self.original, value)

    def __delete__(self, oself):
        delattr(oself, self.original)


class Attribute(object):
    def __init__(self, doc=''):
        self.doc = doc

    def requiredSlots(self, modname, classname, attrname):
        self.name = attrname
        yield attrname

_RAISE = object()
class SetOnce(Attribute):

    def __init__(self, doc='', default=_RAISE):
        Attribute.__init__(self)
        if default is _RAISE:
            self.default = ()
        else:
            self.default = (default,)

    def requiredSlots(self, modname, classname, attrname):
        self.name = attrname
        t = self.trueattr = ('_' + self.name)
        yield t

    def __set__(self, iself, value):
        if not hasattr(iself, self.trueattr):
            setattr(iself, self.trueattr, value)
        else:
            raise AttributeError('%s.%s may only be set once' % (
                    type(iself).__name__, self.name))

    def __get__(self, iself, type=None):
        if type is not None and iself is None:
            return self
        return getattr(iself, self.trueattr, *self.default)

class SchemaMetaMachine(_SlotMetaMachine):

    def determineSchema(meta, dictionary):
        attrs = dictionary['__attributes__'] = []
        name = dictionary['__name__']
        moduleName = dictionary['__module__']
        dictitems = dictionary.items()
        dictitems.sort()
        for k, v in dictitems:
            if isinstance(v, Attribute):
                attrs.append((k, v))
                for slot in v.requiredSlots(moduleName, name, k):
                    if slot == k:
                        del dictionary[k]
                    yield slot

    determineSchema = classmethod(determineSchema)

class _Strict(object):
    """
    I disallow all attributes from being set that do not have an explicit
    descriptor.
    """
    def __setattr__(self, name, value):
        descr = getattr(self.__class__, name, _NOSLOT)
        if descr is _NOSLOT:
            raise AttributeError("%r can't set attribute %r" % (self.__class__.__name__,
                                                                name))
        else:
            descr.__set__(self, value)

class SchemaMachine(_Strict):
    __metaclass__ = SchemaMetaMachine

class SlotMachine(_Strict):
    __metaclass__ = _SlotMetaMachine


class _structlike(list):
    __names__ = []
    __slots__ = []

    def _name2slot(self, name):
        return self.__names__.index(name)

    def __init__(self, *args, **kw):
        super(_structlike, self).__init__(args)
        self.extend([None] * (len(self.__names__) - len(args)))
        for k, v in kw.iteritems():
            self[self._name2slot(k)] = v

    def __getattr__(self, attr):
        try:
            return self[self._name2slot(attr)]
        except (IndexError, ValueError):
            raise AttributeError(attr)

    def __setattr__(self, attr, value):
        try:
            self[self._name2slot(attr)] = value
        except ValueError:
            raise AttributeError(attr)
