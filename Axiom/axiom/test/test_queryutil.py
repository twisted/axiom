
import random

from twisted.trial.unittest import TestCase

from axiom.store import Store
from axiom.item import Item
from axiom.attributes import integer

from axiom.queryutil import overlapping, AttributeTuple

class Segment(Item):
    typeName = 'test_overlap_segment'
    schemaVersion = 1

    x = integer()
    y = integer()

    def __repr__(self):
        return 'Segment<%d,%d>' % (self.x, self.y)

class ABC(Item):
    typeName = 'test_tuple_queries'
    schemaVersion = 1

    a = integer(allowNone=False)
    b = integer(allowNone=False)
    c = integer(allowNone=False)

class TestQueryUtilities(TestCase):

    def testBetweenQuery(self):
        # From a drawn copy of the docstring:

        s = Store()

        G = 3
        K = 4
        H = C = 5
        A = 8
        D = 11
        E = 17
        B = 20
        F = I = 22
        L = 23
        J = 24

        AB = Segment(store=s, x=A, y=B)
        CD = Segment(store=s, x=C, y=D)
        EF = Segment(store=s, x=E, y=F)
        GH = Segment(store=s, x=G, y=H)
        IJ = Segment(store=s, x=I, y=J)
        KL = Segment(store=s, x=K, y=L)

        AL = Segment(store=s, x=A, y=L)
        CB = Segment(store=s, x=C, y=B)

        CA = Segment(store=s, x=C, y=A)
        BL = Segment(store=s, x=B, y=L)

        self.assertEquals(
            list(s.query(Segment,
                         overlapping(Segment.x,
                                     Segment.y,
                                     A, B),
                         sort=Segment.storeID.asc)),
            [AB, CD, EF, KL, AL, CB, CA, BL],
            )

    ('(((A > 2)) '
     'OR ((A == 2) AND (B > 3)) '
     'OR ((A == 2) AND (B == 3) AND (C >= 4)))')

    def testTupleQueryWithTuples(self):
        s = Store()
        s.transact(self._dotestTupleQueryWithTuples, s)

    def _dotestTupleQueryWithTuples(self, s):
        L = []
        for x in range(3):
            for y in range(3):
                for z in range(3):
                    L.append((x, y, z))
        shuffledL = L[:]
        random.shuffle(shuffledL)
        for a, b, c in shuffledL:
            ABC(a=a,
                b=b,
                c=c,
                store=s)

        at = AttributeTuple(ABC.a, ABC.b, ABC.c)
        for comparee in L:
            qobj = s.query(ABC, at > comparee,
                           sort=[ABC.a.ascending,
                                 ABC.b.ascending,
                                 ABC.c.ascending])
            self.assertEquals(
                L[L.index(comparee) + 1:],
                [(o.a, o.b, o.c) for o in qobj])

        for comparee in L:
            qobj = s.query(ABC, at >= comparee,
                           sort=[ABC.a.ascending,
                                 ABC.b.ascending,
                                 ABC.c.ascending])
            self.assertEquals(
                L[L.index(comparee):],
                [(o.a, o.b, o.c) for o in qobj])

        for comparee in L:
            qobj = s.query(ABC, at == comparee,
                           sort=[ABC.a.ascending,
                                 ABC.b.ascending,
                                 ABC.c.ascending])
            self.assertEquals(
                [comparee],
                [(o.a, o.b, o.c) for o in qobj])

        for comparee in L:
            qobj = s.query(ABC, at != comparee,
                           sort=[ABC.a.ascending,
                                 ABC.b.ascending,
                                 ABC.c.ascending])
            self.assertEquals(
                L[:L.index(comparee)] + L[L.index(comparee) + 1:],
                [(o.a, o.b, o.c) for o in qobj])

        for comparee in L:
            qobj = s.query(ABC, at < comparee,
                           sort=[ABC.a.ascending,
                                 ABC.b.ascending,
                                 ABC.c.ascending])
            self.assertEquals(
                L[:L.index(comparee)],
                [(o.a, o.b, o.c) for o in qobj])

        for comparee in L:
            qobj = s.query(ABC, at <= comparee,
                           sort=[ABC.a.ascending,
                                 ABC.b.ascending,
                                 ABC.c.ascending])
            self.assertEquals(
                L[:L.index(comparee) + 1],
                [(o.a, o.b, o.c) for o in qobj])

