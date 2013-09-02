==============
 Transactions
==============

Like any database worth its salt, SQLite supports transactions. Axiom
exposes these through the store's ``transact`` method.

The transact method takes a function. That function will be run in a
database transaction. The changes in the function happen atomically
(that is: either they entirely do or entirely don't).

.. testsetup::

    from axiom.store import Store
    from bunny import Bunny

.. doctest::

    >>> store = Store()
    >>> thumper = Bunny(store=store)
    >>> bugs = Bunny(store=store)
    >>> def petBunny():
    ...     bugs.timesPetted += 1
    ...     thumper.timesPetted += 1
    >>> store.transact(petBunny)
    >>> assert thumper.timesPetted == bugs.timesPetted == 1

Any uncaught exception raised by the transacted function will be
reraised. When this happens, the changes are reset to what they were
before the transaction was initiated.

.. doctest::

    >>> assert thumper.timesPetted == 1
    >>> def runIntoProblems():
    ...     thumper.timesPetted += 1
    ...     raise RuntimeError("fluffiness overload")
    >>> store.transact(runIntoProblems)
    Traceback (most recent call last):
    ...
    RuntimeError: fluffiness overload
    >>> assert thumper.timesPetted == 1

The ``transact`` method takes any amount of arguments (which are
passed verbatim to the transacted function), and will return the
return value of the transacted function.

.. doctest::

    >>> def petBunnies(bunnies, times):
    ...     totalPetsGiven = 0
    ...     for bunny in bunnies:
    ...         bunny.timesPetted += times
    ...         totalPetsGiven += times
    ...     return totalPetsGiven
    >>> store.transact(petBunnies, [thumper, bugs], 2)
    4
