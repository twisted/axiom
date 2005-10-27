from distutils.core import setup

import axiom

distobj = setup(
    name="Axiom",
    version=axiom.version.short(),
    maintainer="Divmod, Inc.",
    maintainer_email="support@divmod.org",
    url="http://divmod.org/trac/wiki/DivmodAxiom",
    license="MIT",
    platforms=["any"],
    description="An in-process object-relational database",
    classifiers=[
        "Intended Audience :: Developers",
        "Programming Language :: Python",
        "Development Status :: 2 - Pre-Alpha",
        "Topic :: Database"],

    scripts=['bin/axiomatic'],

    packages=['axiom',
              'axiom.scripts',
              'axiom.plugins',
              'axiom.test'],

    package_data={'axiom': ['examples/*']})

from epsilon.setuphelper import regeneratePluginCache
regeneratePluginCache(distobj)

