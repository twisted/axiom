# -*- test-case-name: axiom.test.test_dependency -*-
"""
A dependency management system for items.

This module provides C{DependencyMixin}, which enables dependency
management on items that subclass it, and C{dependsOn}, an attribute
that provides automatic loading of dependent items.
"""

import sys, itertools
from zope.interface.advice import addClassAdvisor
from zope.interface import Interface
from axiom.item import Item
from axiom.attributes import reference, boolean, AND
from axiom.errors import ItemNotFound, DependencyError
#There is probably a cleaner way to do this.
_globalDependencyMap = {}

def dependentsOf(cls):
    deps = _globalDependencyMap.get(cls, None)
    if deps is None:
        return []
    else:
        return [d[0] for d in deps]

##Totally ripping off z.i

def dependsOn(itemType, itemCustomizer=None, doc='',
              indexed=True, whenDeleted=reference.NULLIFY):
    """
    This function behaves like L{axiom.attributes.reference} but with
    an extra behaviour: when this item is installed (via
    L{axiom.dependency.DependencyMixin.install} on a target item, the
    type named here will be instantiated and installed on the target
    as well.

    For example::

      class Foo(Item, DependencyMixin):
          counter = integer()
          thingIDependOn = dependsOn(Baz, lambda baz: baz.setup())

    @param itemType: The Item class to instantiate and install.
    @param itemCustomizer: A callable that accepts the item installed
    as a dependency as its first argument. It will be called only if
    an item is created to satisfy this dependency.

    @return: An L{axiom.attributes.reference} instance.
    """

    frame = sys._getframe(1)
    locals = frame.f_locals

    # Try to make sure we were called from a class def.
    if (locals is frame.f_globals) or ('__module__' not in locals):
        raise TypeError("dependsOn can be used only from a class definition.")
    ref = reference(reftype=itemType, doc=doc, indexed=indexed, allowNone=True,
                    whenDeleted=whenDeleted)
    if "__dependsOn_advice_data__" not in locals:
        addClassAdvisor(_dependsOn_advice)
    locals.setdefault('__dependsOn_advice_data__', []).append(
    (itemType, itemCustomizer, ref))
    return ref

def _dependsOn_advice(cls):
    if cls in _globalDependencyMap:
        print "Double advising of %s. dependency map from first time: %s" % (
            cls, _globalDependencyMap[cls])
        #bail if we end up here twice, somehow
        return cls
    for itemType, itemCustomizer, ref in cls.__dict__[
        '__dependsOn_advice_data__']:
        classDependsOn(cls, itemType, itemCustomizer, ref)
    del cls.__dependsOn_advice_data__
    return cls

def classDependsOn(cls, itemType, itemCustomizer, ref):
    _globalDependencyMap.setdefault(cls, []).append(
        (itemType, itemCustomizer, ref))

class _DependencyConnector(Item):
    """
    I am a connector between installed items and their targets.
    """
    installee = reference(doc="The item installed.")
    target = reference(doc="The item installed upon.")
    explicitlyInstalled = boolean(doc="Whether this item was installed"
                                  "explicitly (and thus whether or not it"
                                  "should be automatically uninstalled when"
                                  "nothing depends on it)")


def installOn(self, target):
    """
    Install this object on the target, tracking that the object now
    depends on the target, and the object was explicitly installed
    and therefore should not be uninstalled by subsequent
    uninstallation operations unless it is explicitly removed.

    If the type of the object being installed has a
    "powerupInterfaces" attribute (containing either an interface, a
    sequence of interfaces, or a sequence of (interface, priority)
    tuples), the target will be powered up with this object on those
    interfaces.

    If this object has a "__getPowerupInterfaces__" method, it will
    be called with an iterable of (interface, priority) tuples. The
    iterable of (interface, priority) tuples it returns will then be
    installed.
    """
    _installOn(self, target, True)

def _getPowerupInterfaces(obj):
    powerupInterfaces = getattr(obj.__class__, "powerupInterfaces", ())
    pifs = []
    for x in powerupInterfaces:
        if isinstance(x, type(Interface)):
            #just an interface
            pifs.append((x, 0))
        else:
            #an interface and a priority
            pifs.append(x)

    m = getattr(obj, "__getPowerupInterfaces__", None)
    if m is not None:
        pifs = m(pifs)
        try:
            pifs = [(i, p) for (i, p) in pifs]
        except ValueError:
            raise ValueError("return value from %r.__getPowerupInterfaces__ not an iterable of 2-tuples" % (obj,))
    return pifs

