
from twisted.trial import unittest
from axiom.attributes import integer
from axiom.errors import NoCrossStoreReferences
from axiom.item import Item
from axiom.sequence import List
from axiom.store import Store


class SomeItem(Item):
    schemaVersion = 1
    typeName = 'test_sequence_some_item'
    foo = integer()

    def __repr__(self):
        return '<SomeItem foo=%i at 0x%x>' % (self.foo, id(self))

    def __cmp__(self, other):
        if not isinstance(other, self.__class__):
            return cmp(super(SomeItem, self), other)
        return cmp(self.foo, other.foo)

class SequenceTestCase(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.xy = SomeItem(store=self.store, foo=-1)
        for i in range(10):
            item = SomeItem(store=self.store, foo=i)
            setattr(self, 'i%i'%i, item)

    def assertContents(self, seq, L):
        self.assertEquals(len(seq), len(L))
        for i in range(len(L)):
            self.assertIdentical(seq[i], L[i])

class TestSequenceOfItems(SequenceTestCase):
    def test_createItem(self):
        seq = List(store=self.store)
        self.assertEquals(len(seq), 0)

    def test_createItemWithDefaults(self):
        seq = List([self.i0, self.i1], store=self.store)
        self.assertContents(seq, [self.i0, self.i1])

    def test_createItemWithAliens(self):
        otherStore = Store()
        alien1 = SomeItem(store=otherStore, foo=1)
        alien2 = SomeItem(store=otherStore, foo=2)
        alien3 = SomeItem(store=otherStore, foo=3)
        self.assertRaises(NoCrossStoreReferences,
                          List,
                          [alien1, alien2, alien3],
                          store=self.store)

    def test_appendAndGetItem(self):
        seq = List(store=self.store)
        seq.append(self.i0)
        self.assertEquals(len(seq), 1)
        self.assertEquals(seq[0], self.i0)
        seq.append(self.i1)
        seq.append(self.i2)
        self.assertEquals(seq[1], self.i1)
        self.assertEquals(seq[2], self.i2)

    def test_appendSliceSyntax(self):
        seq = List(store=self.store)
        self.assertContents(seq, [])
        seq[len(seq):len(seq)] = [self.i0]
        seq[len(seq):len(seq)] = [self.i1]
        seq[len(seq):len(seq)] = [self.i2]
        self.assertContents(seq, [self.i0,
                                  self.i1,
                                  self.i2])
    test_appendSliceSyntax.todo = "Slices are not supported yet"

    def test_indexErrors(self):
        seq = List(store=self.store)
        self.assertRaises(IndexError, seq.__getitem__, 0)
        seq.append(self.i0)
        self.assertEquals(seq[0], self.i0)
        self.assertRaises(IndexError, seq.__getitem__, 1)

    def test_negativeIndices(self):
        seq = List(store=self.store)
        seq.append(self.i0)
        seq.append(self.i1)
        seq.append(self.i2)
        self.assertEquals(seq[-1], self.i2)
        self.assertEquals(seq[-2], self.i1)
        self.assertEquals(seq[-3], self.i0)
        self.assertRaises(IndexError, seq.__getitem__, -4)

    def test_setItem(self):
        seq = List(store=self.store)
        seq.append(self.i0)
        seq.append(self.i1)
        self.assertEquals(len(seq), 2)
        self.assertEquals(seq[0], self.i0)
        self.assertEquals(seq[1], self.i1)
        seq[1] = self.i2
        self.assertEquals(seq[1], self.i2)

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


class TestSequenceOperations(SequenceTestCase):
    """
    These test cases were taken from the list of sequence operations
    found at http://docs.python.org/lib/typesseq.html
    """

    def test_x_in_s(self):
        seq = List(store=self.store)
        seq.append(self.i0)
        self.failUnless(self.i0 in seq)
        self.failIf(self.xy in seq)

    def test_x_not_in_s(self):
        seq = List(store=self.store)
        seq.append(self.i0)
        self.failUnless(self.xy not in seq)
        self.failIf(self.i0 not in seq)

    def test_s_plus_t(self):
        L1 = List(store=self.store)
        L2 = List(store=self.store)
        L1.append(self.i0)
        L2.append(self.i1)
        # XXX ASSUMPTION: all operations which return another
        # instance will return regular lists, *not* Lists.
        L = L1 + L2
        self.assertEquals(L, [self.i0, self.i1])

    def test_shallow_copies(self, n=3):
        seq = List(store=self.store)
        seq.append(self.i0)
        for L in (seq * n, n * seq):
            self.assertEquals(L, [self.i0]*n)

    def test_index(self):
        seq = List(store=self.store)
        seq.append(self.i0)
        seq.append(self.i1)
        self.assertIdentical(seq[0], self.i0)
        self.assertIdentical(seq[1], self.i1)
        self.failIfIdentical(seq[0], self.i1)
        self.failIfIdentical(seq[1], self.i0)

    def test_slices(self):
        seq = List(store=self.store)
        seq.append(self.i0)
        seq.append(self.i1)
        seq.append(self.i2)
        seq.append(self.i3)
        self.assertEquals(seq[0:2], [self.i0, self.i1])
        self.assertEquals(seq[0:3], [self.i0, self.i1, self.i2])
        self.assertEquals(seq[1:0], [])
        self.assertEquals(seq[-1:], [self.i3])
    test_slices.todo = "Slices are not supported yet"

    def test_slice_with_step(self):
        seq = List(store=self.store)
        seq.append(self.i0)
        seq.append(self.i1)
        seq.append(self.i2)
        seq.append(self.i3)
        self.assertEquals(seq[0:4:2], [self.i0, self.i2])
        self.assertEquals(seq[1:5:2], [self.i1, self.i3])
    test_slice_with_step.todo = "Slices are not supported yet"

    def test_len(self):
        seq = List(store=self.store)
        self.assertEquals(len(seq), 0)
        seq.append(self.i0)
        self.assertEquals(len(seq), 1)
        seq.append(self.i0)
        self.assertEquals(len(seq), 2)
        seq.append(self.i0)
        self.assertEquals(len(seq), 3)

    def test_min_max(self):
        seq = List(store=self.store)
        seq.append(self.i0)
        seq.append(self.i1)
        seq.append(self.i2)
        self.assertIdentical(min(seq), self.i0)
        self.assertIdentical(max(seq), self.i2)


class TestMutableSequenceOperations(SequenceTestCase):
    """
    These test cases were taken from the list of sequence operations
    found at http://docs.python.org/lib/typesseq-mutable.html

    Some may duplicate L{TestSequenceOperations}, but who cares?
    """

    def test_indexAssignment(self):
        seq = List(store=self.store)
        seq.append(self.i0)
        self.assertIdentical(seq[0], self.i0)
        seq[0] = self.i1
        self.assertIdentical(seq[0], self.i1)

    def test_sliceAssignment(self):
        seq = List(store=self.store)
        seq.append(self.i0)
        seq.append(self.i0)
        seq.append(self.i0)
        seq.append(self.i0)
        self.assertContents(seq, [self.i0,
                                  self.i0,
                                  self.i0,
                                  self.i0])
        seq[1:3] = [self.i1, self.i2]
        self.assertContents(seq, [self.i0,
                                  self.i1,
                                  self.i2,
                                  self.i0])
        seq[1:3] = [self.i3]
        self.assertContents(seq, [self.i0,
                                  self.i3,
                                  self.i0])
        seq[1:3] = []
        self.assertContents(seq, [self.i0])
    test_sliceAssignment.todo = "Slices are not supported yet"

    def test_deleteSlice(self):
        seq = List(store=self.store)
        seq.append(self.i0)
        seq.append(self.i1)
        seq.append(self.i2)
        seq.append(self.i3)
        del seq[1:3]
        self.assertEquals(len(seq), 2)
        self.assertIdentical(seq[0], self.i0)
        self.assertIdentical(seq[1], self.i3)
    test_deleteSlice.todo = "Slices are not supported yet"

    def test_sliceAssignmentStep(self):
        seq = List(store=self.store)
        seq.append(self.i0)
        seq.append(self.i1)
        seq.append(self.i2)
        seq.append(self.i3)
        seq.append(self.i4)
        seq.append(self.i5)
        seq.append(self.i6)
        seq[1:5:2] = [self.i7, self.i7]
        self.assertContents(seq, [self.i0,
                                  self.i7,
                                  self.i2,
                                  self.i7,
                                  self.i4,
                                  self.i5,
                                  self.i6])
    test_sliceAssignmentStep.todo = "Slices are not supported yet"

    def test_deleteSliceStep(self):
        seq = List(store=self.store)
        seq.append(self.i0)
        seq.append(self.i1)
        seq.append(self.i2)
        seq.append(self.i3)
        seq.append(self.i4)
        seq.append(self.i5)
        seq.append(self.i6)
        del seq[1:6:2]
        self.assertContents(seq, [self.i0,
                                  self.i2,
                                  self.i4,
                                  self.i6])
    test_deleteSliceStep.todo = "Slices are not supported yet"

    def test_append(self):
        seq = List(store=self.store)
        self.assertContents(seq, [])
        seq.append(self.i0)
        self.assertContents(seq, [self.i0])
        seq.append(self.i1)
        self.assertContents(seq, [self.i0,
                                  self.i1])

    def test_extend(self):
        L1 = List(store=self.store)
        L1.append(self.i0)
        L1.append(self.i1)
        L2 = List(store=self.store)
        L2.append(self.i2)
        L2.append(self.i3)
        L1.extend(L2)
        self.assertContents(L1, [self.i0,
                                 self.i1,
                                 self.i2,
                                 self.i3])

    def test_extendSliceSyntax(self):
        L1 = List(store=self.store)
        L1.append(self.i0)
        L1.append(self.i1)
        L2 = List(store=self.store)
        L2.append(self.i2)
        L2.append(self.i3)
        L1[len(L1):len(L1)] = L2
        self.assertContents(L1, [self.i0,
                                 self.i1,
                                 self.i2,
                                 self.i3])
    test_extendSliceSyntax.todo = "Slices are not supported yet"

    def test_count(self):
        seq = List(store=self.store)
        seq.append(self.i0)
        seq.append(self.i1)
        seq.append(self.i0)
        seq.append(self.i2)
        seq.append(self.i0)
        seq.append(self.i2)
        self.assertEquals(seq.count(self.i0), 3)
        self.assertEquals(seq.count(self.i1), 1)
        self.assertEquals(seq.count(self.i2), 2)
        self.assertEquals(seq.count(self.i3), 0)

    def test_index(self):
        seq = List(store=self.store)
        seq.append(self.i0)
        seq.append(self.i1)
        seq.append(self.i0)
        seq.append(self.i2)
        seq.append(self.i0)
        seq.append(self.i2)
        self.assertEquals(seq.index(self.i0),    0)
        self.assertEquals(seq.index(self.i0, 0), 0)
        self.assertEquals(seq.index(self.i0, 1), 2)
        self.assertEquals(seq.index(self.i1),    1)
        self.assertEquals(seq.index(self.i1, 1), 1)
        self.assertEquals(seq.index(self.i2),    3)
        self.assertEquals(seq.index(self.i2, 4), 5)
        self.assertRaises(ValueError, seq.index, self.i3)
        self.assertRaises(ValueError, seq.index, self.i1, 3)
        self.assertRaises(ValueError, seq.index, self.i0, 1, 1)
        # TODO: support negative slice boundaries

    def test_insert(self):
        seq = List(store=self.store)
        seq.append(self.i0)
        seq.append(self.i0)
        seq.insert(1, self.i9)
        self.assertContents(seq, [self.i0,
                                  self.i9,
                                  self.i0])

    def test_insertSliceSyntax(self):
        seq = List(store=self.store)
        seq.append(self.i0)
        seq.append(self.i0)
        seq[1:1] = self.i9
        self.assertContents(seq, [self.i0,
                                  self.i9,
                                  self.i0])
    test_insertSliceSyntax.todo = "Slices are not supported yet"

    def test_pop(self):
        seq = List(store=self.store)
        seq.append(self.i0)
        seq.append(self.i1)
        seq.append(self.i2)
        seq.append(self.i3)
        seq.append(self.i4)

        self.assertIdentical(seq.pop(), self.i4)
        self.assertContents(seq, [self.i0,
                                  self.i1,
                                  self.i2,
                                  self.i3])

        self.assertIdentical(seq.pop(0), self.i0)
        self.assertContents(seq, [self.i1,
                                  self.i2,
                                  self.i3])

        self.assertIdentical(seq.pop(-2), self.i2)
        self.assertContents(seq, [self.i1,
                                  self.i3])

        self.assertRaises(IndexError, seq.pop, 13)

    def test_remove(self):
        seq = List(store=self.store)
        seq.append(self.i0)
        seq.append(self.i1)
        seq.append(self.i2)
        seq.append(self.i0)
        seq.append(self.i1)
        seq.append(self.i3)
        seq.append(self.i0)
        self.assertContents(seq, [self.i0,
                                  self.i1,
                                  self.i2,
                                  self.i0,
                                  self.i1,
                                  self.i3,
                                  self.i0])
        seq.remove(self.i0)
        self.assertContents(seq, [self.i1,
                                  self.i2,
                                  self.i0,
                                  self.i1,
                                  self.i3,
                                  self.i0])
        seq.remove(self.i0)
        self.assertContents(seq, [self.i1,
                                  self.i2,
                                  self.i1,
                                  self.i3,
                                  self.i0])
        seq.remove(self.i2)
        self.assertContents(seq, [self.i1,
                                  self.i1,
                                  self.i3,
                                  self.i0])

        self.assertRaises(ValueError, seq.remove, self.i4)

    def test_reverse(self):
        # UPDATE my_list_tbl SET _index = (_index - listlength + 1) * -1
        seq = List(store=self.store)
        seq.append(self.i0)
        seq.append(self.i1)
        seq.append(self.i2)
        seq.append(self.i3)
        self.assertContents(seq, [self.i0,
                                  self.i1,
                                  self.i2,
                                  self.i3])
        seq.reverse()
        self.assertContents(seq, [self.i3,
                                  self.i2,
                                  self.i1,
                                  self.i0])

    '''
    s.sort([cmp[, key[, reverse]]])

    From http://docs.python.org/lib/typesseq-mutable.html

    The sort() method takes optional arguments for controlling the comparisons.

    cmp specifies a custom comparison function of two arguments (list
    items) which should return a negative, zero or positive number
    depending on whether the first argument is considered smaller
    than, equal to, or larger than the second argument:
    "cmp=lambda x,y: cmp(x.lower(), y.lower())"

    key specifies a function of one argument that is used to extract a
    comparison key from each list element:"key=str.lower"

    reverse is a boolean value. If set to True, then the list elements
    are sorted as if each comparison were reversed.

    In general, the key and reverse conversion processes are much
    faster than specifying an equivalent cmp function. This is because
    cmp is called multiple times for each list element while key and
    reverse touch each element only once.

    Changed in version 2.3: Support for None as an equivalent to
    omitting cmp was added.

    Changed in version 2.4: Support for key and reverse was added.
    '''
    def test_sort(self):
        seq = List(store=self.store)
        def seq_randomize():
            while len(seq):
                seq.pop()
            seq.append(self.i3)
            seq.append(self.i0)
            seq.append(self.i1)
            seq.append(self.i4)
            seq.append(self.i2)

        seq_randomize()
        seq.sort()
        self.assertContents(seq, [self.i0,
                                  self.i1,
                                  self.i2,
                                  self.i3,
                                  self.i4])

        seq_randomize()
        seq.sort(lambda x,y: cmp(y,x))
        self.assertContents(seq, [self.i4,
                                  self.i3,
                                  self.i2,
                                  self.i1,
                                  self.i0])

        def strangecmp(x, y):
            xfoo, yfoo = x.foo, y.foo
            if xfoo < 3:
                xfoo += 100
            if yfoo < 3:
                yfoo += 100
            return cmp(xfoo, yfoo)
        seq_randomize()
        seq.sort(strangecmp)
        self.assertContents(seq, [self.i3,
                                  self.i4,
                                  self.i0,
                                  self.i1,
                                  self.i2])

        seq_randomize()
        seq.sort(None, lambda x:x, True)
        self.assertContents(seq, [self.i4,
                                  self.i3,
                                  self.i2,
                                  self.i1,
                                  self.i0])
        seq_randomize()
        seq.sort(strangecmp, lambda x:x, True)
        self.assertContents(seq, [self.i2,
                                  self.i1,
                                  self.i0,
                                  self.i4,
                                  self.i3])

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

    def test_multicontains(self):
        seq1 = List(store=self.store)
        seq2 = List(store=self.store)
        seq1.append(self.i1)
        seq2.append(self.i2)
        self.failUnless(self.i1 in seq1)
        self.failUnless(self.i2 in seq2)
        self.failIf(self.i1 in seq2)
        self.failIf(self.i2 in seq1)

    def test_multidelitem(self):
        seq1 = List(store=self.store)
        seq2 = List(store=self.store)
        seq1.append(self.i1)
        seq1.append(self.i2)
        seq2.append(self.i1)
        seq2.append(self.i2)
        del seq1[0]
        self.assertIdentical(seq2[0], self.i1)
        self.assertIdentical(seq2[1], self.i2)
