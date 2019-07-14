import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

requirements = []
with open('requirements.txt') as f:
  requirements = f.read().splitlines()

extras_require = {
    'docs': [
        'sphinxcontrib_trio==1.1.0',
    ]
}

setuptools.setup(
    name="fortnitepy",
    version="0.0.1",
    author="Terbau",
    description="Library for interacting with fortnite services",
    long_description=long_description,
    long_description_content_type="text/markdown",
    requirements=requirements,
    extras_require=extras_require,
    url="https://github.com/Terbau/fortnitepy",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
