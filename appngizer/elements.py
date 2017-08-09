# -*- coding: utf-8 -*-
'''
    
    This module contains all appNG entities which currently can managed
    via an appNGizer instance:
    
    - :class:`Property`
    - :class:`Site`
    - :class:`Repository`
    - :class:`Application`
    - :class:`Package`
    - :class:`Subject`
    - :class:`Group`
    - :class:`Role`
    - :class:`Permission`
    - :class:`Database`
    - :class:`Platform` (only for reload)
    
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

'''
import sys
import os
import logging
import bcrypt
import hashlib
from copy import deepcopy

from lxml import etree
from lxml import objectify

import appngizer.errors
from appngizer.client import XMLClient

log = logging.getLogger(__name__)


class Element(object):
    '''
        Abstract class of an appNGizer element
        All further appngizer elements will inherits from this class
    '''
    
    # : Dictionary of used namespace prefixes
    XPATH_DEFAULT_NAMESPACE = {'a': 'http://www.appng.org/schema/appngizer'}
    # : Path to appngizer xsd schema file as string
    XSD_APPNGIZER_PATH = (os.path.dirname(os.path.realpath(sys.modules[__name__].__file__))) + '/appngizer.xsd'
    # : List and order of entity fields which should be processed
    ALLOWED_FIELDS = []
    # : List and order of entity fields which should be preserved
    PRESERVED_FIELDS = ['description', 'displayName']
    # : List and order of entity child elements which should be processed
    ALLOWED_CHILDS = []
    # : List of entity child elements which should be processed via CDATA text
    ALLOWED_CDATA_FIELDS = []
    # : List and order of element attributes which should be processed
    ALLOWED_ATTRIBUTES = []
    # : Entity element name of the entity
    TYPE = 'Element'
    # : Entity element name of the entities
    TYPE_C = 'Elements'

    def __init__(self, name=None, parents=None, xml=None):
        '''
        :param str name: Name of entity
        :param list parents: List of :class:`Element` objects which are parents of the current entity
        :param lxml.etree.Element xml: xml representation of the entity
        '''
        self.name = name
        self.type = self.TYPE
        self.type_c = self.TYPE_C
        self.parents = self._set_parents(parents)
        self.url = self._set_url()
        self.xml = self._set_xml(xml)

    def __str__(self):
        '''String representation of the object

        :return: str
        '''
        return self.dump()

    def _set_parents(self, parents=None):
        '''Sets parents attribute if given
        
        :param list parents: list of appngizer element objects who are parents of the entity
        :return: list of appngizer element objects who are parents of the entity
        '''
        parent_elements = None
        if parents:
            parent_elements = []
            for parent in parents:
                parent_elements.append(parent)
        self.parents = parent_elements
        return parent_elements

    def _set_xml(self, xml):
        '''Sets self.xml attribute from a given arg xml or if None get xml from xml template method
        
        :param lxml.etree.Element xml: xml which should be set
        :return: xml which was set
        '''
        if xml is None:
            xml = self._get_xml_template()
        self.is_valide_xml(xml)
        self.xml = xml
        return xml

    def _set_url(self):
        '''Returns dictionary with various url paths of the entity

        :return: dict of url paths (f.e. self url, parent url)
        '''
        url = {'self':None, 'parent':None}
        if not self.parents:
            url['parent'] = self.type.lower()
            url['self'] = '/'.join([url['parent'], self.name])
        else:
            parents_url = ''
            for parent in self.parents:
                parents_url = '/'.join([parents_url, parent.url['self']])
            url['parent'] = '/'.join([parents_url, self.type.lower()])
            url['self'] = '/'.join([url['parent'], self.name])
        return url

    def _strip_ns_prefix(self, xml):
        '''Strip namespaces from xml

        :param lxml.etree.Element xml: xml which should be stripped
        :return: xml which was stripped
        '''
        query = "descendant-or-self::*[namespace-uri()!='']"
        for element in xml.xpath(query):
            element.tag = etree.QName(element).localname
            etree.cleanup_namespaces(xml)
        return xml

    def _update_xml_with_kwargs(self, xml, fdict):
        '''Updates etree with a given dictionary. Currently limited to a
        flat root/field/text() xml structure.

        Which fields and root attributes should be processed and in
        which order is controlled by ALLOWED_ATTRIBUTES|FIELDS|CHILDS.

        fields in PRESERVED_FIELDS will hold their text value even
        no value is given in the dict.
        
        :param lxml.etree.Element xml: xml which should be updated
        :param dict fdict: dictionary of fields which should be applied to the xml
        :return: xml which was updated, bool (True if xml was changed, False if xml was unchanged)
        '''
        log.info('Update etree for {0}({1}) with given fdict {2}'.format(self.type, self.name, fdict))
        log.debug('and given xml {}'.format(self.dump(xml)))

        is_changed = False

        # processing root attributes
        for attribute in self.ALLOWED_ATTRIBUTES:
            log.debug('Processing root attribute {}'.format(attribute))
            log_info = [attribute, self.type, self.name]

            xpath_attribute_selector = '/a:{}/@{}[1]'.format(self.type.lower(), attribute)
            xpath_attribute = xml.xpath(xpath_attribute_selector, namespaces=self.XPATH_DEFAULT_NAMESPACE)
            if len(xpath_attribute) > 0:
                xpath_attribute = xpath_attribute[0]
            else:
                xpath_attribute = None

            if attribute in fdict:
                if type(fdict[attribute]) == type(None):
                    # if value of fdict is None we try to delete the field element
                    log.info('Remove @{} for {}({})'.format(*log_info))
                    if xpath_attribute is not None:
                        xml.attrib.pop(attribute, None)
                        is_changed = True
                        log.info('XML was changed, @{} for {}({})'.format(*log_info))
                else:
                    # if value of fdict is not None we create or update the XML attribute
                    if type(fdict[attribute]) == type(True):
                        # Handle boolean as str.lower
                        text_value = str(fdict[attribute]).lower()
                    else:
                        # Otherwise we use always str
                        text_value = str(fdict[attribute])

                    if xpath_attribute is not None:
                        if xml.get(attribute) != text_value:
                            if xml.get(attribute) == None and text_value == '':
                                log.debug('Skip update @{} for {}({}) because we handle "" as text = None'.format(*log_info))
                            else:
                                xml.set(attribute, text_value)
                                is_changed = True
                                log.info('XML was changed, @{} for {}({})'.format(*log_info))
                        else:
                            log.debug('Skip update @{0} for {1}({2}) because there is no change'.format(*log_info))
                    else:
                        log.debug('Create @{0} for {1}({2}) with value "{3}"'.format(attribute, self.type, self.name, text_value))
                        xml.attrib[attribute] = text_value
                        is_changed = True
                        log.info('XML was changed, @{} for {}({})'.format(*log_info))

        # processing fields which are the 1st lvl childs of the root
        for field in self.ALLOWED_FIELDS:
            log.debug('Processing field {}'.format(field))
            log_info = [field, self.type, self.name]

            xpath_field_selector = '/a:{}/a:{}[1]'.format(self.type.lower(), field)
            xpath_fields = xml.xpath(xpath_field_selector, namespaces=self.XPATH_DEFAULT_NAMESPACE)
            if len(xpath_fields) > 0:
                xpath_field = xpath_fields[0]
            else:
                xpath_field = None

            if field in fdict:
                # if value of fdict is None we try to delete the field element
                if type(fdict[field]) == type(None) or str(fdict[field]).lower() == 'none':

                    if not field in self.PRESERVED_FIELDS:
                        log.info('Removed {} element for {}({})'.format(*log_info))
                        if xpath_field is not None:
                            xpath_field.getparent().remove(xpath_field)
                            is_changed = True
                            log.info('XML was changed in {} element for {}({})'.format(*log_info))
                    else:
                        log.debug('Didnt remove {} element for {}({}) because we should preserve it'.format(*log_info))
                else:
                    # if value of fdict is not None we create or update the XML element
                    if type(fdict[field]) == type(True):
                        # Handle boolean as str.lower
                        text_value = str(fdict[field]).lower()
                    else:
                        # Otherwise we use always str
                        text_value = str(fdict[field])

                    if xpath_field is not None:
                        if xpath_field.text != text_value:
                            if xpath_field.text == None and text_value == '':
                                log.debug('Skip update {} element for {}({}) because we handle "" as text = None'.format(*log_info))
                            else:
                                if field in self.ALLOWED_CDATA_FIELDS:
                                    text_value = etree.CDATA(text_value)

                                xpath_field.text = text_value
                                is_changed = True
                                log.info('XML was changed in {} element for {}({})'.format(*log_info))
                        else:
                            log.debug('Skip update {0} element for {1}({2}) because there is no change'.format(*log_info))
                    else:
                        log.debug('Create {0} element for {1}({2}) with value "{3}"'.format(field, self.type, self.name, text_value))

                        # add +1 offset if links element is in xml
                        xpath_links_selector = '/a:{}/a:{}[1]'.format(self.type.lower(), 'links')
                        xpath_links = xml.xpath(xpath_links_selector, namespaces=self.XPATH_DEFAULT_NAMESPACE)

                        if len(xpath_links) == 1:
                            xml.insert(self.ALLOWED_FIELDS.index(field) + 1, etree.Element("{http://www.appng.org/schema/appngizer}" + "{0}".format(field)))
                        else:
                            xml.insert(self.ALLOWED_FIELDS.index(field), etree.Element("{http://www.appng.org/schema/appngizer}" + "{0}".format(field)))

                        xpath_fields = xml.xpath(xpath_field_selector, namespaces=self.XPATH_DEFAULT_NAMESPACE)
                        if len(xpath_fields) > 0:
                            xpath_field = xpath_fields[0]
                        else:
                            xpath_field = None

                        if field in self.ALLOWED_CDATA_FIELDS:
                            text_value = etree.CDATA(text_value)

                        xpath_field.text = text_value
                        log.debug('Created {0} element for {1}({2}) with value "{3}"'.format(field, self.type, self.name, text_value))
                        is_changed = True
                        log.info('XML was changed in {} element for {}({})'.format(*log_info))
        # processing child entities which are also 1st lvl childs of the root
        for childs in self.ALLOWED_CHILDS:
            log.debug('Processing child {}'.format(childs))
            log_info = [childs, self.type, self.name]

            xpath_childs_selector = '/a:{}/a:{}[1]'.format(self.type.lower(), childs)
            xpath_childs = xml.xpath(xpath_childs_selector, namespaces=self.XPATH_DEFAULT_NAMESPACE)

            if childs in fdict:
                for fchild in fdict.get(childs, []):
                    fchild_name = fchild.xml.get('name')

                    if len(xpath_childs[0].xpath('a:*[@name="{}"]'.format(fchild_name), namespaces=self.XPATH_DEFAULT_NAMESPACE)) == 0:
                        log.debug('Create {0} child-element for {1}({2})'.format(childs, self.type, self.name))
                        xpath_childs[0].append(fchild.xml)
                        is_changed = True
                        log.debug('Created {0} child-element for {1}({2})'.format(childs, self.type, self.name))

                for xchild in xpath_childs[0].xpath('a:*', namespaces=self.XPATH_DEFAULT_NAMESPACE):
                    xchild_name = xchild.get('name')
                    xchild_delete = True
                    for fchild in fdict.get(childs, []):
                        fchild_name = fchild.xml.get('name')
                        if fchild_name == xchild_name:
                            xchild_delete = False
                    if xchild_delete:
                        log.debug('Remove {0} child-element for {1}({2})'.format(childs, self.type, self.name))
                        xchild.getparent().remove(xchild)
                        is_changed = True
                        log.debug('Removed {0} child-element for {1}({2})'.format(childs, self.type, self.name))

        # only set @name if self.name is not empty
        if self.name != None and self.name != '':
            xml.set('name', self.name)

        log.info('Updated etree for {0}({1}) with given fdict {2}'.format(self.type, self.name, fdict))
        log.debug('and the xml result is: {}'.format(self.dump(xml)))
        return xml, is_changed

    def _get_xml_template(self):
        '''Generates and returns empty etree xml representation of the entity

        :return: xml template of the entity
        '''
        xml_template = etree.Element('{' + self.XPATH_DEFAULT_NAMESPACE['a'] + '}' + '{0}'.format(self.type.lower()))
        return xml_template

    def _create(self, fdict):
        '''Creates entity from a given dict

        :param dict fdict: dictionary of fields for the new entity
        :return: xml of the created entity
        '''
        self.xml = self._update_xml_with_kwargs(self.xml, fdict)[0]
        if self.is_valide_xml(self.xml):
            if not self.exist():
                log.info('Create {0}({1})'.format(self.type, self.name))
                request = XMLClient().request('POST', self.url['parent'], str(self))
                response_xml = request.response_transf
                self._set_xml(self.read())
                return response_xml
            else:
                log.error("Create failed. {0}({1}) already exist".format(self.type, self.name))
                raise appngizer.errors.ElementError("Create failed. {0}({1}) already exist".format(self.type, self.name))
        else:
            log.error("Current XML for {0}({1}) does not validate".format(self.type, self.name))
            raise appngizer.errors.ElementError("Current XML for {0}({1}) does not validate: {2}".format(self.type, self.name, self.dump()))

    def _read(self):
        '''Reads entity and return as etree

        :return: xml of the entity
        '''
        request = XMLClient().request('GET', self.url['self'])
        response_xml = request.response_transf
        return response_xml

    def _update(self, fdict):
        '''Updates entity from a given dict

        :param dict fdict: dictionary of fields for the existing entity
        :return: xml of the updated entity
        '''
        self._set_xml(self.read())
        if self._is_update_needed(fdict)[0]:
            log.info('Update {0}({1})'.format(self.type, self.name))
            self.xml = self._update_xml_with_kwargs(self.xml, fdict)[0]
            if self.is_valide_xml(self.xml):
                request = XMLClient().request('PUT', self.url['self'], str(self))
                response_xml = request.response_transf
                self._set_xml(self.read())
                return response_xml
            else:
                log.error("Current XML for {0}({1}) does not validate".format(self.type, self.name))
                raise appngizer.errors.ElementError("Current XML for {0}({1}) does not validate: {2}".format(self.type, self.name, self.dump()))
        else:
            log.warn("No update needed for {0}({1})".format(self.type, self.name))
            return self.xml

    def _delete(self):
        '''Deletes entity

        :return: bool (True if was successfully)
        '''
        if self.exist():
            log.info("Delete {0}({1})".format(self.type, self.name))
            XMLClient().request('DELETE', self.url['self'])
            return True
        else:
            raise appngizer.errors.ElementError("Element does not exist")

    def _exist(self):
        '''Checks if entity already exist

        :return: bool (True if exist, False if not exist)
        '''
        element_exist = False
        elements_xml = eval(self.type_c)(None, self.parents)._read()
        for element_xml in list(elements_xml):
            if element_xml.get('name') == self.name:
                log.debug(self.dump(element_xml))
                element_exist = True
                break
        log.info("Checked if {}({}) already exist and this is {}".format(self.type, self.name, element_exist))
        return element_exist

    def _is_update_needed(self, fdict):
        '''Checks if update of entity is needed

        :param dict fdict: dictionary of fields for the existing entity
        :return: bool (True if needed, False if not needed), xml of current entity, xml of desired entity
        '''
        current_xml = self.read()
        desired_element = eval(self.type)(self.name, self.parents)
        desired_element.xml = deepcopy(current_xml)
        desired_xml, is_update_needed = desired_element._update_xml_with_kwargs(desired_element.xml, fdict)
        log.info('Checked if update is needed for {0}({1}) and this is {2}'.format(self.type, self.name, str(is_update_needed)))
        return is_update_needed, current_xml, desired_xml

    def read(self):
        '''Reads entity

        :return: xml of the entity
        '''
        log_info = [self.type, self.name]
        log.info("Read {}({})".format(*log_info))
        return self._read()

    def delete(self):
        '''Deletes entity

        :return: bool (True if successfully)
        '''
        return self._delete()

    def exist(self):
        '''Checks if entity already exist

        :return: bool (True if exist, False if not exist)
        '''
        return self._exist()

    def dump(self, xml=None):
        '''Pretty print an etree as string
        
        :param lxml.etree.Element xml: xml to be pretty printed, if not given self.xml is used
        :return: string with pretty printed xml
        '''
        if xml is None:
            return etree.tostring(self.xml, encoding='UTF-8', xml_declaration=True, pretty_print=True)
        else:
            return etree.tostring(xml, encoding='UTF-8', xml_declaration=True, pretty_print=True)

    def is_valide_xml(self, xml=None):
        '''Validates a xml against the appNGizer xsd schema

        :param lxml.etree.Element xml: xml to be validated, if not given self.xml attribute is used
        :return: bool (True if validates)
        '''
        doc = file(self.XSD_APPNGIZER_PATH, 'r')
        xsd_schema_doc = etree.parse(doc)
        xsd_schema = etree.XMLSchema(xsd_schema_doc)
        if xml is None:
            xml = self.xml
        try:
            xsd_schema.assertValid(xml)
            is_valide_xml = True
        except etree.DocumentInvalid as e:
            is_valide_xml = False
        except:
            raise
        return is_valide_xml


