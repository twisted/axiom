
import code, os
try:
    import readline
except ImportError:
    readline = None

import axiom
from axiom import store
from axiom.scripts import axiomatic

class AxiomConsole(code.InteractiveConsole):
    def runcode(self, code):
        """
        Override L{code.InteractiveConsole.runcode} to run the code in a
        transaction unless the local C{autocommit} is currently set to a true
        value.
        """
        if not self.locals.get('autocommit', None):
            return self.locals['db'].transact(code.InteractiveConsole.runcode, self, code)
        return code.InteractiveConsole.runcode(self, code)



class Browse(axiomatic.AxiomaticCommand):
    synopsis = "[options]"

    name = 'browse'
    description = 'Interact with an Axiom store.'

    optParameters = [
        ('history-file', 'h', '~/.axiomatic-browser-history',
         'Name of the file to which to save input history.'),
        ]

    optFlags = [
        ('debug', 'b', 'Open Store in debug mode.'),
        ]

    def postOptions(self):
        interp = code.InteractiveConsole(self.namespace(), '<axiom browser>')
        historyFile = os.path.expanduser(self['history-file'])
        if readline is not None and os.path.exists(historyFile):
            readline.read_history_file(historyFile)
        try:
            interp.interact("%s.  Autocommit is off." % (str(axiom.version),))
        finally:
            if readline is not None:
                readline.write_history_file(historyFile)


    def namespace(self):
        """
        Return a dictionary representing the namespace which should be
        available to the user.
        """
        self._ns = {
            'db': self.store,
            'store': store,
            'autocommit': False,
            }
        return self._ns
