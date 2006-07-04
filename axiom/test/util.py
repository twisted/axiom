
"""
Helpers for writing Axiom tests.
"""

from twisted.python.filepath import FilePath

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
    dbdir = testCase.mktemp()
    basePath = _getBaseStorePath(testCase, creator)
    basePath.copyTo(FilePath(dbdir))
    return Store(dbdir)