class Site(Element):
    '''
        Class to manage a site of an appNG instance
    '''
    
    ALLOWED_FIELDS = ['host', 'domain', 'description', 'active', 'createRepositoryPath']
    TYPE = 'Site'
    TYPE_C = 'Sites'

    def _get_xml_template(self):
        Element = objectify.ElementMaker(annotate=False, namespace=self.XPATH_DEFAULT_NAMESPACE['a'])
        xml_template = Element.site(
            Element.host(),
            Element.domain(),
            Element.description(),
            Element.active('false'),
            Element.createRepositoryPath('false'),
            name=''
        )
        xml_etree = etree.fromstring(etree.tostring(xml_template))
        return xml_etree

    def create(self, host, domain, description=None, active=True, createRepositoryPath=True):
        '''Creates a new site

        :param str host: host header
        :param str domain: primary domain with protocol
        :param str description: short description
        :param bool active: activate site
        :param bool createRepositoryPath: create site directory in repository
        :return: xml of created site
        '''
        fdict = dict([(i, locals()[i]) for i in (self.ALLOWED_FIELDS)])
        return self._create(fdict)

    def update(self, host, domain, description=None, active=True, createRepositoryPath=True):
        '''Updates an existing site

        :param str host: host header
        :param str domain: primary domain with protocol
        :param str description: short description
        :param bool active: activate site
        :param bool createRepositoryPath: create site directory in repository
        :return: xml of updated site
        '''
        fdict = dict([(i, locals()[i]) for i in (self.ALLOWED_FIELDS)])
        return self._update(fdict)

    def is_update_needed(self, host, domain, description=None, active=True, createRepositoryPath=True):
        '''Checks if update of site is needed

        :param str host: host header
        :param str domain: primary domain with protocol
        :param str description: short description
        :param bool active: activate site
        :param bool createRepositoryPath: create site directory in repository
        :return: bool (True if needed, False if not needed), xml of current site, xml of desired site
        '''
        fdict = dict([(i, locals()[i]) for i in (self.ALLOWED_FIELDS)])
        return self._is_update_needed(fdict)

    def reload(self):
        '''Reloads a site

        :return: bool (True if reloaded, False if not reloaded)
        '''
        if self.exist():
            if XMLClient().request('PUT', self.url['self'] + '/reload'):
                return True
            else:
                return False
        else:
            return False


