Install python-appngizer
========================

python-appngizer is available in PyPi and can be installed via pip. 

For debian based systems we also provide a stable and unstable apt repository.

pip
---

To fullfill all 3rd party dependencies you probably need further build 
dependencies. On debian you can use the following command:

.. code-block:: bash
    
    # jessie
    $ apt-get install python-dev libxml2-dev libxslt1-dev zlib1g-de libffi-dev
    $ pip install --upgrade cffi
    
    # stretch
    $ apt-get install python-dev libxml2-dev libxslt1-dev zlib1g-dev

And finally:

.. code-block:: bash
    
    pip install appngizer

Debian
------

Add apt repository to your apt sources:

.. code-block:: bash
    
    /etc/apt/sources.list.d/appng.list:
    
    # stable packages
    deb http://appng.org/apt stable main
    # unstable packages
    deb http://appng.org/apt unstable main

Add apt repository public key to your keyring:

.. code-block:: bash
    
    $ wget -qO - https://appng.org/gpg/debian.key | sudo apt-key add -
    
And finally update apt sources and install package:

.. code-block:: bash
    
    $ apt-get update
    $ apt-get install python-appngizer
