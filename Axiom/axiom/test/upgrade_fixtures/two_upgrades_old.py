
from axiom.attributes import integer, reference
from axiom.item import Item

class Referrer(Item):
    referee = reference()


class Referee(Item):
    dummy = integer()
