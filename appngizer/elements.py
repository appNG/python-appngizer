# -*- coding: utf-8 -*-
'''
    This module contains all appNG entities which currently can managed
    via an appNGizer instance.
'''
import sys
import os
import logging
import bcrypt
import hashlib
import re

from copy import deepcopy
from collections import OrderedDict
from requests import Response
from requests.api import request
from distutils.version import LooseVersion

from lxml import etree
from lxml import objectify
from lxml.objectify import ObjectifiedElement, BoolElement

import appngizer.errors
from appngizer.client import XMLClient

log = logging.getLogger(__name__)

# TODO: Examine why we still get BooleanValues instead of str.lower() when setting field value
# TODO: Rework Grant/s Element

class XMLElement(object):
    '''
        Abstract class for an XML appNG entity
    '''
    # : Dictionary of XML namespaces
    XPATH_DEFAULT_NAMESPACE = {'a': 'http://www.appng.org/schema/appngizer'}
    # : Default namespace prefix as string
    NS_PREFIX = '{'+XPATH_DEFAULT_NAMESPACE['a']+'}'
    # : Path to appNGizer XSD schema file as string
    XSD_APPNGIZER_PATH = (os.path.dirname(os.path.realpath(sys.modules[__name__].__file__))) + '/appngizer.xsd'
    # : Entity element name
    TYPE = 'Element'
    # : Entities element name
    TYPE_C = 'Elements'
    # : OrderedDict of entity fields which should be processed and initialised
    FIELDS = OrderedDict()
    # List of FIELDS where value should be preserved if not given in 
    PRESERVED_FIELDS = []
    # List of FIELDS where value should be threatened as CDATA 
    CDATA_FIELDS = []
    # : OrderedDict of entity element attributes which should be processed and initialised
    ATTRIBUTES = OrderedDict()
    # : OrderedDict of entity child elements which should be processed and initialised
    CHILDS = OrderedDict()
    # : OrderedDict of entity sub elements which should be processed but not initialised
    SUBELEMENTS = OrderedDict()
    
    def __str__(self):
        '''Returns XML string representation of the object
        :return: str
        '''
        return self.dump()

    def _get_xml_template(self):
        '''Returns objectify.ObjectElement generated from class constants:

           self.FIELDS are entity fields as SubElements
           self.ATTRIBUTES are entity attributes as ObjectElement Attributes
           self.CHILDS are child entities as SubElements
           
        :return: lxml.objectify.ObjectifiedElement
        '''
        Element = objectify.ElementMaker(annotate=False, 
                                         namespace=self.XPATH_DEFAULT_NAMESPACE['a'])
        xml_template = Element(self.__class__.__name__.lower())
        # SubElements
        for field in self.FIELDS.keys():
            ns_field = '{'+self.XPATH_DEFAULT_NAMESPACE['a']+'}'+field
            objectify.SubElement(xml_template, ns_field, 
                                 namespace=self.XPATH_DEFAULT_NAMESPACE['a'])
            xml_template[field] = self.FIELDS[field]
        # ObjectElement Attributes
        for attribute in self.ATTRIBUTES.keys():
            attribute_value = self.ATTRIBUTES.get(attribute, None)
            if type(attribute_value) == bool:
                attribute_value = str(attribute_value).lower() 
            xml_template.set( attribute, attribute_value )
            # If attribute also exists as class attribute we use value of it 
            if hasattr(self, attribute):
                xml_template.set(attribute, self.__getattribute__(attribute))
        # SubElements
        for child in self.CHILDS.keys():
            ns_field = '{'+self.XPATH_DEFAULT_NAMESPACE['a']+'}'+child
            objectify.SubElement(xml_template, ns_field, 
                                 namespace=self.XPATH_DEFAULT_NAMESPACE['a'])
            xml_template[child] = self.CHILDS[child]
        return xml_template
    
    def _set_xml(self, source):
        '''Set self.xml by a given source
        
        :param lxml.objectify.ObjectifiedElement source(1): As ObjectifiedElement                
        :param Requests.response source(2): As Response object
        :param dict source(3): As dictionary               
        :param lxml.objectify.BoolElement source(4): As BoolElement               
        :return: self
        '''
        if type(source) == BoolElement:
            self.xml = source
        if type(source) == ObjectifiedElement:
            self._set_xml_from_xml_obj(source)
        if type(source) == Response:
            xml_obj = objectify.fromstring(source.content)
            self._set_xml_from_xml_obj(xml_obj)
        if type(source) == dict:    
            self._set_xml_from_dict(source)
        return self

    def _set_xml_from_dict(self, xdict):
        '''Process dictionary and call particular methods to set self.xml
               
           The dictionary should contains a flat key:value structure. Which kind 
           of XML component an dictionary item address is controlled by the corresponding
           key in following class constants:
           
           self.FIELDS are entity fields as SubElements
           self.ATTRIBUTES are entity attributes as ObjectElement attributes
           self.CHILDS are child entities as SubElements
           self.SUBELEMENTS are child entities as SubElements directly under the root element
        
        :param dict xdict: Dictionary of XML components to set
        :return: None
        '''
        # Process fields
        for field in self.FIELDS.iterkeys():
            if field in xdict:
                self._set_xml_field(field, xdict[field])
        # Process attributes
        for attribute in self.ATTRIBUTES.iterkeys():
            if attribute in xdict:
                self._set_xml_attribute(attribute, xdict[attribute])
        # Process childs
        for child in self.CHILDS.iterkeys():
            if child in xdict:
                self._set_xml_child(child, xdict[child])
        # Process elements
        for subelement in self.SUBELEMENTS:
            if subelement in xdict:
                self._set_xml_subelement(subelement, xdict[subelement])
    
    def _set_xml_from_xml_obj(self, xml_obj):
        '''Process :class:`lxml.objectify.ObjectifiedElement` and call particular methods to set self.xml
               
           The ObjectifiedElement is processed directly but still against checking
           against following constants:
           
           self.FIELDS are entity fields as SubElements
           self.ATTRIBUTES are entity attributes as ObjectElement attributes
           self.CHILDS are child entities as SubElements
           self.SUBELEMENTS are child entities as SubElements directly under the root element

           As we deal here with an :class:`lxml.objectify.ObjectifiedElement` the xml structure 
           can be of any form and just have to validate against the xsd schema. 
        
        :param lxml.objectify.ObjectifiedElement xml_obj: Element of the entity
        :return: None
        '''
        # Process fields
        for field in self.FIELDS.iterkeys():
            if hasattr(xml_obj, field):
                self._set_xml_field(field, xml_obj[field])
        # Process attributes
        for attribute in self.ATTRIBUTES.iterkeys():
            if attribute in xml_obj.attrib:
                self._set_xml_attribute(attribute, xml_obj.attrib[attribute])
        # Process childs
        for child in self.CHILDS.iterkeys():
            if hasattr(xml_obj, child):
                self._set_xml_child(child, list(xml_obj[child]))
        # Process subelements
        for subelement in self.SUBELEMENTS:
            if hasattr(xml_obj, subelement):
                self._set_xml_subelement(subelement, list(xml_obj[subelement]))    

    def _set_xml_field(self, field, value):
        '''Set self.xml field element
               
        The field element is a direct child of the root element and is identified by 
        his field name.
        
        An already existing value can be preserved when given in self.PRESERVED_FIELDS.
        
        :param str field: Name of field
        :param * value: Value of field as any lxml.objectify element type
        :return: None
        '''
        # If field in PRESERVED_FIELDS an empty value will be not applied 
        if value == None or value == '' or value == 'None':
            if field not in self.PRESERVED_FIELDS:
                value = ''
                self.xml.__setattr__(field, value)
        else:
            # If field in CDATA_FIELDS value is threatened as CDATA
            if field in self.CDATA_FIELDS:
                cdata_value = etree.CDATA(value)
                self.xml.__setattr__(field, cdata_value)
            else:
                self.xml.__setattr__(field, value)

    def _set_xml_attribute(self, attribute, value):
        '''Set self.xml element attributes
               
        The xml attributes are attributes of the root element.
        
        :param str field: Name of attribute
        :param str value: Value of attribute
        :return: None
        '''
        self.xml.set(attribute, value)
        
    def _set_xml_child(self, child, childs):
        '''Set self.xml field with child elements
        
        The type of a child item in childs must be a :class:`lxml.objectify.ObjectifiedElement`.

        :param str child: Name of child container xml element
        :param list childs: list of child elements from type :class:`lxml.objectify.ObjectifiedElement` 
        :return: None
        '''
        if len(childs) > 0:
            child_tag = childs[0].tag
            # handle the case we got an child element container instead of elements themself
            if child_tag == self.NS_PREFIX+child:
                container_childs = childs[0].getchildren()
                if len(container_childs) > 0:
                    child_tag = container_childs[0].tag
                    self.xml[child].__setattr__(child_tag,container_childs)
                else:
                    self.xml.__delattr__(child)
                    self.xml.__setattr__(child, None) 
            else:
                self.xml[child].__setattr__(child_tag,childs)
        else:
            self.xml.__delattr__(child)
            self.xml.__setattr__(child, None) 

    def _set_xml_subelement(self, subelement, subelements):
        '''Set self.xml subelements
        
        :param str subelement: Name of subelement xml element
        :param list subelements: List of subelements from type :class:`lxml.objectify.ObjectifiedElement` 
        :return: None
        '''
        self.xml.__setattr__(subelement, subelements)
                
    def get_xml_str(self, xml_obj=None):
        '''Copy, deannotate and return as a :class:`lxml.objectify.ObjectifiedElement` as string
        
        :param lxml.objectify.ObjectifiedElement xml_obj: Element to return as string
        :return: string
        '''
        if xml_obj is None:
            xml_obj = self.xml
        xml_deannot = deepcopy(xml_obj)
        objectify.deannotate(xml_deannot, pytype=True, xsi=True, 
                             xsi_nil=True, cleanup_namespaces=True)
        return etree.tostring(xml_deannot)
    
    def convert_xml_obj_to_xml_element(self, xml_obj=None):
        '''Convert :class:`lxml.objectify.ObjectifiedElement` to :class:`lxml.etree.Element`

        :param lxml.objectify.ObjectifiedElement xml_obj: Element to convert
        :return: lxml.etree.Element
        '''
        if xml_obj is None:
            xml_obj = self.xml
        return etree.fromstring( self.get_xml_str(xml_obj) )
    
    def convert_xml_element_to_xml_obj(self, xml=None):
        '''Convert :class:`lxml.etree.Element` to :class:`lxml.objectify.ObjectifiedElement`

        :param lxml.etree.Element xml: Element to convert
        :return: lxml.objectify.ObjectifiedElement
        '''
        if xml is None:
            xml = self.convert_xml_obj_to_xml_element(self.xml)
        return objectify.fromstring(etree.tostring(xml))

    def strip_ns_prefix(self, xml):
        '''Strip namespaces from :class:`lxml.etree.Element` and return it

        :param lxml.etree.Element xml: Element to strip
        :return: lxml.etree.Element
        '''
        query = "descendant-or-self::*[namespace-uri()!='']"
        elements = xml.xpath(query)
        if elements is not None:
            for element in xml.xpath(query):
                element.tag = etree.QName(element).localname
                etree.cleanup_namespaces(xml)
        return xml

    def dump(self, xml=None):
        '''Pretty print an :class:`lxml.etree.Element` or :class:`lxml.objectify.ObjectifiedElement` as string
        
        :param lxml.etree.Element xml(1): Element to pretty print
        :param lxml.objectify.ObjectifiedElement xml(2): Element to pretty print
        :return: string
        '''
        if xml is None:
            xml = self.xml
        
        copy = deepcopy(xml)
        if type(copy) == ObjectifiedElement:
            copy = self.convert_xml_obj_to_xml_element(copy)
        copy = self.strip_ns_prefix(copy)
        
        return etree.tostring(copy, encoding='UTF-8', xml_declaration=True, 
                              pretty_print=True)

    def is_valide_xml(self, xml=None):
        '''Validate :class:`lxml.etree.Element` against the appNGizer xsd schema

        :param lxml.etree.Element xml: Element to be validated, if not self.xml is used
        :return: bool (True if valide)
        '''
        doc = file(self.XSD_APPNGIZER_PATH, 'r')
        xsd_schema_doc = etree.parse(doc)
        xsd_schema = etree.XMLSchema(xsd_schema_doc)
        if xml is None:
            xml = self.convert_xml_obj_to_xml_element()

        try:
            xsd_schema.assertValid(xml)
            is_valide_xml = True
        except etree.DocumentInvalid as e:
            logging.warn(e)
            is_valide_xml = False
        except:
            raise
        return is_valide_xml



