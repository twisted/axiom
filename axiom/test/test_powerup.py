
from twisted.trial import unittest

from axiom.item import Item
from axiom.store import Store
from axiom.iaxiom import IPowerupIndirector
from axiom.attributes import integer, inmemory, reference

from zope.interface import Interface, implements, Attribute


class IValueHaver(Interface):
    value = Attribute("""
    An integer that you can add to other integers.
    """)

class IScalingFactor(Interface):
    scale = Attribute("""
    An integer that a sum can be multiplied by.
    """)

class ISumProducer(Interface):

    def doSum():
        """
        Produce a sum.
        """


class SumContributor(Item):
    schemaVersion = 1
    typeName = 'test_sum_contributor'

    value = integer()

class MinusThree(object):
    implements(IValueHaver)

    def __init__(self, otherValueHaver):
        self.value = otherValueHaver.value - 3

class SubtractThree(Item):
    schemaVersion = 1
    typeName = 'test_powerup_indirection_subtractthree'
    valueHaver = reference()

    implements(IPowerupIndirector)

    def indirect(self, iface):
        assert iface is IValueHaver, repr(iface)
        return MinusThree(self.valueHaver)


class PlusTwo(Item):
    """
    Example powerup with installation information.
    """
    implements(IValueHaver)
    powerupInterfaces = (IValueHaver,)

    value = integer(default=2)

class PlusOneTimesFour(Item):
    """
    Example powerup with dynamic installation information.
    """
    implements(IScalingFactor, IValueHaver)
    scale = integer(default=1)
    value = integer(default=4)

    def __getPowerupInterfaces__(self, powerup):
        yield (IScalingFactor, 1)
        yield (IValueHaver, 3)

class Summer(Item):
    schemaVersion = 1
    typeName = 'test_sum_doer'

    sumTimes = integer()
    sumTotal = integer()

    def __init__(self, **kw):
        super(Summer, self).__init__(**kw)
        self.sumTotal = 0
        self.sumTimes = 0

    def doSum(self):
        total = 0
        for haver in self.store.powerupsFor(IValueHaver):
            value = haver.value
            self.sumTotal += value
            total += value
        self.sumTimes += 1
        for factor in self.store.powerupsFor(IScalingFactor):
            value = factor.scale
            self.sumTotal *= value
            total *= value
        return total

class BrokenPowerup(Item):
    stuff = integer()

    def __getPowerupInterfaces__(self, pifs):
        return 'not a list of pairs'


