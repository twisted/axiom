from distutils.core import setup
import re

versionPattern = re.compile(r"""^__version__ = ['"](.*?)['"]$""", re.M)
with open("axiom/_version.py", "rt") as f:
    version = versionPattern.search(f.read()).group(1)

setup(
    name="Axiom",
    version=version,
    description="An in-process object-relational database",
    url="http://divmod.org/trac/wiki/DivmodAxiom",

    maintainer="Divmod, Inc.",
    maintainer_email="support@divmod.org",

    install_requires=["twisted", "epsilon"],
    packages=[
        'axiom',
        'axiom.scripts',
        'axiom.test',
        'axiom.test.upgrade_fixtures',
        'axiom.test.historic',
        'axiom.plugins',
        'twisted.plugins'
    ],
    scripts=['bin/axiomatic'],

    license="MIT",
    platforms=["any"],

    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Framework :: Twisted",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Topic :: Database"])
