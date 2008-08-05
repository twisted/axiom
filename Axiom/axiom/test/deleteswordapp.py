# -*- test-case-name: axiom.test.test_upgrading -*-

"""
New version of L{axiom.test.oldapp} which upgrades swords by deleting them.
"""

from axiom.item import Item
from axiom.attributes import text
from axiom.upgrade import registerDeletionUpgrader

class Sword(Item):
    typeName = 'test_app_sword'
    schemaVersion = 2

    name = text()

registerDeletionUpgrader(Sword, 1, 2)
