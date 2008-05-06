"""
Tests for table-creation.
"""
from axiom import item
from axiom import attributes
from axiom import store

from twisted.trial.unittest import TestCase
from twisted.python import filepath

class A(item.Item):
    typeName = 'test_table_creator'
    schemaVersion = 1

    attr = attributes.integer(default=3)


class SomeError(Exception):
    """
    Dummy error for testing.
    """



def createAndRaise(s):
    """
    Create an A item, then raise a L{SomeError} (which will revert the
    transaction).  This is because there is no direct API for creating tables.
    """
    A(store=s)
    raise SomeError()


class TableCreationTest(TestCase):
    """
    Tests for table creation.
    """
    def test_committedTableCreation(self):
        """
        When tables are created in a transaction which is committed, they should
        persist in both Axiom's in-memory schema representation and within the
        on-disk SQL store.
        """
        storedir = filepath.FilePath(self.mktemp())
        s1 = store.Store(storedir)
        s1.transact(A, store=s1)
        self.assertIn(A, s1.typeToTableNameCache)
        s1.close()
        s2 = store.Store(storedir)
        self.assertIn(A, s2.typeToTableNameCache)
        s2.close()


    def test_revertedTableCreation(self):
        """
        When tables are created in a transaction which is reverted, they should
        persist in neither the SQL store nor the in-memory schema
        representation.
        """
        storedir = self.mktemp()
        s1 = store.Store(storedir)
        self.assertRaises(SomeError, s1.transact, createAndRaise, s1)
        self.assertNotIn(A, s1.typeToTableNameCache)
        s1.close()
        s2 = store.Store(storedir)
        self.assertNotIn(A, s2.typeToTableNameCache)


    def test_differentStoreTableCreation(self):
        """
        If two different stores are opened before a given table is created, and
        one creates it, this should be transparent to both item creation and
        queries made from either store.
        """
        storedir = self.mktemp()
        s1 = store.Store(storedir)
        s2 = store.Store(storedir)
        a1 = A(store=s1)
        a2 = A(store=s2)
        self.assertEquals(list(s1.query(
                    A, sort=A.storeID.ascending).getColumn("storeID")),
                          [a1.storeID, a2.storeID])
        self.assertEquals(list(s2.query(
                    A, sort=A.storeID.ascending).getColumn("storeID")),
                          [a1.storeID, a2.storeID])


    def test_dontReadTheSchemaSoMuch(self):
        """
        This is a regression test for a bug in Axiom where the schema was
        refreshed from SQL every time a table needed to be created, regardless
        of whether the schema needed to be refreshed or not.  In addition to
        being logically incorrect, this error severely hurt performance.

        The schema should only be re-read when a change is detected, by way of
        a table being created in two different Store objects, as in the test
        above in L{TableCreationTest.test_differentStoreTableCreation}.
        """
        s1 = store.Store(filepath.FilePath(self.mktemp()))
        def die():
            self.fail("schema refreshed unnecessarily called too much")
        s1._startup = die
        A(store=s1)