class Element(XMLElement):
    '''
        Abstract class of an appNG entity
    '''
    def __init__(self, name='', parents=[]):
        '''
        :param str name: Name of entity
        :param list parents: List of :class:`Element` objects which are parents of the entity
        '''
        self.name = name
        self.parents = parents
        self.url = self.get_url_dict()
        self.xml = self._get_xml_template()
        self.loaded = False
        self.modified = False

    def get_url_dict(self):
        '''Return dictionary with url path components of the entity
        
           url['self'] url path to entity
           url['ancestor'] url path to entity type
           url['parents'] url path of parent entities
        
        :return: dict
        '''
        return self._get_url_dict()
    def _get_url_dict(self):
        url = {'self': '', 'ancestor': '', 'parents': '', 'type': self.TYPE.lower()}

        # url['parents']
        if hasattr(self, 'parents'):
            for parent in self.parents:
                url['parents'] = ''.join([ url['parents'], parent.url['self'] ])
        # url['ancestor']
        url['ancestor'] = '/'.join([url['parents'], url['type']])
        # url['self']
        if self.name == None:
            url['self'] = url['ancestor']
        else:
            url['self'] = '/'.join([url['ancestor'], self.name])
        return url

    def load(self):
        '''Load entity via GET and set self.xml from requests.Response.content
        :return: None
        '''
        if len(self.parents) > 0:
            parent_types = ' '.join( [p.TYPE for p in self.parents] )
            log.debug("Load {} {}({})".format(parent_types, self.__class__.__name__, self.name))
        else:
            log.debug("Load {}({})".format(self.__class__.__name__, self.name))
        self._load()
    def _load(self):
        request = XMLClient().request('GET', self.url['self'])
        self._set_xml(request.response)
        self.loaded = True
        self.modified = False

    def load_if_needed(self):
        '''Load entity only if it's not already loaded and not modified by any methods
        :return: None
        '''
        self._load_if_needed()
    def _load_if_needed(self):
        if self.loaded:
            if self.modified:
                self.load()
        else:
            self.load() 
    
    def _create(self, xdict):
        '''Create entity from a given dict

        :param dict xdict: Dictionary of fields and attributes to be set for the new entity
        :return: lxml.etree.Element
        '''
        if len(self.parents) > 0:
            parent_types = ' '.join( [p.TYPE for p in self.parents] )
            log.debug("Create {} {}({})".format(parent_types, self.__class__.__name__, self.name))
        else:
            log.debug("Create {}({})".format(self.__class__.__name__, self.name))
        self._set_xml(xdict)
        if self.is_valide_xml():
            request = XMLClient().request('POST', self.url['ancestor'], self.get_xml_str())
            self._set_xml(request.response)
            self.modified = True
            return self.convert_xml_obj_to_xml_element()
        else:
            raise appngizer.errors.ElementError("Current XML for {0}({1}) does not validate: {2}".format(self.__class__.__name__, self.name, self.dump()))

    def read(self):
        '''Read entity and return as lxml.etree.Element
        :return: lxml.etree.Element
        '''
        log.debug("Read {}({})".format(self.__class__.__name__, self.name))
        self.load_if_needed()
        return self.convert_xml_obj_to_xml_element()

    def _update(self, xdict):
        '''Update entity from a given dict

        :param dict xdict: Dictionary of fields and attributes to be set for the updated entity
        :return: lxml.etree.Element
        '''
        if len(self.parents) > 0:
            parent_types = ' '.join( [p.TYPE for p in self.parents] )
            log.debug("Update {} {}({})".format(parent_types, self.__class__.__name__, self.name))
        else:
            log.debug("Update {}({})".format(self.__class__.__name__, self.name))
        self.load_if_needed()
        self._set_xml(xdict)
        if self.is_valide_xml( self.convert_xml_obj_to_xml_element() ):
            request = XMLClient().request('PUT', self.url['self'], self.get_xml_str())
            self._set_xml(request.response)
            return self.convert_xml_obj_to_xml_element()
        else:
            raise appngizer.errors.ElementError("Current XML for {}({}) does not validate: {}".format(self.__class__.__name__, self.name, self.dump()))

    def delete(self):
        '''Delete entity

        :return: bool (True if successfully)
        '''
        if len(self.parents) > 0:
            parent_types = ' '.join( [p.TYPE for p in self.parents] )
            log.debug("Delete {} {}({})".format(parent_types, self.__class__.__name__, self.name))
        else:
            log.debug("Delete {}({})".format(self.__class__.__name__, self.name))
        return self._delete()
    def _delete(self):
        if self.exist():
            XMLClient().request('DELETE', self.url['self'])
            self.modified = False
            return True
        else:
            raise appngizer.errors.ElementError("Element does not exist")

    def exist(self):
        '''Check if entity already exist

        :return: bool (True if exist)
        '''
        return self._exist()
    def _exist(self):
        try:
            self.load()
            return True
        except:
            return False
        
    def _is_update_needed(self, xdict):
        '''Check if update of entity is needed
        
        :param dict xdict: Dictionary of fields and attributes to be set for the updated entity
        :return: bool (True if needed), lxml.etree.Element (current), lxml.etree.Element (updated)
        '''
        self.load_if_needed()
        
        result = False
        new_obj = deepcopy(self)
        new_obj._set_xml(xdict)
        
        for field in self.FIELDS.iterkeys():
            if self.xml[field].text != new_obj.xml[field].text:
                result = True

        if len(self.parents) > 0:
            parent_types = ' '.join( [p.TYPE for p in self.parents] )
            log.debug("Update needed for {} {}({}) is {}".format(parent_types, self.__class__.__name__, self.name, str(result)))
        else:
            log.debug("Update needed for {}({}) is {}".format(self.__class__.__name__, self.name, str(result)))

        return result, self.xml, new_obj.xml



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
    
    PRESERVED_FIELDS = ['description','domain']

    TYPE = 'Site'
    TYPE_C = 'Sites'

    def create(self, **xdict):
        '''Create site

        :param str xdict['host']*: Hostname of site 
        :param str xdict['domain']*: Main URI of site 
        :param str xdict['description']: Short description of site 
        :param bool xdict['active']: Activate site
        :param bool xdict['createRepositoryPath']: Create site repository directory         
        :return: lxml.etree.Element
        '''
        return self._create(xdict)

    def update(self, **xdict):
        '''Update site

        :param str xdict['host']: Hostname of site 
        :param str xdict['domain']: Main URI of site 
        :param str xdict['description']: Short description of site 
        :param bool xdict['active']: Activate site
        :param bool xdict['createRepositoryPath']: Create site repository directory         
        :return: lxml.etree.Element
        '''
        return self._update(xdict)

    def is_update_needed(self, **xdict):
        '''Check if update of site is needed
        
        :param str xdict['host']: Hostname of site 
        :param str xdict['domain']: Main URI of site 
        :param str xdict['description']: Short description of site 
        :param bool xdict['active']: Activate site
        :param bool xdict['createRepositoryPath']: Create site repository directory         
        :return: bool (True if needed), lxml.etree.Element (current), lxml.etree.Element (updated)
        '''
        return self._is_update_needed(xdict)  

    def reload(self):
        '''Reload site

        :return: bool (True if reloaded)
        '''
        if XMLClient().request('PUT', self.url['self'] + '/reload'):
            return True
        else:
            return False



