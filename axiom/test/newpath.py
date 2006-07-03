# -*- test-case-name: axiom.test.test_upgrading.PathUpgrade.testUpgradePath -*-

from axiom.attributes import path

from axiom.item import Item

from axiom.upgrade import registerAttributeCopyingUpgrader

class Path(Item):
    schemaVersion = 2
    typeName = 'test_upgrade_path'
    thePath = path()

registerAttributeCopyingUpgrader(Path, 1, 2)
