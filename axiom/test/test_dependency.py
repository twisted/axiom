
from twisted.trial import unittest

from axiom import dependency
from axiom.store import Store
from axiom.item import Item
from axiom.attributes import text, integer, reference, inmemory

from zope.interface import Interface, implements

class Kitchen(Item):
    name = text()

class PowerStrip(Item):
    "Required for plugging appliances into."
    voltage = integer()

    def setForUSElectricity(self):
        if not self.voltage:
            self.voltage = 110
        else:
            raise RuntimeError("Oops! power strip already set up")

    def draw(self, watts):
        return "zap zap"

class IAppliance(Interface):
    pass

class IBreadConsumer(Interface):
    pass

class Breadbox(Item):
    slices = integer(default=100)

    def dispenseBread(self, amt):
        self.slices -= amt

class Toaster(Item):
    implements(IBreadConsumer)
    powerupInterfaces = (IAppliance, IBreadConsumer)

    powerStrip = dependency.dependsOn(PowerStrip,
                                      lambda ps: ps.setForUSElectricity(),
                                      doc="the power source for this toaster")
    description = text()
    breadFactory = dependency.dependsOn(Breadbox,
                                        doc="the thing we get bread input from",
                                        whenDeleted=reference.CASCADE)

    callback = inmemory()

    def activate(self):
        self.callback = None

    def installed(self):
        if self.callback is not None:
            self.callback("installed")

    def uninstalled(self):
        if self.callback is not None:
            self.callback("uninstalled")

    def toast(self):
        self.powerStrip.draw(100)
        self.breadFactory.dispenseBread(2)

class Blender(Item):
    powerStrip = dependency.dependsOn(PowerStrip,
                                      lambda ps: ps.setForUSElectricity())
    description = text()

    def __getPowerupInterfaces__(self, powerups):
        yield (IAppliance, 0)

class IceCrusher(Item):
    blender = dependency.dependsOn(Blender)

