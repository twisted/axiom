from distutils.core import setup
import re

versionPattern = re.compile(
    r"__version__ = versions\.Version\("
    "\"(?P<package>\w*)\", "
    "(?P<major>\d*), "
    "(?P<minor>\d*), "
    "(?P<micro>\d*)\)")

with open("axiom/_version.py", "rt") as f:
    match = versionPattern.search(f.read())
    package, major, minor, micro = match.groups()

setup(
    name=package.title(),
    version=".".join([major, minor, micro]),
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
