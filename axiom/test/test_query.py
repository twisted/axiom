
import operator, random, six

from twisted.trial.unittest import TestCase

from axiom.iaxiom import IComparison, IColumn
from axiom.store import Store, ItemQuery, MultipleItemQuery
from axiom.item import Item, Placeholder

from axiom import errors
from axiom.attributes import (
    reference, text, bytes, integer, AND, OR, TableOrderComparisonWrapper)
from six.moves import map

class A(Item):
    schemaVersion = 1
    typeName = 'a'

    reftoc = reference()
    type = text(indexed=True)


class B(Item):
    schemaVersion = 1
    typeName = 'b'

    cref = reference()
    name = text(indexed=True)

class C(Item):
    schemaVersion = 1
    typeName = 'c'

    name = text(indexed=True)

class D(Item):
    schemaVersion = 1
    typeName = 'd'
    id = bytes()
    one = bytes()
    two = bytes()
    three = bytes()
    four = text()

class E(Item):
    schemaVersion = 1
    typeName = 'e'
    name = text()
    transaction = text()
    amount = integer()


class ThingWithCharacterAndByteStrings(Item):
    schemaVersion = 1

    typeName = 'ThingWithCharacterAndByteStrings'

    characterString = text(caseSensitive=True)
    caseInsensitiveCharString = text(caseSensitive=False)

    byteString = bytes()


