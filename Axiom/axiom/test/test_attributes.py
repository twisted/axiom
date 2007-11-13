# -*- test-case-name: axiom.test.test_attributes -*-

import random
from decimal import Decimal

from epsilon.extime import Time

from twisted.trial.unittest import TestCase
from twisted.python.reflect import qual

from axiom.store import Store, ItemQuery
from axiom.item import Item, normalize, Placeholder

from axiom.attributes import (
    Comparable, SQLAttribute, integer, timestamp, textlist, reference,
    ieee754_double, point1decimal, money, manyToMany, manyToOne)



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
        self.assertEquals(dummy.storeID, 1) # not *really* a requirement for
                                            # the future, but a sanity check
                                            # for the rest of the test
        self.assertEquals(
            FullImplementationDummyClass.storeID.__get__(dummy), 1)


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



class Whatever(Item):
    """
    A sample Item that will has a many-to-many relation to other L{Whatever}s.

    @ivar related: A L{manyToMany} to other L{Whatever} objects.
    @ivar score: Some integer which can be set and queried for.
    """
    score = integer()



class WhateverWhatever(Item):
    """
    A sample Item that links L{Whatever}s to L{Whatever}s.
    """
    a = reference(reftype=Whatever)
    b = reference(reftype=Whatever)

Whatever.related = manyToMany(WhateverWhatever,
                              WhateverWhatever.a, WhateverWhatever.b)



class manyToManyTest(TestCase):
    """
    Tests for the L{manyToMany} property.
    """

    def setUp(self):
        self.store = Store()


    def test_add_iter(self):
        """
        Iterating the result of a a L{manyToMany} property should give objects
        that have been added to it.
        """
        what1 = Whatever(store=self.store)
        what2 = Whatever(store=self.store)

        self.assertEquals(list(what1.related), [])
        what1.related.add(what2)
        self.assertEquals(list(what1.related), [what2])


    def test_unlinkAll(self):
        """
        It's possible to delete all relations to other objects.
        """
        what1 = Whatever(store=self.store)
        what2 = Whatever(store=self.store)
        what1.related.add(what2)
        what1.related.unlinkAll()
        self.assertEquals(list(what1.related), [])
        self.assertEquals(what2.store, self.store)


    def test_remove(self):
        """
        It's possible to explicitly remove one item from a relation
        with another.
        """
        what1 = Whatever(store=self.store)
        what2 = Whatever(store=self.store)
        what1.related.add(what2)
        what1.related.remove(what2)
        self.assertEquals(list(what1.related), [])
        self.assertEquals(what2.store, self.store)


    def test_query(self):
        """
        It's possible to restrict the query used to find related objects.
        """
        what1 = Whatever(store=self.store)
        what2 = Whatever(store=self.store, score=2)
        what22 = Whatever(store=self.store, score=2)
        what3 = Whatever(store=self.store, score=3)
        for x in (what2, what22, what3):
            what1.related.add(x)
        self.assertEquals(set(what1.related.query(Whatever.score == 2)),
                          set([what2, what22]))


    def test_item_query(self):
        """
        The object returned from C{query} should be an L{ItemQuery} to
        allow for further customization such as C{count}, C{paginate}
        etc.
        """
        what = Whatever(store=self.store)
        self.assertTrue(isinstance(what.related.query(), ItemQuery))


    def test_sort(self):
        """
        The C{query} method should take a C{sort} argument, just like
        L{Store.query}.
        """
        what = Whatever(store=self.store)
        what3 = Whatever(store=self.store, score=3)
        what1 = Whatever(store=self.store, score=1)
        what2 = Whatever(store=self.store, score=2)
        for x in (what3, what1, what2):
            what.related.add(x)
        self.assertEquals(
            list(what.related.query(sort=Whatever.score.ascending)),
            [what1, what2, what3])


    def test_item_query_limit(self):
        """
        The C{query} method should take a C{limit} argument, just like
        L{Store.query}.
        """
        what = Whatever(store=self.store)
        what3 = Whatever(store=self.store, score=3)
        what1 = Whatever(store=self.store, score=1)
        what2 = Whatever(store=self.store, score=2)
        for x in (what3, what1, what2):
            what.related.add(x)
        self.assertEquals(
            list(what.related.query(sort=Whatever.score.ascending, limit=2)),
            [what1, what2])


    def test_item_query_offset(self):
        """
        The C{query} method should take an C{offset} argument, just like
        L{Store.query}.
        """
        what = Whatever(store=self.store)
        what3 = Whatever(store=self.store, score=3)
        what1 = Whatever(store=self.store, score=1)
        what2 = Whatever(store=self.store, score=2)
        for x in (what3, what1, what2):
            what.related.add(x)
        self.assertEquals(
            list(what.related.query(sort=Whatever.score.ascending,
                                    limit=1, offset=1)),
            [what2])



