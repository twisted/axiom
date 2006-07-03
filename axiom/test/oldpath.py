# -*- test-case-name: axiom.test.test_upgrading.PathUpgrade.testUpgradePath -*-

from axiom.attributes import path

from axiom.item import Item

class Path(Item):
    schemaVersion = 1
    typeName = 'test_upgrade_path'
    thePath = path()
