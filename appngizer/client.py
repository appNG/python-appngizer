# -*- coding: utf-8 -*-
'''
    This module contains network clients which are used to communicate
    with an appNGizer instance.
    
    Currently there is only an implementation of a :class:`XMLClient`.    
'''
import logging
import requests
import re
import urllib, urlparse

from lxml import etree
from lxml.html import soupparser
 
import appngizer.errors

log = logging.getLogger(__name__)

class Singleton(type):
    '''
        Singleton class pattern to be used as metaclass for the :class:`Client`.
    '''
    _instances = {}
    def __call__(self, *args, **kwargs):
        if self not in self._instances:
            self._instances[self] = super(Singleton, self).__call__(*args, **kwargs)
        else:
            if len(args) > 0:
                if not self._instances[self].base_url.startswith(args[0]):
                    del self._instances[self]
                    self._instances[self] = super(Singleton, self).__call__(*args, **kwargs)
        return self._instances[self]

class Client(object):
    '''
        Abstract class of an appNGizer client
        All further appNGizer clients will inherits from this class
    '''
    __metaclass__ = Singleton
    
    # : regex to match a valid http|s:// url
    REGEX_URL = re.compile(
        r'^(?:http)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    def __init__(self, url, sharedsecret):
        '''
        :param str url: url to an appNGizer instance
        :param str sharedsecret: sharedsecret to be used
        '''
        self.base_url = self.validate_url(url)
        self.net = ClientNetwork()
        self.content_type = 'text/plain'
        self.sharedsecret = sharedsecret
        self.authenticated = self._auth()
        self.response = None
        self.response_transf = None
    
    def _auth(self):
        '''Authenticates against an appNGizer instance
        
        :return: bool (True if authenticated)
        '''
        self.net.session.headers.update({'Content-Type': 'text/plain'})
        self.content_type = 'text/plain'
        response = self.net.request('POST', self.base_url, data=self.sharedsecret)
        self.content_type = 'application/xml'
        self.net.session.headers.update({'Content-Type': self.content_type})
        self._process_response(response)
        return True        
    def _process_response(self, response=None, exception=None):
        '''Process received response
        
        :return: bool (True if processed)
        '''
        self._check_response(response)
        self.response = response
        if response.text != '':
            self._transform_response()
        return True
    def _check_response(self, response):
        '''Checks response
        
        :param requests.Response response: response object
        :return: bool (True if valid, Falise if not valid)
        '''
        response_ct = response.headers.get('Content-Type')
        if not response.ok:
            if response.status_code == 400:
                raise appngizer.errors.HttpClientBadRequest('400 - Bad request ({})'.format(response.url))
            if response.status_code == 409:
                raise appngizer.errors.HttpElementConflict('409 - Conflict ({})'.format(response.url))
            if response.status_code == 403:
                raise appngizer.errors.HttpElementForbidden('403 - Forbidden ({})'.format(response.url))
            if response.status_code == 404:
                raise appngizer.errors.HttpElementNotFound('404 - Not found ({})'.format(response.url))
            if response.status_code == 500:
                # try to get exception message from html error page if exist
                if response.text:
                    html_error = soupparser.fromstring(response.text)
                    pre_childs = html_error.xpath('//pre[contains(text(),"Exception")]')
                    pre_texts = []
                    for pre_text in pre_childs:
                        pre_texts.append(pre_text.text)
                    raise appngizer.errors.HttpServerError('500 - Server error ({}): {}'.format(response.url, ' '.join(pre_texts)))                   
                else:
                    raise appngizer.errors.HttpServerError('500 - Server error ({})'.format(response.url))
            else:
                raise appngizer.errors.ClientError(response.raise_for_status())
        else:
            if self.content_type != response_ct:
                if response.status_code == 204 and response.request.method == 'DELETE':
                    return True
                if response.status_code == 200 and response_ct == None:
                    return True
                else:
                    raise appngizer.errors.ClientError('Unexpected response Content-Type: {0}'.format(response_ct))
        return True
    def _transform_response(self):
        '''Transforms and set response attribute
        '''
        self.response_transf = self.response

    def request(self, method, path, pdata=None):
        '''Sends request to appNGizer instance
        
        :param str method: HTTP method
        :param str path: url to appNGizer instance
        :param str pdata: data to send
        :return: :class:`Client` object
        '''
        url = self.validate_url(self.base_url + path)
        response = self.net.request(method, url, data=pdata)
        self._process_response(response)
        return self
    def validate_url(self, url):
        '''Validates an url
        
        :param str url:
        :return: url as string if valide
        '''
        if not url.endswith('/'):
            url = url + '/'
        # TODO: deactivated because this currently conflicts with url encoding 
        # if self.REGEX_URL.match(url):
        #    return url
        # else:
        #    raise appngizer.errors.ClientError('Invalid url: {0}'.format(url))
        return url
    
class XMLClient(Client):
    '''
        appNGizer XML Client class
    '''
    def __init__(self, url, sharedsecret):
        '''
        :param str url: url to an appNGizer instance
        :param str sharedsecret: sharedsecret to be used
        '''
        self.base_url = self.validate_url(url)
        self.net = ClientNetwork()
        self.content_type = 'application/xml'
        self.sharedsecret = sharedsecret
        self.authenticated = self._auth()
        self.response = None
        self.response_transf = None

    def _transform_response(self):
        '''Transforms and set response attribute
        '''
        if self.response.status_code == 204:
            self.response_transf = self.response.content
        else:
            self.response_transf = etree.fromstring(self.response.content)

class ClientNetwork(object):
    '''
        appNGizer ClientNetwork class
    '''
    def __init__(self):
        self.session = requests.Session()
    def __del__(self):
        self.session.close()
        
    def _send_request(self, method, url, *args, **kwargs):
        '''Sends request to an appNGizer instance

        :param str method: HTTP method
        :param str path: url to appNGizer instance
        :param list *args: additional args for :class:`requests.Request` object
        :param dict *kwargs: additional kwargs for :class:`requests.Request`
        :return: :class:`requests.Response` object
        '''
        log.debug('Sending %s request to %s. args: %r, kwargs: %r', method, url, args, kwargs)
        kwargs.setdefault('headers', {})
        response = self.session.request(method, url, *args, **kwargs)
        log.debug('Received %s. Headers: %s.', response, response.headers)
        log.debug('Content: %r', response.content)
        return response
    
    def request(self, method, url, *args, **kwargs):
        '''Sends request to an appNGizer instance

        :param str method: HTTP method
        :param str path: url to appNGizer instance
        :param list args: additional args for :class:`requests.Request` object
        :param dict kwargs: additional kwargs for :class:`requests.Request`
        :return: :class:`requests.Response` object
        '''
        response = self._send_request(method, url, *args, **kwargs)
        return response
