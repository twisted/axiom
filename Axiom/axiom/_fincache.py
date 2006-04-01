
from weakref import ref
from traceback import print_exc

from twisted.python import log

from axiom import iaxiom

class CacheFault(RuntimeError):
    """
    A serious problem has occurred within the cache.  This error is internal
    and should never really be trapped.
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
                del self.data[k]
        except:
            logErrorNoMatterWhat()
    return remove

PROFILING = False

class FinalizingCache:
    """Possibly useful for infrastructure?  This would be a nice addition (or
    perhaps even replacement) for twisted.python.finalize.
    """
    def __init__(self):
        self.data = {}
        if not PROFILING:
            # see docstring for 'has'
            self.has = self.data.has_key

    def cache(self, key, value):
        fin = value.__finalizer__()
        assert key not in self.data, "Duplicate cache key: %r %r %r" % (key, value, self.data[key])
        self.data[key] = ref(value, createCacheRemoveCallback(
                ref(self), key, fin))
        return value

    def uncache(self, key, value):
        assert self.get(key) is value
        del self.data[key]

    def has(self, key):
        """Does the cache have this key?

        (This implementation is only used if the system is being profiled, due
        to bugs in Python's old profiler and its interaction with weakrefs.
        Set the module attribute PROFILING to True at startup for this.)
        """
        if key in self.data:
            o = self.data[key]()
            if o is None:
                del self.data[key]
                return False
            return True
        return False

    def get(self, key):
        o = self.data[key]()
        if o is None:
            raise CacheFault(
                "FinalizingCache has %r but its value is no more." % (key,))
        log.msg(interface=iaxiom.IStatEvent, stat_cache_hits=1, key=key)
        return o

