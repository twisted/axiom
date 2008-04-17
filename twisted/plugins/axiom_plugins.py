# Copyright 2008 Divmod, Inc.  See LICENSE file for details

"""
Axiom plugins for Twisted.
"""

from zope.interface import classProvides

from twisted.plugin import IPlugin
from twisted.python.usage import Options
from twisted.application.service import IServiceMaker, IService


class AxiomaticStart(object):
    """
    L{IServiceMaker} plugin which gets an L{IService} from an Axiom store.
    """
    classProvides(IPlugin, IServiceMaker)

    tapname = "axiomatic-start"
    description = "Run an Axiom database (use 'axiomatic start' instead)"

    class options(Options):
        optParameters = [
            ('dbdir', 'd', None, 'Path containing Axiom database to start')]

        optFlags = [('debug', 'b', 'Enable Axiom-level debug logging')]


    def makeService(cls, options):
        """
        Create an L{IService} for the database specified by the given
        configuration.
        """
        from axiom.store import Store
        store = Store(options['dbdir'], debug=options['debug'])
        return IService(store)
    makeService = classmethod(makeService)
