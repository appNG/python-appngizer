Install python-appngizer
========================

python-appngizer is available via pip and debian package (tested under jessie).

pip
---

.. code-block:: bash
    
    pip install appngizer

To fullfill all 3rd party dependencies you probably need further
build dependencies. Under debian you can use following command:

.. code-block:: bash
    
    apt-get install ...

Debian
------

Add our apt repository to your apt sources:

.. code-block:: bash

    /etc/apt/sources.list.d/appng.list:
    # stable packages
    deb http://appng.org/apt stable main
    # unstable packages
    deb http://appng.org/apt unstable main

Add our apt repository public key:

.. code-block:: bash

  ...

Update souces and install package:

.. code-block:: bash

    apt-get update
    apt-get install python-appngizer
