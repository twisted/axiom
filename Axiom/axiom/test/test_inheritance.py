
# This module is really a placeholder: inheritance between database classes is
# unsupported in XAtop right now.  We are just making sure that it is
# aggressively unsupported.

from twisted.trial import unittest

from axiom.item import Item, NoInheritance
from axiom.attributes import integer

class InheritanceUnsupported(unittest.TestCase):

    def testNoInheritance(self):
        class XA(Item):
            schemaVersion = 1
            typeName = 'inheritance_test_xa'
            a = integer()

        try:
            class XB(XA):
                schemaVersion = 1
                typeName = 'inheritance_test_xb'
                b = integer()
        except NoInheritance:
            pass
        else:
            self.fail("Expected RuntimeError but none occurred")

