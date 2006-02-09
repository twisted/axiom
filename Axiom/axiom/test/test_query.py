from twisted.trial.unittest import TestCase

from axiom.store import Store
from axiom.item import Item

from axiom import errors
from axiom.attributes import reference, text, bytes, integer, AND, OR

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

    def testBasicQuery(self):
        s = Store()

        def entesten():
            c1 = C(store=s,
                   name=u'yes')

            c2 = C(store=s,
                   name=u'no')

            A(store=s,
              reftoc=c1,
              type=u'testc')

            A(store=s,
              reftoc=c2,
              type=u'testc')

            A(store=s,
              reftoc=c1,
              type=u'testx')

            yesb = B(store=s,
                     cref=c1,
                     name=u'correct')

            B(store=s,
              cref=c2,
              name=u'not correct')

            s.checkpoint()

            q = list(s.query(B,
                             AND(AND(C.name == u'yes',
                                     A.type == u'testc'),
                                 AND(C.storeID == B.cref,
                                     A.reftoc == C.storeID)),
                             ))

            self.assertEquals(q, [yesb])

        s.transact(entesten)
        s.close()


    def testStringQueries(self):
        s = Store()

        def createAndStuff():
            text1 = u'Hello, \u1234 world.'
            text2 = u'ThIs sTrInG iS nOt cAsE sEnSiTIvE.  \u4567'
            bytes1 = '\x00, punk'

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
            self.failIf(q, q)

            q = list(
                s.query(ThingWithCharacterAndByteStrings,
                        ThingWithCharacterAndByteStrings.characterString == text1.upper(),
                        ))
            self.failIf(q, q)

            q = list(
                s.query(ThingWithCharacterAndByteStrings,
                        ThingWithCharacterAndByteStrings.characterString == text1,
                        ))

            self.assertEquals(q, [x])

            q = list(
                s.query(ThingWithCharacterAndByteStrings,
                        ThingWithCharacterAndByteStrings.caseInsensitiveCharString == text2,
                        ))

            self.assertEquals(q, [x])

            q = list(
                s.query(ThingWithCharacterAndByteStrings,
                        ThingWithCharacterAndByteStrings.caseInsensitiveCharString == text2.lower(),
                        ))

            self.assertEquals(q, [x])

            q = list(
                s.query(ThingWithCharacterAndByteStrings,
                        ThingWithCharacterAndByteStrings.caseInsensitiveCharString == text2.upper(),
                        ))

            self.assertEquals(q, [x])

            q = list(
                s.query(ThingWithCharacterAndByteStrings,
                        ThingWithCharacterAndByteStrings.byteString == bytes1,
                        ))

            self.assertEquals(q, [x])

            q = list(
                s.query(ThingWithCharacterAndByteStrings,
                        ThingWithCharacterAndByteStrings.byteString == bytes1.upper(),
                        ))

            self.failIf(q, q)

        s.transact(createAndStuff)
        s.close()


    def testAggregateQueries(self):
        s = Store()
        def entesten():
            self.assertEquals(s.query(E).count(), 0)
            self.assertEquals(s.query(E).getColumn("amount").sum(), 0)

            e1 = E(store=s, name=u'widgets', amount=37)
            e2 = E(store=s, name=u'widgets', amount=63)
            e3 = E(store=s, name=u'quatloos', amount=99, transaction=u'yes')
            s.checkpoint()
            q = s.count(E, E.name == u'widgets')
            self.failUnlessEqual(q, 2)
            q = s.sum(E.amount, E.name == u'widgets')
            self.failUnlessEqual(q, 100)
        s.transact(entesten)
        s.close()

    def testAttributeQueries(self):
        s = Store()
        def entesten():
            E(store=s, name=u'b', amount=456)
            E(store=s, name=u'a', amount=123)
            E(store=s, name=u'c', amount=789)
            self.assertEquals(list(s.query(E, sort=E.name.ascending).getColumn("amount")),
                              [123, 456, 789])

        s.transact(entesten)
        s.close()

    def testAttributeQueryCount(self):
        s = Store()
        def entesten():
            E(store=s, name=u'a', amount=123)
            E(store=s, name=u'b', amount=456)
            E(store=s, name=u'c')  # no amount given
            self.assertEquals(s.query(E).getColumn("amount").count(), 2)
        s.transact(entesten)
        s.close()

    def testAttributeQueryDistinct(self):
        s = Store()
        def entesten():
            E(store=s, name=u'a', amount=123)
            E(store=s, name=u'b', amount=789)
            E(store=s, name=u'a', amount=456)
            self.assertEquals(list(s.query(E, sort=E.name.ascending).getColumn("name").distinct()),
                              [u"a", u"b"])
        s.transact(entesten)
        s.close()

