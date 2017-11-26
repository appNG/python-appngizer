[![Build Status](https://www.appng.org/jenkins/buildStatus/icon?job=python-appngizer/master)](https://www.appng.org/jenkins/job/python-appngizer/job/master/)
[![PyPI](https://img.shields.io/pypi/v/appngizer.svg)](https://pypi.python.org/pypi/appngizer)
[![PyPI](https://img.shields.io/pypi/l/appngizer.svg)](https://pypi.python.org/pypi/appngizer)
[![PyPI](https://img.shields.io/pypi/wheel/appngizer.svg)](https://pypi.python.org/pypi/appngizer)
[![PyPI](https://img.shields.io/pypi/format/appngizer.svg)](https://pypi.python.org/pypi/appngizer)
[![PyPI](https://img.shields.io/pypi/status/appngizer.svg)](https://pypi.python.org/pypi/appngizer)

# python-appngizer

Python library/bindings for appNGizer webapplication

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes. See deployment for notes on how to deploy the project on a live system.

### Prerequisites

To fullfill all 3rd party dependencies you probably need further build dependencies. For debian you can use following command:

```
# jessie
$ apt-get install python-dev libxml2-dev libxslt1-dev zlib1g-de libffi-dev
$ pip install --upgrade cffi

# stretch
$ apt-get install python-dev libxml2-dev libxslt1-dev zlib1g-dev
```

### Installing

python-appngizer is available via pip and as debian package (currently just for jessie).

#### pip

```
$ pip install appngizer
```

#### Debian

Add apt repository to your apt sources:

```
/etc/apt/sources.list.d/appng.list:

# stable packages
deb http://appng.org/apt stable main
# unstable packages
deb http://appng.org/apt unstable main
```

Add apt repository public key to your keyring:

```
$ wget -qO - https://appng.org/gpg/debian.key | sudo apt-key add -
```

Update apt sources and install package:

```
$ apt-get update
$ apt-get install python-appngizer
```

## Versioning

We use [SemVer](http://semver.org/) for versioning. For the versions available, see the [tags on this repository](https://github.com/appNG/python-appngizer/tags). 

## Authors

* **Björn Pritzel** - *Initial work* - [aiticon GmbH](https://aiticon.com)

See also the list of [contributors](https://github.com/your/project/contributors) who participated in this project.

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details