class Repository(Element):
    '''
        Class to manage a repository
    '''
    FIELDS = OrderedDict()
    FIELDS['description'] = ''
    FIELDS['remoteName'] = None
    FIELDS['uri'] = None
    FIELDS['enabled'] = True
    FIELDS['strict'] = False
    FIELDS['published'] = False
    FIELDS['mode'] = 'ALL'
    FIELDS['type'] = 'LOCAL'
    FIELDS['packages'] = None
    ATTRIBUTES = {'name': ''}
    
    PRESERVED_FIELDS = ['description']
    
    TYPE = 'Repository'
    TYPE_C = 'Repositories'

    def create(self, **xdict):
        '''Create repository

        :param str xdict['description']: Short description of repository
        :param str xdict['remoteName']: Remote name of a remote repository
        :param str xdict['uri']*: URI to repository
        :param bool xdict['enabled']: Enable repository
        :param bool xdict['strict']: Use strict mode for repository
        :param bool xdict['published']: Publish this repository as remote repository
        :param str xdict['mode']: Type of packages to serve (ALL|STABLE|SNAPSHOT) 
        :param str xdict['type']: Type of repository (LOCAL|REMOTE) 
        :return: lxml.etree.Element
        '''
        return self._create(xdict)

    def update(self, **xdict):
        '''Update repository

        :param str xdict['description']: Short description of repository
        :param str xdict['remoteName']: Remote name of a remote repository
        :param str xdict['uri']: URI to repository
        :param bool xdict['enabled']: Enable repository
        :param bool xdict['strict']: Use strict mode for repository
        :param bool xdict['published']: Publish this repository as remote repository
        :param str xdict['mode']: Type of packages to serve (ALL|STABLE|SNAPSHOT) 
        :param str xdict['type']: Type of repository (LOCAL|REMOTE) 
        :return: lxml.etree.Element
        '''
        return self._update(xdict)

    def is_update_needed(self, **xdict):
        '''Check if update of repository is needed

        :param str xdict['description']: Short description of repository
        :param str xdict['remoteName']: Remote name of a remote repository
        :param str xdict['uri']: URI to repository
        :param bool xdict['enabled']: Enable repository
        :param bool xdict['strict']: Use strict mode for repository
        :param bool xdict['published']: Publish this repository as remote repository
        :param str xdict['mode']: Type of packages to serve (ALL|STABLE|SNAPSHOT) 
        :param str xdict['type']: Type of repository (LOCAL|REMOTE) 
        :return: bool (True if needed), lxml.etree.Element (current), lxml.etree.Element (updated)
        '''
        return self._is_update_needed(xdict)  

    def has_pkg(self, **xdict):
        '''Check if repository have a package 
        
        :param str xdict['name']*: name of package
        :return: bool (True if has package)
        '''
        pkg_name = xdict['name']
        has_pkg = False
        try:
            pkg_url = '/'.join([ self.url['self'],pkg_name ])
            request = XMLClient().request('GET', pkg_url)
            has_pkg = True
        except:
            has_pkg = False
        log.debug("Package({}) in Repository({}) available is {}".format(pkg_name, self.name, str(has_pkg)))
        return has_pkg
    
    def list_pkg(self, **xdict):
        '''Get a list of all variants of a package in the repository
        
        :param str xdict['name']*: name of package
        :return: lxml.objectify.ObjectifiedElement
        '''
        pkg_name = xdict['name']
        log.debug("Read Package({})".format(pkg_name))
        pkg_url = '/'.join([ self.url['self'],pkg_name ])
        try:
            request = XMLClient().request('GET', pkg_url)
        # APPNG-2071 we should catch only if HTTP 404
        except:
            return None
        return objectify.fromstring(request.response.content)
    
    def list_pkgs(self):
        '''Get a list of all packages in the repository 
        
        :return: lxml.objectify.ObjectifiedElement
        '''
        self.load_if_needed()
        return self.xml.packages



