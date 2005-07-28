
from zope.interface import Interface, Attribute

class IStatEvent(Interface):
    """
    Marker for a log message that is useful as a statistic.

    Log messages with 'interface' set to this class will be counted over time.
    This is useful for tracking the rate of events such as page views. These
    messages are observed and thus tracked with a quotient.stats.Statoscope.
    These Statoscopes are periodically saved and are made retrievable by a
    remote interface.

    Log messages conforming to this interface must have these keys:

    - 'name': the name to be used for the backing Statoscope. This is used to
      group related stats for a component. Examples: "IMAP grabber",
      "database".

    Optional keys:

    - 'user': if this stat is something that can be blamed squarely on one
      user, set this to the username (avatar.name)

    - keys starting with 'stat_' map 'stuffs' to 'how many stuffs'. For
      example, stat_bytes=3182.

    """


class IAtomicFile(Interface):
    def __init__(tempname, destdir):
        """Create a new atomic file.

        The file will exist temporarily at C{tempname} and be relocated to
        C{destdir} when it is closed.
        """

    def tell():
        """Return the current offset into the file, in bytes.
        """

    def write(bytes):
        """Write some bytes to this file.
        """

    def close(callback):
        """Close this file.  Move it to its final location.

        @param callback: A no-argument callable which will be invoked
        when this file is ready to be moved to its final location.  It
        must return the segment of the path relative to per-user
        storage of the owner of this file.  Alternatively, a string
        with semantics the same as those previously described for the
        return value of the callable.

        @rtype: C{atop.store.StoreRelativePath}
        @return: A Deferred which fires with the full path to the file
        when it has been closed, or which fails if there is some error
        closing the file.
        """

    def abort():
        """Give up on this file.  Discard its contents.
        """


class IAxiomaticCommand(Interface):
    """
    Subcommand for 'axiomatic' and 'tell-axiom' command line programs.

    Should subclass twisted.python.usage.Options and provide a command to run.

    '.parent' attribute will be set to an object with a getStore method.
    """

    name = Attribute("""
    """)

    description = Attribute("""
    """)