class Repository(Element):
    '''
        Class to manage repositories of an appNG instance
    '''
    
    ALLOWED_FIELDS = ['description', 'remoteName', 'uri', 'enabled', 'strict', 'published', 'mode', 'type']
    TYPE = 'Repository'
    TYPE_C = 'Repositories'

    def _get_xml_template(self):
        Element = objectify.ElementMaker(annotate=False, namespace=self.XPATH_DEFAULT_NAMESPACE['a'])
        xml_template = Element.repository(
            Element.description(),
            Element.remoteName(),
            Element.uri('file:/'),
            Element.enabled('false'),
            Element.strict('false'),
            Element.published('false'),
            Element.mode('LOCAL'),
            Element.type('ALL'),
            Element.packages(),
            name=''
        )
        xml_etree = etree.fromstring(etree.tostring(xml_template))
        return xml_etree

    def create(self, uri, type='LOCAL', remoteName=None, mode='ALL', enabled=True, strict=False, published=False, description=None):
        '''Creates a new repository

        :param str uri: uri to the packages (file:// or http|s://)
        :param str type: type of repository (LOCAL = local repository, REMOTE = remote repository)
        :param str remoteName: name of remote repository
        :param str mode: mode of repository (ALL = all packages, STABLE = only stable packages, SNAPSHOT = only snapshot packages)
        :param bool enabled: enable repository
        :param bool strict: use strict mode
        :param bool published: publish repository
        :param str description: short description
        :return: xml of created repository
        '''
        fdict = dict([(i, locals()[i]) for i in (self.ALLOWED_FIELDS)])
        return self._create(fdict)

    def update(self, uri, type='LOCAL', remoteName=None, mode='ALL', enabled=True, strict=False, published=False, description=None):
        '''Updates a repository

        :param str uri: uri to the packages (file:// or http|s://)
        :param str type: type of repository (LOCAL = local repository, REMOTE = remote repository)
        :param str remoteName: name of remote repository
        :param str mode: mode of repository (ALL = all packages, STABLE = only stable packages, SNAPSHOT = only snapshot packages)
        :param bool enabled: enable repository
        :param bool strict: use strict mode
        :param bool published: publish repository
        :param str description: short description
        :return: xml of updated repository
        '''
        fdict = dict([(i, locals()[i]) for i in (self.ALLOWED_FIELDS)])
        return self._update(fdict)

    def is_update_needed(self, uri, type='LOCAL', remoteName=None, mode='ALL', enabled=True, strict=False, published=False, description=None):
        '''Checks if update of repository is needed

        :param str uri: uri to the packages (file:// or http|s://)
        :param str type: type of repository (LOCAL = local repository, REMOTE = remote repository)
        :param str remoteName: name of remote repository
        :param str mode: mode of repository (ALL = all packages, STABLE = only stable packages, SNAPSHOT = only snapshot packages)
        :param bool enabled: enable repository
        :param bool strict: use strict mode
        :param bool published: publish repository
        :param str description: short description
        :return: bool (True if needed, False if not needed), xml of current repository, xml of desired repository
        '''
        fdict = dict([(i, locals()[i]) for i in (self.ALLOWED_FIELDS)])
        return self._is_update_needed(fdict)