class Property(Element):
    '''
        Class to manage a property
    '''
    
    FIELDS = OrderedDict()
    FIELDS['value'] = ''
    FIELDS['defaultValue'] = ''
    FIELDS['description'] = ''
    ATTRIBUTES = {'name': '', 'clob': False}
    
    PRESERVED_FIELDS = ['description', 'defaultValue']
    
    TYPE = 'Property'
    TYPE_C = 'Properties'

    def create(self, **xdict):
        '''Create property

        :param str xdict['value']: Value of property 
        :param str xdict['defaultValue']: Default value of property 
        :param str xdict['description']: Short description of property 
        :param bool xdict['clob']: Threat value as clob
        :return: lxml.etree.Element
        '''
        if xdict.get('clob', False):
            self.CDATA_FIELDS = ['value', 'defaultValue']
        return self._create(xdict)

    def update(self, **xdict):
        '''Update property

        :param str xdict['value']: Value of property 
        :param str xdict['defaultValue']: Default value of property 
        :param str xdict['description']: Short description of property 
        :param bool xdict['clob']: Threat value as clob
        :return: lxml.etree.Element
        '''
        if xdict.get('clob', False):
            self.CDATA_FIELDS = ['value', 'defaultValue']
        return self._update(xdict)

    def is_update_needed(self, **xdict):
        '''Check if update of property is needed

        :param str xdict['value']: Value of property 
        :param str xdict['defaultValue']: Default value of property 
        :param str xdict['description']: Short description of property 
        :param bool xdict['clob']: Threat value as clob
        :return: bool (True if needed), lxml.etree.Element (current), lxml.etree.Element (updated)
        '''
        if xdict.get('clob', False):
            self.CDATA_FIELDS = ['value', 'defaultValue']
        return self._is_update_needed(xdict)



class Application(Element):
    '''
        Class to manage an application
    '''

    FIELDS = OrderedDict()
    FIELDS['displayName'] = ''
    FIELDS['privileged'] = False
    FIELDS['fileBased'] = False
    FIELDS['hidden'] = False
    FIELDS['version'] = ''
    ATTRIBUTES = {'name': ''}
    
    TYPE = 'Application'
    TYPE_C = 'Applications'

    def update(self, **xdict):
        '''Update application settings

        :param str xdict['displayName']: Name of application to display
        :param bool xdict['privileged']: Give privileged rights for application
        :param bool xdict['fileBased']: Store application in filesystem instead of database
        :param bool xdict['hidden']: Hide application in manager backend
        :return: lxml.etree.Element
        '''
        return self._update(xdict)

    def is_update_needed(self, **xdict):
        '''Check if update of application settings is needed

        :param str xdict['displayName']: Name of application to display
        :param bool xdict['privileged']: Give privileged rights for application
        :param bool xdict['fileBased']: Store application in filesystem instead of database
        :param bool xdict['hidden']: Hide application in backend
        :return: bool (True if needed), lxml.etree.Element (current), lxml.etree.Element (updated)
        '''
        return self._is_update_needed(xdict)  
            
    def delete(self):
        '''Deletes an application
        
        With additional check if application is assigned to any site before try to delete
            
        :return: bool (True if deleted)
        '''
        sites = Sites()
        sites_assigned = []
        is_assigned = False
        for site in sites.site:
            site_obj = Site(site.name)._set_xml(self.convert_xml_obj_to_xml_element(site))
            site_app = Application(self.name)
            
            if site_app.is_assigned( site=site_obj ):
                is_assigned = True
                sites_assigned.append(site.name)
            if is_assigned:
                raise appngizer.errors.ElementError("Delete {0}({1}) aborted, deassign from site/s({2}) first".format(self.__class__.__name__, self.name, ', '.join(sites_assigned)))
            XMLClient().request('DELETE', self.url['self'])
            self.modified = False
            return True

    def is_assigned(self, site):
        '''Check if application is assigned to a site

        :return: bool (True if is assigned)
        '''
        is_assigned = False
        if type(site) != Site:
            raise appngizer.errors.ElementError("Can't check if {0}({1}) is assigned to a site because site is not a Site object".format(self.__class__.__name__, self.name))

        try:
            url = site.url['self'] + self.url['self']
            request = XMLClient().request('GET', url)
            self._set_xml(request.response)
            is_assigned = True
        except appngizer.errors.HttpElementNotFound:
            pass
        except:
            raise
        log.debug("{0}({1}) assigned on site {2} is {3}".format(self.__class__.__name__, self.name, site.name, is_assigned))
        return is_assigned

    def assign(self, site):
        '''Assign application to a site

        :return: bool (True if assigned)
        '''
        if type(site) != Site:
            raise appngizer.errors.ElementError("Can't assign {0}({1}) to site because site is not a Site object".format(self.__class__.__name__, self.name))

        self.load_if_needed()
        log.debug('Assign {}({}) to site {}'.format(self.__class__.__name__,self.name, site.name))
        
        url = site.url['self'] + self.url['self']
        
        request = XMLClient().request('POST', url, self.get_xml_str())
        self.modified = False
        return True

    def deassign(self, site):
        '''Deassign application from a site

        :return: bool (True if deassigned)
        '''
        if type(site) != Site:
            raise appngizer.errors.ElementError("Can't deassign {0}({1}) from a site because site is not a Site object".format(self.__class__.__name__, self.name))

        log.debug('Deassign {0}({1}) to site {2}'.format(self.__class__.__name__,self.name, site.name))

        url = site.url['self'] + self.url['self']
        
        request = XMLClient().request('DELETE', url, self.get_xml_str())
        self.modified = False
        return True

    def deassign_from_all(self):
        '''Deassign application from all sites

        :return: bool (True if deassigned)
        '''
        sites = Sites()
        sites.load()
        for site in sites.xml.site:
            site_obj = Site(site.get('name'))
            site_obj._set_xml(site)
            site_app = Application(self.name, parents=[site_obj])
            
            if site_app.is_assigned(site_obj):
                site_app.deassign(site_obj)
        return True
        