def _installOn(self, target, __explicitlyInstalled=False):
    depBlob = _globalDependencyMap.get(self.__class__, [])
    dependencies, itemCustomizers, refs = (map(list, zip(*depBlob))
                                         or ([], [], []))
    #See if any of our dependencies have been installed already
    for dc in self.store.query(_DependencyConnector,
                               _DependencyConnector.target == target):
        if dc.installee.__class__ in dependencies:
            i = dependencies.index(dc.installee.__class__)
            refs[i].__set__(self, dc.installee)
            del dependencies[i], itemCustomizers[i], refs[i]
        if (dc.installee.__class__ == self.__class__
            and self.__class__ in set(
            itertools.chain([blob[0][0] for blob in
                             _globalDependencyMap.values()]))):
            #Somebody got here before we did... let's punt
            raise DependencyError("An instance of %r is already "
                                  "installed on %r." % (self.__class__,
                                                        target))
    #The rest we'll install
    for i, cls in enumerate(dependencies):
        it = cls(store=self.store)
        if itemCustomizers[i] is not None:
            itemCustomizers[i](it)
        _installOn(it, target, False)
        refs[i].__set__(self, it)
    #And now the connector for our own dependency.

    dc = self.store.findUnique(_DependencyConnector, AND(_DependencyConnector.target==target,
                                                    _DependencyConnector.installee==self,
                                                    _DependencyConnector.explicitlyInstalled==__explicitlyInstalled),
                          None)
    assert dc is None, "Dependency connector already exists, wtf are you doing?"
    _DependencyConnector(store=self.store, target=target,
                         installee=self,
                         explicitlyInstalled=__explicitlyInstalled)

    for interface, priority in _getPowerupInterfaces(self):
        target.powerUp(self, interface, priority)

    callback = getattr(self, "installed", None)
    if callback is not None:
        callback()

def uninstallFrom(self, target):
    """
    Remove this object from the target, as well as any dependencies
    that it automatically installed which were not explicitly
    "pinned" by calling "install", and raising an exception if
    anything still depends on this.

    If the type of the object being uninstalled has a
    "powerupInterfaces" attribute, (containing either an interface, a
    sequence of interfaces, or a sequence of (interface, priority)
    tuples), the target will be powered down with this object on those
    interfaces.

    If this object has a "__getPowerupInterfaces__" method, it will
    be called with an iterable of (interface, priority) tuples. The
    iterable of (interface, priority) tuples it returns will then be
    uninstalled.
    """

    #did this class powerup on any interfaces? powerdown if so.
    for interface, priority in _getPowerupInterfaces(self):
        target.powerDown(self, interface)


    for dc in self.store.query(_DependencyConnector,
                               _DependencyConnector.target==target):
        if dc.installee is self:
            dc.deleteFromStore()

    for item in installedUniqueRequirements(self, target):
        uninstallFrom(item, target)

    callback = getattr(self, "uninstalled", None)
    if callback is not None:
        callback()

def installedOn(self):
    """
    If this item is installed on another item, return the install
    target. Otherwise return None.
    """
    try:
        return self.store.findUnique(_DependencyConnector,
                                     _DependencyConnector.installee == self
                                     ).target
    except ItemNotFound:
        return None


def installedDependents(self, target):
    """
    Return an iterable of things installed on the target that
    require this item.
    """
    for dc in self.store.query(_DependencyConnector,
                               _DependencyConnector.target == target):
        depends = dependentsOf(dc.installee.__class__)
        if self.__class__ in depends:
            yield dc.installee

def installedUniqueRequirements(self, target):
    """
    Return an iterable of things installed on the target that this item
    requires and are not required by anything else.
    """

    myDepends = dependentsOf(self.__class__)
    #XXX optimize?
    for dc in self.store.query(_DependencyConnector,
                               _DependencyConnector.target==target):
        if dc.installee is self:
            #we're checking all the others not ourself
            continue
        depends = dependentsOf(dc.installee.__class__)
        if self.__class__ in depends:
            raise DependencyError(
                "%r cannot be uninstalled from %r, "
                "%r still depends on it" % (self, target, dc.installee))

        for cls in myDepends[:]:
            #If one of my dependencies is required by somebody
            #else, leave it alone
            if cls in depends:
                myDepends.remove(cls)

    for dc in self.store.query(_DependencyConnector,
                               _DependencyConnector.target==target):
        if (dc.installee.__class__ in myDepends
            and not dc.explicitlyInstalled):
            yield dc.installee

def installedRequirements(self, target):
    """
    Return an iterable of things installed on the target that this
    item requires.
    """
    myDepends = dependentsOf(self.__class__)
    for dc in self.store.query(_DependencyConnector,
                               _DependencyConnector.target == target):
        if dc.installee.__class__ in myDepends:
            yield dc.installee

def onlyInstallPowerups(self, target):
    """
    Only power up the target with this object's powerups, without interacting
    with the dependency system. Useful for situations where multiple instances
    of a class can be powered up on the same target.
    """
    for iface, priority in _getPowerupInterfaces(self):
        target.powerUp(self, iface, priority)
