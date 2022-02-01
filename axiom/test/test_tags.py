
from twisted.trial import unittest

from axiom.store import Store
from axiom.tags import Catalog

from axiom.item import Item
from axiom.attributes import text

class Gizmo(Item):
    typeName = 'test_gizmo'
    schemaVersion = 1
    name = text()



class TagTestCase(unittest.TestCase):

    def testTagging(self):
        s = Store()
        c = Catalog(store=s)
        g1 = Gizmo(store=s, name='one')
        g2 = Gizmo(store=s, name='two')

        c.tag(g1, 'single')
        c.tag(g1, 'multi')
        c.tag(g2, 'multi')
        c.tag(g1, 'multi')

        self.assertEqual(list(c.tagsOf(g1)),
                          ['single', 'multi'])
        self.assertEqual(list(c.tagsOf(g2)),
                          ['multi'])

        self.assertEqual(list(c.objectsIn('single')), [g1])
        self.assertEqual(list(c.objectsIn('multi')), [g1, g2])
