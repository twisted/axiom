
from twisted.trial import unittest

from axiom.item import Item
from axiom.store import Store
from axiom.attributes import integer

from zope.interface import Interface, Attribute


class IValueHaver(Interface):
    value = Attribute("""
    An integer that you can add to other integers.
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
        return total


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