class PowerUpTest(unittest.TestCase):

    def testBasicPowerups(self):
        # tests an interaction between __conform__ and other stuff

        s = Store()
        mm = Summer(store=s)
        s.powerUp(mm, ISumProducer)

        s.powerUp(SumContributor(store=s, value=1), IValueHaver)
        s.powerUp(SumContributor(store=s, value=2), IValueHaver)
        s.powerUp(SumContributor(store=s, value=3), IValueHaver)

        self.assertEquals(mm.doSum(), 6)

        s.close()


    def testPowerupIdentity(self):
        s = Store()
        mm = Summer(store=s)
        s.powerUp(mm, ISumProducer)

        sc3 = SumContributor(store=s, value=3)

        s.powerUp(SumContributor(store=s, value=1), IValueHaver)
        s.powerUp(SumContributor(store=s, value=2), IValueHaver)
        s.powerUp(sc3, IValueHaver)
        s.powerUp(sc3, IValueHaver)

        self.assertEquals(mm.doSum(), 6)

        s.close()



    def test_automaticPowerupInstall(self):
        """
        Powerups with 'powerupInterfaces' attributes can be installed
        on those interfaces without the caller needing to refer to
        them directly.
        """
        s = Store()
        mm = Summer(store=s)
        s.powerUp(mm, ISumProducer)
        p = PlusTwo(store=s)
        s.powerUp(p)

        self.assertEquals(mm.doSum(), 2)


    def test_dynamicAutomaticPowerupInstall(self):
        """
        Powerups with '__getPowerupInterfaces__' methods can be
        installed on the interfaces in the iterable that method
        returns.
        """
        s = Store()
        mm = Summer(store=s)
        s.powerUp(mm, ISumProducer)
        p = PlusOneTimesFour(store=s)
        s.powerUp(p)

        self.assertEquals(mm.doSum(), 4)


    def test_dynamicAutomaticPowerupFailure(self):
        """
        Powerups with '__getPowerupInterfaces__' methods that don't return
        iterables of pairs report an informative error message when powered up.
        """
        s = Store()
        mm = Summer(store=s)
        s.powerUp(mm, ISumProducer)
        p = BrokenPowerup(store=s)
        err = self.assertRaises(ValueError, s.powerUp, p)
        self.assertEquals(str(err),
                          'return value from %r.__getPowerupInterfaces__'
                          ' not an iterable of 2-tuples' % (p,))


    def test_automaticPowerDown(self):
        """
        Powerups with 'powerupInterfaces' attributes can be powered
        down automatically on the interfaces they specify.
        """
        s = Store()
        p = PlusTwo(store=s)
        s.powerUp(p)
        s.powerDown(p)
        self.assertEquals(len(list(s.powerupsFor(IValueHaver))), 0)

    def test_automaticDynamicPowerDown(self):
        """
        Powerups with '__getPowerupInterfaces__' methods can be powered
        down automatically on the interfaces they specify.
        """
        s = Store()
        p = PlusOneTimesFour(store=s)
        s.powerUp(p)
        s.powerDown(p)
        self.assertEquals(len(list(s.powerupsFor(IValueHaver))), 0)
        self.assertEquals(len(list(s.powerupsFor(IScalingFactor))), 0)

    def testIndirectedPowerups(self):
        """
        Powerups which implement L{IPowerupIndirector} should not be returned
        directly, the values that they return from indirect() should be
        returned directly.
        """
        s = Store()
        mm = Summer(store=s)
        s.powerUp(
            SubtractThree(
                store=s, valueHaver=SumContributor(store=s, value=5)),
            IValueHaver)
        self.assertEquals(mm.doSum(), 2)
        s.close()


    def testNoIndirectedIndirection(self):
        """
        Because it is a special interface in the powerup system, you can't have
        powerups for IPowerupIndirector; there's no sensible thing that could
        mean other than an infinite loop. Let's make sure that both looking for
        IPowerupIndirector and attempting to install a powerup for it will fail
        appropriately.
        """
        s = Store()
        s3 = SubtractThree(store=s)
        self.assertRaises(TypeError, s.powerUp, s3, IPowerupIndirector)
        self.assertEqual(list(s.powerupsFor(IPowerupIndirector)), [])



from twisted.application.service import IService, Service

class SillyService(Item, Service):
    typeName = 'test_silly_service'
    schemaVersion = 1

    started = integer(default=0)
    stopped = integer(default=0)
    running = integer(default=0)

    parent = inmemory()

    def startService(self):
        self.started += 1
        self.running = 1

    def stopService(self):
        assert self.running
        self.running = 0
        self.stopped += 1

class SpecialCaseTest(unittest.TestCase):

    def testStoreServicePowerup(self):
        s = Store()
        ss = SillyService(store=s)
        s.powerUp(ss, IService)
        IService(s).startService()
        IService(s).stopService()
        self.assertEquals(ss.started, 1)
        self.assertEquals(ss.stopped, 1)
        self.assertEquals(ss.running, 0)

    def testItemServicePowerup(self):
        s = Store()
        sm = Summer(store=s)
        ss = SillyService(store=s)
        sm.powerUp(ss, IService)
        IService(sm).startService()
        IService(sm).stopService()
        self.assertEquals(ss.started, 1)
        self.assertEquals(ss.stopped, 1)
        self.assertEquals(ss.running, 0)



class InMemoryPowerupTests(unittest.TestCase):
    """
    Tests for the behavior of powerups which are not database-resident.
    """
    def test_powerupsFor(self):
        """
        L{Item.powerupsFor} returns a list the first element of which is the
        object previously passed to L{Item.inMemoryPowerUp}.
        """
        powerup = object()
        item = SumContributor(store=Store())
        item.inMemoryPowerUp(powerup, ISumProducer)
        self.assertEqual(list(item.powerupsFor(ISumProducer)), [powerup])


    def test_inMemoryPriority(self):
        """
        Adapting an L{Item} to an interface results in the in-memory powerup on
        that item for that interface even if there are database-resident
        powerups on that item for that interface.
        """
        powerup = object()
        item = SumContributor(store=Store())
        item.inMemoryPowerUp(powerup, ISumProducer)
        item.powerUp(item, ISumProducer)
        self.assertIdentical(ISumProducer(item), powerup)
