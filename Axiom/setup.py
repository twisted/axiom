import re
import setuptools

versionLine = open("axiom/_version.py", "rt").read()
match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", versionLine, re.M)
versionString = match.group(1)

setuptools.setup(
    name="Axiom",
    version=versionString,
    description="An in-process object-relational database",
    url="http://divmod.org/trac/wiki/DivmodAxiom",

    maintainer="Divmod, Inc.",
    maintainer_email="support@divmod.org",

    packages=setuptools.find_packages() + ["twisted.plugins"],
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
