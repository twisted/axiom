from axiom import attributes, item

class Person(item.Item):
    """
    A person.
    """
    name = attributes.text()
