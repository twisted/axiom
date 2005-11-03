from epsilon.setuphelper import autosetup

import axiom

distobj = autosetup(
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

    scripts=['bin/axiomatic'])

