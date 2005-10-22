from twisted.trial.unittest import TestCase

class UnavailableTypeTestCase(TestCase):
    def testUnavailable(self):
        from axiom import attributes, item, store

        def makeItem():
            class MyItem(item.Item):

                typeName = 'test_deadtype_myitem'
                schemaVersion = 1

                hello = attributes.integer()

            return MyItem

        storedir = self.mktemp()

        theStore = store.Store(storedir)
        makeItem()(store=theStore)

        item = reload(item)
        store = reload(store)

        store.Store(storedir)

    testUnavailable.skip = 'This test breaks EVERY subsequent test, because reloading item and store is not allowed'
