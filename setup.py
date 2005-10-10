from distutils.core import setup

distobj = setup(
    name="Axiom",
    version="0.1",
    maintainer="Divmod, Inc.",
    maintainer_email="support@divmod.org",
    url="http://divmod.org/trac/wiki/AxiomProject",
    license="MIT",
    platforms=["any"],
    description="An in-process object-relational database",
    classifiers=(
        "Intended Audience :: Developers",
        "Programming Language :: Python",
        "Development Status :: 2 - Pre-Alpha",
        "Topic :: Database"),

    scripts=['bin/axiomatic'],

    packages=['axiom',
              'axiom.scripts',
              'axiom.plugins',
              'axiom.test'],

    package_data={'axiom': ['examples/*']})

from epsilon.setuphelper import regeneratePluginCache
regeneratePluginCache(distobj)

