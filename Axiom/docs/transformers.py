from axiom import attributes, item
from twisted.internet import defer
from zope import interface


class IRobot(interface.Interface):
    def attack(target):
        """
        Attacks the target.
        """



class ICar(interface.Interface):
    def drive(location):
        """
        Drives to location.
        """



@interface.implementer(IRobot)
class Transformer(item.Item):
    name = attributes.text(allowNone=False)
    damage = attributes.integer(allowNone=False)

    def attack(self, target):
        print "{s} hits {t} for {s.damage} damage!".format(s=self, t=target)



@interface.implementer(ICar)
class Truck(item.Item):
    wheels = attributes.integer(default=18)

    def drive(self, location):
        return defer.succeed(None)



@interface.implementer(ICar)
class HotRod(item.Item):
    color = attributes.text(allowNone=False)

    def drive(self, location):
        return defer.succeed(None)
