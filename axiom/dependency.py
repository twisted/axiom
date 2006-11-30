# -*- test-case-name: axiom.test.test_dependency -*-
"""
A dependency management system for items.

This module provides C{DependencyMixin}, which enables dependency
management on items that subclass it, and C{dependsOn}, an attribute
that provides automatic loading of dependent items.
"""

import sys
from zope.interface.advice import addClassAdvisor, isClassAdvisor
from axiom.item import Item
from axiom.attributes import reference, boolean
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
def dependsOn(itemType, itemCustomizer=None, doc='', indexed=True,
              whenDeleted=reference.NULLIFY):
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

    # Try to make sure we were called from a class def. In 2.2.0 we can't
    # check for __module__ since it doesn't seem to be added to the locals
    # until later on.
    if (locals is frame.f_globals) or (
        ('__module__' not in locals) and sys.version_info[:3] > (2, 2, 0)):
        raise TypeError("dependsOn can be used only from a class definition.")
    ref = reference(reftype=itemType, doc=doc, indexed=indexed, allowNone=True,
                    whenDeleted=whenDeleted)
    locals.setdefault('__dependsOn_advice_data__', []).append(
    (itemType, itemCustomizer, ref))
    if not isClassAdvisor(locals.get('__metaclass__')):
        addClassAdvisor(_dependsOn_advice)
    return ref

def _dependsOn_advice(cls):
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


class DependencyMixin(object):
    """
    I provide dependency management for items. Items that subclass me
    can be installed on other items, either manually via C{installOn}
    or automatically as a dependency of another item being
    installed. Once installed they can be removed (along with unneeded
    dependencies) with C{uninstallFrom}.
    """
    def installOn(self, target):
        """
        Install this object on the target, tracking that the object now
        depends on the target, and the object was explicitly installed
        and therefore should not be uninstalled by subsequent
        uninstallation operations unless it is explicitly removed.
        """
        self._installOn(target, True)

    def _installOn(self, target, __explicitlyInstalled=False):
        depBlob = _globalDependencyMap.get(self.__class__, [])
        dependencies, itemCustomizers, refs = (map(list, zip(*depBlob))
                                             or ([], [], []))
        #See if any of our dependencies have been installed already
        for dc in self.store.query(_DependencyConnector,
                                   _DependencyConnector.target == target):
            if dc.installee.__class__ in dependencies:
                i = dependencies.index(dc.installee.__class__)
                del dependencies[i], itemCustomizers[i], refs[i]
            if dc.installee.__class__ == self.__class__:
                #Somebody got here before we did... let's punt
                raise DependencyError("An instance of %r is already "
                                      "installed on %r." % (self.__class__,
                                                            target))
        #The rest we'll install
        for i, cls in enumerate(dependencies):
            it = cls(store=self.store)
            if itemCustomizers[i] is not None:
                itemCustomizers[i](it)
            it._installOn(target, False)
            refs[i].__set__(self, it)
        #And now the connector for our own dependency.

        _DependencyConnector(store=self.store, target=target,
                             installee=self,
                             explicitlyInstalled=__explicitlyInstalled)

    def uninstallFrom(self, target):
        """
        Remove this object from the target, as well as any dependencies
        that it automatically installed which were not explicitly
        "pinned" by calling "install", and raising an exception if
        anything still depends on this.
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

        #only thing left now are dependencies nobody else needs and
        #our own connector -- remove 'em
        #XXX sheesh we are iterating over this query _again_
        toBeRemoved = []
        for dc in self.store.query(_DependencyConnector,
                                   _DependencyConnector.target==target):
            if dc.installee is self:
                dc.deleteFromStore()
            elif (dc.installee.__class__ in myDepends
                  and not dc.explicitlyInstalled):
                toBeRemoved.append(dc.installee)

        for item in toBeRemoved:
            item.uninstallFrom(target)

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
    installedOn = property(installedOn)

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
