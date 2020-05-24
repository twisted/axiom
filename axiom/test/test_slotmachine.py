
from twisted.trial import unittest
from axiom.slotmachine import SetOnce, Attribute, SlotMachine, SchemaMachine

class A(SlotMachine):
    slots = ['a', 'initialized']

class B(SchemaMachine):
    test = Attribute()
    initialized = SetOnce()
    other = SetOnce(default=None)
    nondescriptor = 'readable'
    method = lambda self: self

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

class Decoy(ClassWithDefault):
    pass

class DecoyDefault(Decoy, DefaultTest):
    pass

class DefaultOverride(DefaultTest):
    x = 5

class SlotMachineTest(unittest.TestCase):

    def assertBSchema(self, b):
        """
        Test that the given instance conforms to L{B}'s schema.
        """
        b.test = 1
        b.test = 2

        self.assertEqual(b.test, 2)
        self.assertRaises(AttributeError, setattr, b, 'nottest', 'anything')
        self.assertRaises(AttributeError, getattr, b, 'nottest')
        self.assertEqual(b.other, None)
        b.other = 7
        self.assertEqual(b.other, 7)
        self.assertRaises(AttributeError, setattr, b, 'other', 'anything')

        self.assertEqual(b.nondescriptor, 'readable')
        err = self.assertRaises(AttributeError,
                                setattr, b, 'nondescriptor', 'writable')
        self.assertEqual(str(err),
                          "%r can't set attribute 'nondescriptor'"
                          % (type(b).__name__,))
        self.assertEqual(b.nondescriptor, 'readable')

        self.assertEqual(b.method(), b)
        err = self.assertRaises(AttributeError,
                                setattr, b, 'method', lambda: 5)
        self.assertEqual(str(err),
                          "%r can't set attribute 'method'"
                          % (type(b).__name__,))
        self.assertEqual(b.method(), b)

    def testAttributesNotAllowed(self):
        b = B()
        self.assertBSchema(b)

    def testTrivialSubclass(self):
        b = Bsub()
        self.assertBSchema(b)

    def testSetOnce(self):
        b = B()
        b.initialized = 1
        self.assertRaises(AttributeError, setattr, b, 'initialized', 2)
        self.assertEqual(b.initialized, 1)


    def testClassicMixin(self):
        x = X()
        x.activate()

        self.assertRaises(AttributeError, setattr, x, 'initialized', 2)
        self.assertRaises(AttributeError, setattr, x, 'nottest', 'anything')
        self.assertRaises(AttributeError, getattr, x, 'nottest')


    def testAttributesTraverseDeepHierarchy(self):
        y = Y()
        self.assertBSchema(y)


    def test_baseDefault(self):
        """
        L{DefaultTest.x} should take precedence over L{ClassWithDefault.x}.
        """
        dt = DefaultTest()
        # self.failUnless('x' in dt.__slots__, 'x not in '+repr(dt.__slots__) )
        dt.x = 2


    def test_decoyDefault(self):
        """
        Same as L{test_baseDefault}, but with a decoy subclass.
        """
        d = DecoyDefault()
        d.x = 2


    def test_descriptorOverride(self):
        """
        L{DefaultOverride.x} should take precedence over L{DefaultTest.x}
        and prevent the I{x} attribute from being set.
        """
        d = DefaultOverride()
        err = self.assertRaises(AttributeError, setattr, d, 'x', 23)
        self.assertEqual(str(err), "'DefaultOverride' can't set attribute 'x'")
        self.assertEqual(d.x, 5)
