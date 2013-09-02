from setuptools import setup, find_packages
from setuptools.command.install import install as Install
import re

versionPattern = re.compile(r"""^__version__ = ['"](.*?)['"]$""", re.M)
with open("axiom/_version.py", "rt") as f:
    version = versionPattern.search(f.read()).group(1)

class InstallAndRegenerate(Install):
    def run(self):
        """
        Runs the usual install logic, then regenerates the plugin cache.
        """
        Install.run(self)
        from twisted import plugin
        list(plugin.getPlugins(plugin.IPlugin, "axiom.plugins"))

setup(
    name="Axiom",
    version=version,
    description="An in-process object-relational database",
    url="http://divmod.org/trac/wiki/DivmodAxiom",

    maintainer="Divmod, Inc.",
    maintainer_email="support@divmod.org",

    install_requires=["twisted", "epsilon"],
    packages=find_packages() + ['twisted.plugins'],
    scripts=['bin/axiomatic'],

    license="MIT",
    platforms=["any"],

    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Framework :: Twisted",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 2 :: Only",
        "Topic :: Database"])
