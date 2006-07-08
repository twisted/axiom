# -*- test-case-name: axiom.test.test_substore -*-

from zope.interface import implements

from twisted.application import service

from axiom.iaxiom import IPowerupIndirector

from axiom.store import Store
from axiom.item import Item, InstallableMixin
from axiom.attributes import path, inmemory, reference

from axiom.upgrade import registerUpgrader

class SubStore(Item):

    schemaVersion = 1
    typeName = 'substore'

    storepath = path()
    substore = inmemory()

    implements(IPowerupIndirector)

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
        """
        I adapt my store object to whatever interface I am adapted to.  This
        allows for avatar adaptation in L{axiom.userbase} to work properly
        without having to know explicitly that all 'avatars' objects are
        SubStore instances, since it is valid to have non-SubStore avatars,
        which are simply adaptable to the cred interfaces they represent.
        """
        ifa = interface(self.open(debug=self.store.debug), None)
        return ifa

    def indirect(self, interface):
        """
        Like __conform__, I adapt my store to whatever interface I am asked to
        produce a powerup for.  This allows for app stores to be installed as
        powerups for their site stores directly, rather than having an
        additional item type for each interface that we might wish to adapt to.
        """
        return interface(self)



class SubStoreStartupService(Item, service.Service, InstallableMixin):
    """
    This class no longer exists.  It is here simply to trigger an upgrade which
    deletes it.  Ignore it, please.
    """
    installedOn = reference()
    parent = inmemory()
    running = inmemory()
    name = inmemory()

    schemaVersion = 2

def eliminateSubStoreStartupService(subservice):
    subservice.deleteFromStore()
    return None

registerUpgrader(eliminateSubStoreStartupService, SubStoreStartupService.typeName, 1, 2)
