# -*- test-case-name: axiom.test.test_substore -*-

from axiom.store import Store
from axiom.item import Item, InstallableMixin
from axiom.attributes import path, inmemory, reference
from twisted.application import service

class SubStore(Item):

    schemaVersion = 1
    typeName = 'substore'

    storepath = path()
    substore = inmemory()

    def createNew(cls, store, pathSegments):
        """
        Create a new SubStore, allocating a new file space for it.
        """
        storepath = store.newDirectory(*pathSegments)
        self = cls(store=store, storepath=storepath)
        self.open()
        self.close()
        return self

    createNew = classmethod(createNew)

    def close(self):
        self.substore.close()
        del self.substore._openSubStore
        del self.substore

    def open(self, debug=False):
        if hasattr(self, 'substore'):
            return self.substore
        else:
            s = self.substore = Store(self.storepath.path,
                                      parent=self.store,
                                      idInParent=self.storeID,
                                      debug=debug)
            s._openSubStore = self # don't fall out of cache as long as the
                                   # store is alive!
            return s

    def __conform__(self, interface):
        ifa = interface(self.open(debug=self.store.debug), None)
        return ifa



class SubStoreStartupService(Item, service.Service, InstallableMixin):
    installedOn = reference()
    parent = inmemory()
    running = inmemory()
    name = inmemory()

    def installOn(self, store):
        super(SubStoreStartupService, self).installOn(store)
        store.powerUp(self, service.IService)
        if self.parent is None:
            self.setServiceParent(store)
            self.startService()
    def startService(self):
        super(SubStoreStartupService, self).startService()
        for ss in self.store.query(SubStore):
            svc = service.IService(ss, None)
            if svc:
                svc.setServiceParent(self)
                if not svc.running:
                    svc.startService()
