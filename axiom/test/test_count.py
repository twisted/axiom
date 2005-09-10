from twisted.trial.unittest import TestCase

from axiom.store import Store
from axiom.item import Item
from axiom.attributes import integer, AND, OR
import random

class ThingsWithIntergers(Item):
    schemaVersion = 1
    typeName = 'ThingsWithIntergers'

    a   = integer()
    b   = integer()

class TestCountQuery(TestCase):


    def assertCountEqualsQuery(self, item, cond = None):
        self.assertEquals(self.store.count(item, cond),
                          len(list(self.store.query(item, cond))),
                          'count and len(list(query)) not equals: %r,%r'%(item, cond))

    def setUp(self):
        self.store = Store()
        def populate():
            for i in xrange(2000):
                ThingsWithIntergers(store = self.store, a = random.randint(0,100), b = random.randint(0,100))
        self.store.transact(populate)

    def testBasicCount(self):
        self.assertCountEqualsQuery(ThingsWithIntergers)

    def testSimpleConditionCount(self):
        self.assertCountEqualsQuery(ThingsWithIntergers,
                                    ThingsWithIntergers.a > 50)

    def testTwoFieldsConditionCount(self):
        self.assertCountEqualsQuery(ThingsWithIntergers,
                                    ThingsWithIntergers.a == ThingsWithIntergers.b)

    def testANDConditionCount(self):
        self.assertCountEqualsQuery(ThingsWithIntergers,
                                    AND(ThingsWithIntergers.a > 50, ThingsWithIntergers.b < 50))

    def testORConditionCount(self):
        self.assertCountEqualsQuery(ThingsWithIntergers,
                                    OR(ThingsWithIntergers.a > 50, ThingsWithIntergers.b < 50))
