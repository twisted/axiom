from twisted.trial import unittest

from axiom import store, item

class NoAttrsItem(item.Item):
    typeName = 'noattrsitem'
    schemaVersion = 1

class TestItem(unittest.TestCase):
    def test_createPlainItem(self):
        st = store.Store()
        self.assertRaises(item.CantInstantiateItem, item.Item, store=st)

    def test_createItemWithNoAttrs(self):
        st = store.Store()
        self.assertRaises(store.NoEmptyItems, NoAttrsItem, store=st)
