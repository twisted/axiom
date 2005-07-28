

from axiom.item import Item
from axiom.attributes import text, integer, reference

class Player(Item):
    typeName = 'test_app_player'
    schemaVersion = 1

    name = text()
    sword = reference()

class Sword(Item):
    typeName = 'test_app_sword'
    schemaVersion = 1

    name = text()
    hurtfulness = integer()
