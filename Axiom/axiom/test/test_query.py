
from twisted.trial.unittest import TestCase

from axiom.store import Store
from axiom.item import Item
from axiom.attributes import reference, text, bytes, AND, OR

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



class AndOrQueries(TestCase):
    def testBooleanCondition(self):
        from axiom.attributes import _BooleanCondition
        self.assertRaises(NotImplementedError, _BooleanCondition)

    def testNoConditions(self):
        self.assertRaises(ValueError, AND)
        self.assertRaises(ValueError, OR)

    def testOneCondition(self):
        query1 = AND(A.type == u'Narf!').getQuery()
        query2 =  OR(A.type == u'Narf!').getQuery()
        expected = '((item_a_v1.type = ?))'
        self.assertEquals(query1, expected)
        self.assertEquals(query2, expected)

    def testMultipleAndConditions(self):
        condition = AND(
            A.type == u'Narf!',
            A.type == u'Poiuyt!',
            A.type == u'Try to take over the world')
        self.assertEquals(
            condition.getQuery(),
            '((item_a_v1.type = ?) AND (item_a_v1.type = ?) AND (item_a_v1.type = ?))')

    def testMultipleOrConditions(self):
        condition = OR(
            A.type == u'Narf!',
            A.type == u'Poiuyt!',
            A.type == u'Try to take over the world')
        self.assertEquals(
            condition.getQuery(),
            '((item_a_v1.type = ?) OR (item_a_v1.type = ?) OR (item_a_v1.type = ?))')
