******
Module
******

The main purpose of python-appngizer is to offer an easy way to implement
python applications to administer and interact with an appNG instance
via the appNGizer REST webapplication. 

To do this entities are represented as :class:`appngizer.elements.Element`.
The :attr:`appngizer.elements.Element.xml` attribute helds the XML representation 
of the entity as an :class:`lxml.objectify.ObjectifiedElement`.

The communication is implemented via the :class:`appngizer.client.XMLClient`.

By using specific methods of an element corresponding HTTP/S requests are send
by the XMLClient (GET for read, POST for create, PUT for update) and 
returns back the HTTP response which is the usually the new XML representation
of the entity.

There are also container elements where entities of the same entity
type are held. Currently they are only usable for read 
operations (f.e. read all available Sites) but can be the start point
for further improvements like bulk operatios.

Read
====

To read an existing appNG entity the :attr:`appngizer.elements.Element.name` 
attribute is used to identify and access the desired entity.

Example
-------

Read Site entity
^^^^^^^^^^^^^^^^

.. code-block:: python

    site = Site('a_site')
    site.read()
    print site.dump()

.. code-block:: xml

    <?xml version='1.0' encoding='UTF-8'?>
    <site name="a_site">
      <host>a_site</host>
      <domain>http://localhost:8080</domain>
      <description>test_description</description>
      <active>true</active>
      <createRepositoryPath>false</createRepositoryPath>
    </site>

Create or Update
================

For data manipulating methods like create or update you usually have to deliver 
all values as kwarg (dictionary is called xdict internally). kwarg are directly
mapped to XML components of the entity :attr:`appngizer.elements.Element.xml`. 

Which kind of XML component (element/s, attribute) an kwarg address is controlled 
by the first matching key in following class constants of the :class:`appngizer.elements.Element`:

- self.FIELDS are entity fields with a simple value (String, Text, Boolean, Integer)
- self.ATTRIBUTES are entity attributes with a simple value (String, Text, Boolean, Integer)
- self.CHILDS are child entities as SubElements wrapped in a childs element
- self.SUBELEMENTS are child entities as SubElements directly under the root element

Example
-------

Create Site entity
^^^^^^^^^^^^^^^^^^

.. code-block:: python

    site = Site('a_site')
    site.create(host='a_site', domain='http://localhost:8080')
    print site.dump()

.. code-block:: xml

    <?xml version='1.0' encoding='UTF-8'?>
    <site name="a_site">
      <host>a_site</host>
      <domain>http://localhost:8080</domain>
      <description></description>
      <active>true</active>
      <createRepositoryPath>false</createRepositoryPath>
    </site>

Update Site entity
^^^^^^^^^^^^^^^^^^

.. code-block:: python

    site = Site('a_site')
    site.read()
    site.update(description='test_description', createRepositoryPath=False)
    print site.dump()

.. code-block:: xml

    <?xml version='1.0' encoding='UTF-8'?>
    <site name="a_site">
      <host>a_site</host>
      <domain>http://localhost:8080</domain>
      <description>test_description</description>
      <active>true</active>
      <createRepositoryPath>true</createRepositoryPath>
    </site>

Site class constants
^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    class Site(Element):
        '''
            Class to manage a site
        '''
        FIELDS = OrderedDict()
        FIELDS['host'] = ''
        FIELDS['domain'] = ''
        FIELDS['description'] = ''
        FIELDS['active'] = True
        FIELDS['createRepositoryPath'] = False
        ATTRIBUTES = OrderedDict()
        ATTRIBUTES['name'] = ''

.. warning:: Be aware that renaming of an entity is not possible.

Parent entities
===============

Some :class:`appngizer.elements.Element` *can* have one or more parent entities.

Parent entities are been set by initialising an :class:`appngizer.elements.Element`
with a param called *parents* as a list of :class:`appngizer.elements.Element`.

Example
-------

Read Property entity with parent entity Site
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    site_property = Property('a_site_property', parents=[ Site('a_site') ])
    site_property.read()
    print site_property.dump()

.. code-block:: xml
    
    <?xml version='1.0' encoding='UTF-8'?>
    <property name="a_site_property" clob="false">
      <value>test_Value</value>
      <defaultValue>test_defaultValue</defaultValue>
      <description>test_description</description>
    </property>    
  
Read Property entity with parent entity Site and Application
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    site_app_property = Property('a_site_app_property', parents=[ Site('a_site'),Application('an_application') ])
    site_app_property.read()
    print site.dump()

.. code-block:: xml

    <?xml version='1.0' encoding='UTF-8'?>
    <property name="a_site_app_property" clob="false">
      <value>test_Value</value>
      <defaultValue>test_defaultValue</defaultValue>
      <description>test_description</description>
    </property>
    
.. warning:: Be aware that every parent is an ancestor of the preceding parent. 
    So this doesn't work:
    .. code-block:: python
    
       Package('appng-manager', parents=[ Repository('a_special_repo'),
                                          Repository('another_repo') ]).install()
                                          
    And as we deal here with lists, order matters, so this also doesn't work:  

    .. code-block:: python
    
       Property('a_site_app_property', parents=[ Application('an_application'),
                                                 Site('a_site') ]).read()

Child entities
==============

Some :class:`appngizer.elements.Element` can also have one or more child entities.

Child entities are also part of the entity XML so we handle them as a 
:class:`lxml.objectify.ObjectifiedElement` and not like parent entities as 
:class:`appngizer.elements.Element`.

To change child entities you usually use the relevant methods of an 
:class:`appngizer.elements.Element` with a kwarg where the key match the 
specific item in self.CHILDS of the :class:`appngizer.elements.Element`.

Example
-------

Create Subject entity with Groups
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    subj_groups = []
    subj_groups.append( Group('Users').xml )
    subj_groups.append( Group('Testers').xml )

    subj_tester = Subject('a_tester')
    subj_tester.create(realName='Andy Arbeit', email='andy@aiticon.com', 
                       digest='andy1976', groups=subj_groups)
    subj_tester.read()
    print subj_tester.dump()

.. code-block:: xml
    
    <?xml version='1.0' encoding='UTF-8'?>
    <subject name="a_tester">
      <realName>Andy Arbeit</realName>
      <email>andy@aiticon.com</email>
      <description></description>
      <digest>$2a$13$0wasGmmSdOF6/Kxybist1eSU42Y/n7h7.H3L2cvdasNKVvxHEheX?</digest>
      <timeZone>Europe/Berlin</timeZone>
      <language>en</language>
      <type>LOCAL_USER</type>
      <groups>
        <group name="Users" self="http://localhost:8080/appNGizer/group/Users">
            <description>appNG Users group</description>
        </group>
        <group name="Testers" self="http://localhost:8080/appNGizer/group/Testers">
            <description>appNG Testers group</description>
        </group>
      </groups>
    </subject>

Subject class constants
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    class Subject(Element):
        '''
            Class to manage a subject
        '''
        FIELDS = OrderedDict()
        FIELDS['realName'] = ''
        FIELDS['email'] = ''
        FIELDS['description'] = ''
        FIELDS['digest'] = ''
        FIELDS['timeZone'] = 'Europe/Berlin'
        FIELDS['language'] = 'en'
        FIELDS['type'] = 'LOCAL_USER'
        
        CHILDS = OrderedDict()
        CHILDS['groups'] = None
        ATTRIBUTES = {'name': ''}
