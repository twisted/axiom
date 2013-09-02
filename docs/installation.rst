==============
 Installation
==============

Using pip
=========

Axiom is reasonably easy to install using pip. However, it does require its
dependency, Epsilon, during ``setup.py egg-info``. That means that it needs to
be available before pip tries to install Axiom. To make matters worse,
Epsilon, in turn, requires Twisted to be available for ``setup.py
egg-info``.

In short, you need to do::

  $ pip install Twisted
  $ pip install Epsilon
  $ pip install Axiom

Unfortunately, due to the way pip works, ``pip install Twisted Epsilon
Axiom`` or putting both of them in a requirements file and installing
it using ``pip -r`` does *not* work.
