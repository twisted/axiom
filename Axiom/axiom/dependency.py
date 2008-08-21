# Copright 2008 Divmod, Inc.  See LICENSE file for details.
# -*- test-case-name: axiom.test.test_dependency -*-
"""
A dependency management system for items.
"""

import sys, itertools, warnings

from twisted.python.reflect import qual
from zope.interface.advice import addClassAdvisor
from zope.interface import Interface

from epsilon.structlike import record

from axiom.item import Item, _PowerupConnector
from axiom.attributes import reference, boolean, AND
from axiom.errors import ItemNotFound, DependencyError, UnsatisfiedRequirement

class DependencyMap(object):
    """
    Collects information about the dependencies of all Items in this program.

    @ivar oldDependencyMap: A mapping of L{Item} subclasses to a tuple of
    (itemType, itemCustomizer, ref). These values are the args to
    L{DependencyMap.classDependsOn}: see its docstring for details.

    @ivar dependencyMap: A mapping of L{Item} subclasses to a tuple of
    (interface, ref) where 'interface' is an interface depended upon by the
    item, and 'ref' is an L{axiom.attributes.reference}.
    """

    def __init__(self):
        self.dependencyMap = {}
        self.oldDependencyMap = {}

    def classDependsOn(self, cls, itemType, itemCustomizer, ref):
        """
        Add a class to the (deprecated) dependency map.

        @param cls: The item type that has this dependency.
        @param itemType: The item type depended upon.
        @param itemCustomizer: A callable that accepts the item installed
        as a dependency as its first argument. It will be called only if
        an item is created to satisfy this dependency.
        @param ref: A L{axiom.attributes.reference}.
        """
        self.oldDependencyMap.setdefault(cls, []).append(
            (itemType, itemCustomizer, ref))


    def classRequiresFromStore(self, cls, interface, ref):
        """
        Add a class to the global dependency map.

        @param interface: An L{Interface}.
        @param ref: A L{axiom.attributes.reference}.
        """
        self.dependencyMap.setdefault(cls, []).append(
            (interface, ref))


    def _dependsOn_advice(self, cls):
        """
        Class advisor for class-based dependencies.
        """
        for dependee, callable, ref, isInterface in cls.__dict__[
            '__dependsOn_advice_data__']:
            if isInterface:
                self.classRequiresFromStore(cls, dependee, ref)
            else:
                self.classDependsOn(cls, dependee, callable, ref)
        del cls.__dependsOn_advice_data__
        return cls


    def _interfaceInstallOn(self, obj):
        """
        Install a powerup on its store, first checking if the powerups it
        depends upon have been installed. If they haven't been, raise a
        L{DependencyError} describing what's missing.
        """
        dependencies = self.dependencyMap.get(obj.__class__, [])
        if obj.store.findUnique(_PowerupConnector, AND(
                _PowerupConnector.powerup == obj,
                _PowerupConnector.item == obj.store),
                                 default=None) is not None:
            raise DependencyError("An instance of %r is already "
                                  "installed on %r." % (obj.__class__,
                                                      obj.store))

        #See if our dependencies have been installed already
        deps = reversed(list(enumerate(dependencies)))
        for (i, (interface, ref)) in deps:
                for pc in obj.store.query(_PowerupConnector, AND(
                            _PowerupConnector.item == obj.store,
                            _PowerupConnector.interface ==
                            qual(interface).decode('ascii'))):
                  ref.__set__(obj, pc.powerup)
                  del dependencies[i]
        if len(dependencies) > 0:
            raise DependencyError("A %r can't be installed on %r"
                                  " until powerups providing: %r are installed."
                                  % (obj.__class__, obj.store,
                                     [d[0] for d in dependencies]))

        obj.store.powerUp(obj)
        callback = getattr(obj, "installed", None)
        if callback is not None:
            callback()


    def installOn(self, obj, target, __explicitlyInstalled=True):
        """
        Install C{obj} on C{target} along with any powerup interfaces it
        declares. Also track that the object now depends on the target, and the
        object was explicitly installed (and therefore should not be
        uninstalled by subsequent uninstallation operations unless it is
        explicitly removed).
        """

        depBlob = self.oldDependencyMap.get(obj.__class__, [])
        dependencies, itemCustomizers, refs = (map(list,
                                                   zip(*depBlob))
                                               or ([], [], []))
        #See if any of our dependencies have been installed already
        for dc in obj.store.query(_DependencyConnector,
                                   _DependencyConnector.target == target):
            if dc.installee.__class__ in dependencies:
                i = dependencies.index(dc.installee.__class__)
                refs[i].__set__(obj, dc.installee)
                del dependencies[i], itemCustomizers[i], refs[i]
            if (dc.installee.__class__ == obj.__class__
                and obj.__class__ in set(
                itertools.chain([blob[0][0] for blob in
                                 self.oldDependencyMap.values()]))):
                #Somebody got here before we did... let's punt
                raise DependencyError("An instance of %r is already "
                                      "installed on %r." % (obj.__class__,
                                                            target))
        #The rest we'll install
        for i, cls in enumerate(dependencies):
            it = cls(store=obj.store)
            if itemCustomizers[i] is not None:
                itemCustomizers[i](it)
            self.installOn(it, target, False)
            refs[i].__set__(obj, it)
        #And now the connector for our own dependency.

        dc = obj.store.findUnique(
            _DependencyConnector,
            AND(_DependencyConnector.target==target,
                _DependencyConnector.installee==obj,
                _DependencyConnector.explicitlyInstalled==__explicitlyInstalled),
            None)
        assert dc is None, "Dependency connector already exists, wtf are you doing?"
        _DependencyConnector(store=obj.store, target=target,
                             installee=obj,
                             explicitlyInstalled=__explicitlyInstalled)

        target.powerUp(obj)

        callback = getattr(obj, "installed", None)
        if callback is not None:
            callback()