class BasicQuery(TestCase):

    def test_rightHandStoreIDComparison(self):
        """
        Test that a StoreID column on the right-hand side of an equality test
        results in a TwoAttributeComparison object rather than an
        AttributeValueComparison or anything else that would be wrong.
        """
        s = Store()
        comparison = (A.reftoc == B.storeID)
        self.assertEqual(
            comparison.getQuery(s),
            '({}.[reftoc] = {}.oid)'.format(
                A.getTableName(s),
                B.getTableName(s)))
        self.assertEqual(comparison.getArgs(s), [])


    def test_leftHandStoreIDComparison(self):
        """
        Test that a StoreID column on the left-hand side of an equality test
        results in a TwoAttributeComparison object rather than an
        AttributeValueComparison or anything else that would be wrong.
        """
        s = Store()
        comparison = (B.storeID == A.reftoc)
        self.assertEqual(
            comparison.getQuery(s),
            '({}.oid = {}.[reftoc])'.format(
                B.getTableName(s),
                A.getTableName(s)))
        self.assertEqual(comparison.getArgs(s), [])


    def test_simplestQuery(self):
        """
        Test that an ItemQuery with no comparison, sorting, or limit generates
        the right SQL for that operation.
        """
        s = Store()
        query = ItemQuery(s, A)
        sql, args = query._sqlAndArgs('SELECT', '*')
        self.assertEqual(
            sql,
            'SELECT * FROM {}'.format(A.getTableName(s)))
        self.assertEquals(args, [])


    def test_simpleIntegerComparison(self):
        """
        Test that an ItemQuery with a single attribute comparison on an integer
        attribute generates SQL with the right WHERE clause.
        """
        s = Store()
        query = ItemQuery(s, E, E.amount == 0)
        sql, args = query._sqlAndArgs('SELECT', '*')
        self.assertEqual(
            sql,
            'SELECT * FROM {} WHERE ({}.[amount] = ?)'.format(
                E.getTableName(s),
                E.getTableName(s)))
        self.assertEqual(args, [0])


    def test_simpleReferenceComparison(self):
        """
        Test that an ItemQuery with a single attribute comparison on a
        reference attribute generates SQL with the right WHERE clause.
        """
        s = Store()
        query = ItemQuery(s, A, A.reftoc == A.storeID)
        sql, args = query._sqlAndArgs('SELECT', '*')
        self.assertEqual(
            sql,
            'SELECT * FROM {} WHERE ({}.[reftoc] = {}.oid)'.format(
                A.getTableName(s),
                A.getTableName(s),
                A.getTableName(s)))
        self.assertEqual(args, [])


    def test_reversedReferenceComparison(self):
        """
        Test that an ItemQuery with a single attribute comparison on a
        reference attribute with the storeID part on the left-hand side
        generates SQL with the right WHERE clause.
        """
        s = Store()
        query = ItemQuery(s, A, A.storeID == A.reftoc)
        sql, args = query._sqlAndArgs('SELECT', '*')
        self.assertEqual(
            sql,
            'SELECT * FROM {} WHERE ({}.oid = {}.[reftoc])'.format(
                A.getTableName(s),
                A.getTableName(s),
                A.getTableName(s)))
        self.assertEqual(args, [])


    def test_unionComparison(self):
        """
        Test that an ItemQuery with two comparisons joined with an L{AND}
        generates the right WHERE clause.
        """
        s = Store()
        query = ItemQuery(s, A, AND(A.reftoc == B.storeID,
                                    B.cref == C.storeID))
        sql, args = query._sqlAndArgs('SELECT', '*')
        self.assertEqual(
            sql,
            'SELECT * FROM %s, %s, %s '
            'WHERE ((%s.[reftoc] = %s.oid) AND '
                   '(%s.[cref] = %s.oid))' % (
                A.getTableName(s),
                B.getTableName(s),
                C.getTableName(s),
                A.getTableName(s),
                B.getTableName(s),
                B.getTableName(s),
                C.getTableName(s)))
        self.assertEqual(args, [])


    def testBasicQuery(self):
        s = Store()

        def entesten():
            c1 = C(store=s,
                   name='yes')

            c2 = C(store=s,
                   name='no')

            A(store=s,
              reftoc=c1,
              type='testc')

            A(store=s,
              reftoc=c2,
              type='testc')

            A(store=s,
              reftoc=c1,
              type='testx')

            yesb = B(store=s,
                     cref=c1,
                     name='correct')

            B(store=s,
              cref=c2,
              name='not correct')

            s.checkpoint()

            q = list(s.query(B,
                             AND(AND(C.name == 'yes',
                                     A.type == 'testc'),
                                 AND(C.storeID == B.cref,
                                     A.reftoc == C.storeID)),
                             ))

            self.assertEqual(q, [yesb])

        s.transact(entesten)
        s.close()


    def testStringQueries(self):
        s = Store()

        def createAndStuff():
            text1 = u'Hello, \u1234 world.'
            text2 = u'ThIs sTrInG iS nOt cAsE sEnSiTIvE.  \u4567'
            bytes1 = b'\x00, punk'

            x = ThingWithCharacterAndByteStrings(
                store=s,
                characterString=text1,
                caseInsensitiveCharString=text2,
                byteString=bytes1)

            x.checkpoint()

            q = list(
                s.query(ThingWithCharacterAndByteStrings,
                        ThingWithCharacterAndByteStrings.characterString == text1.lower(),
                        ))
            self.assertFalse(q, q)

            q = list(
                s.query(ThingWithCharacterAndByteStrings,
                        ThingWithCharacterAndByteStrings.characterString == text1.upper(),
                        ))
            self.assertFalse(q, q)

            q = list(
                s.query(ThingWithCharacterAndByteStrings,
                        ThingWithCharacterAndByteStrings.characterString == text1,
                        ))

            self.assertEqual(q, [x])

            q = list(
                s.query(ThingWithCharacterAndByteStrings,
                        ThingWithCharacterAndByteStrings.caseInsensitiveCharString == text2,
                        ))

            self.assertEqual(q, [x])

            q = list(
                s.query(ThingWithCharacterAndByteStrings,
                        ThingWithCharacterAndByteStrings.caseInsensitiveCharString == text2.lower(),
                        ))

            self.assertEqual(q, [x])

            q = list(
                s.query(ThingWithCharacterAndByteStrings,
                        ThingWithCharacterAndByteStrings.caseInsensitiveCharString == text2.upper(),
                        ))

            self.assertEqual(q, [x])

            q = list(
                s.query(ThingWithCharacterAndByteStrings,
                        ThingWithCharacterAndByteStrings.byteString == bytes1,
                        ))

            self.assertEqual(q, [x])

            q = list(
                s.query(ThingWithCharacterAndByteStrings,
                        ThingWithCharacterAndByteStrings.byteString == bytes1.upper(),
                        ))

            self.assertFalse(q, q)

        s.transact(createAndStuff)
        s.close()


    def testAggregateQueries(self):
        s = Store()
        def entesten():
            self.assertEqual(s.query(E).count(), 0)
            self.assertEqual(s.query(E).getColumn("amount").sum(), 0)

            E(store=s, name='widgets', amount=37)
            E(store=s, name='widgets', amount=63)
            E(store=s, name='quatloos', amount=99, transaction='yes')
            s.checkpoint()
            q = s.count(E, E.name == 'widgets')
            self.assertEqual(q, 2)
            q = s.sum(E.amount, E.name == 'widgets')
            self.assertEqual(q, 100)
        s.transact(entesten)
        s.close()

    def testAttributeQueries(self):
        s = Store()
        def entesten():
            E(store=s, name='b', amount=456)
            E(store=s, name='a', amount=123)
            E(store=s, name='c', amount=789)
            self.assertEqual(list(s.query(E, sort=E.name.ascending).getColumn("amount")),
                              [123, 456, 789])

        s.transact(entesten)
        s.close()

    def testAttributeQueryCount(self):
        s = Store()
        def entesten():
            E(store=s, name='a', amount=123)
            E(store=s, name='b', amount=456)
            E(store=s, name='c')  # no amount given
            self.assertEqual(s.query(E).getColumn("amount").count(), 2)
        s.transact(entesten)
        s.close()

    def testAttributeQueryDistinct(self):
        s = Store()
        def entesten():
            E(store=s, name='a', amount=123)
            E(store=s, name='b', amount=789)
            E(store=s, name='a', amount=456)
            self.assertEqual(list(s.query(E, sort=E.name.ascending).getColumn("name").distinct()),
                              ["a", "b"])
        s.transact(entesten)
        s.close()


    def test_distinctQuerySQLiteBug(self):
        """
        Test for an SQLite bug.

        SQLite versions 3.5.8 and 3.5.9 have a bug that causes incorrect query
        results under certain circumstances:

            - A column with an index
            - SELECT DISTINCT query...
            - ... with an IS NOT NULL comparison on that column.

        Upstream ticket: http://www.sqlite.org/cvstrac/tktview?tn=3236
        """
        s = Store()
        def entesten():
            C(store=s, name='a')
            C(store=s, name='b')
            q = s.query(C, C.name != None).getColumn('name').distinct()
            self.assertEqual(sorted(q), ['a', 'b'])
        s.transact(entesten)
        s.close()


    def test_itemQueryDistinct(self):
        """
        Verify that a join which would produce duplicate rows will not produce
        duplicate item results.
        """
        s = Store()
        def entesten():
            theC = C(store=s, name='it')
            B(store=s, cref=theC)
            B(store=s, cref=theC)
            B(store=s, cref=theC)
            self.assertEqual(list(s.query(C, B.cref == C.storeID).distinct()),
                              [theC])
        s.transact(entesten)
        s.close()


    def test_itemQueryDistinctCount(self):
        """
        Like L{test_itemQueryDistinct} but for the C{count} method of a
        distinct item query.
        """
        s = Store()
        def entesten():
            for n, name in (2, 'it'), (3, 'indefinite nominative'):
                theC = C(store=s, name=name)
                for i in range(n):
                    B(store=s, cref=theC)
            self.assertEqual(
                s.query(C, B.cref == C.storeID).distinct().count(),
                2)
        s.transact(entesten)
        s.close()


    def test_itemQueryLimitAttribute(self):
        """
        L{ItemQuery} implements LI{IQuery} and should provide a 'limit'
        attribute depending on how it was created.
        """
        s = Store()
        q = s.query(C, limit=3)
        self.assertEqual(q.limit, 3)


    def test_itemQueryClone(self):
        """
        L{ItemQuery.cloneQuery} should return a new L{ItemQuery} which is
        equivalent, but not identical, to the original query.
        """
        s = Store()
        q1 = s.query(C, limit=3)
        q2 = q1.cloneQuery()
        self.assertEqual(q1.store, q2.store)
        self.assertEqual(q2.limit, q1.limit)
        self.assertNotIdentical(q1, q2)


    def test_itemQueryLimitSetToNone(self):
        """
        L{ItemQuery.cloneQuery} should set the limit attribute back to None when
        None is passed.  (e.g. it should not use None as the default value.
        HAX!)
        """
        s = Store()
        q1 = s.query(C, limit=3)
        q2 = q1.cloneQuery(limit=None)
        self.assertEqual(q1.store, q2.store)
        self.assertEqual(q2.limit, None)


    def test_itemQueryCloneLimit(self):
        """
        L{ItemQuery} implements L{IQuery} and should provide a 'cloneQuery'
        method which can accept a 'limit' parameter to change its limit.
        """
        s = Store()
        q1 = s.query(C, limit=3)
        q2 = q1.cloneQuery(5)
        self.assertEqual(q1.store, q2.store)
        self.assertEqual(q2.limit, 5)


    def test_itemQueryStoreAttribute(self):
        """
        L{ItemQuery} implements L{IQuery} and should provide a 'store' attribute
        that points to the store it will yield items from.
        """
        s = Store()
        q = s.query(C)
        self.assertEqual(q.store, s)


    def test_itemQueryDistinctLimitAttribute(self):
        """
        L{_DistinctQuery} implements L{IQuery} and should provide a 'limit'
        attribute depending on how it was created.
        """
        s = Store()
        q = s.query(C, limit=3).distinct()
        self.assertEqual(q.limit, 3)


    def test_itemQueryDistinctClone(self):
        """
        L{_DistinctQuery.cloneQuery} should return a new L{ItemQuery} which is
        equivalent, but not identical, to the original query.
        """
        s = Store()
        q1 = s.query(C, limit=3).distinct()
        q2 = q1.cloneQuery()
        self.assertEqual(q1.store, q2.store)
        self.assertEqual(q2.limit, q1.limit)


    def test_itemQueryDistinctCloneLimit(self):
        """
        L{_DistinctQuery} implements L{IQuery} and should provide a 'cloneQuery'
        method which can accept a 'limit' parameter to change its limit.
        """
        s = Store()
        q1 = s.query(C, limit=3).distinct()
        q2 = q1.cloneQuery(5)
        self.assertEqual(q1.store, q2.store)
        self.assertEqual(q2.limit, 5)


    def test_itemQueryDistinctStoreAttribute(self):
        """
        L{_DistinctQuery} implements L{IQuery} and should provide a 'store' attribute
        that points to the store it will yield items from.
        """
        s = Store()
        q = s.query(C).distinct()
        self.assertEqual(q.store, s)



    def testAttributeQueryMinMax(self):
        s = Store()
        def entesten():
            E(store=s, amount=-4)
            E(store=s, amount=10)
            E(store=s, amount=99)
            E(store=s, amount=456)

            self.assertEqual(s.query(E).getColumn("amount").min(), -4)
            self.assertEqual(s.query(E).getColumn("amount").max(), 456)

            self.assertRaises(ValueError, s.query(D).getColumn("id").max)
            self.assertRaises(ValueError, s.query(D).getColumn("id").min)

            self.assertEqual(s.query(D).getColumn("id").min(default=41), 41)
            self.assertEqual(s.query(D).getColumn("id").max(default=42), 42)


        s.transact(entesten)
        s.close()

    def test_attributeQueryLimitAttribute(self):
        """
        L{AttributeQuery} implements LI{IQuery} and should provide a 'limit'
        attribute depending on how it was created.
        """
        s = Store()
        q = s.query(C, limit=3).getColumn('name')
        self.assertEqual(q.limit, 3)


    def test_attributeQueryClone(self):
        """
        L{AttributeQuery.cloneQuery} should return a new L{AttributeQuery}
        which is equivalent, but not identical, to the original query.
        """
        s = Store()
        q1 = s.query(C, limit=3).getColumn('name')
        q2 = q1.cloneQuery()
        self.assertEqual(q1.store, q2.store)
        self.assertEqual(q2.limit, q1.limit)


    def test_attributeQueryCloneLimit(self):
        """
        L{AttributeQuery} implements L{IQuery} and should provide a 'cloneQuery'
        method which can accept a 'limit' parameter to change its limit.
        """
        s = Store()
        q1 = s.query(C, limit=3).getColumn('name')
        q2 = q1.cloneQuery(5)
        self.assertEqual(q1.store, q2.store)
        self.assertEqual(q2.limit, 5)
        self.assertEqual(q1.attribute, q2.attribute)
        self.assertEqual(q1.raw, q2.raw)


    def test_attributeQueryStoreAttribute(self):
        """
        L{AttributeQuery} implements L{IQuery} and should provide a 'store' attribute
        that points to the store it will yield attributes from.
        """
        s = Store()
        q = s.query(C).getColumn('name')
        self.assertEqual(q.store, s)