class Property(Element):
    '''
        Class to manage properties of an appNG instance
    '''
    
    ALLOWED_FIELDS = ['value', 'defaultValue', 'description']
    ALLOWED_ATTRIBUTES = ['clob']
    PRESERVED_FIELDS = ['description', 'defaultValue']
    TYPE = 'Property'
    TYPE_C = 'Properties'

    def _get_xml_template(self):
        Element = objectify.ElementMaker(annotate=False, namespace=self.XPATH_DEFAULT_NAMESPACE['a'])
        xml_template = Element.property(
            Element.value(),
            Element.defaultValue(),
            Element.description(),
            name=''
        )
        xml_etree = etree.fromstring(etree.tostring(xml_template))
        return xml_etree

    def create(self, value, defaultValue=None, description=None, clob=False):
        '''Creates a new property

        :param str value: value of property
        :param str defaultValue: default value of property
        :param str description: short description
        :param bool clob: treat property value as clob
        :return: xml of created property
        '''
        fdict = dict([(i, locals()[i]) for i in (self.ALLOWED_FIELDS + self.ALLOWED_ATTRIBUTES)])
        if clob:
            self.ALLOWED_CDATA_FIELDS = ['value', 'defaultValue']
        return self._create(fdict)

    def update(self, value, defaultValue=None, description=None, clob=False):
        '''Updates a new property

        :param str value: value of property
        :param str defaultValue: default value of property
        :param str description: short description
        :param bool clob: treat property value as clob
        :return: xml of updated property
        '''
        fdict = dict([(i, locals()[i]) for i in (self.ALLOWED_FIELDS + self.ALLOWED_ATTRIBUTES)])
        if clob:
            self.ALLOWED_CDATA_FIELDS = ['value', 'defaultValue']
        return self._update(fdict)

    def is_update_needed(self, value, defaultValue=None, description=None, clob=None):
        '''Checks if update of property is needed

        :param str value: value of property
        :param str defaultValue: default value of property
        :param str description: short description
        :param bool clob: treat property value as clob
        :return: bool (True if needed, False if not needed), xml of current property, xml of desired property
        '''
        fdict = dict([(i, locals()[i]) for i in (self.ALLOWED_FIELDS + self.ALLOWED_ATTRIBUTES)])
        if clob:
            self.ALLOWED_CDATA_FIELDS = ['value', 'defaultValue']
        return self._is_update_needed(fdict)


class Application(Element):
    '''
        Class to manage applications of an appNG instance
    '''
    
    ALLOWED_FIELDS = ['displayName', 'core', 'fileBased', 'hidden', 'version']
    TYPE = 'Application'
    TYPE_C = 'Applications'

    def _get_xml_template(self):
        Element = objectify.ElementMaker(annotate=False, namespace=self.XPATH_DEFAULT_NAMESPACE['a'])
        xml_template = Element.application(
            Element.displayName(),
            Element.core('false'),
            Element.fileBased('false'),
            Element.hidden('false'),
            Element.version(),
            name=''
        )
        xml_etree = etree.fromstring(etree.tostring(xml_template))
        return xml_etree

    def read(self, site=None):
        '''Reads application from platform or if given from an assigned site

        :return: xml of application
        '''
        if site and type(site) is Site:
            read_url = '/'.join([site.url['self'], self.url['self']])
        else:
            read_url = self.url['self']
        request = XMLClient().request('GET', read_url)
        response_xml = request.response_transf
        return response_xml

    def update(self, hidden=False, core=False, fileBased=False, displayName=None):
        '''Updates an application

        :param bool hidden: hide application
        :param bool core: run as core application
        :param bool fileBased: store application filebased, otherwise databased
        :param str displayName: display name of application
        :return: xml of updated application
        '''

        fdict = dict([(i, locals()[i]) for i in (locals().keys())])
        return self._update(fdict)

    def delete(self):
        '''Deletes an application
        
        With additional check if application is assigned to any site before try to delete
            
        :return: bool (True if deleted)
        '''
        
        if self.exist():
            sites = Sites()
            sites_assigned = []
            is_assigned = False
            for site in sites.elements:
                if self.is_assigned(site):
                    is_assigned = True
                    sites_assigned.append(site)
            if is_assigned:
                raise appngizer.errors.ElementError("Delete {0}({1}) aborted, deassign from site/s({2}) first".format(self.type, self.name, ', '.join(sites_assigned)))
            XMLClient().request('DELETE', self.url['self'])
            return True
        else:
            log.error("Delete {0}({1}) failed, application does not exist".format(self.type, self.name))
            raise appngizer.errors.ElementError("Delete {0}({1}) failed, application does not exist")

    def is_update_needed(self, hidden=False, core=False, fileBased=False, displayName=None):
        '''Checks if update of application is needed

        :param bool hidden: hide application
        :param bool core: run as core application
        :param bool fileBased: store application filebased, otherwise databased
        :param str displayName: display name of application
        :return: bool (True if needed, False if not needed), xml of current application, xml of desired application
        '''
        fdict = dict([(i, locals()[i]) for i in (locals().keys())])
        return self._is_update_needed(fdict)

    def is_assigned(self, site=None):
        '''Checks if application is already assigned to a site

        :param elements.Site site: site object
        :return: bool (True if assigned, False if not assigned)
        '''
        if site is not None:
            is_assigned = False
            try:
                self.read(site)
                is_assigned = True
            except appngizer.errors.HttpElementNotFound:
                pass
            except:
                raise
            log.info("Checked if {0}({1}) already assigned on site {2} and this is {3}".format(self.type, self.name, site.name, is_assigned))
        else:
            is_assigned = False
            for site in Sites().elements:
                try:
                    self.read(site)
                    is_assigned = True
                except appngizer.errors.HttpElementNotFound:
                    pass
                except:
                    raise
                log.info("Checked if {0}({1}) already assigned on site {2} and this is {3}".format(self.type, self.name, site.name, is_assigned))
        return is_assigned

    def assign(self, site):
        '''Assigns application to a site

        :param elements.Site site: site object
        :return: xml of assigned application
        '''

        if self.exist():
            if site.exist():
                if not self.is_assigned(site):
                    log.info('Assign {0}({1}) to site {2}'.format(self.type, self.name, site.name))
                    self.xml = self.read()
                    request = XMLClient().request('POST', '/'.join([site.url['self'], self.url['self']]), str(self))
                    response_xml = request.response_transf
                    return response_xml
                else:
                    log.error('Assign {0}({1}) to site {2} failed, application already assigned'.format(self.type, self.name, site.name))
                    raise appngizer.errors.ElementError("Assign {0}({1}) to site {2} failed, application already assigned".format(self.type, self.name, site.name))
            else:
                log.error('Assign {0}({1}) to site {2} failed, site does not exist'.format(self.type, self.name, site.name))
                raise appngizer.errors.ElementError("Assign {0}({1}) to site {2} failed, site does not exist".format(self.type, self.name, site.name))
        else:
            log.error('Assign {0}({1}) to site {2} failed, application is not installed'.format(self.type, self.name, site.name))
            raise appngizer.errors.ElementError("Assign {0}({1}) to site {2} failed, application is not installed".format(self.type, self.name, site.name))
    def assign_by_name(self, site_name):
        '''Assigns application to a site via site_name

        :param elements.Site site_name: str
        :return: xml of assigned application
        '''
        site = Site(site_name)
        return self.assign(site)

    def deassign(self, site):
        '''Deassigns application from a site

        :param elements.Site site: site object
        :return: xml of deassigned application
        '''
        if self.exist():
            if site.exist():
                if self.is_assigned(site):
                    log.info('Deassign {0}({1}) to site {2}'.format(self.type, self.name, site.name))
                    self.xml = self.read(site)
                    request = XMLClient().request('DELETE', '/'.join([site.url['self'], self.url['self']]), str(self))
                    response_xml = request.response_transf
                    return response_xml
                else:
                    log.error('Deassign {0}({1}) to site {2} failed, application is not assigned to site'.format(self.type, self.name, site.name))
                    raise appngizer.errors.ElementError("Deassign {0}({1}) to site {2} failed, application is not assigned to site".format(self.type, self.name, site.name))
            else:
                log.error('Deassign {0}({1}) to site {2} failed, site does not exist'.format(self.type, self.name, site.name))
                raise appngizer.errors.ElementError("Deassign {0}({1}) to site {2} failed, site does not exist".format(self.type, self.name, site.name))
        else:
            log.error('Deassign {0}({1}) to site {2} failed, application is not installed'.format(self.type, self.name, site.name))
            raise appngizer.errors.ElementError("Deassign {0}({1}) to site {2} failed, application is not installed".format(self.type, self.name, site.name))
    def deassign_by_name(self, site_name):
        '''Deassigns application from a site via site_name

        :param elements.Site site_name: str
        :return: xml of deassigned application
        '''
        site = Site(site_name)
        return self.deassign(site)

    def deassign_from_all(self):
        '''Deassigns application from all sites

        :return: bool (True if deassigned)
        '''
        if self.exist():
            sites = Sites()
            for site in sites.elements:
                if self.is_assigned(site):
                    self.deassign(site)
            return True
        else:
            msg = 'Deassign {}({}) from all sites failed, application is not installed'.format(self.type, self.name)
            log.error(msg)
            raise appngizer.errors.ElementError(msg)


