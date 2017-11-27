appNGizer Module
================

The main purpose of python-appngizer is to offer an easy way to implement
python applications to administer and interact with an appNG instance
via the appNGizer REST webapplication. 

To do this the :attr:`appngizer.elements.Element.xml` attribute 
helds the xml representation of an entity as an :class:`lxml.objectify.ObjectifiedElement`.

The communication are implemented via the :class:`appngizer.client.XMLClient`.
If a specific operation requires it the :attr:`appngizer.elements.Element.xml` attribute
is added to the request data of the HTTP/S request (usually in a PUT/POST request).

There also container elements where appNG entities of the same entity
type are held. Currently they are only usable for read 
operations (f.e. read all available Sites) but can be the start point
for further improvements like bulk operatios.

- :class:`Properties`
- :class:`Sites`
- :class:`Repositories`
- :class:`Applications`
- :class:`Packages`
- :class:`Subjects`
- :class:`Groups`
- :class:`Roles`
- :class:`Permissions`
- :class:`Databases`
- :class:`Grants`

To address an appNG entity the :attr:`appngizer.elements.Element.name` attribute
must be set to identify and access the desired entity.

** Example **

- Site entity::

    site = Site('a_site')
    site.read()
    print site.dump()

Parent entities
---------------

Some :class:`appngizer.elements.Element` *can* have one or more parent entities and
there also entities where a parent entity is required. 

A parent entity is been set on initialising an :class:`appngizer.elements.Element`
object, as a list of :class:`appngizer.elements.Element`.

** Example **

- Property entity with a parent entity Site::

    site_property = Property('a_site_property', parents=[ Site('a_site') ])
    site_property.read()
    print site_property.dump()
  
- Property entity with a parent entity Site and Application::

    site_app_property = Property('a_site_app_property', parents=[ Site('a_site'),Application('an_application') ])
    site_app_property.read()
    print site.dump()
