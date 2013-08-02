from weakref import ref
from traceback import print_exc

from twisted.python import log

from axiom import iaxiom

class CacheFault(KeyError):
    """
    An item has fallen out of cache, but the weakref callback has not yet run.
    """



class CacheInconsistency(RuntimeError):
    """
    A key being cached is already present in the cache.
    """



def logErrorNoMatterWhat():
    try:
        log.msg("Exception in finalizer cannot be propagated")
        log.err()
    except:
        try:
            emergLog = file("WEAKREF_EMERGENCY_ERROR.log", 'a')
            print_exc(file=emergLog)
            emergLog.flush()
            emergLog.close()
        except:
            # Nothing can be done.  We can't get an emergency log file to write
            # to.  Don't bother.
            return



def createCacheRemoveCallback(w, k, f):
    def remove(self):
        # Weakref callbacks cannot raise exceptions or DOOM ensues
        try:
            f()
        except:
            logErrorNoMatterWhat()
        try:
            self = w()
            if self is not None:
                try:
                    del self.data[k]
                except KeyError:
                    # Already gone
                    pass
        except:
            logErrorNoMatterWhat()
    return remove



class FinalizingCache:
    """Possibly useful for infrastructure?  This would be a nice addition (or
    perhaps even replacement) for twisted.python.finalize.
    """
    def __init__(self):
        self.data = {}


    def cache(self, key, value):
        fin = value.__finalizer__()
        try:
            if self.data[key]() is not None:
                raise CacheInconsistency(
                    "Duplicate cache key: %r %r %r" % (
                        key, value, self.data[key]))
        except KeyError:
            pass
        self.data[key] = ref(value, createCacheRemoveCallback(
                ref(self), key, fin))
        return value


    def uncache(self, key, value):
        """
        Remove a key from the cache.

        As a sanity check, if the specified key is present in the cache, it
        must have the given value.

        @param key: The key to remove.
        @param value: The expected value for the key.
        """
        try:
            assert self.get(key) is value
            del self.data[key]
        except KeyError:
            pass


    def get(self, key):
        o = self.data[key]()
        if o is None:
            del self.data[key]
            raise CacheFault(
                "FinalizingCache has %r but its value is no more." % (key,))
        log.msg(interface=iaxiom.IStatEvent, stat_cache_hits=1, key=key)
        return o

