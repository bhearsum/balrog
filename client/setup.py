from os import path

from setuptools import find_packages, setup

here = path.abspath(path.dirname(__file__))
# We're using a pip8 style requirements file, which allows us to embed hashes
# of the packages in it. However, setuptools doesn't support parsing this type
# of file, so we need to strip those out before passing the requirements along
# to it.
with open(path.join(here, "requirements", "base.txt")) as f:
    requirements = []
    for line in f:
        # Skip empty and comment lines
        if not line.strip() or line.strip().startswith("#"):
            continue
        # Skip lines with hash values
        if not line.strip().startswith("--"):
            requirement_without_python_filter = line.split(";")[0]
            requirement_without_trailing_characters = requirement_without_python_filter.split()[0]
            requirements.append(requirement_without_trailing_characters)


setup(
    name="balrogclient",
    version="0.6.0",
    description="Balrog Admin API Client",
    author="Mozilla Release Engineers",
    author_email="release+python@mozilla.com",
    url="https://github.com/mozilla/balrog",
    license="MPL-2.0",
    packages=find_packages(),
    install_requires=requirements,
    test_suite="balrogclient.test",
    include_package_data=True,
)