class Package(Element):
    '''
        Class to manage packages of an appNG instance
    '''
    
    ALLOWED_FIELDS = ['displayName', 'version', 'timestamp', 'release', 'snapshot', 'installed', 'type']
    TYPE = 'Package'
    TYPE_C = 'Packages'

    def _get_xml_template(self):
        E = objectify.ElementMaker(annotate=False, namespace=self.XPATH_DEFAULT_NAMESPACE['a'])
        xml_template = E.package(
            E.displayName(),
            E.version(),
            E.timestamp(),
            E.release(),
            E.snapshot(),
            E.installed('false'),
            E.type(),
            name=''
        )
        xml_etree = etree.fromstring(etree.tostring(xml_template))
        return xml_etree

    def _set_url(self):
        '''Returns dictionary with various url paths of the entity
        
        For a package there is no entity type path component

        :return: dict of url paths (f.e. self url, parent url)
        '''
        url = {'self':None, 'parent':None}
        parents_url = ''
        for parent in self.parents:
            parents_url = '/'.join([parents_url, parent.url['self']])
        url['parent'] = '/'.join([parents_url])
        url['self'] = '/'.join([url['parent'], self.name])
        return url

    def exist(self, version, timestamp=None):
        '''Checks if package exist

        :param str version: version of package
        :param str timestamp: timestamp of package
        :return: bool (True if exist, False if not exist)
        '''
        package_exist = False
        try:
            self.read(version, timestamp)
            package_exist = True
        except:
            pass
        log.info("Checked if {}({}) already exist and this is {}".format(self.type, self.name, package_exist))
        return package_exist

    def read(self, version, timestamp=None):
        '''Reads package
        
        :param str version: version of package
        :param str timestamp: timestamp of package
        :return: xml of package
        '''
        request = XMLClient().request('GET', self.url['self'])
        response_xml = request.response_transf
        package_xml = None

        for package_packages_xml in list(response_xml):
            if str(package_packages_xml.xpath("a:version/text()", namespaces=self.XPATH_DEFAULT_NAMESPACE)[0]) == version:
                if timestamp:
                    if str(package_packages_xml.xpath("a:timestamp/text()", namespaces=self.XPATH_DEFAULT_NAMESPACE)[0]) == timestamp:
                        package_xml = package_packages_xml
                        break
                else:
                    package_xml = package_packages_xml
                    break
        if package_xml is not None:
            log.info("Read {0}({1})".format(self.type, self.name))
            # We must return a copy here otherwise root element is still packages
            return deepcopy(package_xml)
        else:
            raise appngizer.errors.ElementError("Package ({}) does not exist in repository ({})".format(self.name, self.parents[0].name))

    def update(self, version, timestamp=None, type='APPLICATION'):
        '''Updates an installed package

        :param str version: version of package
        :param str timestamp: timestamp of package
        :param str type: type of package (APPLICATION|TEMPLATE)
        :return: xml of updated package
        '''
        # For an update the existing XML is read and set for the current element
        # Additional updates via kwargs
        fdict = dict([(i, locals()[i]) for i in (locals().keys())])

        if timestamp:
            log_info = [self.type, self.name, version, timestamp]
        else:
            log_info = [self.type, self.name, version, '']
        if self.exist(version, timestamp):
            if self.is_installed():
                is_update_needed = self.is_update_needed(version, timestamp)[0]
                if is_update_needed:
                    log.debug("Update {}({}) with version {} {}".format(*log_info))
                    self.xml = self._update_xml_with_kwargs(self.read(version, timestamp), fdict)[0]
                    self.is_valide_xml(self.xml)
                    XMLClient().request('PUT', self.url['parent'] + '/install', str(self))
                    if not self.is_installed():
                        msg = "{}({}) failed to update version {} {}".format(*log_info)
                        log.warn(msg)
                        raise appngizer.errors.ElementError(msg)
                    package_xml = self.read(version, timestamp)
                    return package_xml
            else:
                msg = "{}({}) is not installed".format(*log_info)
                log.error(msg)
                raise appngizer.errors.ElementError(msg)
        else:
            msg = "{}({}) is not available in version {} {}".format(*log_info)
            log.error(msg)
            raise appngizer.errors.ElementError(msg)

    def delete(self):
        '''Deletes a package

        :raises appngizer.errors.ElementError: delete is not avaible for packages
        '''
        log.error("Delete not available for {0}({1})".format(self.type, self.name))
        raise appngizer.errors.ElementError("Delete not available for {0}({1})".format(self.type, self.name))

    def is_update_needed(self, version, timestamp=None):
        '''Checks if update of an installed package is needed

        :param str version: version of package
        :param str timestamp: timestamp of package
        :return: bool (True if needed, False if not needed), xml of current package, xml of desired package
        '''
        
        # Check against the version/timestamp field
        if timestamp:
            log_info = [self.type, self.name, version, timestamp]
        else:
            log_info = [self.type, self.name, version, '']
        is_update_needed = False
        current_package_xml = None
        desired_package_xml = None
        if self.exist(version, timestamp) and self.is_installed():
            current_package_xml = self.read_installed()
            current_package_version = str(current_package_xml.xpath("a:version/text()", namespaces=self.XPATH_DEFAULT_NAMESPACE)[0])
            current_package_timestamp = str(current_package_xml.xpath("a:timestamp/text()", namespaces=self.XPATH_DEFAULT_NAMESPACE)[0])
            desired_package_xml = self.read(version, timestamp)
            desired_package_version = str(desired_package_xml.xpath("a:version/text()", namespaces=self.XPATH_DEFAULT_NAMESPACE)[0])
            desired_package_timestamp = str(desired_package_xml.xpath("a:timestamp/text()", namespaces=self.XPATH_DEFAULT_NAMESPACE)[0])
            if current_package_version != desired_package_version:
                if timestamp:
                    if current_package_timestamp != desired_package_timestamp:
                        is_update_needed = True
                else:
                    is_update_needed = True
        else:
            msg = "Failed to read information for {}({}) version {} {}".format(*log_info)
            log.error(msg)
            raise appngizer.errors.ElementError(msg)
        return is_update_needed, current_package_xml, desired_package_xml

    def is_installed(self):
        '''Checks if a package is already installed

        :return: bool (True if installed, False if not installed)
        '''
        is_installed = False
        try:
            self.read_installed()
            is_installed = True
        except appngizer.errors.HttpElementNotFound:
            pass
        except:
            raise
        log.info("Checked if {}({}) already exist and this is {}".format(self.type, self.name, is_installed))
        return is_installed

    def read_installed(self):
        '''Reads package which is already installed

        :return: xml of installed package
        '''
        request = XMLClient().request('GET', self.url['self'])
        response_xml = request.response_transf
        package_xml = None
        for package_packages_xml in list(response_xml):
            if str(package_packages_xml.xpath("a:installed/text()", namespaces=self.XPATH_DEFAULT_NAMESPACE)[0]) == 'true':
                package_xml = package_packages_xml
                break
        if package_xml is not None:
            log.info("Read {0}({1})".format(self.type, self.name))
            return package_xml
        else:
            raise appngizer.errors.HttpElementNotFound("Package ({}) is not installed".format(self.name))

    def install(self, version, timestamp=None, type='APPLICATION'):
        '''Installs a package
        
        :param str version: version of package
        :param str timestamp: timestamp of package
        :param str type: type of package (APPLICATION|TEMPLATE)
        :return: xml of installed package
        '''

        fdict = dict([(i, locals()[i]) for i in (locals().keys())])
        if timestamp:
            log_info = [self.type, self.name, version, timestamp]
        else:
            log_info = [self.type, self.name, version, '']
        if self.exist(version, timestamp):
            if not self.is_installed():
                self.xml = self.read(version, timestamp)
                self.xml = self._update_xml_with_kwargs(self.xml, fdict)[0]
                self.is_valide_xml(self.xml)
                XMLClient().request('PUT', self.url['parent'] + '/install', str(self))
                if not self.is_installed():
                    msg = "{}({}) failed to install version {} {}".format(*log_info)
                    log.error(msg)
                    raise appngizer.errors.ElementError(msg)
                package_xml = self.read(version, timestamp)
                log.info("Installed {}({}) with version {} {}".format(*log_info))
                log.debug(self.dump(package_xml))
                return package_xml
            else:
                msg = "{}({}) is already installed".format(*log_info)
                log.info(msg)
                raise appngizer.errors.ElementError(msg)
        else:
            msg = "{}({}) is not available in version {} {}".format(*log_info)
            log.info(msg)
            raise appngizer.errors.ElementError(msg)


