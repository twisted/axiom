# -*- test-case-name: axiom.test.test_attributes -*-

import random
from decimal import Decimal

from epsilon.extime import Time

from twisted.trial.unittest import TestCase

from axiom.store import Store
from axiom.item import Item

from axiom.attributes import Comparable, integer, timestamp, textlist

from axiom.attributes import ieee754_double, point1decimal, money

class Number(Item):
    typeName = 'test_number'
    schemaVersion = 1

    value = ieee754_double()


class IEEE754DoubleTest(TestCase):

    def testRoundTrip(self):
        s = Store()
        Number(store=s, value=7.1)
        n = s.findFirst(Number)
        self.assertEquals(n.value, 7.1)

    def testFPSumsAreBrokenSoDontUseThem(self):
        s = Store()
        for x in range(10):
            Number(store=s,
                   value=0.1)
        self.assertNotEquals(s.query(Number).getColumn("value").sum(),
                             1.0)

        # This isn't really a unit test.  It's documentation.
        self.assertEquals(s.query(Number).getColumn("value").sum(),
                          0.99999999999999989)



class DecimalDoodad(Item):
    integral = point1decimal(default=0, allowNone=False)
    otherMoney = money(allowNone=True)
    extraintegral = integer()
    money = money(default=0)

class FixedPointDecimalTest(TestCase):
    def testSum(self):
        s = Store()
        for x in range(10):
            DecimalDoodad(store=s,
                          money=Decimal("0.10"))
        self.assertEquals(s.query(DecimalDoodad).getColumn("money").sum(),
                          1)

    def testRoundTrip(self):
        s = Store()
        DecimalDoodad(store=s, integral=19947,
                      money=Decimal("4.3"),
                      otherMoney=Decimal("-17.94"))
        self.assertEquals(s.findFirst(DecimalDoodad).integral, 19947)
        self.assertEquals(s.findFirst(DecimalDoodad).money, Decimal("4.3"))
        self.assertEquals(s.findFirst(DecimalDoodad).otherMoney, Decimal("-17.9400"))

    def testComparisons(self):
        s = Store()
        DecimalDoodad(store=s,
                      money=Decimal("19947.000000"),
                      otherMoney=19947)
        self.assertEquals(
            s.query(DecimalDoodad,
                    DecimalDoodad.money == DecimalDoodad.otherMoney).count(),
            1)
        self.assertEquals(
            s.query(DecimalDoodad,
                    DecimalDoodad.money != DecimalDoodad.otherMoney).count(),
            0)
        self.assertEquals(
            s.query(DecimalDoodad,
                    DecimalDoodad.money == 19947).count(),
            1)
        self.assertEquals(
            s.query(DecimalDoodad,
                    DecimalDoodad.money == Decimal("19947")).count(),
            1)


    def testDisallowedComparisons(self):
        # These tests should go away; it's (mostly) possible to support
        # comparison of different precisions:

        # sqlite> select 1/3;
        # 0
        # sqlite> select 3/1;
        # 3
        # sqlite> select 3/2;
        # 1


        s = Store()
        DecimalDoodad(store=s,
                      integral=1,
                      money=1)

        self.assertRaises(TypeError,
                          lambda : s.query(
                DecimalDoodad,
                DecimalDoodad.integral == DecimalDoodad.money))

        self.assertRaises(TypeError,
                          lambda : s.query(
                DecimalDoodad,
                DecimalDoodad.integral == DecimalDoodad.extraintegral))


class SpecialStoreIDAttributeTest(TestCase):

    def testStringStoreIDsDontWork(self):
        s = Store()
        sid = Number(store=s, value=1.0).storeID
        self.assertRaises(TypeError, s.getItemByID, str(sid))
        self.assertRaises(TypeError, s.getItemByID, float(sid))
        self.assertRaises(TypeError, s.getItemByID, unicode(sid))

class SortedItem(Item):
    typeName = 'test_sorted_thing'
    schemaVersion = 1

    goingUp = integer()
    goingDown = integer()
    theSame = integer()

class SortingTest(TestCase):

    def testCompoundSort(self):
        s = Store()
        L = []
        r10 = range(10)
        random.shuffle(r10)
        L.append(SortedItem(store=s,
                            goingUp=0,
                            goingDown=1000,
                            theSame=8))
        for x in r10:
            L.append(SortedItem(store=s,
                                goingUp=10+x,
                                goingDown=10-x,
                                theSame=7))

        for colnms in [['goingUp'],
                       ['goingUp', 'storeID'],
                       ['goingUp', 'theSame'],
                       ['theSame', 'goingUp'],
                       ['theSame', 'storeID']]:
            LN = L[:]
            LN.sort(key=lambda si: tuple([getattr(si, colnm) for colnm in colnms]))

            ascsort = [getattr(SortedItem, colnm).ascending for colnm in colnms]
            descsort = [getattr(SortedItem, colnm).descending for colnm in colnms]

            self.assertEquals(LN, list(s.query(SortedItem,
                                               sort=ascsort)))
            LN.reverse()
            self.assertEquals(LN, list(s.query(SortedItem,
                                               sort=descsort)))


class FunkyItem(Item):
    name = unicode()

class BadAttributeTest(TestCase):

    def testBadAttribute(self):
        s = Store()
        self.failUnlessRaises(AttributeError, FunkyItem, store=s,name=u"foo")


class WhiteboxComparableTest(TestCase):
    def testLikeRejectsIllegalOperations(self):
        self.assertRaises(ValueError, Comparable()._like, 'XYZ')

someRandomDate = Time.fromISO8601TimeAndDate("1980-05-29")

class DatedThing(Item):
    date = timestamp(default=someRandomDate)

class CreationDatedThing(Item):
    creationDate = timestamp(defaultFactory=lambda : Time())

class StructuredDefaultTestCase(TestCase):
    def testTimestampDefault(self):
        s = Store()
        sid = DatedThing(store=s).storeID
        self.assertEquals(s.getItemByID(sid).date,
                          someRandomDate)

    def testTimestampNow(self):
        s = Store()
        sid = CreationDatedThing(store=s).storeID
        self.failUnless(
            (Time().asDatetime() - s.getItemByID(sid).creationDate.asDatetime()).seconds <
            10)


class TaggedListyThing(Item):
    strlist = textlist()

class StringListTestCase(TestCase):
    def testSimpleListOfStrings(self):
        s = Store()
        SOME_VALUE = ['abc', 'def, ghi', 'jkl']
        tlt = TaggedListyThing(store=s, strlist=SOME_VALUE)
        self.assertEquals(tlt.strlist, SOME_VALUE)