class SampleN21(Item):
    """
    A sample item that has a 1:N relationship with L{Other}s.
    """
    UNUSED = integer()


class Other(Item):
    """
    A sample item that has a reference to L{SampleN21}.
    """
    score = integer()
    sample = reference(reftype=SampleN21)

SampleN21.others = manyToOne(Other, Other.sample)



class manyToOneTest(TestCase):
    """
    Tests for the L{manyToOne} property.
    """
    def setUp(self):
        self.store = Store()


    def test_iter(self):
        """
        Iterating the L{manyToOne} should yield related objects.
        """
        samp = SampleN21(store=self.store)
        self.assertEquals(list(samp.others), [])
        unrelated = Other(store=self.store)
        self.assertEquals(list(samp.others), [])
        related = Other(store=self.store, sample=samp)
        self.assertEquals(list(samp.others), [related])

    def test_query(self):
        """
        It's possible to restrict the query used to find related objects.
        """
        samp = SampleN21(store=self.store)
        other1 = Other(store=self.store, score=1, sample=samp)
        other12 = Other(store=self.store, score=1, sample=samp)
        other2 = Other(store=self.store, score=2, sample=samp)
        unrelated = Other(store=self.store, score=1)
        self.assertEquals(set(samp.others.query(Other.score == 1)),
                          set([other1, other12]))

    def test_item_query(self):
        """
        The object returned from C{query} should be an L{ItemQuery} to
        allow for further customization such as C{count}, C{paginate}
        etc.
        """
        samp = SampleN21(store=self.store)
        self.assertTrue(isinstance(samp.others.query(), ItemQuery))


    def test_sort(self):
        """
        The C{query} method should take a C{sort} argument, just like
        L{Store.query}.
        """
        samp = SampleN21(store=self.store)
        other3 = Other(store=self.store, score=3, sample=samp)
        other1 = Other(store=self.store, score=1, sample=samp)
        other2 = Other(store=self.store, score=2, sample=samp)
        self.assertEquals(
            list(samp.others.query(sort=Other.score.ascending)),
            [other1, other2, other3])


    def test_item_query_limit(self):
        """
        The C{query} method should take a C{limit} argument, just like
        L{Store.query}.
        """
        samp = SampleN21(store=self.store)
        other3 = Other(store=self.store, score=3, sample=samp)
        other1 = Other(store=self.store, score=1, sample=samp)
        other2 = Other(store=self.store, score=2, sample=samp)
        self.assertEquals(
            list(samp.others.query(sort=Other.score.ascending, limit=2)),
            [other1, other2])


    def test_item_query_offset(self):
        """
        The C{query} method should take an C{offset} argument, just like
        L{Store.query}.
        """
        samp = SampleN21(store=self.store)
        other3 = Other(store=self.store, score=3, sample=samp)
        other1 = Other(store=self.store, score=1, sample=samp)
        other2 = Other(store=self.store, score=2, sample=samp)
        self.assertEquals(
            list(samp.others.query(sort=Other.score.ascending,
                                    limit=1, offset=1)),
            [other2])
