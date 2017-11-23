appNGizer Module
================

The main purpose of python-appngizer is to offer an easy way to implement
python applications which should administer and interact with an appNG instance
via the appNGizer REST webapplication. 

    To do this the :attr:`appngizer.elements.Element.xml` attribute 
    helds the xml representation of the entity as an :class:`lxml.etree.Element`.
    
    CRUD methods on the entity are done via the 
    :class:`appngizer.client.XMLClient` where the :attr:`appngizer.elements.Element.xml` attribute
    is added to the data of the HTTP/S request if needed (usually in a PUT/POST request).
    
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
    
    To address an appNG entity we use their :attr:`appngizer.elements.Element.name` attribute, the entity 
    type name :const:`appngizer.elements.Element.TYPE` and their :attr:`appngizer.elements.Element.parents` attribute.
    
    **Examples:**
    
    - Site entity 'an_appng_site'::
    
        Site('an_appng_site')
      
    - Site application property 'a_site_app_property'::
    
        Property('a_site_app_property', parents=[ Site('an_appng_site') , Application('an_app') ] )