class MultipleQuery(TestCase):
    """
    Test cases for queries that yield multiple item types.
    """

    def test_basicJoin(self):
        """
        Verify that querying for multiple Item classes gives
        us the right number and type of Items, in a plausible order.
        """
        s = Store()
        def entesten():
            for i in range(3):
                c = C(store=s, name="C.%s" % i)
                B(store=s, name="B.%s" % (2-i), cref=c)

            query = s.query( (B, C),
                             B.cref == C.storeID,
                             sort=C.name.ascending)

            self.assertEqual(query.count(), 3)

            result = next(iter(query))

            self.assertEqual(len(result), 2)

            b, c = result

            self.assertTrue(isinstance(b, B))
            self.assertTrue(isinstance(c, C))

            self.assertEqual(b.name, "B.2")
            self.assertEqual(c.name, "C.0")

        s.transact(entesten)
        s.close()

    def test_count(self):
        """
        Verify that count() gives the right result in the
        presence of offset and limit.
        """
        s = Store()
        def entesten():
            for i in range(3):
                c = C(store=s, name="C.%s" % i)
                B(store=s, name="B.%s" % (2-i), cref=c)
                B(store=s, name="B2.%s" % (2-i), cref=c)

            query = s.query( (B, C),
                             B.cref == C.storeID)

            totalCombinations = 6

            self.assertEqual(query.count(), totalCombinations)

            for offset in range(totalCombinations):
                for limit in range(totalCombinations + 1):
                    query = s.query( (B, C),
                                     B.cref == C.storeID,
                                     offset=offset, limit=limit )
                    expectedCount = min((totalCombinations-offset), limit)
                    actualCount = query.count()
                    self.assertEquals(actualCount, expectedCount,
                                      "Got {} results with offset {}, limit {}".format(
                                      actualCount, offset, limit))

        s.transact(entesten)
        s.close()

    def test_distinct(self):
        """
        Verify that distinct gives the right answers for a multiple
        item queries.
        """
        s = Store()
        def entesten():
            for i in range(3):
                c = C(store=s, name="C.%s" % i)
                b = B(store=s, name="B.%s" % i, cref=c)
                A(store=s, type="A.%s" % i, reftoc=b)
                A(store=s, type="A.%s" % i, reftoc=b)

            query = s.query( (B, C),
                             AND(B.cref == C.storeID,
                                 A.reftoc == B.storeID),
                             sort = C.name.ascending )

            self.assertEqual(query.count(), 6)

            distinct = query.distinct()

            self.assertEqual(distinct.count(), 3)

            for i, (b, c) in enumerate(query.distinct()):
                self.assertEqual(b.name, "B.%s" % i)
                self.assertEqual(c.name, "C.%s" % i)

        s.transact(entesten)
        s.close()

    def test_tree(self):
        """
        Verify that queries using the same Item class more than
        once behave correctly.
        """
        s = Store()
        def entesten():
            pops = B(store=s, name="Pops")
            dad = B(store=s, name="Dad", cref=pops)
            B(store=s, name="Bro", cref=dad)
            B(store=s, name="Sis", cref=dad)

            Gen1 = Placeholder(B)
            Gen2 = Placeholder(B)
            Gen3 = Placeholder(B)

            query = s.query( (Gen1, Gen2, Gen3),
                             AND(Gen3.cref == Gen2.storeID,
                                 Gen2.cref == Gen1.storeID),
                             sort=Gen3.name.ascending )

            self.assertEqual(query.count(), 2)

            self.assertEquals(tuple(b.name for b in next(iter(query))),
                              (u"Pops", u"Dad", u"Bro"))
        s.transact(entesten)
        s.close()

    def test_oneTuple(self):
        """
        Verify that tuples of length one don't do anything crazy.
        """
        s = Store()
        def entesten():
            for i in range(3):
                C(store=s, name="C.%s" % i)

            query = s.query( (C,),
                             sort=C.name.ascending)

            self.assertEqual(query.count(), 3)

            results = iter(query)

            for i in range(3):
                result = next(results)
                self.assertEquals(len(result), 1)
                c, = result
                self.assertTrue(isinstance(c, C), "%s is not a C" % c)
                self.assertEqual(c.name, "C.%s" % i, i)

        s.transact(entesten)
        s.close()

    def test_emptyTuple(self):
        """
        Verify that empty tuples don't give SQL crashes.
        """
        s = Store()
        def entesten():
            self.assertRaises(ValueError, s.query, ())

        s.transact(entesten)
        s.close()


    def test_limitAttribute(self):
        """
        L{MultipleItemQuery} implements LI{IQuery} and should provide a 'limit'
        attribute depending on how it was created.
        """
        s = Store()
        q = s.query((B, C), limit=3)
        self.assertEqual(q.limit, 3)


    def test_clone(self):
        """
        L{MultipleItemQuery.cloneQuery} should return a new L{MultipleItemQuery}
        which is equivalent, but not identical, to the original query.
        """
        s = Store()
        q1 = s.query((B, C), limit=3)
        q2 = q1.cloneQuery()
        self.assertEqual(q1.store, q2.store)
        self.assertEqual(q2.limit, q1.limit)


    def test_cloneLimit(self):
        """
        L{MultipleItemQuery} implements L{IQuery} and should provide a 'cloneQuery'
        method which can accept a 'limit' parameter to change its limit.
        """
        s = Store()
        q1 = s.query((B, C), limit=3)
        q2 = q1.cloneQuery(5)
        self.assertEqual(q1.store, q2.store)
        self.assertEqual(q2.limit, 5)


    def test_storeAttribute(self):
        """
        L{MultipleItemQuery} implements L{IQuery} and should provide a 'store' attribute
        that points to the store it will yield attributes from.
        """
        s = Store()
        q = s.query((B, C))
        self.assertEqual(q.store, s)


    def test_limitAttributeDistinct(self):
        """
        L{_MultipleItemDistinctQuery} implements LI{IQuery} and should provide a
        'limit' attribute depending on how it was created.
        """
        s = Store()
        q = s.query((B, C), limit=3)
        self.assertEqual(q.limit, 3)


    def test_cloneDistinct(self):
        """
        L{_MultipleItemDistinctQuery.cloneQuery} should return a new
        L{MultipleItemQuery} which is equivalent, but not identical, to the
        original query.
        """
        s = Store()
        q1 = s.query((B, C), limit=3).distinct()
        q2 = q1.cloneQuery()
        self.assertEqual(q1.store, q2.store)
        self.assertEqual(q2.limit, q1.limit)


    def test_cloneLimitDistinct(self):
        """
        L{_MultipleItemDistinctQuery} implements L{IQuery} and should provide a
        'cloneQuery' method which can accept a 'limit' parameter to change its
        limit.
        """
        s = Store()
        q1 = s.query((B, C), limit=3).distinct()
        q2 = q1.cloneQuery(5)
        self.assertEqual(q1.store, q2.store)
        self.assertEqual(q2.limit, 5)


    def test_storeAttributeDistinct(self):
        """
        L{_MultipleItemDistinctQuery} implements L{IQuery} and should provide a
        'store' attribute that points to the store it will yield attributes
        from.
        """
        s = Store()
        q = s.query((B, C)).distinct()
        self.assertEqual(q.store, s)



