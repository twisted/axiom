from setuptools import setup, find_packages

setup(
    name="Axiom",
    description="An in-process object-relational database",
    url="https://github.com/twisted/axiom",

    maintainer="Divmod, Inc.",
    maintainer_email="support@divmod.org",

    use_scm_version=True,
    setup_requires=['setuptools_scm'],
    install_requires=[
        "Twisted>=13.2.0",
        "Epsilon>=0.7.0"
    ],
    extras_require={
        'test': ['hypothesis[datetime]>=2.0.0,<3.0.0'],
        },
    packages=find_packages() + ['twisted.plugins'],
    scripts=['bin/axiomatic'],
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
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 2 :: Only",
        "Topic :: Database"])
