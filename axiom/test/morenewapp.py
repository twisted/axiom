# -*- test-case-name: axiom.test.test_upgrading.SchemaUpgradeTest.testUpgradeWithMissingVersion -*-


from axiom.item import Item
from axiom.attributes import text, integer, reference, inmemory

from axiom.upgrade import registerUpgrader

class ActivateHelper:
    activated = 0
    def activate(self):
        self.activated += 1

class Adventurer(ActivateHelper, Item):
    typeName = 'test_app_player'
    schemaVersion = 2

    name = text()
    activated = inmemory()

class InventoryEntry(ActivateHelper, Item):
    typeName = 'test_app_inv'
    schemaVersion = 1

    owner = reference()
    owned = reference()

    activated = inmemory()

class Sword(ActivateHelper, Item):
    typeName = 'test_app_sword'
    schemaVersion = 3

    name = text()
    damagePerHit = integer()
    activated = inmemory()

    def owner():
        def get(self):
            return self.store.findUnique(InventoryEntry,
                                         InventoryEntry.owned == self).owner
        return get,

    owner = property(*owner())


def sword2to3(oldsword):
    newsword = oldsword.upgradeVersion('test_app_sword', 2, 3)
    n = oldsword.store.getOldVersionOf('test_app_sword', 2)
    itrbl = oldsword.store.query(n)
    newsword.name = oldsword.name
    newsword.damagePerHit = oldsword.damagePerHit
    invent = InventoryEntry(store=newsword.store,
                            owner=oldsword.owner,
                            owned=newsword)
    return newsword


registerUpgrader(sword2to3, 'test_app_sword', 2, 3)


####### DOUBLE-LEGACY UPGRADE SPECTACULAR !! ###########

# declare legacy class.

from axiom.item import declareLegacyItem

declareLegacyItem(typeName = 'test_app_sword',
                  schemaVersion = 2,

                  attributes = dict(name=text(),
                                    damagePerHit=integer(),
                                    owner=reference(),
                                    activated=inmemory()))


def upgradePlayerAndSword(oldplayer):
    newplayer = oldplayer.upgradeVersion('test_app_player', 1, 2)
    newplayer.name = oldplayer.name

    oldsword = oldplayer.sword

    newsword = oldsword.upgradeVersion('test_app_sword', 1, 2,
                                       name=oldsword.name,
                                       damagePerHit=oldsword.hurtfulness * 2,
                                       owner=newplayer)

    return newplayer, newsword

def player1to2(oldplayer):
    newplayer, newsword = upgradePlayerAndSword(oldplayer)
    return newplayer

def sword1to2(oldsword):
    oldPlayerType = oldsword.store.getOldVersionOf('test_app_player', 1)
    oldplayer = list(oldsword.store.query(oldPlayerType,
                                          oldPlayerType.sword == oldsword))[0]
    newplayer, newsword = upgradePlayerAndSword(oldplayer)
    return newsword


registerUpgrader(sword1to2, 'test_app_sword', 1, 2)
registerUpgrader(player1to2, 'test_app_player', 1, 2)