class Package(Element):
    '''
        Class to manage a package
    '''
    FIELDS = OrderedDict()
    FIELDS['displayName'] = ''
    FIELDS['version'] = ''
    FIELDS['timestamp'] = ''
    FIELDS['installed'] = False
    FIELDS['type'] = 'APPLICATION'
    ATTRIBUTES = {'name': ''}
    
    TYPE = 'Package'
    TYPE_C = 'Packages'
    
    def __init__(self, name=None, parents=[]):
        '''Initialising of package object
        
        :param str name: Name of entity
        :param list parents: List of :class:`Element` objects which are parents of the current entity
        '''
        self.name = name
        self.parents = parents
        self.xml = self._get_xml_template()
        self.loaded = False
        self.modified = False
        
    def exist(self, **xdict):
        '''Check if a package exist
        
        :param str xdict['version']: Filter for a specific version
        :param str xdict['timestamp']: Filter for a specific timestamp
        :return: bool (True if exist)
        '''
        filter = {}
        if 'version' in xdict:
            filter['version'] = xdict['version']
        if 'timestamp' in xdict:
            filter['timestamp'] = xdict['timestamp']  
        
        find_pkg = Packages(parents=self.parents).find(name=self.name, filter=filter)
        
        if hasattr(find_pkg, 'package'):
            package_exist = True
        else:
            package_exist = False
        return package_exist
    
    def is_installed(self):
        '''Check if a package is already installed

        :return: bool (True if installed)
        '''
        is_installed = False
        if Application(self.name).exist():
            is_installed = True
        return is_installed

    def is_update_needed(self, **xdict):
        '''Check if update of an installed package is needed

        :param str xdict['version']: Update to a specific version
        :param str xdict['timestamp']: Update to a specific timestamp
        :param bool xdict['allow_snapshot']: Allow snapshot packages if no specific version is given        
        :return: bool (True if needed), lxml.etree.Element (current), lxml.etree.Element (updated)
        '''
        is_update_needed = False
        filter = {}
        if 'version' in xdict:
            filter['version'] = xdict['version']
        if 'timestamp' in xdict:
            filter['timestamp'] = xdict['timestamp']
        allow_snapshot = xdict.get('allow_snapshot', False)
        find_pkg = None
        
        self.read()

        find_pkgs = Packages(parents=self.parents).find(name=self.name, filter=filter)
        if not hasattr(find_pkgs, 'package'):
            raise appngizer.errors.ElementNotFound('Package {} is not available with {}'.format(self.name, filter))
        if not allow_snapshot:
            for pkg in find_pkgs.package:
                if '-SNAPSHOT' not in pkg.version.text:
                    find_pkg = pkg
                    break
        else:
            find_pkg = find_pkgs.package[0]
        if find_pkg is None:
            raise appngizer.errors.ElementNotFound('Package {} is not available with {}'.format(self.name, filter))

        if self.xml.version != find_pkg.version:
            if LooseVersion(self.xml.version.text) < LooseVersion(find_pkg.version.text):
                is_update_needed = True        
        elif self.xml.timestamp != find_pkg.timestamp:
            is_update_needed = True

        delattr(find_pkg, 'repository')
        return is_update_needed, self.convert_xml_obj_to_xml_element(self.xml), self.convert_xml_obj_to_xml_element(find_pkg)

    def load(self):
        '''Load package data from Packages object
        :return: None
        '''
        log.debug("Load {0}({1})".format(self.__class__.__name__, self.name))
        filter = { 'installed':'true' }
        find_pkg = Packages(parents=self.parents).find(name=self.name, filter=filter)
        if hasattr(find_pkg, 'package'):
            self._set_xml(find_pkg.package)
        else:
            # Quick hack to load pkg data from any repository
            # if currently installed does not comes from parent repository
            find_pkg = Packages(parents=[]).find(name=self.name, filter=filter)
            if hasattr(find_pkg, 'package'):
                self._set_xml(find_pkg.package[0])
            else:
                raise appngizer.errors.ElementNotFound('Package {} is not installed'.format(self.name))
        self.loaded = True

    def install(self, **xdict):
        '''Install a package

        :param str xdict['version']: Install a specific version
        :param str xdict['timestamp']: Install a specific timestamp
        :param bool xdict['allow_snapshot']: Allow snapshot packages if no specific version is given         
        :return: lxml.etree.Element
        '''
        filter = {}
        if 'version' in xdict:
            filter['version'] = xdict['version']
        if 'timestamp' in xdict:
            filter['timestamp'] = xdict['timestamp']
        allow_snapshot = xdict.get('allow_snapshot', False)
        find_pkg = None
        
        self._set_xml(xdict)
        
        find_pkgs = Packages(parents=self.parents).find(name=self.name, filter={})
        if not hasattr(find_pkgs, 'package'):
            raise appngizer.errors.ElementNotFound('Package {} is not available with {}'.format(self.name, filter))
        if not allow_snapshot:
            for pkg in find_pkgs.package:
                if '-SNAPSHOT' not in pkg.version.text:
                    find_pkg = pkg
                    break
        else:
            find_pkg = find_pkgs.package[0]
        if find_pkg is None:
            raise appngizer.errors.ElementNotFound('Package {} is not available with {}'.format(self.name, filter))
        
        find_pkg_repo = find_pkg.repository
        self._set_xml(find_pkg)
        
        log.debug('Install {}({}) in version ({})'.format(self.__class__.__name__, self.name, self.xml.version))
        return self._install(find_pkg_repo)
    def _install(self, repository):
        self.xml.installed = True
        if self.is_valide_xml():
            install_url = '/'.join([ '/repository',repository.get('name'),'install' ])
            request = XMLClient().request('PUT', install_url, self.get_xml_str())
            self._set_xml(request.response)
            self.modified = True
            return self.convert_xml_obj_to_xml_element()
        else:
            raise appngizer.errors.ElementError("Current XML for {0}({1}) does not validate: {2}".format(self.__class__.__name__, self.name, self.dump()))
    def update(self, **xdict):
        '''update() is an alias for install()
        '''
        return self.install(**xdict)

    def delete(self):
        '''
        :raises appngizer.errors.ElementError: Method is not avaible for entity
        '''
        raise appngizer.errors.ElementError("Method not available for {0}({1})".format(self.__class__.__name__, self.name))



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
    
    PRESERVED_FIELDS = ['description','email','timeZone','language','type']
    
    TYPE = 'Subject'
    TYPE_C = 'Subjects'

    def digest_match_hash(self, digest, hashed):
        '''Check if digest match hash
        
        If digest does not start with '$2a$' it will handled as plaintext
        otherwise digest is directly matched against hashed
        
        :param str digest: digest of subject
        :param str hashed: bcrypt hash of digest to match
        :return: bool (True if match)
        '''
        if str(digest).startswith('$2a$'):
            if str(digest) == str(hashed):
                return True
            else:
                return False
        else:
            if bcrypt.hashpw(str(digest), str(hashed)) == str(hashed):
                return True
            else:
                return False

    def create(self, **xdict):
        '''Create subject

        :param str xdict['realName']*: Real name of subject 
        :param str xdict['email']*: E-Mail address of subject 
        :param str xdict['description']: Short description of subject
        :param str xdict['digest']*: Password as plaintext or bcrypt hash
        :param str xdict['timeZone']: Timezone for subject
        :param str xdict['language']: Language for subject
        :param str xdict['type']:  Type of subject (LOCAL_USER|GLOBAL_USER|GLOBAL_GROUP)
        :return: lxml.etree.Element
        '''
        return self._create(xdict)

    def update(self, **xdict):
        '''Update subject

        :param str xdict['realName']: Real name of subject 
        :param str xdict['email']: E-Mail address of subject 
        :param str xdict['description']: Short description of subject
        :param str xdict['digest']: Password as plaintext or bcrypt hash
        :param str xdict['timeZone']: Timezone for subject
        :param str xdict['language']: Language for subject
        :param str xdict['type']:  Type of subject (LOCAL_USER|GLOBAL_USER|GLOBAL_GROUP)
        :return: lxml.etree.Element
        '''
        if 'digest' in xdict:
            old_digest = self.xml.digest
            new_digest = xdict['digest']
            if self.digest_match_hash(new_digest, old_digest):
                xdict['digest'] = old_digest
        return self._update(xdict)

    def is_update_needed(self, **xdict):
        '''Check if update of subject is needed

        :param str xdict['realName']: Real name of subject 
        :param str xdict['email']: E-Mail address of subject 
        :param str xdict['description']: Short description of subject
        :param str xdict['digest']: Password as plaintext or bcrypt hash
        :param str xdict['timeZone']: Timezone for subject
        :param str xdict['language']: Language for subject
        :param str xdict['type']:  Type of subject (LOCAL_USER|GLOBAL_USER|GLOBAL_GROUP)
        :return: bool (True if needed), lxml.etree.Element (current), lxml.etree.Element (updated)
        '''
        if 'digest' in xdict:
            self.read()
            old_digest = self.xml.digest
            new_digest = xdict['digest']
            if self.digest_match_hash(new_digest, old_digest):
                xdict['digest'] = old_digest
        return self._is_update_needed(xdict)



