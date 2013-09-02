from axiom import attributes, item, upgrade
from decimal import Decimal

class Measurement(item.Item):
    typeName = "measurement"
    schemaVersion = 2

    temperature = attributes.point4decimal()
    pressure = attributes.point4decimal()

def _upgradeMeasurementTemperature(old):
    new = old.upgradeVersion("measurement", 1, 2)
    new.temperature = ((old.temperature - 32) * 5 / 9) + Decimal("273.15")
    return new

upgrade.registerUpgrader(_upgradeMeasurementTemperature, "measurement", 1, 2)
