# -*- coding: utf-8 -*-
#
# This file is part of couchapp released under the Apache 2 license. 
# See the NOTICE for more information.

import glob
from hashlib import md5
import os
import re
try:
    import json
except ImportError:
    import couchapp.simplejson as json

from couchapp.errors import MacroError
from couchapp.utils import to_bytestring

def package_shows(doc, funcs, app_dir, objs, ui):
   apply_lib(doc, funcs, app_dir, objs, ui)
         
def package_views(doc, views, app_dir, objs, ui):
   for view, funcs in views.iteritems():
       if hasattr(funcs, "iteritems"):
           apply_lib(doc, funcs, app_dir, objs, ui)

def apply_lib(doc, funcs, app_dir, objs, ui):
    for k, v in funcs.iteritems():
        if not isinstance(v, basestring):
            continue
        else:
            if ui.verbose>=2:
                ui.logger.info("process function: %s" % k)
            old_v = v
            try:
                funcs[k] = run_json_macros(doc, 
                    run_code_macros(v, app_dir, ui), app_dir, ui)
            except ValueError, e:
                raise MacroError("Error running !code or !json on function \"%s\": %s" % (k, e))
            if old_v != funcs[k]:
                objs[md5(to_bytestring(funcs[k])).hexdigest()] = old_v
           
def run_code_macros(f_string, app_dir, ui):
   def rreq(mo):
       # just read the file and return it
       path = os.path.join(app_dir, mo.group(2).strip())
       library = ''
       filenum = 0
       for filename in glob.iglob(path):            
           if ui.verbose>=2:
               ui.logger.info("process code macro: %s" % filename)
           try:
               content = ui.read(filename)
               # macro extraction recursively
               library += run_code_macros(content, app_dir, ui)
           except IOError, e:
               raise MacroError(str(e))
           filenum += 1
           
       if not filenum:
           raise MacroError("Processing code: No file matching '%s'" % mo.group(2))
       return library

   re_code = re.compile('(\/\/|#)\ ?!code (.*)')
   return re_code.sub(rreq, f_string)

def run_json_macros(doc, f_string, app_dir, ui):
   included = {}
   varstrings = []

   def rjson(mo):
       if mo.group(2).startswith('_attachments'): 
           # someone  want to include from attachments
           path = os.path.join(app_dir, mo.group(2).strip())
           filenum = 0
           for filename in glob.iglob(path):
               if ui.verbose>=2:
                   ui.logger.info("process json macro: %s" % filename)
               library = ''
               try:
                   if filename.endswith('.json'):
                       library = ui.read_json(filename)
                   else:
                       library = ui.read(filename)
               except IOError, e:
                   raise MacroError(str(e))
               filenum += 1
               current_file = filename.split(app_dir)[1]
               fields = current_file.split('/')
               count = len(fields)
               include_to = included
               for i, field in enumerate(fields):
                   if i+1 < count:
                       include_to[field] = {}
                       include_to = include_to[field]
                   else:
                       include_to[field] = library
           if not filenum:
               raise MacroError("Processing code: No file matching '%s'" % mo.group(2))
       else:	
           if ui.verbose>=2:
               ui.logger.info("process json macro: %s" % mo.group(2))
           fields = mo.group(2).strip().split('.')
           library = doc
           count = len(fields)
           include_to = included
           for i, field in enumerate(fields):
               if not field in library:
                   ui.logger.warn("process json macro: unknown json source: %s" % mo.group(2))
                   break
               library = library[field]
               if i+1 < count:
                   include_to[field] = include_to.get(field, {})
                   include_to = include_to[field]
               else:
                   include_to[field] = library

       return f_string

   def rjson2(mo):
       return '\n'.join(varstrings)

   re_json = re.compile('(\/\/|#)\ ?!json (.*)')
   re_json.sub(rjson, f_string)

   if not included:
       return f_string

   for k, v in included.iteritems():
       varstrings.append("var %s = %s;" % (k, json.dumps(v).encode('utf-8')))

   return re_json.sub(rjson2, f_string)