class QueryingTestCase(TestCase):
    def setUp(self):
        s = self.store = Store()
        def _createStuff():
            self.d1 = D(store=s, one=b'd1.one', two=b'd1.two',
                        three=b'd1.three', four=u'd1.four', id=b'1')
            self.d2 = D(store=s, one=b'd2.one', two=b'd2.two',
                        three=b'd2.three', four=u'd2.four', id=b'2')
            self.d3 = D(store=s, one=b'd3.one', two=b'd3.two',
                        three=b'd3.three', four=u'd3.four', id=b'3')
        s.transact(_createStuff)

    def tearDown(self):
        self.store.close()

    def query(self, *a, **kw):
        return list(self.store.query(*a, **kw))

    def assertQuery(self, query, expected, args=None):
        """
        Perform byte-for-byte comparisons against generated SQL.  It would be
        slightly nicer if we have a SQL parser which emited an AST we could
        test against instead, but in the absence of that, we'll do the more
        difficult thing and keep the tests in sync with the SQL generator.
        If, someday, we have multiple backends which have different SQL
        generation requirements, we'll probably need to split all these tests
        up.

        While it is true that we don't actually directly care about what SQL
        gets generated, we do want to test the SQL generation as a /unit/,
        rather than indirectly testing it by making assertions about the
        result set it generates.  This for all the usual reasons one writes
        unit tests (ease of debugging, refactoring, maintenance).  Other
        tests cover the actual query behavior this SQL results in, and
        ideally some day we will have some tests which interact with the
        actual underlying rdbm to test basic assumptions we are making about
        the behavior of particular snippets of SQL.

        To sum up, changes to the SQL generation code may rightly require
        changes to tests which use assertQuery.  If the SQL we want to generate
        changes, do not be afraid to update the tests.
        """
        if args is None:
            args = []

        sql = query.getQuery(self.store)
        self.assertEqual(
            sql,
            expected,
            "\n%r != %r\n(if SQL generation code has changed, maybe this test "
            "should be updated)\n" % (sql, expected))
        self.assertEqual([bytes(a) for a in query.getArgs(self.store)], args)



