from setuptools import setup
from setuptools import find_packages

setup(
    name="pydp",
    version="0.1.0",
    license="MIT LICENCE",
    description="construct and generate minecraft datapack.",
    author="txkodo",
    url="https://github.com/txkodo/pydp",
    packages=find_packages("src"),
    package_dir={"": "src"}
)
