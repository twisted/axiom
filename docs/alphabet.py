import string
from axiom import attributes, item

letters = string.ascii_lowercase.decode("ascii")

class Letter(item.Item):
    """
    A letter in the alphabet being recited.
    """
    value = attributes.text(defaultFactory=iter(letters).next)
    # This creates an iterator over the list, and takes its ``next`` method.
    # Calling this method will produce the letters in sequence.
