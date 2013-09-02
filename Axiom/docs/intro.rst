==============
 Introduction
==============

What is Axiom?
==============

Simply put, Axiom is a Python object database written on top of SQLite.

However, to just call it an "object database" doesn't quite do it justice.
Axiom has many other cool features, including but not limited to:

- powerups, allowing you to pretty much tack arbitrary behavior on to stores
  and items within those stores alike
- scheduling, allowing you to efficiently persist tasks to be executed at
  some point in the future
- upgrading, allowing you to transparently upgrade items in stores through
  pretty much any schema change imaginable

Despite all of this, Axiom manages to be small enough to fit in your head, a
property often sorely missed in more complex systems. For example, there's an
obvious one-to-one mapping from any Axiom item definition to a database schema.

Why this book?
==============

Because Axiom is not always given the attention it deserves. Also, Axiom's
many useful features and properties are not always obvious to the casual
observer, and warrant some more explaining.

Additionally, a catastrophic fate has befallen the server that originally
hosted all of the code and documentation, meaning documentation is often
harder to find than it needs to be. This book aims to alleviate that problem.
