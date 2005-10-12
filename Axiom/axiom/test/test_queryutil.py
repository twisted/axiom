
from axiom.store import Store
from axiom.item import Item
from axiom.attributes import integer

from axiom.queryutil import overlapping

class Segment(Item):
    typeName = 'test_overlap_segment'
    schemaVersion = 1

    x = integer()
    y = integer()

    def __repr__(self):
        return 'Segment<%d,%d>' % (self.x, self.y)

from twisted.trial.unittest import TestCase

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