class Subject(Element):
    '''
        Class to manage subjects of an appNG instance
    '''
    
    ALLOWED_FIELDS = ['realName', 'email', 'description', 'digest', 'timeZone', 'language', 'type']
    ALLOWED_CHILDS = ['groups']
    TYPE = 'Subject'
    TYPE_C = 'Subjects'

    def _get_xml_template(self):
        Element = objectify.ElementMaker(annotate=False, namespace=self.XPATH_DEFAULT_NAMESPACE['a'])
        xml_template = Element.subject(
            Element.realName(),
            Element.email(),
            Element.description(),
            Element.digest(),
            Element.timeZone('Europe/Berlin'),
            Element.language('en'),
            Element.type('LOCAL_USER'),
            Element.groups(),
            name=''
        )
        xml_etree = etree.fromstring(etree.tostring(xml_template))
        return xml_etree

    def get_digest_hash(self):
        '''Gets digest field value from subject

        :return: digest of subject as string
        '''
        subject_xml = self.read()
        subject_digest = subject_xml.xpath('/a:subject/a:digest', namespaces=self.XPATH_DEFAULT_NAMESPACE)
        return subject_digest[0].text

    def digest_match_hash(self, digest, hashed):
        '''Checks if digest match hash
        
        If digest does not start with '$2a$' it will handled as plaintext
        otherwise digest is directly matched against hashed
        
        :param str digest: digest of subject
        :param str hashed: bcrypt hash of digest to match
        :return: bool (True if match, False if not match)
        '''
        if digest.startswith('$2a$'):
            if digest == hashed:
                return True
            else:
                return False
        else:
            if bcrypt.hashpw(digest, hashed) == hashed:
                return True
            else:
                return False

    def create(self, realName, digest, email, description=None, language='en', type='LOCAL_USER', timeZone='Europe/Berlin', groups=[]):
        '''Creates a new subject

        :param str realName: real name
        :param str digest: digest of subject (can be plaintext or bcrypt hash ($2a$13$))
        :param str email: e-mail address
        :param str description: short description
        :param str language: language setting
        :param str type: subject type (LOCAL_USER|GLOBAL_USER|GLOBAL_GROUP)
        :param str timeZone: timezone setting
        :param list groups: list of :class:`Group` objects the subject should be assigned to
        :return: xml of created subject
        '''
        
        fdict = dict([(i, locals()[i]) for i in (locals().keys())])
        return self._create(fdict)

    def update(self, realName, digest, email, description=None, language='en', type='LOCAL_USER', timeZone='Europe/Berlin', groups=[]):
        '''Updates a subject

        :param str realName: real name
        :param str digest: digest of subject (can be plaintext or bcrypt hash ($2a$13$))
        :param str email: e-mail address
        :param str description: short description
        :param str language: language setting
        :param str type: subject type (LOCAL_USER|GLOBAL_USER|GLOBAL_GROUP)
        :param str timeZone: timezone setting
        :param list groups: list of :class:`Group` objects the subject should be assigned to
        :return: xml of updated subject
        '''
        if self.digest_match_hash(digest, self.get_digest_hash()):
            digest = self.get_digest_hash()
        fdict = dict([(i, locals()[i]) for i in (locals().keys())])
        return self._update(fdict)

    def is_update_needed(self, realName, digest, email, description=None, language='en', type='LOCAL_USER', timeZone='Europe/Berlin', groups=[]):
        '''Checks if update of subject is needed

        :param str realName: real name
        :param str digest: digest of subject (can be plaintext or bcrypt hash ($2a$13$))
        :param str email: e-mail address
        :param str description: short description
        :param str language: language setting
        :param str type: subject type (LOCAL_USER|GLOBAL_USER|GLOBAL_GROUP)
        :param str timeZone: timezone setting
        :param list groups: list of :class:`Group` objects the subject should be assigned to
        :return: bool (True if needed, False if not needed), xml of current subject, xml of desired subject
        '''
        if self.digest_match_hash(digest, self.get_digest_hash()):
            digest = self.get_digest_hash()
        fdict = dict([(i, locals()[i]) for i in (locals().keys())])
        return self._is_update_needed(fdict)


class Group(Element):
    '''
        Class to manage groups of an appNG instance.
    '''
    
    ALLOWED_FIELDS = ['description']
    ALLOWED_CHILDS = ['roles']
    TYPE = 'Group'
    TYPE_C = 'Groups'

    def _get_xml_template(self):
        Element = objectify.ElementMaker(annotate=False, namespace=self.XPATH_DEFAULT_NAMESPACE['a'])
        xml_template = Element.group(
            Element.description(),
            Element.roles(),
            name=''
        )
        xml_etree = etree.fromstring(etree.tostring(xml_template))
        return xml_etree

    def create(self, description=None, roles=[]):
        '''Creates a new group

        :param str description: short description
        :param list roles: list of :class:`Role` objects the group should be assigned to
        :return: xml of created group
        '''
        fdict = dict([(i, locals()[i]) for i in (locals().keys())])
        return self._create(fdict)

    def update(self, description=None, roles=[]):
        '''Updates a group

        :param str description: short description
        :param list roles: list of :class:`Role` objects the group should be assigned to
        :return: xml of updated group
        '''
        fdict = dict([(i, locals()[i]) for i in (locals().keys())])
        return self._update(fdict)

    def is_update_needed(self, description=None, roles=[]):
        '''Checks if update of group is needed

        :param str description: short description
        :param list roles: list of :class:`Role` objects the group should be assigned to
        :return: bool (True if needed, False if not needed), xml of current group, xml of desired group
        '''
        fdict = dict([(i, locals()[i]) for i in (locals().keys())])
        return self._is_update_needed(fdict)


