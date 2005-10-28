
from twisted.trial.unittest import TestCase

from axiom.item import Item
from axiom.attributes import integer

from axiom.slotmachine import hyper as super

__metaclass__ = type

class X:
    xm = 0
    def m(self):
        self.xm += 1
        return self.xm

class Y(X):
    ym = 0

    def m(self):
        ret = super(Y, self).m()
        self.ym += 1
        ret += 1
        return ret

class Z(X):
    zm = 0
    def m(self):
        ret = super(Z, self).m()
        ret += 1
        self.zm += 1
        return ret

class XYZ(Y, Z):
    pass

class ItemXYZ(Item, XYZ):
    typeName = 'item_xyz'
    schemaVersion = 1

    xm = integer(default=0)
    ym = integer(default=0)
    zm = integer(default=0)


class TestBorrowedMixins(TestCase):

    def testSanity(self):
        xyz = XYZ()
        val = xyz.m()
        self.assertEquals(val, 3)

    def testItemSanity(self):
        xyz = ItemXYZ()
        val = xyz.m()
        self.assertEquals(val, 3)
