from os.path import abspath, dirname, join

from setuptools import find_packages, setup


# Bump src/jpp/__init__.py __version__ as well.
VERSION = "0.1.0"
REQUIREMENTS = ["dateparser", "tomlkit"]


def read_file(filename):
    with open(join(abspath(dirname(__file__)), filename), "r") as fp:
        return fp.read()


setup(
    name="jpp",
    version=VERSION,
    author="Peter Schmidbauer",
    author_email="peter.schmidb@gmail.com",
    url="http://github.com/pspeter/jpp",
    download_url="http://pypi.python.org/pypi/jpp",
    description="Simple cli that creates and manages text-based journals",
    long_description=read_file("README.md"),
    long_description_content_type="text/markdown",
    keywords=["jpp", "diary", "journal", "note-taking", "daybook", "cli"],
    python_requires=">=3.6",
    license="MIT",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha" "License :: OSI Approved :: MIT License",
        "Environment :: Console" "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Utilities",
    ],
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data={"jpp": ["py.typed"]},
    install_requires=REQUIREMENTS,
    entry_points={"console_scripts": ["jpp=jpp.cli:main"]},
)
