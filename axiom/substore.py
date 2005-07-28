# -*- test-case-name: axiom.test.test_substore -*-

from axiom.store import Store
from axiom.item import Item
from axiom.attributes import integer, path, inmemory

class SubStore(Item):

    schemaVersion = 1
    typeName = 'substore'

    storepath = path()
    substore = inmemory()

    def __init__(self, store, path, *a, **kw):
        super(SubStore, self).__init__(store=store, *a, **kw)
        self.storepath = store.newDirectory(*path)

    def open(self):
        if hasattr(self, 'substore'):
            return self.substore
        else:
            s = self.substore = Store(self.storepath.path,
                                      parent=self.store,
                                      idInParent=self.storeID)
            s._openSubStore = self # don't fall out of cache as long as the
                                   # store is alive!
            return s

    def __conform__(self, interface):
        return interface(self.open())