class TableOrder(TestCase):
    """
    Tests for the order of tables when joins are being performed.
    """
    def test_baseQuery(self):
        """
        Test that the simplest query possible, one with only a FROM clause,
        specifies only the table for the type being queried.
        """
        store = Store()
        query = store.query(A)
        self.assertEqual(query.fromClauseParts, [store.getTableName(A)])


    def test_singleValueComparison(self):
        """
        Test that a query with a simple comparison against a value specifies
        only the table for the type being queried.
        """
        store = Store()
        query = store.query(A, A.type == 'value')
        self.assertEqual(query.fromClauseParts, [store.getTableName(A)])


    def test_twoColumnComparison(self):
        """
        Test that a query which compares one column against another from the
        type being queried specifies only the table for the type being queried
        for the FROM clause.
        """
        store = Store()
        query = store.query(A, A.type == A.reftoc)
        self.assertEqual(query.fromClauseParts, [store.getTableName(A)])


    def test_baseSort(self):
        """
        Test that a query which includes an ORDER BY clause including a column
        from the type being queried properly includes only the table for the
        type being queried in the FROM clause.
        """
        store = Store()
        query = store.query(A, sort=A.type.ascending)
        self.assertEqual(query.fromClauseParts, [store.getTableName(A)])


    def test_comparisonWithSort(self):
        """
        Test that a query with both a WHERE clause and an ORDER BY clause from
        the table being queried properly has only the table for the type being
        queried included in the FROM clause.
        """
        store = Store()
        query = store.query(A, A.type == 'value', sort=A.type.ascending)
        self.assertEqual(query.fromClauseParts, [store.getTableName(A)])


    def test_invalidComparison(self):
        """
        Test that a query with a WHERE clause which does not reference the type
        being queried for is rejected.
        """
        store = Store()
        self.assertRaises(
            ValueError,
            store.query, A, B.name == 'value')


    def test_invalidSort(self):
        """
        Test that sorting by a column from a table other than the one being
        queried without joining on that table is rejected.
        """
        store = Store()
        self.assertRaises(
            ValueError,
            store.query, A, sort=B.name.ascending)


    def test_singleJoin(self):
        """
        Test that joining on another table by performing a comparison between
        two types properly includes both table names, in the right order (the
        order of tables in the comparison, left to right), in the FROM CLAUSE.
        """
        store = Store()
        query = store.query(A, A.type == B.name)
        self.assertEqual(
            query.fromClauseParts,
            [store.getTableName(A), store.getTableName(B)])


    def test_singleJoinReversed(self):
        """
        Test that joining on another table by performing a comparison between
        two types properly includes both table names, in the right order (the
        order of tables in the comparison, left to right), in the FROM CLAUSE.
        """
        store = Store()
        query = store.query(A, B.name == A.type)
        self.assertEqual(
            query.fromClauseParts,
            [store.getTableName(B), store.getTableName(A)])


    def test_explicitTableOrder(self):
        """
        Test that the order of tables in a join can be explicitly specified by
        using L{TableOrderComparisonWrapper}.
        """
        store = Store()
        query = store.query(
            A, TableOrderComparisonWrapper(
                [E, D, C, B, A],
                AND(A.type == B.name,
                    B.name == C.name,
                    C.name == D.four,
                    D.four == E.name)))
        self.assertEqual(
            query.fromClauseParts,
            [store.getTableName(E), store.getTableName(D),
             store.getTableName(C), store.getTableName(B),
             store.getTableName(A)])


class AndOrQueries(QueryingTestCase):
    def testNoConditions(self):
        self.assertRaises(ValueError, AND)
        self.assertRaises(ValueError, OR)


    def testOneCondition(self):
        """
        Test that an L{AND} or an L{OR} with a single argument collapses to
        just that argument.
        """
        self.assertQuery(
            AND(A.type == u'Narf!'),
            '(({} = ?))'.format(A.type.getColumnName(self.store)),
            ['Narf!'])
        self.assertQuery(
            OR(A.type == u'Narf!'),
            '(({} = ?))'.format(A.type.getColumnName(self.store)),
            ['Narf!'])
        self.assertEqual(self.query(D, AND(D.one == b'd1.one')), [self.d1])
        self.assertEqual(self.query(D, OR(D.one == b'd1.one')), [self.d1])


    def testMultipleAndConditions(self):
        condition = AND(A.type == 'Narf!',
                        A.type == 'Poiuyt!',
                        A.type == 'Try to take over the world')

        expectedSQL = '((%s = ?) AND (%s = ?) AND (%s = ?))'
        expectedSQL %= (A.type.getColumnName(self.store),) * 3

        self.assertQuery(
            condition,
            expectedSQL,
            ['Narf!', 'Poiuyt!', 'Try to take over the world'])
        self.assertEqual(
            self.query(D, AND(D.one == b'd1.one',
                              D.two == b'd1.two',
                              D.three == b'd1.three')),
            [self.d1])

    def testMultipleOrConditions(self):
        condition = OR(A.type == 'Narf!',
                       A.type == 'Poiuyt!',
                       A.type == 'Try to take over the world')
        expectedSQL = '((%s = ?) OR (%s = ?) OR (%s = ?))'
        expectedSQL %= (A.type.getColumnName(self.store),) * 3
        self.assertQuery(
            condition,
            expectedSQL,
            ['Narf!', 'Poiuyt!', 'Try to take over the world'])
        q = self.query(D, OR(D.one == b'd1.one',
                             D.one == b'd2.one',
                             D.one == b'd3.one'))
        e = [self.d1, self.d2, self.d3]
        self.assertEqual(sorted(q, key=lambda d: d.one),
                         sorted(e, key=lambda d: d.one))


class SetMembershipQuery(QueryingTestCase):

    def test_oneOfValueQueryGeneration(self):
        """
        Test that comparing an attribute for containment against a value set
        generates the appropriate SQL.
        """
        values = ['a', 'b', 'c']
        comparison = C.name.oneOf(values)
        self.assertTrue(IComparison.providedBy(comparison))
        self.assertEqual(
            comparison.getQuery(self.store),
            '{} IN (?, ?, ?)'.format(
                C.name.getColumnName(self.store)))
        self.assertEquals(
            comparison.getArgs(self.store),
            values)


    def test_oneOfColumnQueryGeneration(self):
        """
        Test that comparing an attribute for containment against an L{IColumn}
        generates the appropriate SQL.
        """
        values = A.type
        comparison = C.name.oneOf(values)
        self.assertTrue(IComparison.providedBy(comparison))
        self.assertEqual(
            comparison.getQuery(self.store),
            '{} IN ({})'.format(
                C.name.getColumnName(self.store),
                A.type.getColumnName(self.store)))
        self.assertEqual(
            comparison.getArgs(self.store),
            [])


    def test_oneOfColumnQueryQueryGeneration(self):
        """
        Test that comparing an attribute for containment against another query
        generates a sub-select.
        """
        subselect = self.store.query(A).getColumn('type')
        comparison = C.name.oneOf(subselect)
        self.assertTrue(IComparison.providedBy(comparison))
        self.assertEqual(
            comparison.getQuery(self.store),
            '{} IN (SELECT {} FROM {})'.format(
                C.name.getColumnName(self.store),
                A.type.getColumnName(self.store),
                A.getTableName(self.store)))
        self.assertEqual(
            comparison.getArgs(self.store),
            [])


    def test_oneOfColumnQueryQueryGenerationWithArguments(self):
        """
        Like test_oneOfColumnQueryQueryGeneration, but pass some values to the
        subselect and make sure they come out of the C{getArgs} method
        properly.
        """
        value = b'10'
        subselect = self.store.query(
            D,
            AND(D.id == value,
                D.four == C.name)).getColumn('one')

        comparison = C.name.oneOf(subselect)
        self.assertTrue(IComparison.providedBy(comparison))
        self.assertEqual(
            comparison.getQuery(self.store),
            '{} IN (SELECT {} FROM {}, {} WHERE (({} = ?) AND ({} = {})))'.format(
                C.name.getColumnName(self.store),
                D.one.getColumnName(self.store),
                D.getTableName(self.store),
                C.getTableName(self.store),
                D.id.getColumnName(self.store),
                D.four.getColumnName(self.store),
                C.name.getColumnName(self.store)))
        self.assertEquals(
            list(comparison.getArgs(self.store)),
            [value])


    def testOneOfWithList(self):
        cx = C(store=self.store, name='x')
        C(store=self.store, name='y')
        cz = C(store=self.store, name='z')

        query = self.store.query(
            C, C.name.oneOf(['x', 'z', 'a']), sort=C.name.ascending)

        self.assertEqual(list(query), [cx, cz])


    def testOneOfWithSet(self):
        s = Store()

        cx = C(store=s, name='x')
        C(store=s, name='y')
        cz = C(store=s, name='z')

        self.assertEquals(list(s.query(C, C.name.oneOf({u'x', u'z', u'a'}), sort=C.name.ascending)),
                          [cx, cz])