class Role(Element):
    '''
        Class to manage roles of an appNG instance
    '''
    
    ALLOWED_FIELDS = ['application', 'description']
    ALLOWED_CHILDS = ['permissions']
    TYPE = 'Role'
    TYPE_C = 'Roles'

    def _get_xml_template(self):
        Element = objectify.ElementMaker(annotate=False, namespace=self.XPATH_DEFAULT_NAMESPACE['a'])
        xml_template = Element.role(
            Element.application(),
            Element.description(),
            Element.permissions(),
            name=''
        )
        xml_etree = etree.fromstring(etree.tostring(xml_template))
        return xml_etree

    def create(self, description=None, permissions=[]):
        '''Creates a new role

        :param str description: short description
        :param list permissions: list of :class:`Permission` objects the role should be assigned to
        :return: xml of created role
        '''
        # We have to set an explicit application element which we can create from the parent element
        fdict = dict([(i, locals()[i]) for i in (locals().keys())])
        fdict.update({'application':self.parents[0].name})
        return self._create(fdict)

    def update(self, description=None, permissions=[]):
        '''Updates a role

        :param str description: short description
        :param list permissions: list of :class:`Permission` objects the role should be assigned to
        :return: xml of updated role
        '''
        # We have to set an explicit application element which we can create from the parent element
        fdict = dict([(i, locals()[i]) for i in (locals().keys())])
        fdict.update({'application':self.parents[0].name})
        return self._update(fdict)

    def is_update_needed(self, description=None, permissions=[]):
        '''Checks if update of role is needed

        :param str description: short description
        :param list permissions: list of :class:`Permission` objects the role should be assigned to
        :return: bool (True if needed, False if not needed), xml of current role, xml of desired role
        '''
        # We have to set an explicit application element which we can create from the parent element
        fdict = dict([(i, locals()[i]) for i in (locals().keys())])
        fdict.update({'application':self.parents[0].name})
        return self._is_update_needed(fdict)


class Permission(Element):
    '''
        Class to manage roles of an appNG instance
    '''
    
    ALLOWED_FIELDS = ['description']
    TYPE = 'Permission'
    TYPE_C = 'Permissions'

    def _get_xml_template(self):
        Element = objectify.ElementMaker(annotate=False, namespace=self.XPATH_DEFAULT_NAMESPACE['a'])
        xml_template = Element.permission(
            Element.application(),
            Element.description(),
            name=''
        )
        xml_etree = etree.fromstring(etree.tostring(xml_template))
        return xml_etree

    def create(self, description=None):
        '''Creates a new permission

        :param str description: short description
        :return: xml of created permission
        '''
        # We have to set an explicit application element which we can create from the parent element
        fdict = dict([(i, locals()[i]) for i in (locals().keys())])
        fdict.update({'application':self.parents[0].name})
        return self._create(fdict)

    def update(self, description=None):
        '''Updates a permission

        :param str description: short description
        :return: xml of updated permission
        '''
        # We have to set an explicit application element which we can create from the parent element
        fdict = dict([(i, locals()[i]) for i in (locals().keys())])
        fdict.update({'application':self.parents[0].name})
        return self._update(fdict)

    def is_update_needed(self, description=None):
        '''Checks if update of permission is needed

        :param str description: short description
        :return: xml of updated permission
        :return: bool (True if needed, False if not needed), xml of current permission, xml of desired permission
        '''
        # We have to set an explicit application element which we can create from the parent element
        fdict = dict([(i, locals()[i]) for i in (locals().keys())])
        fdict.update({'application':self.parents[0].name})
        return self._is_update_needed(fdict)


class Platform(Element):
    '''
        Class to manage the platform of an appNG instance.
    '''
    
    ALLOWED_FIELDS = []
    TYPE = 'Platform'
    TYPE_C = 'Platform'

    def __init__(self, name='', parents=None, xml=None):
        # : Platform entity does not have a name attribute, we set it to an empty string
        self.name = ''
        self.type = self.TYPE
        self.type_c = self.TYPE_C
        self.parents = self._set_parents(parents)
        self.url = self._set_url()
        self.xml = self._set_xml(xml)

    def read(self):
        '''Reads a platform

        :raise errors.ElementError: read is not avaible for platform
        '''
        msg = "read not available for {0}({1})".format(self.type, self.name)
        log.error(msg)
        raise appngizer.errors.ElementError(msg)

    def delete(self):
        '''Deletes a platform

        :raise errors.ElementError: delete is not avaible for platform
        '''
        msg = "delete not available for {0}({1})".format(self.type, self.name)
        log.error(msg)
        raise appngizer.errors.ElementError(msg)

    def exist(self):
        '''Checks if platform already exist

        :raise errors.ElementError: exist is not avaible for platform
        '''
        msg = "exist not available for {0}({1})".format(self.type, self.name)
        log.error(msg)
        raise appngizer.errors.ElementError(msg)

    def reload(self):
        '''Reloads a platform

        :return: bool (True if reloaded, False if not reloaded)
        '''
        if XMLClient().request('POST', self.url['self'] + '/reload'):
            return True
        else:
            return False


