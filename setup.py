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
        "Development Status :: 5 - Production/Stable",
        "Framework :: Twisted",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Topic :: Database"],

    scripts=['bin/axiomatic'])

