
from twisted.trial import unittest
from axiom.slotmachine import SetOnce, Attribute, SlotMachine, SchemaMachine

class A(SlotMachine):
    slots = ['a', 'initialized']

class B(SchemaMachine):
    test = Attribute()
    initialized = SetOnce()
    other = SetOnce(default=None)

class Bsub(B):
    pass

class C(object):
    __slots__ = ['a', 'b',
                 'c', 'initialized']

class D:
    def activate(self):
        self.initialized = 1
        self.test = 2
        self.a = 3
        self.b = 4
        self.c = 5

class E(object):
    pass

class X(B, A, C, D, E):
    pass

class Y(Bsub):
    blah = SetOnce()

class ClassWithDefault:
    x = 1

class DefaultTest(SchemaMachine, ClassWithDefault):
    x = Attribute()


class SlotMachineTest(unittest.TestCase):

    def btest(self, b):
        b.test = 1
        b.test = 2

        self.assertEquals(b.test, 2)
        self.assertRaises(AttributeError, setattr, b, 'nottest', 'anything')
        self.assertRaises(AttributeError, getattr, b, 'nottest')
        self.assertEquals(b.other, None)
        b.other = 7
        self.assertEquals(b.other, 7)
        self.assertRaises(AttributeError, setattr, b, 'other', 'anything')

    def testAttributesNotAllowed(self):
        b = B()
        self.btest(b)

    def testTrivialSubclass(self):
        b = Bsub()
        self.btest(b)

    def testSetOnce(self):
        b = B()
        b.initialized = 1
        self.assertRaises(AttributeError, setattr, b, 'initialized', 2)
        self.assertEquals(b.initialized, 1)


    def testClassicMixin(self):
        x = X()
        x.activate()

        self.assertRaises(AttributeError, setattr, x, 'initialized', 2)
        self.assertRaises(AttributeError, setattr, x, 'nottest', 'anything')
        self.assertRaises(AttributeError, getattr, x, 'nottest')

    def testAttributesTraverseDeepHierarchy(self):
        y = Y()
        self.btest(y)

    def testBaseDefault(self):
        dt = DefaultTest()
        # self.failUnless('x' in dt.__slots__, 'x not in '+repr(dt.__slots__) )
        dt.x = 2




