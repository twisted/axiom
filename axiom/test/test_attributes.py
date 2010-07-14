# -*- test-case-name: axiom.test.test_attributes -*-

import random
from decimal import Decimal

from epsilon.extime import Time

from twisted.trial.unittest import TestCase
from twisted.python.reflect import qual

from axiom.store import Store
from axiom.item import Item, normalize, Placeholder

from axiom.attributes import (
    Comparable, SQLAttribute, integer, timestamp, textlist, ConstraintError,
    ieee754_double, point1decimal, money)

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



class _Integer(Item):
    """
    Dummy item with an integer attribute.
    """
    value = integer()



class IntegerTests(TestCase):
    """
    Tests for L{integer} attributes.
    """
    def setUp(self):
        self.store = Store()


    def test_roundtrip(self):
        """
        A Python int roundtrips through an integer attribute.
        """
        i = _Integer(store=self.store, value=42)
        self.assertEquals(i.value, 42)


    def test_roundtripLong(self):
        """
        A Python long roundtrips through an integer attribute.
        """
        i = _Integer(store=self.store, value=42L)
        self.assertEquals(i.value, 42)


    def test_magnitudeBound(self):
        """
        Storing a value larger than what SQLite supports raises an exception.
        """
        i = _Integer()
        self.assertRaises(ConstraintError, _Integer, value=9999999999999999999)
        self.assertRaises(ConstraintError, _Integer, value=9223372036854775808)
        _Integer(value=9223372036854775807)
        _Integer(value=-9223372036854775808)
        self.assertRaises(ConstraintError, _Integer, value=-9223372036854775809)
        self.assertRaises(ConstraintError, _Integer, value=-9999999999999999999)



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

    def test_badAttribute(self):
        """
        L{Item} should not allow setting undeclared attributes.
        """
        s = Store()
        err = self.failUnlessRaises(AttributeError,
                                    FunkyItem, store=s, name=u"foo")
        self.assertEquals(str(err), "'FunkyItem' can't set attribute 'name'")


class WhiteboxComparableTest(TestCase):
    def test_likeRejectsIllegalOperations(self):
        """
        Test that invoking the underlying method which provides the interface
        to the LIKE operator raises a TypeError if it is invoked with too few
        arguments.
        """
        self.assertRaises(TypeError, Comparable()._like, 'XYZ')

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
    def tryRoundtrip(self, value):
        """
        Attempt to roundtrip a value through a database store and load, to
        ensure the representation is not lossy.
        """
        s = Store()
        tlt = TaggedListyThing(store=s, strlist=value)
        self.assertEquals(tlt.strlist, value)

        # Force it out of the cache, so it gets reloaded from the store
        del tlt
        tlt = s.findUnique(TaggedListyThing)
        self.assertEquals(tlt.strlist, value)


    def test_simpleListOfStrings(self):
        """
        Test that a simple list can be stored and retrieved successfully.
        """
        SOME_VALUE = [u'abc', u'def, ghi', u'jkl']
        self.tryRoundtrip(SOME_VALUE)


    def test_emptyList(self):
        """
        Test that an empty list can be stored and retrieved successfully.
        """
        self.tryRoundtrip([])


    def test_oldRepresentation(self):
        """
        Test that the new code can still correctly load the old representation
        which could not handle an empty list.
        """

        oldCases = [
            (u'foo', [u'foo']),
            (u'', [u'']),
            (u'\x1f', [u'', u'']),
            (u'foo\x1fbar', [u'foo', u'bar']),
            ]

        for dbval, pyval in oldCases:
            self.assertEqual(TaggedListyThing.strlist.outfilter(dbval, None), pyval)



class SQLAttributeDummyClass(Item):
    """
    Dummy class which L{SQLAttributeTestCase} will poke at to assert various
    behaviors.
    """
    dummyAttribute = SQLAttribute()



class FullImplementationDummyClass(Item):
    """
    Dummy class which L{SQLAttributeTestCase} will poke at to assert various
    behaviors - SQLAttribute is really an abstract base class, so this uses a
    concrete attribute (integer) for its assertions.
    """
    dummyAttribute = integer()


