# -*- test-case-name: axiom.test.test_upgrading -*-


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


class Sword(ActivateHelper, Item):
    typeName = 'test_app_sword'
    schemaVersion = 2

    name = text()
    damagePerHit = integer()
    owner = reference()
    activated = inmemory()


def upgradePlayerAndSword(oldplayer):
    newplayer = oldplayer.upgradeVersion('test_app_player', 1, 2)
    newplayer.name = oldplayer.name

    oldsword = oldplayer.sword

    newsword = oldsword.upgradeVersion('test_app_sword', 1, 2)
    newsword.name = oldsword.name
    newsword.damagePerHit = oldsword.hurtfulness * 2
    newsword.owner = newplayer

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

