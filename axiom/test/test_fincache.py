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



class SyntheticGCInteractions(SynchronousTestCase):
    """
    Tests for garbage collector interactions that cannot be provoked with
    public APIs.
    """

    def test_collectBeforeCallbacks(self):
        """
        Sometimes, the garbage collector runs and causes weakrefs to expire
        (start returning None when called) before they are finalized (their
        callback is invoked).  When this happens, FinalizingCache keeps track
        of expired cache keys so that future callback invocations will not
        expire any I{new} cache entries with the same key as the
        already-expired ones.

        Presently this only happens on PyPy, and there is no discrete public
        API which causes the garbage collector to call callbacks, only to do
        the collection which will I{eventually} (at some unpredictable, future
        time) call those callbacks, so this is verified against fake weakrefs.
        """
        test = self

        class Expirables(object):
            """
            A colletion of expirable weak references.
            """
            def __init__(self):
                self.references = []

            def ref(self, target, callback=lambda ref: None):
                """
                Create a reference to the given target with the given callback.
                """
                self.references.append(ExpireableRef(target, callback))
                return self.references[-1]

            def expireFor(self, target):
                """
                Expire all weak references that point to C{target} and return
                the number of references expired.
                """
                count = 0
                for ref in self.references:
                    if ref.target is target:
                        ref.expire()
                        count += 1
                return count

            def invokeExpired(self):
                """
                Invoke all expired references.
                """
                for ref in self.references:
                    if ref.expired and not ref.invoked:
                        ref.invoke()

        class ExpireableRef(object):
            """
            A reference that can be expired.
            """
            def __init__(self, target, callback):
                self.target = target
                self.callback = callback
                self.expired = False
                self.invoked = False

            def __call__(self):
                """
                Return the target if we have not yet been expired.
                """
                if not self.expired:
                    return self.target
                else:
                    return None

            def invoke(self):
                """
                Invoke the callback associated with this weakref.
                """
                test.assertEqual(self.expired, True, "Expire before invoking.")
                self.invoked = True
                self.callback(self)

            def expire(self):
                """
                Expire this weakref so it no longer points to its value.
                """
                self.expired = True

        expirables = Expirables()
        cache = FinalizingCache(expirables.ref)
        class identifiable(object):
            def __init__(self, name):
                self.name = name
            def __repr__(self):
                return self.name
            def __finalizer__(self):
                return noop

        a = identifiable("a")
        b = identifiable("b")
        cache.cache(1, a)
        self.assertEqual(expirables.expireFor(a), 1)
        cache.cache(1, b)
        expirables.invokeExpired()
        self.assertIdentical(cache.get(1), b)
