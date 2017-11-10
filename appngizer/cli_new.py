#!/usr/bin/python2.7
# encoding: utf-8
'''
    
    This module contains a rudimentary command line script which can be 
    used directly on the shell.
        
'''
import copy
import traceback
import json
import yaml

import appngizer
from appngizer.elements import *
from appngizer.utils.xmljson import BadgerFish, Yahoo

from argparse import ArgumentParser
from argparse import RawDescriptionHelpFormatter

from timeit import default_timer as timer

__all__ = []
__version__ = appngizer.__version__
__date__ = appngizer.__date__
__updated__ = appngizer.__updated__

def _init_xmlclient(**connection_args):
    if connection_args.get('connection_url',False) and connection_args.get('connection_ssecret',False):
        client = appngizer.client.XMLClient( connection_args.get('connection_url'),connection_args.get('connection_ssecret') ) 
    elif connection_args.get('connection_file',False):  
        with open( connection_args.get('connection_file') ) as connection_file:
            connection_data = json.load(connection_file)
            client = appngizer.client.XMLClient( connection_data.get('url'),connection_data.get('sharedsecret') )
    else:
        raise appngizer.errors.CLIError('No connection information are given')
    return client

def _get_parents(element,vargs):
    parents = None
    if element in ['property','properties']:
        parents = []
        if vargs.get('site',None):
            parents.append(Site(vargs['site']))
        if vargs.get('application',None):
            parents.append(Application(vargs['application']))
        if vargs.get('site',None) is None and vargs.get('application',False) is None:
            parents.append(Platform())
        return parents
    if element in ['package','packages']:
        parents = []
        if vargs.get('repository',None):
            parents.append(Repository(vargs['repository']))
        return parents
    if element in ['permission','permissions', 'role', 'roles']:
        parents = []
        if vargs.get('application',None):
            parents.append(Application(vargs['application']))
        return parents
    if element in ['database','databases']:
        parents = []
        if vargs.get('site',None):
            parents.append(Site(vargs['site']))
        if vargs.get('application',None):
            parents.append(Application(vargs['application']))
        return parents
    if element in ['grant']:
        parents = []
        parents.append(Site(vargs['gsite']))
        parents.append(Application(vargs['application']))
        return parents
    if element in ['grants']:
        parents = []
        parents.append(Site(vargs['gsite']))
        parents.append(Application(vargs['application']))
        return parents

def _get_childs(element,vargs,parents=None):
    childs = []
    if element in ['role']:
        for permission in vargs.get('permissions', []):
            permission = Permission(permission,parents=parents)
            permission._set_xml(permission.read())
            childs.append(permission)
    if element in ['group']:
        for role in vargs.get('roles', []):
            application, role = role.split(',')
            parent = Application(application)
            role = Role(role,parents=[parent])
            role._set_xml(role.read())
            childs.append(role)
    if element in ['subject']:
        for group in vargs.get('groups', []):
            group = Group(group)
            group._set_xml(group.read())
            childs.append(group)
    return childs

def _execute(nargs):
    '''Execute an appNG element operation
    :param : named arguments
    :return: ???
    '''
    
    # Determine element itself and desired operation from nargs.command splitted by '-'
    element_operation = nargs.command.split('-')[0]
    element_name = nargs.command.split('-')[1]
    element_title = element_name.title()
    
    vargs = copy.deepcopy(vars(nargs))
    
    parents = _get_parents(element_name, vargs)
    childs = _get_childs(element_name, vargs, parents)
    
    if element_name in ['role']:
        vargs['permissions'] = childs
        vargs.pop('application')
    if element_name in ['group']:
        vargs['roles'] = childs
    if element_name in ['subject']:
        vargs['groups'] = childs
    
    # Instance element object 
    if (element_name == 'site'):
        if vargs.get('name',False):
            element = eval('new' + element_title)(nargs.name)
        else:
            element = eval('new' + element_title)(parents=parents)
    else:
        if vargs.get('name',False):
            element = eval('' + element_title)(nargs.name,parents=parents)
        else:
            element = eval('' + element_title)(parents=parents)
    
    for key in vargs.keys():
        if key not in element.ALLOWED_FIELDS and key not in element.ALLOWED_CHILDS:
            if key == 'salt' and element_name == 'database' and cmd_name == 'update':
                pass
            elif key == 'site' and element_name == 'grant':
                pass
            else:
                vargs.pop(key)
    
    try:
        if element_operation == 'create':
            out = element.create(**vargs)
        if element_operation == 'read':
            if element_name in ['package','grant']:
                out = element.read(**vargs)
            else:
                out = element.read()
        if element_operation == 'update':
            out = element.update(**vargs)
        if element_operation == 'delete':
            out = element.delete()
        if element_operation == 'reload':
            out = element.reload()
        if element_operation == 'install':            
            out = element.install(**vargs)
        if element_operation == 'assign':
            if element_name == 'application':
                out = element.assign_by_name(nargs.site)
        if element_operation == 'deassign':
            if element_name == 'application':
                out = element.deassign_by_name(nargs.site)
        if element_operation == 'grant':
            out = element.grant(**vargs)
    except appngizer.errors.ElementError as e:
        raise
        
    return out

def _render_output(output, mode='XML'):
    if type(output) == bool:
        output = etree.fromstring('<bool>' + str(output) + '</bool>')
    elif type(output) != etree._Element:
        output = etree.fromstring('<output>' + str(output) + '</output>')

    output = _strip_ns_prefix(output)
    output = _strip_appngizer_specials(output)

    if mode == 'JSON':
        return json.dumps(BadgerFish().data(output))
    if mode == 'YAML':
        json_dump = json.dumps(Yahoo().data(output))
        json_dict = json.loads(json_dump) 
        return yaml.safe_dump(json_dict, allow_unicode=True, default_flow_style=False)
    else:
        return etree.tostring(output, encoding='UTF-8', xml_declaration=True, pretty_print=True)

