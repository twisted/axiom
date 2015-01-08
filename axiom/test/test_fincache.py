import gc

from twisted.trial.unittest import SynchronousTestCase

from axiom._fincache import FinalizingCache


def noop():
    pass



class Object(object):
    """
    An object which can be stored in a FinalizingCache.
    """
    def __init__(self, name=None):
        self.name = name


    def __finalizer__(self):
        return noop


class FinalizingCacheTests(SynchronousTestCase):
    """
    Tests for L{axiom._fincache.FinalizingCache}.
    """
    def setUp(self):
        self.cache = FinalizingCache()

    def test_nonexistentItem(self):
        """
        Retrieving a nonexistent item from the cache results in L{KeyError}.
        """
        self.assertRaises(KeyError, self.cache.get, 42)


    def test_storeItem(self):
        """
        Storing an object in the cache, then retrieving it, results in the
        exact same object reference.
        """
        o = Object()
        self.cache.cache(42, o)
        self.assertIdentical(o, self.cache.get(42))


    def test_storeItemAndCollect(self):
        """
        An object will be removed from the cache if it is garbage collected.
        """
        o = Object()
        self.cache.cache(42, o)
        del o
        gc.collect()
        self.assertRaises(KeyError, self.cache.get, 42)


    def test_storeOverCollectedItem(self):
        """
        If an item is replaced in the cache, the finalizer from the first item
        does not remove the second item.
        """
        o1 = Object(1)
        self.cache.cache(42, o1)
        gc.disable()
        del o1
        gc.collect()

        o2 = Object(2)
        self.cache.cache(42, o2)
        gc.enable()
        self.assertEqual(2, self.cache.get(42).name)