class Database(Element):
    '''
        Class to manage databases of an appNG instance
    '''
    
    ALLOWED_FIELDS = ['user', 'password', 'driver', 'url']
    TYPE = 'Database'
    TYPE_C = 'Databases'

    def __init__(self, name='', parents=None, xml=None):
        # : Database entity does not have a name attribute, we set it to an empty string
        self.name = ''
        self.type = self.TYPE
        self.type_c = self.TYPE_C
        self.parents = self._set_parents(parents)
        self.url = self._set_url()
        self.xml = self._set_xml(xml)

    def _get_xml_template(self):
        Element = objectify.ElementMaker(annotate=False, namespace=self.XPATH_DEFAULT_NAMESPACE['a'])
        xml_template = Element.database(
            Element.type(),
            Element.user(),
            Element.password(),
            Element.dbVersion(),
            Element.driver(),
            Element.url(),
            Element.ok(),
            id=''
        )
        xml_etree = etree.fromstring(etree.tostring(xml_template))
        return xml_etree

    def _exist(self):
        '''Checks if database already exist
        
        Currently we only check if read was succesfully and contains an database element

        :return: bool (True if exist, False if not exist)
        '''
        element_exist = False
        elements_xml = eval(self.type_c)(None, self.parents)._read()
        if elements_xml.tag == '{http://www.appng.org/schema/appngizer}database':
            element_exist = True
        log.info("Checked if {}({}) already exist and this is {}".format(self.type, self.name, element_exist))
        return element_exist
        
    def _update(self, fdict):
        '''Updates entity from a given dict

        :param dict fdict: dictionary of fields for the existing entity
        :return: xml of the updated entity
        '''
        self._set_xml(self.read())
        # hack to change fdict['password'] to original value
        plain_password = fdict['password']
        if self._is_update_needed(fdict)[0]:
            log.info('Update {0}({1})'.format(self.type, self.name))
            # hack to change fdict['password'] to original value
            fdict['password'] = plain_password
            self.xml = self._update_xml_with_kwargs(self.xml, fdict)[0]
            if self.is_valide_xml(self.xml):
                request = XMLClient().request('PUT', self.url['self'], str(self))
                response_xml = request.response_transf
                self._set_xml(self.read())
                return response_xml
            else:
                log.error("Current XML for {0}({1}) does not validate".format(self.type, self.name))
                raise appngizer.errors.ElementError("Current XML for {0}({1}) does not validate: {2}".format(self.type, self.name, self.dump()))
        else:
            log.warn("No update needed for {0}({1})".format(self.type, self.name))
            return self.xml

    def _is_update_needed(self, fdict):
        '''Checks if update of entity is needed

        :param dict fdict: dictionary of fields for the existing entity
        :return: bool (True if needed, False if not needed), xml of current entity, xml of desired entity
        '''
        # change password in fdict to a bcrypt hash because read() will 
        # always give us a bcrypt hash instead of plaintext password
        salt = fdict['salt']
        salt_sha256 = hashlib.sha256(salt.encode())
        password_hash = bcrypt.hashpw(fdict['password'], '$2a$13$' + salt_sha256.hexdigest())
        fdict['password'] = password_hash

        current_xml = self.read()
        desired_element = eval(self.type)(self.name, self.parents)
        desired_element.xml = deepcopy(current_xml)
        desired_xml, is_update_needed = desired_element._update_xml_with_kwargs(desired_element.xml, fdict)
        log.info('Checked if update is needed for {0}({1}) and this is {2}'.format(self.type, self.name, str(is_update_needed)))
        return is_update_needed, current_xml, desired_xml

    def create(self):
        '''Creates a database

        :raise errors.ElementError: create is not avaible for database
        '''
        msg = "create not available for {0}({1})".format(self.type, self.name)
        log.error(msg)
        raise appngizer.errors.ElementError(msg)

    def delete(self):
        '''Delete a database
        
        :raise errors.ElementError: delete is not avaible for database
        '''
        msg = "Delete not available for {0}({1})".format(self.type, self.name)
        log.error(msg)
        raise appngizer.errors.ElementError(msg)

    def update(self, user, password, salt, driver, url):
        '''Updates a database

        :param str user: database username
        :param str password: database password
        :param str salt: salt (appNGizer uses platform.sharedsecret) to generate bcrypt hash of password
        :param str driver: jdbc driver class
        :param str url: jdbc url of database
        :return: xml of updated database
        '''
        local_list = list(self.ALLOWED_FIELDS)
        local_list.append('salt')
        fdict = dict([(i, locals()[i]) for i in (local_list)])
        return self._update(fdict)

    def is_update_needed(self, user, password, salt, driver, url):
        '''Checks if update of database is needed

        :param str user: database username
        :param str password: database password
        :param str salt: salt (appNGizer uses platform.sharedsecret) to generate bcrypt hash of password
        :param str driver: jdbc driver class
        :param str url: jdbc url of database
        :return: bool (True if needed, False if not needed), xml of current database, xml of desired database
        '''
        local_list = list(self.ALLOWED_FIELDS)
        local_list.append('salt')
        fdict = dict([(i, locals()[i]) for i in (local_list)])
        return self._is_update_needed(fdict)


class Elements(Element):
    '''
        Abstract class of an appNGizer container element
        All further appngizer container elements will inherits from this class
        
        Currently only reading is implemented.
    '''

    def __init__(self, name='', parents=[], xml=None):
        '''
            :param list parents: List of :class:`Element` objects which are the parent of the current entity
            :param lxml.etree.Element xml: xml representation of the entity
        '''
        self.name = ''
        self.type = self.TYPE_C
        self.type_element = self.TYPE
        self.parents = parents
        self.url = self._set_url()
        self.xml = self._set_xml(xml)
        self.elements = self._set_elements()

    def _set_url(self):
        url = {'self':None}
        if not self.parents:
            url['self'] = self.type_element.lower()
        else:
            parents_url = ''
            for parent in self.parents:
                parents_url = '/'.join([parents_url, parent.url['self']])
            url['self'] = '/'.join([parents_url, self.type_element.lower()])
        return url

    def _set_elements(self):
        '''Sets and return list of all :class:`Element` objects
        
        :return: list of :class:`Element` objects
        '''
        elements = []
        elements_xml = self.read()
        for element_xml in list(elements_xml):
            elements.append(eval(self.type_element)(element_xml.get('name'), parents=self.parents))
        self.elements = elements
        return elements

    def _get_xml_template(self):
        xml_template = etree.Element('{' + self.XPATH_DEFAULT_NAMESPACE['a'] + '}' + '{0}'.format(self.type.lower()))
        return xml_template

    def exist(self):
        '''Check if entity already exist

        :raise errors.ElementError: exist is not avaible for entity
        '''
        msg = "exist not available for {0}({1})".format(self.type, self.name)
        log.error(msg)
        raise appngizer.errors.ElementError(msg)

    def delete(self):
        '''Deletes an entity

        :raise error.ElementError: delete is not avaible for entity
        '''
        msg = "delete not available for {0}({1})".format(self.type, self.name)
        log.error(msg)
        raise appngizer.errors.ElementError(msg)

    def is_update_needed(self, **kwargs):
        '''Checks if update of entity is needed
        
        :raise error.ElementError: is_update_needed is not avaible for entity
        '''
        msg = "is_update_needed not available for {0}({1})".format(self.type, self.name)
        log.error(msg)
        raise appngizer.errors.ElementError(msg)


class Sites(Elements):
    '''
        Class to manage sites of an appNG instance
    '''
    TYPE = 'Site'
    TYPE_C = 'Sites'


class Repositories(Elements):
    '''
        Class to manage repositories of an appNG instance
    '''
    TYPE = 'Repository'
    TYPE_C = 'Repositories'


class Properties(Elements):
    '''
        Class to manage properties of an appNG instance
    '''
    TYPE = 'Property'
    TYPE_C = 'Properties'


class Applications(Elements):
    '''
        Class to manage application of an appNG instance
    '''

    TYPE = 'Application'
    TYPE_C = 'Applications'

    def read(self, site=None):
        '''Reads applications global or if given from an assigned site

        :return: xml of the applications
        '''
        log.debug('Read {0}({1})'.format(self.type, self.name))
        if site and type(site) is Site:
            read_url = '/'.join(site.url['self'], self.url['self'])
        else:
            read_url = self.url['self']
        request = XMLClient().request('GET', read_url)
        response_xml = request.response_transf
        log.info("Read {0}({1})".format(self.type, self.name))
        log.debug(self.dump(response_xml))
        return response_xml


class Packages(Elements):
    '''
        Class to manage packages of an appNG instance
    '''
    TYPE = 'Package'
    TYPE_C = 'Packages'

    def _set_url(self):
        # For a package there is no entity type path component
        url = {'self':None}
        parents_url = self.parents[0].url['self']
        url['self'] = '/'.join([parents_url])
        return url

    def read(self):
        '''Reads packages from a repository

        :return: xml of the packages
        '''
        request = XMLClient().request('GET', self.url['self'])
        response_xml = request.response_transf
        packages_xml = response_xml.xpath('//a:packages', namespaces=self.XPATH_DEFAULT_NAMESPACE)[0]
        return packages_xml


class Subjects(Elements):
    '''
        Class to manage subjects of an appNG instance
    '''
    TYPE = 'Subject'
    TYPE_C = 'Subjects'


class Groups(Elements):
    '''
        Class to manage groups of an appNG instance
    '''
    TYPE = 'Group'
    TYPE_C = 'Groups'


class Roles(Elements):
    '''
        Class to manage roles of an appNG instance
    '''
    TYPE = 'Role'
    TYPE_C = 'Roles'


class Permissions(Elements):
    '''
        Class to manage permissions of an appNG instance
    '''
    TYPE = 'Permission'
    TYPE_C = 'Permissions'


class Databases(Elements):
    '''
        Class to manage databases of an appNG instance
    '''
    TYPE = 'Database'
    TYPE_C = 'Databases'

    def _set_elements(self):
        # Use @id instead of @name
        elements = []
        elements_xml = self.read()
        for element_xml in list(elements_xml):
            elements.append(eval(self.type_element)(element_xml.get('id'), parents=self.parents))
        self.elements = elements
        return elements
