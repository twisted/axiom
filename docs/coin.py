from axiom import attributes, item

class Coin(item.Item):
    """
    A coin.
    """
    # attributes.money is the same thing as point4decimal
    value = attributes.money(allowNone=False)
