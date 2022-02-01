
from axiom.tags import Catalog
from axiom.test.historic.stubloader import StubbedTest

class CatalogUpgradeTest(StubbedTest):
    def testCatalogTagNames(self):
        """
        Test that the tagNames method of L{axiom.tags.Catalog} returns all the
        correct tag names.
        """
        c = self.store.findUnique(Catalog)
        self.assertEqual(
            sorted(c.tagNames()),
            ["external", "green", "internal"])