def _strip_ns_prefix(xml):
    query = "descendant-or-self::*[namespace-uri()!='']"
    for element in xml.xpath(query):
        element.tag = etree.QName(element).localname
    etree.cleanup_namespaces(xml)
    return xml
def _strip_appngizer_specials(xml):
    query = "descendant-or-self::*[@self]"
    for element in xml.xpath(query):
        element.attrib.pop('self')
    query = "//links"
    for element in xml.xpath(query):
        element.getparent().remove(element)
    return xml

def get_argparser(formatter_class=RawDescriptionHelpFormatter):
    program_name = os.path.basename(sys.argv[0])
    program_version = "v%s" % __version__
    program_build_date = str(__updated__)
    program_version_message = '%%(prog)s %s (%s)' % (program_version, program_build_date)
    program_shortdesc = __doc__.split("\n")[1]
    program_license = '''%s

  Created by Björn Pritzel on %s.
  Copyright 2017 aiticon GmbH. All rights reserved.

  Licensed under the Apache License 2.0
  http://www.apache.org/licenses/LICENSE-2.0

  Distributed on an "AS IS" basis without warranties
  or conditions of any kind, either express or implied.

USAGE
''' % (program_shortdesc, str(__date__))

    # Setup argument parser
    parser = ArgumentParser(description=program_license, formatter_class=formatter_class)
    
    parser.add_argument("--verbose", '-v', dest="verbose", action="count", help="set verbosity level [default: %(default)s]")
    parser.add_argument('--version', action='version', version=program_version_message)
    parser.add_argument("--url", dest="cliurl", action="store", default='http://localhost:8080/appNGizer', help="URL to appNGizer REST API [default: %(default)s]")
    parser.add_argument('--secret', dest='clisharedsecret', action='store', default=None, help="Shared secret to use (yes it's unsecure to use it that way)")
    parser.add_argument('--file', dest='clifile', action='store', default=None, help="JSON connection file to use")
    parser.add_argument('--mode', dest='climode', action='store', default='YAML', help="Output mode to use (XML|JSON|YAML)")
    
    cmd_p = parser.add_subparsers(help='commands', dest='command')
    
    # Site / Sites       
    cs_p = cmd_p.add_parser('create-site', help='Create a new site')
    cs_p.add_argument('-n', dest='name', action='store', help='Name of site')
    cs_p.add_argument('-H', dest='host', action='store', help='Host of site')
    cs_p.add_argument('-d', dest='domain', action='store', help='Primary URL of site (incl. protocol, optional port)')
    cs_p.add_argument('-t', dest='description', action='store', default='', help='Short description of site')
    cs_p.add_argument('-e', dest='active', action='store_true', default=False, help='Enable site')
    cs_p.add_argument('-c', dest='createRepositoryPath', action='store_true', default=False, help='Create site repository directory')

    rss_p = cmd_p.add_parser('read-sites', help='Read all sites')
    rs_p = cmd_p.add_parser('read-site', help='Read a site')
    rs_p.add_argument('-n', dest='name', action='store', help='Name of site')

    us_p = cmd_p.add_parser('update-site', help='Update a site')
    us_p.add_argument('-n', dest='name', action='store', help='Name of site')
    us_p.add_argument('-H', dest='host', action='store', help='Host of site')
    us_p.add_argument('-d', dest='domain', action='store', help='Primary URL of site (incl. protocol, optional port)')
    us_p.add_argument('-t', dest='description', action='store', default='', help='Short description of site')
    us_p.add_argument('-e', dest='active', action='store_true', default=False,help='Enable site')
    us_p.add_argument('-c', dest='createRepositoryPath', action='store_true', default=False, help='Create site repository directory')
    
    ds_p = cmd_p.add_parser('delete-site', help='Delete site')
    ds_p.add_argument('-n', dest='name', action='store', help='Name of site')
    
    ers_p = cmd_p.add_parser('reload-site', help='Reload a site')
    ers_p.add_argument('-n', dest='name', action='store', help='Name of site')

    return parser

def main(argv=None): # IGNORE:C0111
    '''Command line options.'''

    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)

    try:
        # Get parser and parse arguments
        parser = get_argparser()
        nargs = parser.parse_args()
        # Verbose handling
        verbose = nargs.verbose
        if verbose == 1:
            logging.basicConfig(stream=sys.stdout, level=logging.INFO)
        elif verbose > 1:
            logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
        else:
            logging.basicConfig(stream=sys.stdout, level=logging.WARN)
        
        start = timer()
        
        # Create client session
        connection_args = {}
        if nargs.cliurl:
            connection_args['connection_url'] = nargs.cliurl
        if nargs.clisharedsecret:
            connection_args['connection_ssecret'] = nargs.clisharedsecret
        if nargs.clifile:    
            connection_args['connection_file'] = nargs.clifile
        _init_xmlclient(**connection_args)
        
        # Execute operation on element
        print('---------------------------------')
        print('Execute: {0} ({1})'.format(nargs.command,nargs.climode))
        print('---------------------------------')
        op = _execute(nargs)
        # Render output of op
        print(_render_output(op,nargs.climode))
        end = timer()
        print('Time taken: {0}s'.format(end - start))
        print('---------------------------------\n')        
        return True
    except KeyboardInterrupt:
        ### handle keyboard interrupt ###
        return 0
    except Exception:
        traceback.print_exc()
        return 2

def run():
    """
        Entry point for console_scripts
    """
    main(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
