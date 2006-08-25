from twisted.trial import unittest

from axiom import dependency
from axiom.store import Store
from axiom.item import Item
from axiom.attributes import text, integer


class Kitchen(Item):
    name = text()

class PowerStrip(Item, dependency.DependencyMixin):
    "Required for plugging appliances into."
    voltage = integer()

    def setForUSElectricity(self):
        if not self.voltage:
            self.voltage = 110
        else:
            raise RuntimeError("Oops! power strip already set up")

    def draw(self, watts):
        return "zap zap"

class Breadbox(Item, dependency.DependencyMixin):
    slices = integer(default=100)

    def dispenseBread(self, amt):
        self.slices -= amt

class Toaster(Item, dependency.DependencyMixin):
    powerStrip = dependency.dependsOn(PowerStrip,
                                      lambda ps: ps.setForUSElectricity())
    description = text()
    breadFactory = dependency.dependsOn(Breadbox)

    def toast(self):
        self.powerStrip.draw(100)
        self.breadFactory.dispenseBread(2)

class Blender(Item, dependency.DependencyMixin):
    powerStrip = dependency.dependsOn(PowerStrip,
                                      lambda ps: ps.setForUSElectricity())
    description = text()

class IceCrusher(Item, dependency.DependencyMixin):
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
        e.installOn(foo)
        e.toast()
        ps = self.store.findUnique(PowerStrip, default=None)
        bb = self.store.findUnique(Breadbox, default=None)
        self.failIfIdentical(ps, None)
        self.failIfIdentical(bb, None)
        self.assertEquals(e.powerStrip, ps)
        self.assertEquals(ps.voltage, 110)
        self.assertEquals(e.breadFactory, bb)
        self.assertEquals(set(e.installedRequirements(foo)), set([ps, bb]))
        self.assertEquals(list(ps.installedDependents(foo)), [e])

        #this part I made up myself
        self.assertEquals(e.installedOn, foo)
        self.assertEquals(ps.installedOn, foo)
        self.assertEquals(bb.installedOn, foo)

    def test_basicUninstall(self):
        """
        Ensure that uninstallation removes the adapter from the former
        install target and all orphaned dependencies.
        """
        foo = Kitchen(store=self.store)
        e = Toaster(store=self.store)
        e.installOn(foo)
        ps = self.store.findUnique(PowerStrip)
        e.uninstallFrom(foo)

        #more made up stuff
        self.failIf(e.installedOn)
        self.failIf(ps.installedOn)

    def test_wrongUninstall(self):
        """
        Ensure that attempting to uninstall an item that something
        else depends on fails.
        """
        foo = Kitchen(store=self.store)
        e = Toaster(store=self.store)
        e.installOn(foo)

        ps = self.store.findUnique(PowerStrip)
        self.failUnlessRaises(dependency.DependencyError, ps.uninstallFrom, foo)

    def test_properOrphaning(self):
        """
        If two installed items both depend on a third, it should be
        removed as soon as both installed items are removed, but no
        sooner.
        """

        foo = Kitchen(store=self.store)
        e = Toaster(store=self.store)
        e.installOn(foo)
        ps = self.store.findUnique(PowerStrip)
        bb = self.store.findUnique(Breadbox)
        f = Blender(store=self.store)
        f.installOn(foo)

        self.assertEquals(list(self.store.query(PowerStrip)), [ps])
        #XXX does ordering matter?
        self.assertEquals(set(ps.installedDependents(foo)), set([e, f]))
        self.assertEquals(set(e.installedRequirements(foo)), set([bb, ps]))
        self.assertEquals(list(f.installedRequirements(foo)), [ps])

        e.uninstallFrom(foo)
        self.assertEquals(ps.installedOn, foo)

        f.uninstallFrom(foo)
        self.assertEquals(ps.installedOn, None)

    def test_customizerCalledOnce(self):
        """
        The item customizer defined for a dependsOn attribute should
        only be called if an item is created implicitly to satisfy the
        dependency.
        """
        foo = Kitchen(store=self.store)
        ps = PowerStrip(store=self.store)
        ps.installOn(foo)
        ps.voltage = 115
        e = Toaster(store=self.store)
        e.installOn(foo)
        self.assertEqual(ps.voltage, 115)

    def test_explicitInstall(self):
        """
        If an item is explicitly installed, it should not be
        implicitly uninstalled.
        """
        foo = Kitchen(store=self.store)
        ps = PowerStrip(store=self.store)
        ps.installOn(foo)
        e = Toaster(store=self.store)
        e.installOn(foo)

        e.uninstallFrom(foo)
        self.assertEquals(ps.installedOn, foo)

    def test_doubleInstall(self):
        """
        Make sure that installing two instances of a class on the same
        target fails.
        """
        foo = Kitchen(store=self.store)
        e = Toaster(store=self.store)
        e.installOn(foo)
        ps = PowerStrip(store=self.store)
        self.failUnlessRaises(dependency.DependencyError, ps.installOn, foo)

    def test_recursiveInstall(self):
        """
        Installing an item should install all of its dependencies, and
        all of its dependencies, and so forth.
        """
        foo = Kitchen(store=self.store)
        ic = IceCrusher(store=self.store)
        ic.installOn(foo)
        blender = self.store.findUnique(Blender)
        ps = self.store.findUnique(PowerStrip)

        self.assertEquals(blender.installedOn, foo)
        self.assertEquals(ps.installedOn, foo)
        self.assertEquals(list(ic.installedRequirements(foo)), [blender])

    def test_recursiveUninstall(self):
        """
        Removal of items should recursively remove orphaned
        dependencies.
        """
        foo = Kitchen(store=self.store)
        ic = IceCrusher(store=self.store)
        ic.installOn(foo)
        blender = self.store.findUnique(Blender)
        ps = self.store.findUnique(PowerStrip)

        ic.uninstallFrom(foo)

        self.failIf(blender.installedOn)
        self.failIf(ps.installedOn)
        self.failIf(ic.installedOn)

    def test_wrongDependsOn(self):
        self.assertRaises(TypeError, dependency.dependsOn, Toaster)
