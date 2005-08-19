# -*- test-case-name: axiom.test.test_slotmachine -*-

_borrowed = {}

def borrow(C, slotgather=lambda _slots: None):
    """
    Use implementation, but not identity or inheritance, from a class.  This is
    useful when you want to avoid mucking with class metadata - in particular,
    if you want to have a class which has no slots (and the semantics
    associated with that, i.e. no unintended attributes) which inherits from
    old-style and/or potentially __dict__-ful mixins.
    """
    if C is object:
        return C

    if C in _borrowed:
        C = _borrowed[C]

    if C.__name__.endswith("(Borrowed)"):
        slotgather(C.__all_slots__)
        return C

    D = dict(C.__dict__)
    allslots = list(D.get('__slots__', ()))
    oldslots = allslots[:]

    slotgather(oldslots)

    for oldslot in oldslots:
        # member_descriptor let's hope
        del D[oldslot]

    D['__slots__'] = ()

    def gatherforme(stuff):
        slotgather(stuff)
        allslots.extend(stuff)

    basetuple = []

    for base in C.__bases__:
        basetuple.append(borrow(base, gatherforme))

    allslots = dict.fromkeys(allslots).keys()
    D['__all_slots__'] = allslots
    new = type(C.__name__+"(Borrowed)", tuple(basetuple), D)
    _borrowed[C] = new
    return new

_NOSLOT = object()

class SlotMetaMachine(type):
    def __new__(meta, name, bases, dictionary):
        dictionary['__name__'] = name
        slots = ['__weakref__'] + list(
            meta.determineSchema(dictionary))
        if bases:
            borrowedBases = tuple([borrow(x, slots.extend) for x in bases])
        else:
            borrowedBases = ()
        slots = dict.fromkeys(slots).keys() # uniquify
        fin = []
        for slot in slots:
            for base in borrowedBases:
                baseslot = getattr(base, slot, _NOSLOT)
                if baseslot is not _NOSLOT:
                    if hasattr(baseslot, '__get__') or hasattr(baseslot, '__set__'):
                        # It's a descriptor; if we get in the way, we'll break
                        # it - if we don't get in the way, it leads to
                        # surprising behavior. perhaps further consideration is
                        # in order.
                        if slot == '__weakref__':
                            # ALL new-style classes have a useless 'weakref'
                            # descriptor.  Don't avoid clobbering it, because
                            # it is pretty much designed to be clobbered.
                            fin.append(slot)
                        break
                    underlay = '_conflict_'+slot
                    dictionary[slot] = DescriptorWithDefault(baseslot, underlay)
                    fin.append(underlay)
                    break
            else:
                fin.append(slot)
        slots = fin
        assert '__weakref__' in slots, "__weakref__ not in %r for %r" % (slots, name)
        dictionary['__slots__'] = slots
        nt = type.__new__(meta, name, borrowedBases, dictionary)
        if nt.__dictoffset__:
            raise AssertionError(
                "SlotMachine with __dict__ (this should be impossible)")
        return nt

    def determineSchema(meta, dictionary):
        if '__slots__' in dictionary:
            raise AssertionError(
                "When using SlotMachine, specify 'slots' not '__slots__'")
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

class SchemaMetaMachine(SlotMetaMachine):

    def determineSchema(meta, dictionary):
        attrs = dictionary['__attributes__'] = []
        name = dictionary['__name__']
        moduleName = dictionary['__module__']
        dictitems = dictionary.items()
        dictitems.sort()        # deterministic ordering is important because
                                # we generate SQL schemas from these attribute
                                # lists

        # this does NOT traverse the class hierarchy.  The SlotMetaMachine base
        # class does all the hierarchy-traversing work in its __new__.  Do not
        # add any hierarchy traversal here; it will almost certainly be broken
        # in surprising ways (as if borrow() weren't surprising enough) -glyph

        for k, v in dictitems:
            if isinstance(v, Attribute):
                attrs.append((k, v))
                for slot in v.requiredSlots(moduleName, name, k):
                    if slot == k:
                        del dictionary[k]
                    yield slot

    determineSchema = classmethod(determineSchema)

class SchemaMachine:
    __metaclass__ = SchemaMetaMachine

class SlotMachine:
    __metaclass__ = SlotMetaMachine


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