class Group(Element):
    '''
        Class to manage a group
    '''
    FIELDS = OrderedDict()
    FIELDS['description'] = ''
    CHILDS = OrderedDict()
    CHILDS['roles'] = None
    ATTRIBUTES = {'name': ''}
    
    PRESERVED_FIELDS = ['description']

    TYPE = 'Group'
    TYPE_C = 'Groups'

    def create(self, **xdict):
        '''Create group

        :param str xdict['description']: Short description of group 
        :param list xdict['roles']: List of role :class:`lxml.objectify.ObjectifiedElement`s
        :return: lxml.etree.Element
        '''
        return self._create(xdict)

    def update(self, **xdict):
        '''Update group

        :param str xdict['description']: Short description of group 
        :param list xdict['roles']: List of role :class:`lxml.objectify.ObjectifiedElement`s
        :return: lxml.etree.Element
        '''
        return self._update(xdict)

    def is_update_needed(self, **xdict):
        '''Check if update of group is needed

        :param str xdict['description']: Short description of group 
        :param list xdict['roles']: List of role :class:`lxml.objectify.ObjectifiedElement`s
        :return: bool (True if needed), lxml.etree.Element (current), lxml.etree.Element (updated)
        '''
        return self._is_update_needed(xdict)



class Role(Element):
    '''
        Class to manage a role
    '''
    FIELDS = OrderedDict()
    FIELDS['application'] = ''
    FIELDS['description'] = ''
    CHILDS = OrderedDict()
    CHILDS['permissions'] = None
    ATTRIBUTES = {'name': ''}
    
    PRESERVED_FIELDS = ['description']

    TYPE = 'Role'
    TYPE_C = 'Roles'
    
    def __init__(self, name=None, parents=[]):
        '''
        :param str name: Name of entity
        :param list parents: List of :class:`Element` objects which are parents of the current entity
        '''
        self.name = name
        self.parents = parents
        self.url = self.get_url_dict()
        self.xml = self._get_xml_template_role()
        self.loaded = False
        self.modified = False
    
    def _get_xml_template_role(self):
        xml_template = self._get_xml_template()
        xml_template.application = self.parents[0].name
        return xml_template

    def create(self, **xdict):
        '''Create role

        :param str xdict['description']: Short description of role
        :param list xdict['permissions']: List of permission :class:`lxml.objectify.ObjectifiedElement`s
        :return: lxml.etree.Element
        '''
        return self._create(xdict)

    def update(self, **xdict):
        '''Update role

        :param str xdict['description']: Short description of role
        :param list xdict['permissions']: List of permission :class:`lxml.objectify.ObjectifiedElement`s
        :return: lxml.etree.Element
        '''
        return self._update(xdict)

    def is_update_needed(self, **xdict):
        '''Check if update of role is needed

        :param str xdict['description']: Short description of role
        :param list xdict['permissions']: List of permission :class:`lxml.objectify.ObjectifiedElement`s
        :return: bool (True if needed), lxml.etree.Element (current), lxml.etree.Element (updated)
        '''
        return self._is_update_needed(xdict)



class Permission(Element):
    '''
        Class to manage a permission
    '''
    FIELDS = OrderedDict()
    FIELDS['application'] = ''
    FIELDS['description'] = ''
    ATTRIBUTES = {'name': ''}
    
    PRESERVED_FIELDS = ['description']

    TYPE = 'Permission'
    TYPE_C = 'Permissions'
    
    def __init__(self, name=None, parents=[]):
        '''
        :param str name: Name of entity
        :param list parents: List of :class:`Element` objects which are parents of the current entity
        '''
        self.name = name
        self.parents = parents
        self.url = self._get_url_dict()
        self.xml = self._get_xml_template_permission()
        self.loaded = False
        self.modified = False
    
    def _get_xml_template_permission(self):
        xml_template = self._get_xml_template()
        xml_template.application = self.parents[0].name
        return xml_template

    def create(self, **xdict):
        '''Create permission

        :param str xdict['description']: Short description of permission
        :return: lxml.etree.Element
        '''
        return self._create(xdict)

    def update(self, **xdict):
        '''Update permission

        :param str xdict['description']: Short description of permission
        :return: lxml.etree.Element
        '''
        return self._update(xdict)

    def is_update_needed(self, **xdict):
        '''Check if update of permission is needed

        :param str xdict['description']: Short description of permission
        :return: (bool (True if needed), lxml.etree.Element (current), lxml.etree.Element (updated))
        '''
        return self._is_update_needed(xdict)
    
    