theDependencyMap = DependencyMap()
installOn = theDependencyMap.installOn
classDependsOn = theDependencyMap.classDependsOn
interfaceInstallOn = theDependencyMap._interfaceInstallOn


def _dependsOn(dependee, callable, doc, indexed, whenDeleted, isInterface):
    """
    Adds an entry to an item's dependency map.
    """

    frame = sys._getframe(2)
    locals = frame.f_locals
    isInterface = issubclass(dependee, Interface)
    reftype = None
    if not isInterface:
        reftype = dependee
    # Try to make sure we were called from a class def.
    if (locals is frame.f_globals) or ('__module__' not in locals):
        raise TypeError("dependsOn can be used only from a class definition.")
    ref = reference(reftype=reftype, doc=doc, indexed=indexed, allowNone=True,
                    whenDeleted=whenDeleted)
    if "__dependsOn_advice_data__" not in locals:
        addClassAdvisor(theDependencyMap._dependsOn_advice, depth=3)
    locals.setdefault('__dependsOn_advice_data__', []).append(
    (dependee, callable, ref, isInterface))
    return ref


def dependentsOf(cls):
    deps = theDependencyMap.oldDependencyMap.get(cls, None)
    if deps is None:
        return []
    else:
        return [d[0] for d in deps]


def dependsOn(itemType, itemCustomizer=None, doc='',
              indexed=True, whenDeleted=reference.NULLIFY):
    """
    This function behaves like L{axiom.attributes.reference} but with
    an extra behaviour: when this item is installed (via
    L{axiom.dependency.installOn} on a target item, the
    type named here will be instantiated and installed on the target
    as well.

    For example::

      class Foo(Item):
          counter = integer()
          thingIDependOn = dependsOn(Baz, lambda baz: baz.setup())

    @param itemType: The Item class to instantiate and install.
    @param itemCustomizer: A callable that accepts the item installed
    as a dependency as its first argument. It will be called only if
    an item is created to satisfy this dependency.

    @return: An L{axiom.attributes.reference} instance.
    """
    warnings.warn("Items should declare their dependencies using"
                  " axiom.dependency.requiresFromStore, not"
                  " axiom.dependency.dependsOn.",
                  PendingDeprecationWarning)

    return _dependsOn(itemType, itemCustomizer, doc,
                      indexed, whenDeleted, False)


def requiresFromStore(interface, doc='', indexed=True):
    """
    This function behaves like L{axiom.attributes.reference} but with an extra
    behaviour: when an item containing this attribute is instantiated, a check
    is made on the store the item is to be created in for a powerup
    implementing ths interface. If it is found, this attribute will be set to
    reference it. If it isn't found, a L{DependencyError} is raised.
    """

    return _dependsOn(interface, None, doc, indexed, reference.DISALLOW, True)



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



def uninstallFrom(self, target):
    """
    Remove this object from the target, as well as any dependencies
    that it automatically installed which were not explicitly
    "pinned" by calling "install", and raising an exception if
    anything still depends on this.
    """

    #did this class powerup on any interfaces? powerdown if so.
    target.powerDown(self)


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
    Deprecated - L{Item.powerUp} now has this functionality.
    """
    target.powerUp(self)



class requiresFromSite(
    record('powerupInterface defaultFactory siteDefaultFactory',
           defaultFactory=None,
           siteDefaultFactory=None)):
    """
    A read-only descriptor that will return the site store's powerup for a
    given item.

    @ivar powerupInterface: an L{Interface} describing the powerup that the
    site store should be adapted to.

    @ivar defaultFactory: a 1-argument callable that takes the site store and
    returns a value for this descriptor.  This is invoked in cases where the
    site store does not provide a default factory of its own, and this
    descriptor is retrieved from an item in a store with a parent.

    @ivar siteDefaultFactory: a 1-argument callable that takes the site store
    and returns a value for this descriptor.  This is invoked in cases where
    this descriptor is retrieved from an item in a store without a parent.
    """

    def _invokeFactory(self, defaultFactory, siteStore):
        if defaultFactory is None:
            raise UnsatisfiedRequirement()
        return defaultFactory(siteStore)


    def __get__(self, oself, type=None):
        """
        Retrieve the value of this dependency from the site store.
        """
        siteStore = oself.store.parent
        if siteStore is not None:
            pi = self.powerupInterface(siteStore, None)
            if pi is None:
                pi = self._invokeFactory(self.defaultFactory, siteStore)
        else:
            pi = self._invokeFactory(self.siteDefaultFactory, oself.store)
        return pi