class WildcardQueries(QueryingTestCase):
    def testNoConditions(self):
        self.assertRaises(TypeError, D.one.like)
        self.assertRaises(TypeError, D.one.notLike)


    def test_likeValueComparisonInvolvedTables(self):
        """
        Test that only the table to which a column belongs is included in the
        involved tables set when that column is compared to a literal value
        using like.
        """
        comparison = D.one.like('foo')
        self.assertEqual(comparison.getInvolvedTables(), [D])


    def test_likeColumnComparisonInvolvedTables(self):
        """
        Test that both the table to which a column belongs and the table to
        which a target column belongs are included in the involved tables set
        when those columns are compared using like.
        """
        comparison = D.one.like(A.type)
        self.assertEqual(comparison.getInvolvedTables(), [D, A])


    def testOneString(self):
        self.assertQuery(
            D.one.like(b'foobar%'),
            '({} LIKE (?))'.format(D.one.getColumnName(self.store)),
            [b'foobar%'])
        self.assertQuery(
            D.one.notLike(b'foobar%'),
            '({} NOT LIKE (?))'.format(D.one.getColumnName(self.store)),
            [b'foobar%'])
        self.assertEqual(self.query(D, D.four.like(u'd1.four')), [self.d1])
        self.assertEqual(self.query(D, D.four.notLike(u'd%.four')), [])

    def testOneColumn(self):
        self.assertQuery(
            D.one.like(D.two),
            '({} LIKE ({}))'.format(D.one.getColumnName(self.store),
                                D.two.getColumnName(self.store)))
        self.assertEqual(self.query(D, D.one.like(D.two)), [])

    def testOneColumnAndStrings(self):
        self.assertQuery(
            D.four.like(u'%', D.id, u'%four'),
            '({} LIKE (? || {} || ?))'.format(D.four.getColumnName(self.store),
                                          D.id.getColumnName(self.store)),
            ['%', '%four'])
        q = self.query(D, D.four.like('%', D.id, '%four'))
        e = [self.d1, self.d2, self.d3]
        self.assertEqual(sorted(q, key=lambda d: d.id),
                         sorted(e, key=lambda d: d.id))

    def testMultipleColumns(self):
        self.assertQuery(
            D.one.like(D.two, b'%', D.three),
            '({} LIKE ({} || ? || {}))'.format(D.one.getColumnName(self.store),
                                           D.two.getColumnName(self.store),
                                           D.three.getColumnName(self.store)),
            [b'%'])
        self.assertEqual(
            self.query(D, D.one.like(D.two, b'%', D.three)), [])


    def testStartsEndsWith(self):
        self.assertQuery(
            D.four.startswith(u'foo'),
            '({} LIKE (?))'.format(D.four.getColumnName(self.store)),
            ['foo%'])
        self.assertQuery(
            D.four.endswith(u'foo'),
            '({} LIKE (?))'.format(D.four.getColumnName(self.store)),
            ['%foo'])
        self.assertEqual(
            self.query(D, D.four.startswith('d1')), [self.d1])
        self.assertEqual(
            self.query(D, D.four.endswith('3.four')), [self.d3])


    def testStartsEndsWithText(self):
        self.assertEqual(
            self.query(D, D.four.startswith('d1')),
            [self.d1])
        self.assertEqual(
            self.query(D, D.four.endswith('2.four')),
            [self.d2])



class UniqueTest(TestCase):

    def setUp(self):
        s = self.s = Store()
        self.c = C(store=s, name='unique')
        self.dupc1 = C(store=s, name='non-unique')
        self.dupc2 = C(store=s, name='non-unique')

    def testUniqueFound(self):
        self.assertEqual(self.s.findUnique(C, C.name == 'unique'), self.c)

    def testUniqueNotFoundError(self):
        self.assertRaises(errors.ItemNotFound, self.s.findUnique,
                          C, C.name == 'non-existent')

    def testUniqueNotFoundDefault(self):
        bing = object()
        self.assertEqual(bing, self.s.findUnique(
                C, C.name == 'non-existent',
                default=bing))

    def testUniqueDuplicate(self):
        self.assertRaises(errors.DuplicateUniqueItem,
                          self.s.findUnique, C, C.name == 'non-unique')



class PlaceholderTestItem(Item):
    """
    Type used by the placeholder support test cases.
    """
    attr = integer()
    other = integer()
    characters = text()


COMPARISON_OPS = [
    operator.lt, operator.le, operator.eq,
    operator.ne, operator.ge, operator.gt]

