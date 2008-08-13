# Copright 2008 Divmod, Inc.  See LICENSE file for details.

from zope.interface import Interface, implements

from twisted.trial import unittest

from axiom import dependency
from axiom.store import Store
from axiom.substore import SubStore
from axiom.item import Item
from axiom.errors import UnsatisfiedRequirement
from axiom.attributes import text, integer, reference, inmemory


class IElectricityGrid(Interface):
    """
    An interface representing something likely to be present in the site store.
    As opposed to the other examples below, present in a hypothetical kitchen,
    it is something managed for lots of different people.
    """

    def draw(watts):
        """
        Draw some number of watts from this power grid.

        @return: a constant, one of L{REAL_POWER} or L{FAKE_POWER}.
        """


FAKE_POWER = 'fake power'
REAL_POWER = 'real power'

class NullGrid(object):
    """
    This is a null electricity grid.  It is provided as a default grid in the
    case where a site store is not present.
    """
    implements(IElectricityGrid)

    def __init__(self, siteStore):
        """
        Create a null grid with a reference to the site store.
        """
        self.siteStore = siteStore


    def draw(self, watts):
        """
        Draw some watts from the null power grid.  For simplicity of examples
        below, this works.  Not in real life, though.  In a more realistic
        example, this might do something temporary to work around the site
        misconfiguration, and warn an administrator that someone was getting
        power out of thin air.  Or, depending on the application, we might
        raise an exception to prevent this operation from succeeding.
        """
        return FAKE_POWER


class RealGrid(Item):
    """
    A power grid for the power utility; this is an item which should be
    installed on a site store.
    """
    implements(IElectricityGrid)

    powerupInterfaces = (IElectricityGrid,)

    totalWattage = integer(default=10000000,
                           doc="""
                           Total wattage of the entire electricity grid.  (This
                           is currently a dummy attribute.)
                           """)

    def draw(self, watts):
        """
        Draw some real power from the real power grid.  This is the way that
        the site should probably be working.
        """
        return REAL_POWER



def noGrid(siteStore):
    """
    No power grid was available.  Raise an exception.
    """
    raise RuntimeError("No power grid available.")



class IronLung(Item):
    """
    This item is super serious business!  It has to draw real power from the
    real power grid; it won't be satisfied with fake power; too risky for its
    life-critical operation.  So it doesn't specify a placeholder default grid.

    @ivar grid: a read-only reference to an L{IElectricityGrid} provider,
    resolved via the site store this L{IronLung} is in.
    """

    wattsPerPump = integer(default=100, allowNone=False,
                           doc="""
                           The number of watts to draw from L{self.grid} when
                           L{IronLung.pump} is called.
                           """)

    grid = dependency.requiresFromSite(IElectricityGrid)

    def pump(self):
        """
        Attempting to pump the iron lung by talking to the power grid.
        """
        return self.grid.draw(self.wattsPerPump)



class SpecifiedBadDefaults(Item):
    """
    Depends on a power grid, but specifies defaults for that dependency that
    should never be invoked.  This item can't retrieve a grid.

    @ivar grid: Retrieving this attribute should never work.  It should raise
    L{RuntimeError}.
    """
    dummy = integer(doc="""
    Dummy attribute required by axiom for Item class definition.
    """)

    grid = dependency.requiresFromSite(IElectricityGrid, noGrid, noGrid)

    def pump(self):
        """
        Attempting to pump the iron lung by talking to the power grid.
        """
        return self.grid.draw(100)


class Kitchen(Item):
    name = text()

class PowerStrip(Item):
    """
    A simulated collection of power points.  This is where L{IAppliance}
    providers get their power from.

    @ivar grid: A read-only reference to an L{IElectricityGrid} provider.  This
    may be a powerup provided by the site store or a L{NullGrid} if no powerup
    is installed.
    """
    voltage = integer()
    grid = dependency.requiresFromSite(IElectricityGrid, NullGrid, NullGrid)

    def setForUSElectricity(self):
        if not self.voltage:
            self.voltage = 110
        else:
            raise RuntimeError("Oops! power strip already set up")

    def draw(self, watts):
        """
        Draw the given amount of power from this strip's electricity grid.

        @param watts: The number of watts to draw.

        @type watts: L{int}
        """
        return self.grid.draw(watts)