class QueryingTestCase(TestCase):
    def setUp(self):
        s = self.store = Store()
        def _createStuff():
            self.d1 = D(store=s, one='d1.one', two='d1.two', three='d1.three', four=u'd1.four', id='1')
            self.d2 = D(store=s, one='d2.one', two='d2.two', three='d2.three', four=u'd2.four', id='2')
            self.d3 = D(store=s, one='d3.one', two='d3.two', three='d3.three', four=u'd3.four', id='3')
        s.transact(_createStuff)

    def tearDown(self):
        self.store.close()

    def query(self, *a, **kw):
        return list(self.store.query(*a, **kw))

    def assertQuery(self, query, sql, args=None):
        if args is None:
            args = []
        # XXX: WTF?!? somebody wrote tests here that compare byte-for-byte SQL:
        # since we are now (properly) quoting all attribute names, the SQL is
        # subtly different; and there is no handy SQL AST that we can compare
        # them against.  Really we should be comparing query results anyway; we
        # should probably remove the SQL code entirely from these tests. (but
        # at least the args are right, and it does grant some coverage, so I'm
        # leaving them in for now)

        # self.assertEquals(query.getQuery(), sql)
        self.assertEquals([str(a) for a in query.getArgs(self.store)], args)


class AndOrQueries(QueryingTestCase):
    def testNoConditions(self):
        self.assertRaises(ValueError, AND)
        self.assertRaises(ValueError, OR)

    def testOneCondition(self):
        self.assertQuery(
            AND(A.type == u'Narf!'), '((item_a_v1.type = ?))', ['Narf!'])
        self.assertQuery(
            OR(A.type == u'Narf!'), '((item_a_v1.type = ?))', ['Narf!'])
        self.assertEquals(self.query(D, AND(D.one == 'd1.one')), [self.d1])
        self.assertEquals(self.query(D,  OR(D.one == 'd1.one')), [self.d1])

    def testMultipleAndConditions(self):
        self.assertQuery(
            AND(A.type == u'Narf!',
                A.type == u'Poiuyt!',
                A.type == u'Try to take over the world'),
            '((item_a_v1.type = ?) AND (item_a_v1.type = ?) AND (item_a_v1.type = ?))',
            ['Narf!', 'Poiuyt!', 'Try to take over the world'])
        self.assertEquals(
            self.query(D, AND(D.one == 'd1.one',
                              D.two == 'd1.two',
                              D.three == 'd1.three')),
            [self.d1])

    def testMultipleOrConditions(self):
        self.assertQuery(
            OR(A.type == u'Narf!',
               A.type == u'Poiuyt!',
               A.type == u'Try to take over the world'),
            '((item_a_v1.type = ?) OR (item_a_v1.type = ?) OR (item_a_v1.type = ?))',
            ['Narf!', 'Poiuyt!', 'Try to take over the world'])
        q = self.query(D, OR(D.one == 'd1.one',
                             D.one == 'd2.one',
                             D.one == 'd3.one'))
        e = [self.d1, self.d2, self.d3]
        self.assertEquals(sorted(q), sorted(e))


class SetMembershipQuery(QueryingTestCase):

    def testOneOfWithList(self):
        s = Store()

        cx = C(store=s, name=u'x')
        cy = C(store=s, name=u'y')
        cz = C(store=s, name=u'z')

        self.assertEquals(list(s.query(C, C.name.oneOf([u'x', u'z', u'a']), sort=C.name.ascending)),
                          [cx, cz])

    def testOneOfWithSet(self):
        s = Store()

        cx = C(store=s, name=u'x')
        cy = C(store=s, name=u'y')
        cz = C(store=s, name=u'z')

        self.assertEquals(list(s.query(C, C.name.oneOf(set([u'x', u'z', u'a'])), sort=C.name.ascending)),
                          [cx, cz])


