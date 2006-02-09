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

class InventoryEntry(ActivateHelper, Item):
    typeName = 'test_app_inv'
    schemaVersion = 1

    owner = reference()
    owned = reference()

class Sword(ActivateHelper, Item):
    typeName = 'test_app_sword'
    schemaVersion = 3

    name = text()
    damagePerHit = integer()
    activated = inmemory()


def sword2to3(oldsword):
    newsword = oldsword.upgradeVersion('test_app_player', 2, 3)
    newsword.name = oldsword.name
    newsword.damagePerHit = oldsword.damagePerHit
    invent = InventoryEntry(store=newsword.store,
                            owner=oldsword.owner,
                            owned=newsword)
    return newsword


registerUpgrader(sword2to3, 'test_app_sword', 2, 3)