class PowerPlant(Item):
    """
    This is an item which supplies the grid with power.  It lives in the site
    store.

    @ivar grid: a read-only reference to an L{IElectricityGrid} powerup on the
    site store, or a L{NullGrid} if none is installed.  If this item is present
    in a user store, retrieving this will raise a L{RuntimeError}.
    """

    wattage = integer(default=1000, allowNone=False,
                      doc="""
                      The amount of power the grid will be supplied with.
                      Currently a dummy attribute required by axiom for item
                      definition.
                      """)
    grid = dependency.requiresFromSite(IElectricityGrid, noGrid, NullGrid)



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
    breadFactory = dependency.dependsOn(
        Breadbox,
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

def powerstripSetup(ps):
    ps.setForUSElectricity()
class Blender(Item):
    powerStrip = dependency.dependsOn(PowerStrip,
                                      powerstripSetup)
    description = text()

    def __getPowerupInterfaces__(self, powerups):
        yield (IAppliance, 0)

class IceCrusher(Item):
    blender = dependency.dependsOn(Blender)

class Blender2(Item):
    powerStrip = reference()

class DependencyTest(unittest.TestCase):
    def setUp(self):
        self.store = Store()

    def test_dependsOn(self):
        """
        Ensure that classes with dependsOn attributes set up the dependency map
        properly.
        """
        foo = Blender(store=self.store)
        depBlob = dependency._globalDependencyMap.get(Blender, None)[0]
        self.assertEqual(depBlob[0], PowerStrip)
        self.assertEqual(depBlob[1], powerstripSetup)
        self.assertEqual(depBlob[2], Blender.__dict__['powerStrip'])

    def test_classDependsOn(self):
        """
        Ensure that classDependsOn sets up the dependency map properly.
        """
        dependency.classDependsOn(Blender2, PowerStrip, powerstripSetup,
                                  Blender2.__dict__['powerStrip'])
        depBlob = dependency._globalDependencyMap.get(Blender2, None)[0]
        self.assertEqual(depBlob[0], PowerStrip)
        self.assertEqual(depBlob[1], powerstripSetup)
        self.assertEqual(depBlob[2], Blender2.__dict__['powerStrip'])

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
        self.assertEquals(set(dependency.installedRequirements(e, foo)),
                          set([ps, bb]))
        self.assertEquals(list(dependency.installedDependents(ps, foo)), [e])

    def test_basicUninstall(self):
        """
        Ensure that uninstallation removes the adapter from the former
        install target and all orphaned dependencies.
        """
        foo = Kitchen(store=self.store)
        e = Toaster(store=self.store)
        dependency.installOn(e, foo)
        dependency.uninstallFrom(e, foo)
        self.assertEqual(dependency.installedOn(e), None)
        self.assertEqual(dependency.installedOn(e.powerStrip), None)

    def test_wrongUninstall(self):
        """
        Ensure that attempting to uninstall an item that something
        else depends on fails.
        """
        foo = Kitchen(store=self.store)
        e = Toaster(store=self.store)
        dependency.installOn(e, foo)

        ps = self.store.findUnique(PowerStrip)
        self.failUnlessRaises(dependency.DependencyError,
                              dependency.uninstallFrom, ps, foo)

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
        self.assertEquals(set(dependency.installedDependents(ps, foo)),
                          set([e, f]))
        self.assertEquals(set(dependency.installedRequirements(e, foo)),
                          set([bb, ps]))
        self.assertEquals(list(dependency.installedRequirements(f, foo)),
                          [ps])

        dependency.uninstallFrom(e, foo)
        self.assertEquals(dependency.installedOn(ps), foo)

        dependency.uninstallFrom(f, foo)
        self.assertEquals(dependency.installedOn(ps), None)

    def test_installedUniqueRequirements(self):
        """
        Ensure that installedUniqueRequirements lists only powerups depended on
        by exactly one installed powerup.
        """
        foo = Kitchen(store=self.store)
        e = Toaster(store=self.store)
        dependency.installOn(e, foo)
        ps = self.store.findUnique(PowerStrip)
        bb = self.store.findUnique(Breadbox)
        f = Blender(store=self.store)
        dependency.installOn(f, foo)

        self.assertEquals(list(dependency.installedUniqueRequirements(e, foo)),
                          [bb])

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
        self.assertEquals(list(dependency.installedRequirements(ic, foo)),
                          [blender])

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
        'installed' and 'uninstalled' callbacks should fire on
        install/uninstall.
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


    def test_onlyInstallPowerups(self):
        """
        Make sure onlyInstallPowerups doesn't load dependencies or prohibit
        multiple calls.
        """
        foo = Kitchen(store=self.store)
        e = Toaster(store=self.store)
        f = Toaster(store=self.store)
        dependency.onlyInstallPowerups(e, foo)
        dependency.onlyInstallPowerups(f, foo)
        self.assertEquals(list(foo.powerupsFor(IBreadConsumer)), [e, f])
        self.assertEquals(list(self.store.query(
                    dependency._DependencyConnector)), [])


class RequireFromSiteTests(unittest.TestCase):
    """
    L{axiom.dependency.requiresFromSite} should allow items in either a user or
    site store to depend on powerups in the site store.
    """

    def setUp(self):
        """
        Create a L{Store} to be used as the site store for these tests.
        """
        self.store = Store()


    def test_requiresFromSite(self):
        """
        The value of a L{axiom.dependency.requiresFromSite} descriptor ought to
        be the powerup on the site for the instance it describes.
        """
        dependency.installOn(RealGrid(store=self.store), self.store)
        substore = SubStore.createNew(self.store, ['sub']).open()
        self.assertEquals(PowerStrip(store=substore).draw(1), REAL_POWER)


    def test_requiresFromSiteDefault(self):
        """
        The value of a L{axiom.dependency.requiresFromSite} descriptor on an
        item in a user store ought to be the result of invoking its default
        factory parameter.
        """
        substore = SubStore.createNew(self.store, ['sub']).open()
        ps = PowerStrip(store=substore)
        self.assertEquals(ps.draw(1), FAKE_POWER)
        self.assertEquals(ps.grid.siteStore, self.store)


    def test_requiresFromSiteInSiteStore(self):
        """
        L{axiom.dependency.requiresFromSite} should use the
        C{siteDefaultFactory} rather than the C{defaultFactory} to satisfy the
        dependency for items stored in a site store.  It should use this
        default whether or not any item which could satisfy the requirement is
        installed on the site store.

        This behavior is important because some powerup interfaces are provided
        for site and user stores with radically different behaviors; for
        example, the substore implementation of L{IScheduler} depends on the
        site implementation of L{IScheduler}; if a user's substore were opened
        accidentally as a site store (i.e. with no parent) then the failure of
        the scheduler API should be obvious and immediate so that it can
        compensate; it should not result in an infinite recursion as the
        scheduler is looking for its parent.

        Items which wish to be stored in a site store and also depend on items
        in the site store can specifically adapt to the appropriate interface
        in the C{siteDefaultFactory} supplied to
        L{dependency.requiresFromSite}.
        """
        plant = PowerPlant(store=self.store)
        self.assertEquals(plant.grid.siteStore, self.store)
        self.assertEquals(plant.grid.draw(100), FAKE_POWER)
        dependency.installOn(RealGrid(store=self.store), self.store)
        self.assertEquals(plant.grid.siteStore, self.store)
        self.assertEquals(plant.grid.draw(100), FAKE_POWER)


    def test_requiresFromSiteNoDefault(self):
        """
        The default function shouldn't be needed or invoked if its value isn't
        going to be used.
        """
        dependency.installOn(RealGrid(store=self.store), self.store)
        substore = SubStore.createNew(self.store, ['sub']).open()
        self.assertEquals(SpecifiedBadDefaults(store=substore).pump(),
                          REAL_POWER)


    def test_requiresFromSiteUnspecifiedException(self):
        """
        If a default factory function isn't supplied, an
        L{UnsatisfiedRequirement}, which should be a subtype of
        L{AttributeError}, should be raised when the descriptor is retrieved.
        """
        lung = IronLung(store=self.store)
        siteLung = IronLung(
            store=SubStore.createNew(self.store, ['sub']).open())
        self.assertRaises(UnsatisfiedRequirement, lambda : lung.grid)
        self.assertRaises(UnsatisfiedRequirement, lambda : siteLung.grid)
        default = object()
        self.assertIdentical(getattr(lung, 'grid', default), default)