class Platform(Element):
    '''
        Class to manage the platform
    '''
    
    TYPE = 'Platform'
    TYPE_C = 'Platform'

    def reload(self):
        '''Reload Platform

        :return: bool (True if reloaded)
        '''
        if XMLClient().request('PUT', self.url['self'] + '/reload'):
            return True
        else:
            return False

    def delete(self):
        '''
        :raises appngizer.errors.ElementError: Method is not avaible for entity
        '''
        raise appngizer.errors.ElementError("Method not available for {0}({1})".format(self.__class__.__name__, self.name))



class Grant(Element):
    '''
        Class to manage a site application grant
    '''
    
    TYPE = 'Grant'
    TYPE_C = 'Grant'
    
    def _get_xml_template(self):
        Element = objectify.ElementMaker(annotate=False, namespace=self.XPATH_DEFAULT_NAMESPACE['a'])
        xml_template = Element.grant(
            site=self.name
        )
        return xml_template
    
    def load(self):
        '''Load grant data from Grants object
        :return: None
        '''
        log.debug("Load installed {0}({1})".format(self.__class__.__name__, self.name))
        grant = Grants(parents=self.parents).get_grant(self.name)
        if grant is not None:
            self._set_xml(grant)
            self.loaded = True
        else:
            raise appngizer.errors.ElementNotFound('Grant {} is not available'.format(self.name))
    
    def delete(self):
        '''
        :raises appngizer.errors.ElementError: Method is not avaible for entity
        '''
        raise appngizer.errors.ElementError("Method not available for {0}({1})".format(self.__class__.__name__, self.name))



class Database(Element):
    '''
        Class to manage site application databases of an appNG instance
    '''
    TYPE = 'Database'
    TYPE_C = 'Databases'
    FIELDS = OrderedDict()
    FIELDS['type'] = ''
    FIELDS['user'] = ''
    FIELDS['password'] = ''
    FIELDS['dbVersion'] = ''
    FIELDS['driver'] = ''
    FIELDS['url'] = ''
    FIELDS['ok'] = ''
    CHILDS = OrderedDict()
    ATTRIBUTES = {'id': ''}
    
    def _get_sharedsecret(self,xdict):
        '''Get the sharedsecret from platform properties
        :return: string
        '''
        if 'salt' in xdict:
            sharedseceret = xdict['salt']
        else:
            p_sharedsecret = Property('sharedSecret', parents=[ Platform() ])
            p_sharedsecret.load()
            sharedseceret = p_sharedsecret.xml.value.text
        return sharedseceret
    
    def update(self, **xdict):
        '''Update database

        :param str xdict['user']: DB user
        :param str xdict['password']: DB password 
        :param str xdict['driver']: DB driver to use 
        :param bool xdict['type']: DB type to use
        :param bool xdict['url']: DB URI
        :return: lxml.etree.Element
        '''
        return self._update(xdict)

    def is_update_needed(self, **xdict):
        '''Check if update of database is needed

        :param str xdict['user']: DB user
        :param str xdict['password']: DB password 
        :param str xdict['driver']: DB driver to use 
        :param bool xdict['type']: DB type to use
        :param bool xdict['url']: DB URI
        :return: bool (True if needed), lxml.etree.Element (current), lxml.etree.Element of (updated)
        '''
        if 'password' in xdict:
            xdict_copy = deepcopy(xdict) 
            xdict_copy['password'] = self.gen_password_hash(xdict['password'], self._get_sharedsecret(xdict))
        return self._is_update_needed(xdict_copy)
        
    def gen_password_hash(self, password, salt):
        '''Generate bcrypt hash from plaintext password and salt

        :param str password: Plaintext password
        :param str salt: Plaintext salt 
        :return: str
        '''
        salt_sha256 = hashlib.sha256(salt.encode())
        return bcrypt.hashpw(password, '$2a$13$' + salt_sha256.hexdigest())

    def delete(self):
        '''
        :raises appngizer.errors.ElementError: Method is not avaible for entity
        '''
        raise appngizer.errors.ElementError("Method not available for {0}({1})".format(self.__class__.__name__, self.name))



class Elements(Element):
    '''
        Abstract class of an appNGizer container element
    '''
    def _get_xml_template(self):
        '''Returns lxml.objectify.ObjectifiedElement template of entity:
        :return: lxml.objectify.ObjectifiedElement
        '''
        Element = objectify.ElementMaker(annotate=False, namespace=self.XPATH_DEFAULT_NAMESPACE['a'])
        xml_template = Element(self.TYPE_C.lower())
        return xml_template
    
    def delete(self):
        '''
        :raises appngizer.errors.ElementError: Method is not avaible for entity
        '''
        raise appngizer.errors.ElementError("Method not available for {0}({1})".format(self.__class__.__name__, self.name))
    def exist(self):
        '''
        :raises appngizer.errors.ElementError: Method is not avaible for entity
        '''
        raise appngizer.errors.ElementError("Method not available for {0}({1})".format(self.__class__.__name__, self.name))
    def is_update_needed(self, **xdict):
        '''
        :raises appngizer.errors.ElementError: Method is not avaible for entity
        '''
        raise appngizer.errors.ElementError("Method not available for {0}({1})".format(self.__class__.__name__, self.name))



class Sites(Elements):
    '''
        Class to manage sites
    '''
    TYPE = 'Site'
    TYPE_C = 'Sites'

    SUBELEMENTS = { 'site': [] }



class Repositories(Elements):
    '''
        Class to manage repositories
    '''
    TYPE = 'Repository'
    TYPE_C = 'Repositories'
    
    SUBELEMENTS = { 'repository': [] }



class Properties(Elements):
    '''
        Class to manage properties
    '''
    TYPE = 'Property'
    TYPE_C = 'Properties'
    
    SUBELEMENTS = { 'property': [] }



class Applications(Elements):
    '''
        Class to manage applications
    '''

    TYPE = 'Application'
    TYPE_C = 'Applications'

    SUBELEMENTS = { 'application': [] }



