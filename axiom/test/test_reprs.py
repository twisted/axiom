
"""
This module contains tests for C{__repr__} implementations within Axiom, to
make sure they contain enough information to be useful, and work when objects
are incompletely initialized.
"""

from axiom.iaxiom import IOrdering
from axiom.attributes import integer, text, reference
from axiom.item import Item
from axiom.store import Store

from twisted.trial.unittest import TestCase

class ReprTesterItemClass(Item):
    intattr = integer()
    txtattr = text()

class ReprTesterWithReference(Item):
    """
    Test fixture for testing 'reference' attributes.
    """
    refattr = reference()


class BasicInformation(TestCase):
    """
    Basic tests to verify that C{__repr__} implementations for various axiom
    objects provide enough information to debug them.
    """

    def test_storeID(self):
        """
        Verify that the storeID column tells you that it is a storeID, and who
        it belongs to.
        """
        R = repr(ReprTesterItemClass.storeID)
        self.assertIn('storeID', R)
        self.assertIn(ReprTesterItemClass.__name__, R)
        self.assertNotIn('intattr', R)


    def test_query(self):
        """
        Verify that queries tell you something about their target and
        comparison.
        """
        s = Store()
        R = repr(s.query(ReprTesterItemClass,
                         ReprTesterItemClass.intattr == 1))
        self.assertIn('intattr', R)
        self.assertIn(ReprTesterItemClass.__name__, R)


    def test_simpleOrdering(self):
        """
        Verify that ordering objects tell you something about their ordering.
        """
        R = repr(ReprTesterItemClass.intattr.ascending)
        self.assertIn("intattr", R)
        self.assertIn("asc", R.lower()) # leaving this a little open-ended so
                                        # that we can fiddle with case, ASC and
                                        # DESC vs. ascending and descending

    def test_complexOrdering(self):
        """
        Verify that complex orderings tell us about their component parts.
        """
        R = repr(IOrdering((ReprTesterItemClass.intattr.ascending,
                            ReprTesterItemClass.txtattr.descending)))
        self.assertIn(repr(ReprTesterItemClass.intattr.ascending), R)
        self.assertIn(repr(ReprTesterItemClass.txtattr.descending), R)


    def test_referenceAttribute(self):
        """
        Verify that repr()ing an object with reference attributes will show the ID.
        """
        s = Store()
        i1 = ReprTesterWithReference(store=s)
        i2 = ReprTesterWithReference(store=s)
        i1.refattr = i2
        R = repr(i1)
        self.assertIn("reference(%d)" % (i2.storeID,), R)


    def test_recursiveReferenceAttribute(self):
        """
        Verify that repr()ing an object with reference attributes that refer to
        themselves will not recurse.
        """
        s = Store()
        i1 = ReprTesterWithReference(store=s)
        i1.refattr = i1
        R = repr(i1)
        self.assertIn("reference(%d)" % (i1.storeID,), R)


    def test_unstoredReferenceAttribute(self):
        """
        Verify that repr()ing an object with reference attributes that refer to
        items not in a store does something reasonable.
        """
        i1 = ReprTesterWithReference()
        i2 = ReprTesterWithReference()
        i1.refattr = i2
        R = repr(i1)
        self.assertIn("reference(unstored@%d)" % (id(i2),), R)


