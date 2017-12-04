*******************
Command line Client
*******************

python-appngizer brings a basic command line client to administer appNG instances 
via the appNGizer REST webapplication.

It does not cover all available features and options which python-appngizer offers 
but can be a good starting point and or example for own applications.

Usage
=====

On a regular installation (pip/debian package) the command line client *appngizer* 
should be in your PATH and can be executed directly:

.. code-block:: bash

    # pip
    $ which appngizer
    
    /usr/local/bin/appngizer
  
    # debian package
    $ which appngizer
    
    /usr/bin/appngizer

Help
----

Basic
^^^^^

.. code-block:: bash

    $ appngizer -h

    usage: appngizer [-h] [--verbose] [--version] [--url CLIURL]
                     [--secret CLISHAREDSECRET] [--file CLIFILE] [--mode CLIMODE]
                     {create-site,read-sites,read-site,update-site,delete-site,
                     reload-site,create-property,read-properties,read-property,
                     update-property,delete-property,create-repository,
                     read-repositories,read-repository,update-repository,
                     delete-repository,read-applications,read-application,
                     update-application,delete-application,assign-application,
                     deassign-application,read-grants,read-grant,grant-grants,
                     read-packages,read-package,install-package,update-package,
                     create-subject,read-subjects,read-subject,update-subject,
                     delete-subject,create-group,read-groups,read-group,
                     update-group,delete-group,create-role,read-roles,
                     read-role,update-role,delete-role,create-permission,
                     read-permissions,read-permission,update-permission,
                     delete-permission,read-databases,read-database,
                     update-database,reload-platform}

Command specific
^^^^^^^^^^^^^^^^

.. code-block:: bash
    
    $ appngizer <command> -h

**Example create-site**:

.. code-block:: bash
    
    $ appngizer create-site -h
    
    usage: appngizer create-site [-h] [-n NAME] [-H HOST] [-d DOMAIN]
                                 [-t DESCRIPTION] [-e] [-c]
