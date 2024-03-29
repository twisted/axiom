# -*- test-case-name: axiom.test.test_substore -*-

from zope.interface import implementer

from twisted.application import service

from axiom.iaxiom import IPowerupIndirector

from axiom.store import Store
from axiom.item import Item
from axiom.attributes import path, inmemory, reference

from axiom.upgrade import registerUpgrader
import six

@implementer(IPowerupIndirector)
class SubStore(Item):

    schemaVersion = 1
    typeName = 'substore'

    storepath = path()
    substore = inmemory()

    @classmethod
    def createNew(cls, store, pathSegments):
        """
        Create a new SubStore, allocating a new file space for it.
        """
        if isinstance(pathSegments, six.string_types):
            raise ValueError(
                'Received {!r} instead of a sequence'.format(pathSegments))
        if store.dbdir is None:
            self = cls(store=store, storepath=None)
        else:
            storepath = store.newDirectory(*pathSegments)
            self = cls(store=store, storepath=storepath)
        self.open()
        self.close()
        return self


    def close(self):
        self.substore.close()
        del self.substore._openSubStore
        del self.substore


    def open(self, debug=None):
        if hasattr(self, 'substore'):
            return self.substore
        else:
            if debug is None:
                debug = self.store.debug
            s = self.substore = self.createStore(debug, self.store.journalMode)
            s._openSubStore = self # don't fall out of cache as long as the
                                   # store is alive!
            return s


    def createStore(self, debug, journalMode=None):
        """
        Create the actual Store this Substore represents.
        """
        if self.storepath is None:
            self.store._memorySubstores.append(self) # don't fall out of cache
            if self.store.filesdir is None:
                filesdir = None
            else:
                filesdir = (self.store.filesdir.child("_substore_files")
                                               .child(str(self.storeID))
                                               .path)
            return Store(parent=self.store,
                         filesdir=filesdir,
                         idInParent=self.storeID,
                         debug=debug,
                         journalMode=journalMode)
        else:
            return Store(self.storepath.path,
                         parent=self.store,
                         idInParent=self.storeID,
                         debug=debug,
                         journalMode=journalMode)


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



class SubStoreStartupService(Item, service.Service):
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
