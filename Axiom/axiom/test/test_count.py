from twisted.trial.unittest import TestCase

from axiom.store import Store
from axiom.item import Item
from axiom.attributes import integer, AND, OR

class ThingsWithIntegers(Item):
    schemaVersion = 1
    typeName = 'axiom_test_thing_with_integers'

    a = integer()
    b = integer()


class NotARealThing(Item):
    schemaVersion = 1
    typeName = 'axiom_test_never_created_item'

    irrelevantAttribute = integer()

    def __init__(self, **kw):
        raise NotImplementedError("You cannot create things that are not real!")


class TestCountQuery(TestCase):

    RANGE = 10
    MIDDLE = 5


    def assertCountEqualsQuery(self, item, cond = None):
        self.assertEquals(self.store.count(item, cond),
                          len(list(self.store.query(item, cond))),
                          'count and len(list(query)) not equals: %r,%r'%(item, cond))

    def setUp(self):
        self.store = Store()
        def populate():
            for i in xrange(self.RANGE):
                for j in xrange(self.RANGE):
                    ThingsWithIntegers(store = self.store, a = i, b = j)
        self.store.transact(populate)

    def testBasicCount(self):
        self.assertCountEqualsQuery(ThingsWithIntegers)

    def testSimpleConditionCount(self):
        self.assertCountEqualsQuery(ThingsWithIntegers,
                                    ThingsWithIntegers.a > self.MIDDLE)

    def testTwoFieldsConditionCount(self):
        self.assertCountEqualsQuery(ThingsWithIntegers,
                                    ThingsWithIntegers.a == ThingsWithIntegers.b)

    def testANDConditionCount(self):
        self.assertCountEqualsQuery(ThingsWithIntegers,
                                    AND(ThingsWithIntegers.a > self.MIDDLE, ThingsWithIntegers.b < self.MIDDLE))

    def testORConditionCount(self):
        self.assertCountEqualsQuery(ThingsWithIntegers,
                                    OR(ThingsWithIntegers.a > self.MIDDLE, ThingsWithIntegers.b < self.MIDDLE))

    def testEmptyResult(self):
        self.assertCountEqualsQuery(ThingsWithIntegers,
                                    ThingsWithIntegers.a == self.RANGE + 3)

    def testNonExistentTable(self):
        self.assertCountEqualsQuery(NotARealThing,
                                    NotARealThing.irrelevantAttribute == self.RANGE + 3)
