
from twisted.trial import unittest
from axiom.attributes import integer
from axiom.item import Item
from axiom.sequence import List
from axiom.store import Store


class SomeItem(Item):
    schemaVersion = 1
    typeName = 'test_sequence_some_item'
    foo = integer()
    bar = integer()


class TestSequenceOfItems(unittest.TestCase):

    def setUp(self):
        self.store = Store()
        self.i1 = SomeItem(store=self.store, foo=1, bar=1)
        self.i2 = SomeItem(store=self.store, foo=2, bar=2)
        self.i3 = SomeItem(store=self.store, foo=3, bar=3)

    def test_appendAndGetItem(self):
        seq = List(store=self.store)
        seq.append(self.i1)
        self.assertEquals(seq.length, 1)
        self.assertEquals(seq[0], self.i1)
        seq.append(self.i2)
        seq.append(self.i3)
        self.assertEquals(seq[1], self.i2)
        self.assertEquals(seq[2], self.i3)

    def test_indexErrors(self):
        seq = List(store=self.store)
        self.assertRaises(IndexError, seq.__getitem__, 0)
        seq.append(self.i1)
        self.assertEquals(seq[0], self.i1)
        self.assertRaises(IndexError, seq.__getitem__, 1)

    def test_negativeIndices(self):
        seq = List(store=self.store)
        seq.append(self.i1)
        seq.append(self.i2)
        seq.append(self.i3)
        self.assertEquals(seq[-1], self.i3)
        self.assertEquals(seq[-2], self.i2)
        self.assertEquals(seq[-3], self.i1)
        self.assertRaises(IndexError, seq.__getitem__, -4)

    def test_setItem(self):
        seq = List(store=self.store)
        seq.append(self.i1)
        seq.append(self.i2)
        self.assertEquals(seq.length, 2)
        self.assertEquals(seq[0], self.i1)
        self.assertEquals(seq[1], self.i2)
        seq[1] = self.i3
        self.assertEquals(seq[1], self.i3)
    
    def test_delItem(self):
        seq = List(store=self.store)
        seq.append(self.i1)
        seq.append(self.i2)
        seq.append(self.i3)
        self.assertEquals(seq.length, 3)
        self.assertEquals(seq[0], self.i1)
        self.assertEquals(seq[1], self.i2)
        self.assertEquals(seq[2], self.i3)
        del seq[1]
        self.assertEquals(seq.length, 2)
        self.assertEquals(seq[0], self.i1)
        self.assertEquals(seq[1], self.i3)
        self.assertRaises(IndexError, seq.__getitem__, 2)

    def test_count(self):
        seq = List(store=self.store)
        seq.append(self.i1)
        seq.append(self.i2)
        seq.append(self.i2)
        seq.append(self.i3)
        seq.append(self.i3)
        seq.append(self.i3)
        self.assertEquals(seq.count(self.i1), 1)
        self.assertEquals(seq.count(self.i2), 2)
        self.assertEquals(seq.count(self.i3), 3)
    
    def test_contains(self):
        seq = List(store=self.store)
        seq.append(self.i1)
        seq.append(self.i2)
        self.failUnless(self.i1 in seq)
        self.failUnless(self.i2 in seq)
        self.failIf(self.i3 in seq)
