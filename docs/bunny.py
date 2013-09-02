from axiom import attributes, item

class Bunny(item.Item):
    """
    A bunny in a petting zoo.
    """
    timesPetted = attributes.integer(default=0)
