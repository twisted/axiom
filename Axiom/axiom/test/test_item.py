from twisted.trial import unittest

from axiom import store, item

class NoAttrsItem(item.Item):
    typeName = 'noattrsitem'
    schemaVersion = 1

class TestItem(unittest.TestCase):
    def test_createPlainItem(self):
        st = store.Store()
        i = item.Item(store=st)

    test_createPlainItem.todo = 'this should be legal, or at least fail with a sane error'

    def test_createItemWithNoAttrs(self):
        st = store.Store()
        NoAttrsItem(store=st)

    test_createItemWithNoAttrs.todo = 'this should work but does not and must be fixed'
