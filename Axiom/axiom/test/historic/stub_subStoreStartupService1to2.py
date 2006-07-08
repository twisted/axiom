# -*- test-case-name: axiom.test.historic.test_subStoreStartupService1to2 -*-

from zope.interface import implements
from twisted.application.service import IService

from axiom.item import Item
from axiom.attributes import boolean
from axiom.substore import SubStore, SubStoreStartupService

from axiom.test.historic.stubloader import saveStub

class DummyService(Item):
    """
    Service which does nothing but mark itself as run, if it's ever run.  After
    the upgrader it should not be run.
    """
    typeName = 'substore_service_upgrade_stub_service'
    everStarted = boolean(default=False)
    implements(IService)

    name = property(lambda : "sucky-service")
    running = property(lambda : False)

    def setName(self, name):
        pass
    def setServiceParent(self, parent):
        pass
    def disownServiceParent(self):
        pass
    def startService(self):
        self.everStarted = True
    def stopService(self):
        pass
    def privilegedStartService(self):
        pass


def createDatabase(s):
    """
    Create a store which contains a substore-service-starter item powered up
    for IService, and a substore, which contains a service that should not be
    started after the upgrader runs.
    """
    ssi = SubStore.createNew(s, ["sub", "test"])
    ss = ssi.open()
    ds = DummyService(store=ss)
    ss.powerUp(ds, IService)
    ssss = SubStoreStartupService(store=s).installOn(s)

if __name__ == '__main__':
    saveStub(createDatabase, 7615)