class SQLAttributeTestCase(TestCase):
    """
    Tests for behaviors of the L{axiom.attributes.SQLAttribute} class.
    """

    def test_attributeName(self):
        """
        Test that an L{SQLAttribute} knows its own local name.
        """
        self.assertEquals(
            SQLAttributeDummyClass.dummyAttribute.attrname,
            'dummyAttribute')


    def test_fullyQualifiedName(self):
        """
        Test that the L{SQLAttribute.fullyQualifiedName} method correctly
        returns the fully qualified Python name of the attribute: that is, the
        fully qualified Python name of the type it is defined on (plus a dot)
        plus the name of the attribute.
        """
        self.assertEquals(
            SQLAttributeDummyClass.dummyAttribute.fullyQualifiedName(),
            'axiom.test.test_attributes.SQLAttributeDummyClass.dummyAttribute')


    def test_fullyQualifiedStoreID(self):
        """
        Test that the L{IColumn} implementation on the storeID emits the
        correct fullyQualifiedName as well.  This is necessary because storeID
        is unfortunately implemented differently than other columns, due to its
        presence on Item.
        """
        self.assertEquals(
            SQLAttributeDummyClass.storeID.fullyQualifiedName(),
            'axiom.test.test_attributes.SQLAttributeDummyClass.storeID')


    def test_fullyQualifiedPlaceholder(self):
        """
        Verify that the L{IColumn.fullyQualifiedName} implementation on
        placeholder attributes returns a usable string, but one which is
        recognizable as an invalid Python identifier.
        """
        ph = Placeholder(SQLAttributeDummyClass)
        self.assertEquals(
            'axiom.test.test_attributes.SQLAttributeDummyClass'
            '.dummyAttribute.<placeholder:%d>' % (ph._placeholderCount,),
            ph.dummyAttribute.fullyQualifiedName())


    def test_accessor(self):
        """
        Test that the __get__ of SQLAttribute does the obvious thing, and returns
        its value when given an instance.
        """
        dummy = FullImplementationDummyClass(dummyAttribute=1234)
        self.assertEquals(
            FullImplementationDummyClass.dummyAttribute.__get__(dummy), 1234)
        self.assertEquals(dummy.dummyAttribute, 1234)


    def test_storeIDAccessor(self):
        """
        Test that the __get__ of the IColumn implementation for storeID works
        the same as that for normal attributes.
        """
        s = Store()
        dummy = FullImplementationDummyClass(store=s)
        self.assertIdentical(s.getItemByID(dummy.storeID), dummy)

    def test_placeholderAccessor(self):
        """
        Test that the __get__ of SQLAttribute does the obvious thing, and returns
        its value when given an instance.
        """
        dummy = FullImplementationDummyClass(dummyAttribute=1234)
        self.assertEquals(
            Placeholder(FullImplementationDummyClass
                        ).dummyAttribute.__get__(dummy), 1234)
        self.assertEquals(dummy.dummyAttribute, 1234)


    def test_typeAttribute(self):
        """
        Test that the C{type} attribute of an L{SQLAttribute} references the
        class on which the attribute is defined.
        """
        self.assertIdentical(
            SQLAttributeDummyClass,
            SQLAttributeDummyClass.dummyAttribute.type)


    def test_getShortColumnName(self):
        """
        Test that L{Store.getShortColumnName} returns something pretty close to
        the name of the attribute.

        XXX Testing this really well would require being able to parse a good
        chunk of SQL.  I don't know how to do that yet. -exarkun
        """
        s = Store()
        self.assertIn(
            'dummyAttribute',
            s.getShortColumnName(SQLAttributeDummyClass.dummyAttribute))


    def test_getColumnName(self):
        """
        Test that L{Store.getColumnName} returns something made up of the
        attribute's type's typeName and the attribute's name.
        """
        s = Store()
        self.assertIn(
            'dummyAttribute',
            s.getColumnName(SQLAttributeDummyClass.dummyAttribute))
        self.assertIn(
            normalize(qual(SQLAttributeDummyClass)),
            s.getColumnName(SQLAttributeDummyClass.dummyAttribute))
