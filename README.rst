.. image:: https://github.com/twisted/axiom/workflows/Python%20package/badge.svg?branch=master&event=push
  :target: https://github.com/twisted/axiom/actions?query=event%3Apush+branch%3Amaster+workflow%3A%22Python+package%22

.. image:: https://codecov.io/github/twisted/axiom/coverage.svg?branch=master
  :target: https://codecov.io/github/twisted/axiom?branch=master

Divmod Axiom is an object database, or alternatively, an object-relational
mapper, implemented on top of Python.

    Note: Axiom currently supports only SQLite and does NOT have any features
    for dealing with concurrency.  We do plan to add some later, and perhaps
    also support other databases in the future.

Its primary goal is to provide an object-oriented layer with what we consider
to be the key aspects of OO, i.e. polymorphism and message dispatch, without
hindering the power of an RDBMS.

Axiom is a live database, not only an SQL generation tool: it includes an
implementation of a scheduler service, external file references, automatic
upgraders, robust failure handling, and Twisted integration.

Axiom is tightly integrated with Twisted, and can store, start, and stop
Twisted services directly from the database using the included 'axiomatic'
command-line tool.