class Packages(Elements):
    '''
        Class to manage packages
    '''
    TYPE = 'Package'
    TYPE_C = 'Packages'
    
    SUBELEMENTS = { 'package': [] }
    
    def __init__(self, name=None, parents=[]):
        '''
        :param str name: Name of entity
        :param list parents: List of :class:`Element` objects which are parents of the current entity
        '''
        self.name = name
        self.parents = parents
        self.xml = self._get_xml_template()
        self.loaded = False
        self.modified = False
        
    def load(self):
        '''Load entity via GET and set self.xml from requests.Response.content
        :return: None
        '''
        log.debug("Load {0}({1})".format(self.__class__.__name__, self.name))
        
        packages = []
        repositories = []
        if len(self.parents) > 0 and type(self.parents[0]) == Repository:
            repo_obj = self.parents[0]
            repositories.append(repo_obj)
        else:
            repos_obj = Repositories()
            repos_obj.load()
            for repo in repos_obj.xml.repository:
                repo_obj = Repository(repo.get('name'))
                repositories.append(repo_obj)
        
        for repo in repositories:
            for list_pkg in repo.list_pkgs():
                if hasattr(list_pkg, 'package'):
                    for pkg in list_pkg.package:
                        packages.append(pkg)
        
        self.xml.package = packages
        self.sort_packages_by_version(self.xml)
        self.loaded = True
    
    def find(self, **xdict):
        '''Find all available packages of a package

        :param str xdict['name']*: Name of package
        :param dict xdict['filter']: Dictionary of field:value items to filter packages  
        :return: lxml.objectify.ObjectifiedElement
        '''
        packages = []
        repositories = []
        
        if len(self.parents) > 0 and type(self.parents[0]) == Repository:
            repo_obj = self.parents[0]
            repositories.append(repo_obj)
        else:
            repos_obj = Repositories()
            repos_obj.load()
            for repo in repos_obj.xml.repository:
                repo_obj = Repository(repo.get('name'))
                repositories.append(repo_obj)
        
        for repo in repositories:
            if repo.has_pkg(name=xdict['name']):
                for list_pkg in repo.list_pkg(name=xdict['name']):
                    for pkg in list_pkg.package:
                        if 'filter' in xdict:
                            filter_ok = True
                            for key,value in xdict['filter'].iteritems():
                                if pkg.findtext(self.NS_PREFIX+key) != value:
                                    filter_ok = False
                                    break
                            if filter_ok:
                                pkg.repository = repo.xml
                                packages.append(pkg)    
                        else:
                            pkg.repository = repo.xml
                            packages.append(pkg)

        packages_xml = self._get_xml_template()
        packages_xml.package = packages
        return self.sort_packages_by_version(packages_xml)

    def sort_packages_by_version(self, xml_obj):
        '''Sort packages by version

        :param lxml.objectify.ObjectifiedElement xml_obj: Packages ObjectifiedElement to sort
        :return: lxml.objectify.ObjectifiedElement
        '''
        packages = xml_obj.find(self.NS_PREFIX+'package')
        data = [] 
        if packages is not None and len(packages) > 0:
            for package in packages:
                version = package.findtext(self.NS_PREFIX+'version')
                timestamp = package.findtext(self.NS_PREFIX+'timestamp')
                if version is not None:
                    lversion = LooseVersion(version)
                else:
                    lversion = version
                data.append(( lversion, timestamp, package ))
            data.sort(reverse=True)
            packages[:] = [item[-1] for item in data]
        return xml_obj
    


class Subjects(Elements):
    '''
        Class to manage subjects
    '''
    TYPE = 'Subject'
    TYPE_C = 'Subjects'
    
    SUBELEMENTS = { 'subject': [] }



class Groups(Elements):
    '''
        Class to manage groups
    '''
    TYPE = 'Group'
    TYPE_C = 'Groups'
    
    SUBELEMENTS = { 'group': [] }



class Roles(Elements):
    '''
        Class to manage roles
    '''
    TYPE = 'Role'
    TYPE_C = 'Roles'
    
    SUBELEMENTS = { 'role': [] }



class Permissions(Elements):
    '''
        Class to manage permissions
    '''
    TYPE = 'Permission'
    TYPE_C = 'Permissions'
    
    SUBELEMENTS = { 'permission': [] }



class Grants(Elements):
    '''
        Class to manage site application grants
    '''
    
    SUBELEMENTS = { 'grant': [] }

    TYPE = 'Grant'
    TYPE_C = 'Grants'
    
    def get_url_dict(self):
        '''Return dictionary with url path components of the entity
        
           url['self'] url path to entity
           url['ancestor'] url path to entity type
           url['parents'] url path of parent entities
        
        :return: dict
        '''
        url = {'self': '', 'ancestor': '', 'parents': '', 'type': self.TYPE_C.lower()}

        # Determine parents URL path
        if hasattr(self, 'parents'):
            for parent in self.parents:
                url['parents'] = ''.join([ url['parents'], parent.url['self'] ])
        # Determine ancestor URL path
        url['ancestor'] = '/'.join([url['parents'], url['type']])
        # Determine self URL path
        if self.name == None:
            url['self'] = url['ancestor']
        else:
            url['self'] = '/'.join([url['ancestor'], self.name])
        return url
    
    def get_grant(self, name):
        '''Get grant ObjectifiedElement of a site
        :param str name: Name of site
        :return: lxml.objectify.ObjectifiedElement
        '''
        self.load_if_needed()
        grant = None
        if hasattr(self.xml, 'grant') and len(self.xml.grant) > 0:
            for g in self.xml.grant:
                if g.get('site') == name:
                    grant = g
                    break
        return grant

    def update_grant(self, name, is_granted):
        '''Update grant for a site
        :param str name: Name of site
        :param bool is_granted: Site is granted to access application
        :return: lxml.objectify.ObjectifiedElement
        '''
        self.load_if_needed()
        for g in self.xml.grant:
            if g.get('site') == name:
                # Do we really know what we are doing?
                g._setText(str(is_granted).lower())
                break
        request = XMLClient().request('PUT', self.url['self'], self.get_xml_str())
        self._set_xml(request.response)
        self.modified = True
        return self.convert_xml_obj_to_xml_element()
    def update_grants(self, grants=[]):
        '''Update all grants of a site application
        :param list grants: List of grant lxml.objectify.ObjectifiedElements
        :return: lxml.objectify.ObjectifiedElement
        '''
        self.load_if_needed()
        for arg_g in grants:
            arg_g_site, arg_g_is_granted = arg_g
            
            for g in self.xml.grant:
                if g.get('site') == arg_g_site:
                    # Do we really know what we are doing?
                    g._setText(str(arg_g_is_granted).lower())
                    break
        request = XMLClient().request('PUT', self.url['self'], self.get_xml_str())
        self._set_xml(request.response)
        self.modified = True
        return self.convert_xml_obj_to_xml_element()

    def is_update_needed(self, **xdict):
        '''Check if update of Grants is needed
        
        :param str xdict['grant']: List of grant lxml.objectify.ObjectifiedElements
        :return: bool (True if needed), lxml.etree.Element (current), lxml.etree.Element (updated)
        '''
        rc,o,n = self._is_update_needed(xdict)  
        return rc,o,n
    def _is_update_needed(self, xdict):
        self.load_if_needed()

        result = False
        new_obj = deepcopy(self)
        new_obj._set_xml(xdict)
      
        for ogrant in self.xml.grant:
          site = ogrant.get('site') 
          for ngrant in new_obj.xml.grant:
            if ngrant.get('site') == site:
              if ogrant.text != ngrant.text:
                result = True 
              break

        if len(self.parents) > 0: 
            parent_types = ' '.join( [p.TYPE for p in self.parents] )
            log.debug("Update needed for {} {}({}) is {}".format(parent_types, self.__class__.__name__, self.name, str(result)))
        else:
            log.debug("Update needed for {}({}) is {}".format(self.__class__.__name__, self.name, str(result)))

        return result, self.xml, new_obj.xml



class Databases(Elements):
    '''
        Class to manage databases
    '''
    TYPE = 'Database'
    TYPE_C = 'Databases'
    
    SUBELEMENTS = { 'database': [] }
