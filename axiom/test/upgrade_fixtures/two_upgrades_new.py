
from axiom.attributes import integer, reference
from axiom.item import Item, normalize
from axiom.upgrade import registerUpgrader

class Referrer(Item):
    # Don't import the old schema. -exarkun
    typeName = normalize(
        'axiom.test.upgrade_fixtures.two_upgrades_old.Referrer')
    schemaVersion = 2
    referee = reference()

def upgradeReferrer1to2(old):
    return old.upgradeVersion(
        old.typeName, 1, 2,
        referee=old.referee)

registerUpgrader(upgradeReferrer1to2, Referrer.typeName, 1, 2)

class Referee(Item):
    # Don't import the old schema. -exarkun
    typeName = normalize(
        'axiom.test.upgrade_fixtures.two_upgrades_old.Referee')
    schemaVersion = 2
    dummy = integer()

def upgradeReferee1to2(old):
    return old.upgradeVersion(
        old.typeName, 1, 2,
        dummy=old.dummy)

registerUpgrader(upgradeReferee1to2, Referee.typeName, 1, 2)
