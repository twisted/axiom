
from axiom import item
from axiom import attributes
from axiom import store

from twisted.trial.unittest import TestCase

class A(item.Item):
    typeName = 'test_table_creator'
    schemaVersion = 1

    attr = attributes.integer(default=3)

def setup(s):
    A(store=s)
    1/0


class TableCreationTest(TestCase):

    def testTableCreation(self):
        storedir = self.mktemp()
        s1 = store.Store(storedir)
        self.assertRaises(ZeroDivisionError, s1.transact, setup, s1)
        s1.close()
        s2 = store.Store(storedir)
        self.assertRaises(ZeroDivisionError, s2.transact, setup, s2)
        s2.close()