class DependencyTest(unittest.TestCase):
    def setUp(self):
        self.store = Store()

    def test_basicInstall(self):
        """
        If a Toaster gets installed in a Kitchen, make sure that the
        required dependencies get instantiated and installed too.
        """
        foo = Kitchen(store=self.store)
        e = Toaster(store=self.store)
        self.assertEquals(e.powerStrip, None)
        dependency.installOn(e, foo)
        e.toast()
        ps = self.store.findUnique(PowerStrip, default=None)
        bb = self.store.findUnique(Breadbox, default=None)
        self.failIfIdentical(ps, None)
        self.failIfIdentical(bb, None)
        self.assertEquals(e.powerStrip, ps)
        self.assertEquals(ps.voltage, 110)
        self.assertEquals(e.breadFactory, bb)
        self.assertEquals(set(dependency.installedRequirements(e, foo)), set([ps, bb]))
        self.assertEquals(list(dependency.installedDependents(ps, foo)), [e])

    def test_basicUninstall(self):
        """
        Ensure that uninstallation removes the adapter from the former
        install target and all orphaned dependencies.
        """
        foo = Kitchen(store=self.store)
        e = Toaster(store=self.store)
        dependency.installOn(e, foo)
        ps = self.store.findUnique(PowerStrip)
        dependency.uninstallFrom(e, foo)

    def test_wrongUninstall(self):
        """
        Ensure that attempting to uninstall an item that something
        else depends on fails.
        """
        foo = Kitchen(store=self.store)
        e = Toaster(store=self.store)
        dependency.installOn(e, foo)

        ps = self.store.findUnique(PowerStrip)
        self.failUnlessRaises(dependency.DependencyError, dependency.uninstallFrom, ps, foo)

    def test_properOrphaning(self):
        """
        If two installed items both depend on a third, it should be
        removed as soon as both installed items are removed, but no
        sooner.
        """

        foo = Kitchen(store=self.store)
        e = Toaster(store=self.store)
        dependency.installOn(e, foo)
        ps = self.store.findUnique(PowerStrip)
        bb = self.store.findUnique(Breadbox)
        f = Blender(store=self.store)
        dependency.installOn(f, foo)

        self.assertEquals(list(self.store.query(PowerStrip)), [ps])
        #XXX does ordering matter?
        self.assertEquals(set(dependency.installedDependents(ps, foo)), set([e, f]))
        self.assertEquals(set(dependency.installedRequirements(e, foo)), set([bb, ps]))
        self.assertEquals(list(dependency.installedUniqueRequirements(e, foo)), [bb])
        self.assertEquals(list(dependency.installedRequirements(f, foo)), [ps])

        dependency.uninstallFrom(e, foo)
        self.assertEquals(dependency.installedOn(ps), foo)

        dependency.uninstallFrom(f, foo)
        self.assertEquals(dependency.installedOn(ps), None)

    def test_customizerCalledOnce(self):
        """
        The item customizer defined for a dependsOn attribute should
        only be called if an item is created implicitly to satisfy the
        dependency.
        """
        foo = Kitchen(store=self.store)
        ps = PowerStrip(store=self.store)
        dependency.installOn(ps, foo)
        ps.voltage = 115
        e = Toaster(store=self.store)
        dependency.installOn(e, foo)
        self.assertEqual(ps.voltage, 115)

    def test_explicitInstall(self):
        """
        If an item is explicitly installed, it should not be
        implicitly uninstalled. Also, dependsOn attributes should be
        filled in properly even if a dependent item is not installed
        automatically.
        """
        foo = Kitchen(store=self.store)
        ps = PowerStrip(store=self.store)
        dependency.installOn(ps, foo)
        e = Toaster(store=self.store)
        dependency.installOn(e, foo)
        self.assertEqual(e.powerStrip, ps)
        dependency.uninstallFrom(e, foo)
        self.assertEquals(dependency.installedOn(ps), foo)

    def test_doubleInstall(self):
        """
        Make sure that installing two instances of a class on the same
        target fails, if something depends on that class, and succeeds
        otherwise.
        """
        foo = Kitchen(store=self.store)
        e = Toaster(store=self.store)
        dependency.installOn(e, foo)
        ps = PowerStrip(store=self.store)
        self.failUnlessRaises(dependency.DependencyError,
                              dependency.installOn, ps, foo)
        e2 = Toaster(store=self.store)
        dependency.installOn(e2, foo)


    def test_recursiveInstall(self):
        """
        Installing an item should install all of its dependencies, and
        all of its dependencies, and so forth.
        """
        foo = Kitchen(store=self.store)
        ic = IceCrusher(store=self.store)
        dependency.installOn(ic, foo)
        blender = self.store.findUnique(Blender)
        ps = self.store.findUnique(PowerStrip)

        self.assertEquals(dependency.installedOn(blender), foo)
        self.assertEquals(dependency.installedOn(ps), foo)
        self.assertEquals(list(dependency.installedRequirements(ic, foo)), [blender])

    def test_recursiveUninstall(self):
        """
        Removal of items should recursively remove orphaned
        dependencies.
        """
        foo = Kitchen(store=self.store)
        ic = IceCrusher(store=self.store)
        dependency.installOn(ic, foo)
        blender = self.store.findUnique(Blender)
        ps = self.store.findUnique(PowerStrip)

        dependency.uninstallFrom(ic, foo)

        self.failIf(dependency.installedOn(blender))
        self.failIf(dependency.installedOn(ps))
        self.failIf(dependency.installedOn(ic))

    def test_wrongDependsOn(self):
        """
        dependsOn should raise an error if used outside a class definition.
        """
        self.assertRaises(TypeError, dependency.dependsOn, Toaster)

    def test_referenceArgsPassthrough(self):
        """
        dependsOn should accept (most of) attributes.reference's args.
        """

        self.failUnless("power source" in Toaster.powerStrip.doc)
        self.assertEquals(Toaster.breadFactory.whenDeleted, reference.CASCADE)

    def test_powerupInterfaces(self):
        """
        Make sure interfaces are powered up and down properly.
        """

        foo = Kitchen(store=self.store)
        e = Toaster(store=self.store)
        f = Blender(store=self.store)
        dependency.installOn(e, foo)
        dependency.installOn(f, foo)
        self.assertEquals(IAppliance(foo), e)
        self.assertEquals(IBreadConsumer(foo), e)
        dependency.uninstallFrom(e, foo)
        self.assertEquals(IAppliance(foo), f)
        dependency.uninstallFrom(f, foo)
        self.assertRaises(TypeError, IAppliance, foo)


    def test_callbacks(self):
        """
        'installed' and 'uninstalled' callbacks should fire on install/uninstall.
        """
        foo = Kitchen(store=self.store)
        e = Toaster(store=self.store)
        self.installCallbackCalled = False
        e.callback = lambda _: setattr(self, 'installCallbackCalled', True)
        dependency.installOn(e, foo)
        self.failUnless(self.installCallbackCalled)
        self.uninstallCallbackCalled = False
        e.callback = lambda _: setattr(self, 'uninstallCallbackCalled', True)
        dependency.uninstallFrom(e, foo)
        self.failUnless(self.uninstallCallbackCalled)
