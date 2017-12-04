import pytest
from appngizer.elements import *

def main():
    
    def default_test_case(elements, element):
        elements.read()
        if type(elements) == Grants:
            elements.get_grant('testsite')
            elements.update_grant('testsite', True )
            elements.update_grants( grants = [('testsite', True)] )
                
        if type(element) != Application and type(element) != Permission \
        and type(element) != Package and type(element) != Grant and type(element) != Database:
            if element.exist():
                element.delete()
            element.create(**create_dict)
        
        if type(element) == Permission:
            if not element.exist():
                element.create(**create_dict)
        if type(element) == Package:
            if element.exist():
                if element.is_installed():
                    Application( element.name ).deassign_from_all()
                else:
                    element.install()
        if type(element) == Application:
            if element.exist():
                if element.is_assigned( site=Site('testsite') ):
                    element.deassign( site=Site('testsite') )
                    element.deassign_from_all()
                element.assign( site=Site('testsite') )
                element.update(**create_dict)
        if type(element) == Grant:
            if element.exist():
                element.read()
                return True
            else:
                return True
                
        element.read()
        print element.dump()

        element.is_update_needed(**create_dict)
        element.is_update_needed(**update_dict)
        element.is_update_needed(**update_min_dict)

        element.update(**update_dict)
        element.update(**update_min_dict)
        
        if type(element) == Repository:
            element.has_pkg(name='appng-manager')
            element.list_pkg(name='appng-manager')
            element.list_pkgs()

        if type(element) == Site:
            element.reload()
    
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    client = appngizer.client.XMLClient('http://127.0.0.1:8080/appNGizer','')

    # Test objects
    testsite = Site('testsite')
    
    testrepo = Repository('testrepo')
    testpkg = Package('appng-mediacenter')
    testapp = Application('appng-mediacenter')
    testapp_os = Application('appng-mediacenter')
    
    testperm = Permission('test-permission',parents=[testapp_os])
    testperm2 = Permission('test-permission2',parents=[testapp_os])
    testrole = Role('Tester',parents=[testapp_os])
    testgroup = Group('Tester')
    testsubject = Subject('Tester')
    
    testgrant = Grant(testsite.name, parents=[testapp])
    
    testappdb = Database( parents=[ testsite,testapp_os ] )
    
    # Test xdicts
    create_dict = {'host': 'testsite', 'domain': 'http://localhost:8080', 
                    'description': 'test_description', 'active': True, 
                    'createRepositoryPath': False,
                    'value': 'test_value', 'defaultValue': 'test_defaultValue',
                    'uri': 'file:///tmp', 'enabled': True,
                    'privileged': True,
                    'allow_snapshot': True,
                    'permissions': [ testperm.xml ],
                    'roles': [ testrole.xml ],
                    'realName': 'Python Tester', 'email':'info@aiticon.com',
                    'digest': 'tester', 'groups': [],
                    'user':'tester','password':'test'
                    }
    update_dict = {'host': 'testsite', 'domain': 'http://localhost:8080', 
                    'description': 'test_description_update', 'active': True, 
                    'createRepositoryPath': False,
                    'value': 'test_value', 'defaultValue': 'test_defaultValue',
                    'privileged': False,
                    'uri': 'file:///tmp', 'enabled': False,
                    'allow_snapshot': False,
                    'permissions': [ testperm.xml,testperm2.xml ],
                    'roles': [],
                    'realName': 'Python Tester', 'email':'info@aiticon.com',
                    'digest': 'tester', 'groups': [ testgroup.xml ],
                    'user':'tester','password':'test'
                    }
    update_min_dict = {'description': 'test_description_update', 
                       'privileged': False,
                       'permissions': [],
                       'allow_snapshot': False,
                       'user':'tester','password':'test'
                        }

    ### Tests
    
    # Site
    #default_test_case(Sites(), testsite)
    # Repository
    #default_test_case(Repositories(), testrepo)
    # Package
    #default_test_case(Packages(), testpkg)
    # Application
    #default_test_case(Applications(), testapp)
    # Platform Property
    #default_test_case(Properties(parents=[Platform()]), 
    #                  Property( 'testproperty',parents=[Platform()] ))
    # Application Property
    #default_test_case(Properties(parents=[testapp]), 
    #                  Property( 'testproperty',parents=[testapp] ))
    # Site Property
    #default_test_case(Properties(parents=[testsite]), 
    #                  Property( 'testproperty',parents=[testsite] ))
    # Site App Property
    #default_test_case(Properties(parents=[testsite, testapp_os]), 
    #                  Property( 'testproperty',parents=[testsite, testapp_os] ))
    # Site App Grants
    #default_test_case(Grants(parents=[testsite,testapp]), testgrant)    
    # Permission
    #default_test_case(Permissions(parents=[testapp_os]), testperm)
    #default_test_case(Permissions(parents=[testapp_os]), testperm2)
    # Role
    #default_test_case(Roles(parents=[testapp_os]), testrole)
    # Group
    #default_test_case(Groups(), testgroup)
    # Subject
    #default_test_case(Subjects(), testsubject)
    # Database
    #default_test_case(Databases( parents=[testsite] ), testappdb)

def run():
    """
        Entry point for console_scripts
    """
    main()

if __name__ == "__main__":
    sys.exit(main())
