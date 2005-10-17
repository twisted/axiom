
from twisted.trial import unittest
from axiom import store

tntmrc = store._typeNameToMostRecentClass
def choose(module=None):
    del tntmrc[oldapp.Player.typeName]
    del tntmrc[oldapp.Sword.typeName]
    if module is not None:
        reload(module)

from axiom.test import oldapp

choose()

from axiom.test import newapp


class SchemaUpgradeTest(unittest.TestCase):
    def setUp(self):
        self.dbdir = self.mktemp()

    def _testTwoObjectUpgrade(self):
        choose(oldapp)
        s = store.Store(self.dbdir)

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

        s.close()

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

    def _testAutoUpgrade(self, playerID, swordID):
        choose(newapp)
        s = store.Store(self.dbdir)

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

        s = store.Store(self.dbdir)
        player = s.getItemByID(playerID)
        sword = s.getItemByID(swordID)
        return player, sword

    def _testLoadSwordFirst(self, playerID, swordID):
        choose(newapp)

        s = store.Store(self.dbdir)
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
