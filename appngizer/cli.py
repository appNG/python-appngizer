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
    cmd_name = nargs.command.split('-')[0]
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
    
    if vargs.get('name',False):
        element = eval(element_title)(nargs.name,parents=parents)
    else:
        element = eval(element_title)(parents=parents)
    
    for key in vargs.keys():
        if key not in element.ALLOWED_FIELDS and key not in element.ALLOWED_CHILDS:
            if key == 'salt' and element_name == 'database' and cmd_name == 'update':
                pass
            else:
                vargs.pop(key)
    
    try:
        if cmd_name == 'create':
            out = element.create(**vargs)
        if cmd_name == 'read':
            if element_name == 'package':
                out = element.read(**vargs)
            else:
                out = element.read()
        if cmd_name == 'update':
            out = element.update(**vargs)
        if cmd_name == 'delete':
            out = element.delete()
        if cmd_name == 'reload':
            out = element.reload()
        if cmd_name == 'install':            
            out = element.install(**vargs)
        if cmd_name == 'assign':
            if element_name == 'application':
                out = element.assign_by_name(nargs.site)
        if cmd_name == 'deassign':
            if element_name == 'application':
                out = element.deassign_by_name(nargs.site)
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

    # propertie/s
    cp_p = cmd_p.add_parser('create-property', help='Create a new property')
    cp_p.add_argument('-n', dest='name', action='store', help='Name of property')
    cp_p.add_argument('-s', dest='site', action='store', help='Name of site')
    cp_p.add_argument('-a', dest='application', action='store', help='Name of application')
    cp_p.add_argument('-p', dest='value', action='store', help='Value of property')
    cp_p.add_argument('-d', dest='defaultValue', action='store', help='Default value of property')
    cp_p.add_argument('-t', dest='description', action='store', help='Short description of property')

    rps_p = cmd_p.add_parser('read-properties', help='Read all properties')
    rps_p.add_argument('-s', dest='site', action='store', help='Name of site')
    rps_p.add_argument('-a', dest='application', action='store', help='Name of application')
    rp_p = cmd_p.add_parser('read-property', help='Read a property')
    rp_p.add_argument('-n', dest='name', action='store', help='Name of property')
    rp_p.add_argument('-s', dest='site', action='store', help='Name of site')
    rp_p.add_argument('-a', dest='application', action='store', help='Name of application')
    
    up_p = cmd_p.add_parser('update-property', help='Update a property')
    up_p.add_argument('-n', dest='name', action='store', help='Name of property')
    up_p.add_argument('-s', dest='site', action='store', help='Name of site')
    up_p.add_argument('-a', dest='application', action='store', help='Name of application')
    up_p.add_argument('-p', dest='value', action='store', help='Value of property')
    up_p.add_argument('-d', dest='defaultValue', action='store', help='Default value of property')
    up_p.add_argument('-t', dest='description', action='store', help='Short description of property')
    
    dp_p = cmd_p.add_parser('delete-property', help='Delete a property')
    dp_p.add_argument('-n', dest='name', action='store', help='Name of property')
    dp_p.add_argument('-s', dest='site', action='store', help='Name of site')
    dp_p.add_argument('-a', dest='application', action='store', help='Name of application')

    # repositorie/s
    cr_p = cmd_p.add_parser('create-repository', help='Create a new repository')
    cr_p.add_argument('-n', dest='name', action='store', help='Name of site')
    cr_p.add_argument('-u', dest='uri', action='store', help='URI to repository (file:/ or http://)')
    cr_p.add_argument('-rn', dest='remoteName', action='store', help='Remote-Name if remote repository')
    cr_p.add_argument('-t', dest='description', action='store', help='Description of site')
    cr_p.add_argument('-m', dest='mode', action='store', default='ALL', choices=['ALL','STABLE','SNAPSHOT'], help='Mode of repository')
    cr_p.add_argument('-rt', dest='type', action='store', default='LOCAL', choices=['LOCAL','REMOTE'], help='Type of repository')
    cr_p.add_argument('-e', dest='enabled', action='store_true', default=False, help='Enable repository')
    cr_p.add_argument('-s', dest='strict', action='store_true', default=False, help='Enable strict')
    cr_p.add_argument('-p', dest='published', action='store_true', default=False, help='Publish repository')

    rrs_p = cmd_p.add_parser('read-repositories', help='Read all repositories')
    rr_p = cmd_p.add_parser('read-repository', help='Read a repository')
    rr_p.add_argument('-n', dest='name', action='store', help='Name of repository')
    
    ur_p = cmd_p.add_parser('update-repository', help='Update a repository')
    ur_p.add_argument('-n', dest='name', action='store', help='Name of repository')
    ur_p.add_argument('-u', dest='uri', action='store', help='URI to repository (file:/ or http://)')
    ur_p.add_argument('-rn', dest='remoteName', action='store', help='Remote-Name if remote repository')
    ur_p.add_argument('-m', dest='mode', action='store', default='ALL', choices=['ALL','STABLE','SNAPSHOT'], help='Mode of repository')
    ur_p.add_argument('-rt', dest='type', action='store', default='LOCAL', choices=['LOCAL','REMOTE'], help='Type of repository')
    ur_p.add_argument('-e', dest='enabled', action='store_true', default=False, help='Enable repository')
    ur_p.add_argument('-s', dest='strict', action='store_true', default=False, help='Enable strict')
    ur_p.add_argument('-p', dest='published', action='store_true', default=False, help='Publish repository')
    ur_p.add_argument('-t', dest='description', action='store', help='Short description of repository')
    
    dr_p = cmd_p.add_parser('delete-repository', help='Delete repository')
    dr_p.add_argument('-n', dest='name', action='store', help='Name of repository')

    # application/s
    ras_p = cmd_p.add_parser('read-applications', help='Read all applications')
    ras_p.add_argument('-s', dest='site', action='store', help='Name of site')
    ra_p = cmd_p.add_parser('read-application', help='Read a application')
    ra_p.add_argument('-n', dest='name', action='store', help='Name of application')
    ra_p.add_argument('-s', dest='site', action='store', help='Name of site')
    
    ua_p = cmd_p.add_parser('update-application', help='Update settings of application')
    ua_p.add_argument('-n', dest='name', action='store', help='Name of application')
    ua_p.add_argument('-dn', dest='displayName', action='store', help='Display name of application')
    ua_p.add_argument('-hi', dest='hidden', action='store', default=False, help='Hide application in manager')
    ua_p.add_argument('-c', dest='core', action='store', default=False, help='Install as core application')
    ua_p.add_argument('-f', dest='fileBased', action='store', default=False, help='Install application in local filesystem instead of database')
    
    da_p = cmd_p.add_parser('delete-application', help='Uninstall application')
    da_p.add_argument('-n', dest='name', action='store', help='Name of application')
    
    aas_p = cmd_p.add_parser('assign-application', help='Assign an application to a site')
    aas_p.add_argument('-n', dest='name', action='store', help='Name of application')
    aas_p.add_argument('-s', dest='site', action='store', help='Name of site')
    
    das_p = cmd_p.add_parser('deassign-application', help='Deassign an application to a site')
    das_p.add_argument('-n', dest='name', action='store', help='Name of application')
    das_p.add_argument('-s', dest='site', action='store', help='Name of site')

    # package/s
    rps_p = cmd_p.add_parser('read-packages', help='Read packages')
    rps_p.add_argument('-r', dest='repository', action='store', help='Name of repository to use')
    
    rp_p = cmd_p.add_parser('read-package', help='Read package')
    rp_p.add_argument('-n', dest='name', action='store', help='Name of package')
    rp_p.add_argument('-r', dest='repository', action='store', help='Name of repository to use')
    rp_p.add_argument('-pv', dest='version', action='store', help='Version of package')
    rp_p.add_argument('-pt', dest='timestamp', action='store', help='Timestamp of package if SNAPSHOT')
    
    ip_p = cmd_p.add_parser('install-package', help='Install an package from a repository')
    ip_p.add_argument('-r', dest='repository', action='store', help='Name of repository to use')
    ip_p.add_argument('-n', dest='name', action='store', help='Name of application')
    ip_p.add_argument('-pv', dest='version', action='store', help='Version of application')
    ip_p.add_argument('-pt', dest='timestamp', action='store', help='Timestamp of application snapshot')
    ip_p.add_argument('-pty', dest='type', action='store', default='APPLICATION', choices=['APPLICATION', 'TEMPLATE'], help='Type of application')
    
    up_p = cmd_p.add_parser('update-package', help='Update an package from a repository')
    up_p.add_argument('-r', dest='repository', action='store', help='Name of repository to use')
    up_p.add_argument('-n', dest='name', action='store', help='Name of application')
    up_p.add_argument('-pv', dest='version', action='store', help='Version of application')
    up_p.add_argument('-pt', dest='timestamp', action='store', help='Timestamp of application snapshot')
    up_p.add_argument('-pty', dest='type', action='store', default='APPLICATION', choices=['APPLICATION', 'TEMPLATE'], help='Type of application')

    # subject/s
    cu_p = cmd_p.add_parser('create-subject', help='Create a new subject')
    cu_p.add_argument('-n', dest='name', action='store', help='Name of subject')
    cu_p.add_argument('-rn', dest='realName', action='store', help='RealName of subject')
    cu_p.add_argument('-e', dest='email', action='store', help='E-Mail of subject')
    cu_p.add_argument('-t', dest='description', action='store', help='Short description of subject')
    cu_p.add_argument('-l', dest='language', action='store', default='en', help='Language of subject')
    cu_p.add_argument('-ut', dest='type', action='store', default='LOCAL_USER', choices=['LOCAL_USER','GLOBAL_USER','GLOBAL_GROUP'], help='Type of subject')
    cu_p.add_argument('-p', dest='digest', action='store', help='Password of subject')
    cu_p.add_argument('-tz', dest='timeZone', action='store', default='Europe/Berlin', help='Timezone for subject')
    cu_p.add_argument('-g', dest='groups', nargs='+', action='store', help='List of group names')

    rus_p = cmd_p.add_parser('read-subjects', help='Read all subjects')
    ru_p = cmd_p.add_parser('read-subject', help='Read a subject')
    ru_p.add_argument('-n', dest='name', action='store', help='Name of subject')
    
    uu_p = cmd_p.add_parser('update-subject', help='Update a subject')
    uu_p.add_argument('-n', dest='name', action='store', help='Name of subject')
    uu_p.add_argument('-rn', dest='realName', action='store', help='RealName of subject')
    uu_p.add_argument('-e', dest='email', action='store', help='E-Mail of subject')
    uu_p.add_argument('-t', dest='description', action='store', help='Short description of subject')
    uu_p.add_argument('-l', dest='language', action='store', default='en', help='Language of subject')
    uu_p.add_argument('-ut', dest='type', action='store', default='LOCAL_USER', choices=['LOCAL_USER','GLOBAL_USER','GLOBAL_GROUP'], help='Type of subject')
    uu_p.add_argument('-p', dest='digest', action='store', help='Password of subject')
    uu_p.add_argument('-tz', dest='timeZone', action='store', default='Europe/Berlin', help='Timezone for subject')
    uu_p.add_argument('-g', dest='groups', nargs='+', action='store', help='List of group names')
    
    du_p = cmd_p.add_parser('delete-subject', help='Delete subject')
    du_p.add_argument('-n', dest='name', action='store', help='Name of subject')

    # group/s
    cg_p = cmd_p.add_parser('create-group', help='Create a new group')
    cg_p.add_argument('-n', dest='name', action='store', help='Name of group')
    cg_p.add_argument('-t', dest='description', action='store', help='Short description of group')
    cg_p.add_argument('-ar', dest='roles', nargs='+' , action='store', help='List of Roles for this group (Syntax: appname1,rolename1 appname2,rolename2 ...)')
    
    rgs_p = cmd_p.add_parser('read-groups', help='Read all group')
    rg_p = cmd_p.add_parser('read-group', help='Read a group')
    rg_p.add_argument('-n', dest='name', action='store', help='Name of group')
    
    ug_p = cmd_p.add_parser('update-group', help='Update a group')
    ug_p.add_argument('-n', dest='name', action='store', help='Name of group')
    ug_p.add_argument('-t', dest='description', action='store', help='Short description of group')
    ug_p.add_argument('-ar', dest='roles', nargs='+' , action='store', help='List of Roles for this group (Syntax: appname1,rolename1 appname2,rolename2 ...)')
    
    dg_p = cmd_p.add_parser('delete-group', help='Delete group')
    dg_p.add_argument('-n', dest='name', action='store', help='Name of group')

    # role/s
    cro_p = cmd_p.add_parser('create-role', help='Create a new role')
    cro_p.add_argument('-n', dest='name', action='store', help='Name of role')
    cro_p.add_argument('-t', dest='description', action='store', help='Short description of role')
    cro_p.add_argument('-a', dest='application', action='store', help='Application of role')
    cro_p.add_argument('-p', dest='permissions', nargs='+', action='store', help='Permissions of role')

    rros_p = cmd_p.add_parser('read-roles', help='Read all roles')
    rros_p.add_argument('-a', dest='application', action='store', help='Application of role')
    rro_p = cmd_p.add_parser('read-role', help='Read a role')
    rro_p.add_argument('-n', dest='name', action='store', help='Name of group')
    rro_p.add_argument('-a', dest='application', action='store', help='Application of role')
    
    uro_p = cmd_p.add_parser('update-role', help='Update a group')
    uro_p.add_argument('-n', dest='name', action='store', help='Name of group')
    uro_p.add_argument('-t', dest='description', action='store', help='Short description of role')
    uro_p.add_argument('-a', dest='application', action='store', help='Application of role')
    uro_p.add_argument('-p', dest='permissions', nargs='+', action='store', help='Permissions of role')
    
    dro_p = cmd_p.add_parser('delete-role', help='Delete group')
    dro_p.add_argument('-n', dest='name', action='store', help='Name of group')
    dro_p.add_argument('-a', dest='application', action='store', help='Application of role')

    # permission/s
    cpe_p = cmd_p.add_parser('create-permission', help='Create a new permission')
    cpe_p.add_argument('-n', dest='name', action='store', help='Name of permission')
    cpe_p.add_argument('-t', dest='description', action='store', help='Short description of permission')
    cpe_p.add_argument('-a', dest='application', action='store', help='Application of permission')
    
    rpes_p = cmd_p.add_parser('read-permissions', help='Read all permissions')
    rpes_p.add_argument('-a', dest='application', action='store', help='Application of permission')
    rpe_p = cmd_p.add_parser('read-permission', help='Read a permission')
    rpe_p.add_argument('-n', dest='name', action='store', help='Name of permission')
    rpe_p.add_argument('-a', dest='application', action='store', help='Application of permission')

    upe_p = cmd_p.add_parser('update-permission', help='Update a permission')
    upe_p.add_argument('-n', dest='name', action='store', help='Name of permission')
    upe_p.add_argument('-t', dest='description', action='store', help='Short description of permission')
    upe_p.add_argument('-a', dest='application', action='store', help='Application of permission')
    
    dpe_p = cmd_p.add_parser('delete-permission', help='Delete permission')
    dpe_p.add_argument('-n', dest='name', action='store', help='Name of permission')
    dpe_p.add_argument('-a', dest='application', action='store', help='Application of permission')

    # database
    rdbs_p = cmd_p.add_parser('read-databases', help='Read database connections of a site')
    rdbs_p.add_argument('-s', dest='site', action='store', help='Name of site')
    rdb_p = cmd_p.add_parser('read-database', help='Read database connection of a site application')
    rdb_p.add_argument('-s', dest='site', action='store', help='Name of site')
    rdb_p.add_argument('-a', dest='application', action='store', help='Name of application')

    udb_p = cmd_p.add_parser('update-database', help='Update a database connection')
    udb_p.add_argument('-s', dest='site', action='store', help='Name of site')
    udb_p.add_argument('-a', dest='application', action='store', help='Name of application')
    udb_p.add_argument('-u', dest='user', action='store', help='DB user name')
    udb_p.add_argument('-p', dest='password', action='store', help='DB user password')
    udb_p.add_argument('-ss', dest='salt', action='store', help='Salt to use for password hashing (platform.sharedsecret)')
    udb_p.add_argument('-dd', dest='driver', action='store', default='com.mysql.jdbc.Driver', help='JDBC driver to use')
    udb_p.add_argument('-du', dest='url', action='store', help='JDBC url of database')

    # platform
    rpl_p = cmd_p.add_parser('reload-platform', help='Reload platform')

    return parser

def main(argv=None): # IGNORE:C0111
    '''Command line options.'''

    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)

    try:

        parser = get_argparser()

        # Process arguments
        nargs = parser.parse_args()

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
