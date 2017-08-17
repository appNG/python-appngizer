# -*- coding: utf-8 -*-
import pkg_resources

try:
  __version__ = pkg_resources.get_distribution(__name__).version
except:
  __version__ = '1.14.1'

__date__ = '2017-08-11'
__updated__ = '2017-08-15'
