
"""
Helpers for writing Axiom tests.
"""

from twisted.python.filepath import FilePath

from twisted.trial.unittest import SkipTest

from axiom.store import Store

_theBaseStorePaths = {}
def _getBaseStorePath(testCase, creator):
    if creator not in _theBaseStorePaths:
        s = creator(testCase)
        _theBaseStorePaths[creator] = s.dbdir
        s.close()
    return _theBaseStorePaths[creator]


def getPristineStore(testCase, creator):
    """
    Get an Axiom Store which has been created and initialized by C{creator} but
    which has been otherwise untouched.  If necessary, C{creator} will be
    called to make one.

    @type testCase: L{twisted.trial.unittest.TestCase}
    @type creator: one-argument callable
    @param creator: A factory for the Store configuration desired.  Will be
    invoked with the testCase instance if necessary.
    @rtype: L{axiom.store.Store}
    """
    dbdir = FilePath(testCase.mktemp())
    basePath = _getBaseStorePath(testCase, creator)
    basePath.copyTo(dbdir)
    return Store(dbdir)



class CommandStubMixin:
    """
    Pretend to be the parent command for a subcommand.
    """
    def getStore(self):
        # fake out "parent" implementation for stuff.
        return self.store


    def getSynopsis(self):
        return '<CommandStubMixin>'

    subCommand = property(lambda self: self.__class__.__name__)



class CommandStub(object):
    """
    Mock for L{axiom.scripts.axiomatic.Options} which is always set as the
    C{parent} attribute of an I{axiomatic} subcommand.

    @ivar _store: The L{Store} associated which will be supplied to the
        subcommand.
    """
    def __init__(self, store, subCommand):
        self._store = store
        self.subCommand = subCommand


    def getSynopsis(self):
        return "Usage: axiomatic [options]"


    def getStore(self):
        return self._store



class QueryCounter:
    """
    This is a counter object which measures the number of VDBE instructions
    SQLite will execute to fulfill a particular query.

    The count of VDBE instructions is very useful as a proxy for CPU time and
    disk usage, because it (as opposed to CPU time and disk usage) is
    deterministic between runs of a given query regardless of various accidents
    of operating-system latency.

    When creating data for a query involving a limit, start with B{more} Items
    than will be returned by the limited query, not exactly the right number.
    SQLite will do a little bit more work in the case where the limit restricts
    the number of Items returned, and this will cause a test to fail even
    though the performance characteristics being demonstrated are actually
    correct.

    Put another way, if you are testing::

        s.query(MyItem, limit=5)


    You should create six instances of C{MyItem} before the first C{measure}
    call and then create one or more additional instances of C{MyItem} before
    the second C{measure} call.
    """

    def __init__(self, store):
        """
        Create a new query counter and install it on the provided store.

        @param store: an axiom L{Store}.
        """
        self.reset()
        self.store = store

        c = self.store.connection._connection
        # XXX: this only works with the pysqlite backend, even _with_ the hack
        # detection; if we ever care about the apsw backend again, we should
        # probably do something about adding the hack to it, adding this as a
        # public Axiom API, or something.
        sph = getattr(c, "set_progress_handler", None)
        if sph is None:
            raise SkipTest(
                "QueryCounter requires PySQLite 2.4 or newer, or a patch "
                "(see <http://initd.org/tracker/pysqlite/ticket/182>) to "
                "expose the set_progress_handler API.")
        sph(self.progressHandler, 1)

    def progressHandler(self):
        """
        This method will be called internally by SQLite for each bytecode executed.

        It increments a counter.

        @return: 0, aka SQLITE_OK, so that this does not abort the current
        query.
        """
        self.counter += 1
        return 0

    def reset(self):
        """Reset the internal counter to 0.
        """
        self.counter = 0

    def measure(self, f, *a, **k):
        """
        The primary public API of this class, which runs a given function and
        counts the number of bytecodes between its start and finish.

        @return: an integer, the number of VDBE instructions executed.
        """
        save = self.counter
        self.reset()
        try:
            f(*a, **k)
        finally:
            result = self.counter
            self.counter = save
        return result
