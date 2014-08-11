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
        _regenerateCache()



def _regenerateCache():
    from twisted import plugin
    from axiom import plugins
    list(plugin.getPlugins(plugin.IPlugin)) # Twisted
    list(plugin.getPlugins(plugin.IPlugin, plugins)) # Axiom


setup(
    name="Axiom",
    version=version,
    description="An in-process object-relational database",
    url="https://github.com/twisted/axiom",

    maintainer="Divmod, Inc.",
    maintainer_email="support@divmod.org",

    install_requires=[
        "Twisted>=13.2.0",
        "Epsilon>=0.7.0"
    ],
    packages=find_packages() + ['twisted.plugins'],
    scripts=['bin/axiomatic'],
    cmdclass={
        "install": InstallAndRegenerate,
    },
    include_package_data=True,

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