class PlaceholderTestCase(TestCase):
    """
    Tests for placeholder table name support.
    """
    def test_placeholderType(self):
        """
        Test that the C{type} attribute of a Placeholder column is the
        Placeholder from which it came.
        """
        p = Placeholder(PlaceholderTestItem)
        a = p.attr
        self.assertIdentical(a.type, p)


    def test_placeholderTableName(self):
        """
        Test that the table name of a Placeholder is the same as the table name
        of the underlying Item class.
        """
        s = Store()
        p = Placeholder(PlaceholderTestItem)
        self.assertEqual(p.getTableName(s), PlaceholderTestItem.getTableName(s))


    def test_placeholderColumnInterface(self):
        """
        Test that a column from a placeholder provides L{IColumn}.
        """
        p = Placeholder(PlaceholderTestItem)
        a = p.attr
        self.assertTrue(IColumn.providedBy(a))


    def test_placeholderAttributeValueComparison(self):
        """
        Test that getting an attribute from a Placeholder which exists on the
        underlying Item class and comparing it to a value returns an
        L{IComparison} provider.
        """
        value = 0
        p = Placeholder(PlaceholderTestItem)
        for op in COMPARISON_OPS:
            self.assertTrue(IComparison.providedBy(op(p.attr, value)))
            self.assertTrue(IComparison.providedBy(op(value, p.attr)))


    def test_placeholderAttributeColumnComparison(self):
        """
        Test that getting an attribute from a Placeholder which exists on the
        underlying Item class and comparing it to another column returns an
        L{IComparison} provider.
        """
        p = Placeholder(PlaceholderTestItem)
        for op in COMPARISON_OPS:
            self.assertTrue(IComparison.providedBy(op(p.attr, PlaceholderTestItem.attr)))
            self.assertTrue(IComparison.providedBy(op(PlaceholderTestItem.attr, p.attr)))


    def _placeholderAttributeSimilarity(self, kind, sql, args):
        s = Store()
        value = 'text'

        p = Placeholder(PlaceholderTestItem)

        # Explicitly call this, since we aren't going through ItemQuery.
        p.getTableAlias(s, ())

        comparison = getattr(p.characters, kind)(value)
        self.assertTrue(IComparison.providedBy(comparison))
        self.assertEqual(comparison.getQuery(s),
                          sql % (p.characters.getColumnName(s),))
        self.assertEqual(
            comparison.getArgs(s),
            [args % (value,)])


    def test_placeholderAttributeSimilarity(self):
        """
        Test that placeholder attributes can be used with the SQL LIKE
        operator.
        """
        return self._placeholderAttributeSimilarity('like', '(%s LIKE (?))', '%s')


    def test_placeholderAttributeDisimilarity(self):
        """
        Test that placeholder attributes can be used with the SQL NOT LIKE
        operator.
        """
        return self._placeholderAttributeSimilarity('notLike', '(%s NOT LIKE (?))', '%s')


    def test_placeholderAttributeStartsWith(self):
        """
        Test that placeholder attributes work with the .startswith() method.
        """
        return self._placeholderAttributeSimilarity('startswith', '(%s LIKE (?))', '%s%%')


    def test_placeholderAttributeEndsWith(self):
        """
        Test that placeholder attributes work with the .endswith() method.
        """
        return self._placeholderAttributeSimilarity('endswith', '(%s LIKE (?))', '%%%s')


    def test_placeholderLikeTarget(self):
        """
        Test that a placeholder can be used as the right-hand argument to a SQL
        LIKE expression.
        """
        s = Store()
        p = Placeholder(PlaceholderTestItem)

        # Call this since we're not using ItemQuery
        p.getTableAlias(s, ())

        comparison = PlaceholderTestItem.attr.like(p.attr)
        self.assertTrue(IComparison.providedBy(comparison))
        self.assertEqual(
            comparison.getQuery(s),
            '({} LIKE (placeholder_0.[attr]))'.format(
                PlaceholderTestItem.attr.getColumnName(s)))
        self.assertEquals(
            comparison.getArgs(s),
            [])


    def test_placeholderContainment(self):
        """
        Test that placeholder attributes can be used with the SQL IN and NOT IN
        operators.
        """
        s = Store()
        value = [1, 2, 3]
        p = Placeholder(PlaceholderTestItem)

        # Call this since we're not using ItemQuery
        p.getTableAlias(s, ())

        comparison = p.attr.oneOf(value)
        self.assertTrue(IComparison.providedBy(comparison))
        self.assertEqual(
            comparison.getQuery(s),
            '{} IN (?, ?, ?)'.format(p.attr.getColumnName(s)))
        self.assertEquals(
            comparison.getArgs(s),
            value)


    def test_placeholderAntiContainment(self):
        """
        Test that placeholder attributes can be used with the SQL NOT IN
        operator.
        """
        s = Store()
        value = [1, 2, 3]
        p = Placeholder(PlaceholderTestItem)

        # Call this since we're not using ItemQuery
        p.getTableAlias(s, ())

        comparison = p.attr.notOneOf(value)
        self.assertTrue(IComparison.providedBy(comparison))
        self.assertEqual(
            comparison.getQuery(s),
            '{} NOT IN (?, ?, ?)'.format(p.attr.getColumnName(s)))
        self.assertEquals(
            comparison.getArgs(s),
            value)


    def test_placeholderContainmentTarget(self):
        """
        Test that a placeholder attribute can be used as the right-hand
        argument to the SQL IN operator.
        """
        s = Store()
        p = Placeholder(PlaceholderTestItem)

        # Call this since we're not using ItemQuery
        p.getTableAlias(s, ())

        comparison = PlaceholderTestItem.attr.oneOf(p.attr)
        self.assertTrue(IComparison.providedBy(comparison))
        self.assertEqual(
            comparison.getQuery(s),
            '{} IN ({})'.format(PlaceholderTestItem.attr.getColumnName(s),
                            p.attr.getColumnName(s)))
        self.assertEqual(
            comparison.getArgs(s),
            [])


    def test_placeholderAntiContainmentTarget(self):
        """
        Test that a placeholder attribute can be used as the right-hand
        argument to the SQL NOT IN operator.
        """
        s = Store()
        p = Placeholder(PlaceholderTestItem)

        # Call this since we're not using ItemQuery
        p.getTableAlias(s, ())

        comparison = PlaceholderTestItem.attr.notOneOf(p.attr)
        self.assertTrue(IComparison.providedBy(comparison))
        self.assertEqual(
            comparison.getQuery(s),
            '{} NOT IN ({})'.format(PlaceholderTestItem.attr.getColumnName(s),
                            p.attr.getColumnName(s)))
        self.assertEqual(
            comparison.getArgs(s),
            [])


    def test_placeholderStoreID(self):
        """
        Test that the C{storeID} attribute of a Placeholder can be retrieved
        just like any other attribute.
        """
        value = 0
        p = Placeholder(PlaceholderTestItem)
        self.assertTrue(IComparison.providedBy(p.storeID > value))


    def test_placeholderAttributeError(self):
        """
        Test that trying to get an attribute from a Placeholder which is not an
        L{IComparison} on the underlying Item class raises an AttributeError.
        """
        p = Placeholder(PlaceholderTestItem)
        self.assertRaises(AttributeError, getattr, p, 'nonexistentAttribute')


    def test_placeholderComparisonTables(self):
        """
        Test that the result of L{IComparison.getInvolvedTables} on an
        attribute retrieved from a Placeholder returns a special placeholder
        item.
        """
        s = Store()
        p = Placeholder(PlaceholderTestItem)
        value = 0
        involvedTables = (p.attr > value).getInvolvedTables()
        self.assertEquals(len(involvedTables), 1)
        theTable = next(iter(involvedTables))
        self.assertEquals(theTable.getTableName(s),
                          PlaceholderTestItem.getTableName(s))
        self.assertEqual(theTable.getTableAlias(s, ()),
                          'placeholder_0')


    def test_placeholderComparisonQuery(self):
        """
        Test that the result of L{IComparison.getQuery} on an attribute
        retrieved from a Placeholder returns SQL which correctly uses an alias
        of the wrapped table.
        """
        s = Store()
        p = Placeholder(PlaceholderTestItem)

        # Explicitly call this here, since we're not going through ItemQuery or
        # another more reasonable codepath, which would have called it for us.
        p.getTableAlias(s, ())

        value = 0
        comparison = (p.attr > value)
        self.assertEqual(
            comparison.getQuery(s),
            '(placeholder_0.[attr] > ?)')
        self.assertEqual(
            comparison.getArgs(s),
            [value])


    def test_placeholderComparisonArgs(self):
        """
        Test that the result of L{IComparison.getArgs} on an attribute
        retrieved from a Placeholder returns the right values for the
        comparison.
        """
        s = Store()
        p = Placeholder(PlaceholderTestItem)
        value = 0
        args = (p.attr > value).getArgs(s)
        self.assertEqual(args, [0])


    def test_placeholderQuery(self):
        """
        Test that an ItemQuery can be created with Placeholder instances and
        the SQL it emits as a result correctly assigns and uses table aliases.
        """
        s = Store()
        p = Placeholder(PlaceholderTestItem)
        sql, args = ItemQuery(s, p)._sqlAndArgs('SELECT', '*')
        self.assertEqual(
            sql,
            'SELECT * FROM {} AS placeholder_0'.format(
                PlaceholderTestItem.getTableName(s)))


    def test_placeholderMultiQuery(self):
        """
        Test that a MultipleItemQuery can be created with Placeholder instances
        and the SQL it emits as a result correctly assigns and uses table
        aliases.
        """
        s = Store()
        p1 = Placeholder(PlaceholderTestItem)
        p2 = Placeholder(PlaceholderTestItem)
        sql, args = MultipleItemQuery(s, (p1, p2))._sqlAndArgs('SELECT', '*')
        tableName = PlaceholderTestItem.getTableName(s)
        self.assertEqual(
            sql,
            'SELECT * FROM {} AS placeholder_0, {} AS placeholder_1'.format(
                tableName, tableName))


    def test_placeholderComparison(self):
        """
        Test that a comparison which contains a Placeholder also results in
        properly generated SQL.
        """
        s = Store()
        p = Placeholder(PlaceholderTestItem)
        query = ItemQuery(
            s,
            PlaceholderTestItem,
            PlaceholderTestItem.attr == p.attr)
        sql, args = query._sqlAndArgs('SELECT', '*')
        self.assertEqual(
            sql,
            'SELECT * '
            'FROM %s, %s AS placeholder_0 '
            'WHERE (%s.[attr] = placeholder_0.[attr])' % (
                PlaceholderTestItem.getTableName(s),
                PlaceholderTestItem.getTableName(s),
                PlaceholderTestItem.getTableName(s)))
        self.assertEqual(args, [])


    def test_placeholderOrdering(self):
        """
        Placeholders should be ordered based on the order in which they were
        instantiated.
        """
        p1 = Placeholder(PlaceholderTestItem)
        p2 = Placeholder(PlaceholderTestItem)
        self.assertTrue(p1 < p2)
        self.assertTrue(p2 > p1)
        self.assertFalse(p1 >= p2)
        self.assertFalse(p2 <= p1)
        self.assertFalse(p1 == p2)
        self.assertFalse(p2 == p1)
        self.assertTrue(p1 != p2)
        self.assertTrue(p2 != p1)


    def test_placeholderObjectSorting(self):
        """
        Placeholders should sort based on the order in which they were
        instantiated.
        """
        placeholders = [Placeholder(PlaceholderTestItem) for n in range(10)]
        shuffledPlaceholders = list(placeholders)
        random.shuffle(shuffledPlaceholders)
        shuffledPlaceholders.sort()
        self.assertEqual(placeholders, shuffledPlaceholders)


    def test_placeholderAliasAssignment(self):
        """
        Test that each placeholder selects a unique alias for itself.
        """
        s = Store()
        p1 = Placeholder(PlaceholderTestItem)
        p2 = Placeholder(PlaceholderTestItem)

        aliases = []
        self.assertEqual(p1.getTableAlias(s, aliases), 'placeholder_0')
        self.assertEqual(p1.getTableAlias(s, aliases), 'placeholder_0')
        aliases.append('placeholder_')
        self.assertEqual(p1.getTableAlias(s, aliases), 'placeholder_0')
        self.assertEqual(p2.getTableAlias(s, aliases), 'placeholder_1')


    def test_multiplePlaceholderComparisons(self):
        """
        Test that using multiple different placeholders in a comparison at once
        properly gives each a unique name.
        """
        s = Store()
        p1 = Placeholder(PlaceholderTestItem)
        p2 = Placeholder(PlaceholderTestItem)

        query = ItemQuery(
            s,
            PlaceholderTestItem,
            AND(PlaceholderTestItem.attr == p1.attr,
                PlaceholderTestItem.other == p1.other,
                PlaceholderTestItem.attr == p2.attr,
                PlaceholderTestItem.characters == p2.characters))
        sql, args = query._sqlAndArgs('SELECT', '*')
        self.assertEqual(
            sql,
            'SELECT * '
            'FROM %s, %s AS placeholder_0, %s AS placeholder_1 '
            'WHERE ((%s = placeholder_0.[attr]) AND '
                   '(%s = placeholder_0.[other]) AND '
                   '(%s = placeholder_1.[attr]) AND '
                   '(%s = placeholder_1.[characters]))' % (
                PlaceholderTestItem.getTableName(s),
                PlaceholderTestItem.getTableName(s),
                PlaceholderTestItem.getTableName(s),
                PlaceholderTestItem.attr.getColumnName(s),
                PlaceholderTestItem.other.getColumnName(s),
                PlaceholderTestItem.attr.getColumnName(s),
                PlaceholderTestItem.characters.getColumnName(s)))
        self.assertEqual(args, [])


    def test_sortByPlaceholderAttribute(self):
        """
        Test that a placeholder attribute can be used as a sort key.
        """
        s = Store()
        p = Placeholder(PlaceholderTestItem)

        query = ItemQuery(
            s,
            p,
            sort=p.attr.ascending)
        sql, args = query._sqlAndArgs('SELECT', '*')

        expectedSQL = ('SELECT * '
                       'FROM %s AS placeholder_0 '
                       'ORDER BY placeholder_0.[attr] ASC')
        expectedSQL %= (p.getTableName(s),)

        self.assertEqual(sql, expectedSQL)
        self.assertEqual(args, [])


    def test_placeholderColumnNamesInQueryTarget(self):
        """
        Test that placeholders are used correctly in the 'result'
        portion of an SQL query.
        """
        s = Store()
        p = Placeholder(PlaceholderTestItem)

        query = ItemQuery(s, p)

        expectedSQL = "placeholder_0.oid, placeholder_0.[attr], placeholder_0.[characters], placeholder_0.[other]"

        self.assertEqual(query._queryTarget, expectedSQL)



bytes_deprecated_prefix = 'axiom.attributes.bytes.' if six.PY3 else 'axiom.attributes.'



class BytesDeprecatedLikeTests(TestCase):
    """
    Deprecated tests for LIKE queries on L{axiom.attributes.bytes}.
    """
    def test_startsWith(self):
        self.assertWarns(
            DeprecationWarning,
            bytes_deprecated_prefix + 'startswith was deprecated in Axiom 0.7.5',
            __file__,
            lambda: D.one.startswith('string'))


    def test_endsWith(self):
        self.assertWarns(
            DeprecationWarning,
            bytes_deprecated_prefix + 'endswith was deprecated in Axiom 0.7.5',
            __file__,
            lambda: D.one.endswith('string'))


    def test_like(self):
        self.assertWarns(
            DeprecationWarning,
            bytes_deprecated_prefix + 'like was deprecated in Axiom 0.7.5',
            __file__,
            lambda: D.one.like('string'))


    def test_notLike(self):
        self.assertWarns(
            DeprecationWarning,
            bytes_deprecated_prefix + 'notLike was deprecated in Axiom 0.7.5',
            __file__,
            lambda: D.one.notLike('string'))
