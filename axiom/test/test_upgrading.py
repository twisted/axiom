
from twisted.trial import unittest
from axiom import store, upgrade
from twisted.application.service import IService

tntmrc = store._typeNameToMostRecentClass
upgreg = upgrade._upgradeRegistry

def choose(module=None):
    # This has an unfortunate amount of knowledge of the implementation.  TODO:
    # add an API that can be used both for this test, and for general-purpose
    # run-time module reloading.
    tnames = [oldapp.Player.typeName,
              oldapp.Sword.typeName,
              'test_app_inv']
    for tn in tnames:
        tntmrc.pop(tn, None)

    for k in upgreg.keys():
        if k[0] in tnames:
            upgreg.pop(k)

    if module is not None:
        reload(module)

from axiom.test import oldapp

choose()

from axiom.test import toonewapp

choose()

from axiom.test import newapp


class SchemaUpgradeTest(unittest.TestCase):
    def setUp(self):
        self.dbdir = self.mktemp()

    def openStore(self):
        self.currentStore = store.Store(self.dbdir)
        return self.currentStore

    def closeStore(self):
        self.currentStore.close()
        self.currentStore = None

    def startStoreService(self):
        svc = IService(self.currentStore)
        svc.getServiceNamed("Batch Processing Controller").disownServiceParent()
        svc.startService()

    def testUnUpgradeableStore(self):
        self._testTwoObjectUpgrade()
        choose(toonewapp)
        self.assertRaises(RuntimeError, self.openStore)

    def _testTwoObjectUpgrade(self):
        choose(oldapp)
        s = self.openStore()

        sword = oldapp.Sword(
            store=s,
            name=u'flaming vorpal doom',
            hurtfulness=7
            )

        player = oldapp.Player(
            store=s,
            name=u'Milton',
            sword=sword
            )

        self.closeStore()

        # Perform an adjustment.

        return player.storeID, sword.storeID

    def testTwoObjectUpgrade_OuterFirst(self):
        playerID, swordID = self._testTwoObjectUpgrade()
        player, sword = self._testLoadPlayerFirst(playerID, swordID)
        self._testPlayerAndSwordState(player, sword)

    def testTwoObjectUpgrade_InnerFirst(self):
        playerID, swordID = self._testTwoObjectUpgrade()
        player, sword = self._testLoadSwordFirst(playerID, swordID)
        self._testPlayerAndSwordState(player, sword)

    def testTwoObjectUpgrade_AutoOrder(self):
        playerID, swordID = self._testTwoObjectUpgrade()
        player, sword = self._testAutoUpgrade(playerID, swordID)
        self._testPlayerAndSwordState(player, sword)

    def testTwoObjectUpgrade_UseService(self):
        playerID, swordID = self._testTwoObjectUpgrade()
        choose(newapp)
        s = self.openStore()
        self.startStoreService()

        # XXX *this* test really needs 10 or so objects to play with in order
        # to be really valid...

        def afterUpgrade(result):
            player = s.getItemByID(playerID, autoUpgrade=False)
            sword = s.getItemByID(swordID, autoUpgrade=False)
            self._testPlayerAndSwordState(player, sword)

        return s.whenFullyUpgraded().addCallback(afterUpgrade)

    def _testAutoUpgrade(self, playerID, swordID):
        choose(newapp)
        s = self.openStore()

        # XXX: this is certainly not the right API, but I needed a white-box
        # test before I started messing around with starting processes or
        # scheduling tasks automatically.
        while s._upgradeOneThing():
            pass

        player = s.getItemByID(playerID, autoUpgrade=False)
        sword = s.getItemByID(swordID, autoUpgrade=False)

        return player, sword

    def _testLoadPlayerFirst(self, playerID, swordID):
        # Everything old is new again
        choose(newapp)

        s = self.openStore()
        player = s.getItemByID(playerID)
        sword = s.getItemByID(swordID)
        return player, sword

    def _testLoadSwordFirst(self, playerID, swordID):
        choose(newapp)

        s = self.openStore()
        sword = s.getItemByID(swordID)
        player = s.getItemByID(playerID)
        return player, sword

    def _testPlayerAndSwordState(self, player, sword):
        self.assertEquals(player.name, 'Milton')
        self.failIf(hasattr(player, 'sword'))
        self.assertEquals(sword.name, 'flaming vorpal doom')
        self.assertEquals(sword.damagePerHit, 14)
        self.failIf(hasattr(sword, 'hurtfulness'))
        self.assertEquals(sword.owner.storeID, player.storeID)
        self.assertEquals(type(sword.owner), type(player))
        self.assertEquals(sword.owner, player)
        self.assertEquals(sword.activated, 1)
        self.assertEquals(player.activated, 1)


from axiom.substore import SubStore

class SubStoreCompat(SchemaUpgradeTest):
    def setUp(self):
        self.topdbdir = self.mktemp()
        self.subStoreID = None

    def openStore(self):
        self.currentTopStore = store.Store(self.topdbdir)
        if self.subStoreID is not None:
            self.currentSubStore = self.currentTopStore.getItemByID(self.subStoreID).open()
        else:
            ss = SubStore.createNew(self.currentTopStore,
                                    ['sub'])
            self.subStoreID = ss.storeID
            self.currentSubStore = ss.open()
        return self.currentSubStore

    def closeStore(self):
        self.currentSubStore.close()
        self.currentTopStore.close()
        self.currentSubStore = None
        self.currentTopStore = None

    def startStoreService(self):
        svc = IService(self.currentTopStore)
        svc.getServiceNamed("Batch Processing Controller").disownServiceParent()
        svc.startService()