class WildcardQueries(QueryingTestCase):
    def testNoConditions(self):
        self.assertRaises(ValueError, D.one.like)
        self.assertRaises(ValueError, D.one.not_like)

    def testOneString(self):
        self.assertQuery(
            D.one.like('foobar%'),
            '(item_d_v1.one LIKE (?))', ['foobar%'])
        self.assertQuery(
            D.one.not_like('foobar%'),
            '(item_d_v1.one NOT LIKE (?))', ['foobar%'])
        self.assertEquals(self.query(D, D.one.like('d1.one')), [self.d1])
        self.assertEquals(self.query(D, D.one.not_like('d%.one')), [])

    def testOneColumn(self):
        self.assertQuery(
            D.one.like(D.two),
            '(item_d_v1.one LIKE (item_d_v1.two))')
        self.assertEquals(self.query(D, D.one.like(D.two)), [])
        
    def testOneColumnAndStrings(self):
        self.assertQuery(
            D.one.like('%', D.id, '%one'),
            '(item_d_v1.one LIKE (? || item_d_v1.id || ?))',
            ['%', '%one'])
        q = self.query(D, D.one.like('%', D.id, '%one'))
        e = [self.d1, self.d2, self.d3]
        self.assertEquals(sorted(q), sorted(e))

    def testMultipleColumns(self):
        self.assertQuery(
            D.one.like(D.two, '%', D.three),
            '(item_d_v1.one LIKE (item_d_v1.two || ? || item_d_v1.three))',
            ['%'])
        self.assertEquals(
            self.query(D, D.one.like(D.two, '%', D.three)), [])

    def testStartsEndsWith(self):
        self.assertQuery(
            D.one.startswith('foo'),
            '(item_d_v1.one LIKE (? || ?))', ['foo', '%'])
        self.assertQuery(
            D.one.endswith('foo'),
            '(item_d_v1.one LIKE (? || ?))', ['%', 'foo'])
        self.assertEquals(
            self.query(D, D.one.startswith('d1')), [self.d1])
        self.assertEquals(
            self.query(D, D.one.endswith('3.one')), [self.d3])

    def testStartsEndsWithColumn(self):
        self.assertQuery(
            D.one.startswith(D.two),
            '(item_d_v1.one LIKE (item_d_v1.two || ?))', ['%'])
        self.assertEquals(
            self.query(D, D.one.startswith(D.two)), [])

    def testStartsEndsWithText(self):
        self.assertEquals(
            self.query(D, D.four.startswith(u'd1')),
            [self.d1])
        self.assertEquals(
            self.query(D, D.four.endswith(u'2.four')),
            [self.d2])
    testStartsEndsWithText.todo = 'This is issue #402'

    def testOtherTable(self):
        self.assertQuery(
            D.one.startswith(A.type),
            '(item_d_v1.one LIKE (item_a_v1.type || ?))', ['%'])

        C(store=self.store, name=u'd1.')
        C(store=self.store, name=u'2.one')
        self.assertEquals(
            self.query(D, D.one.startswith(C.name)), [self.d1])
        self.assertEquals(
            self.query(D, D.one.endswith(C.name)), [self.d2])


class UniqueTest(TestCase):

    def setUp(self):
        s = self.s = Store()
        self.c = C(store=s, name=u'unique')
        self.dupc1 = C(store=s, name=u'non-unique')
        self.dupc2 = C(store=s, name=u'non-unique')

    def testUniqueFound(self):
        self.assertEquals(self.s.findUnique(C, C.name == u'unique'), self.c)

    def testUniqueNotFoundError(self):
        self.assertRaises(errors.ItemNotFound, self.s.findUnique,
                          C, C.name == u'non-existent')

    def testUniqueNotFoundDefault(self):
        bing = object()
        self.assertEquals(bing, self.s.findUnique(
                C, C.name == u'non-existent',
                default=bing))

    def testUniqueDuplicate(self):
        self.assertRaises(errors.DuplicateUniqueItem,
                          self.s.findUnique, C, C.name == u'non-unique')

