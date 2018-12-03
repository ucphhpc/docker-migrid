#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# --- BEGIN_HEADER ---
#
# vgridworkflows - data-driven workflows for owners and members
# Copyright (C) 2003-2018  The MiG Project lead by Brian Vinter
#
# This file is part of MiG.
#
# MiG is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# MiG is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA  02110-1301, USA.
#
# -- END_HEADER ---
#


"""
Register a jupyter notebook containing workflow patterns as a vGrid workflow.
"""
import os
import json

import shared.returnvalues as returnvalues
from shared.base import client_id_dir
from shared.defaults import csrf_field, session_id_bytes
from shared.init import initialize_main_variables
from shared.handlers import safe_handler, get_csrf_limit
from shared.functional import validate_input_and_cert
from shared.pwhash import generate_random_ascii


def signature():
    return ['', {}]


def handle_form_input(file, user_arguments_dict, configuration):
    """ Retrieve the jupyter notebook file"""
    pass


def main(client_id, user_arguments_dict):
    (configuration, logger, output_objects, op_name) = \
        initialize_main_variables(client_id, op_header=False)
    client_dir = client_id_dir(client_id)
    defaults = signature()[1]
    validate_args = {}
    # validate_args = dict([(key, user_arguments_dict.get(key, val)) for \
    #                       (key, val) in defaults.items()])

    logger.info("User args: %s" % (user_arguments_dict))
    # Allow csrf_field from upload
    validate_args[csrf_field] = user_arguments_dict.get(csrf_field,
                                                        ['AllowMe'])

    (validate_status, accepted) = validate_input_and_cert(
        validate_args,
        defaults,
        output_objects,
        client_id,
        configuration,
        allow_rejects=False,
    )
    if not validate_status:
        return (accepted, returnvalues.CLIENT_ERROR)

    logger.info("regjupyterpattern as User: %s accepted %s" %
                (client_id, accepted))

    if not safe_handler(configuration, 'post', op_name, client_id,
                        get_csrf_limit(configuration), accepted):
        output_objects.append(
            {'object_type': 'error_text', 'text': '''Only accepting
            CSRF-filtered POST requests to prevent unintended updates'''
             })
        return (output_objects, returnvalues.CLIENT_ERROR)

    # Validate that the notebook is there
    upload_key = 'jupyter-notebook'
    upload_name = 'jupyter-notebookfilename'
    if upload_key not in user_arguments_dict:
        output_objects.append({'object_type': 'error_text',
                               'text': 'No jupyter notebook was provided'})
        return (output_objects, returnvalues.CLIENT_ERROR)

    if not isinstance(user_arguments_dict[upload_key], list) and \
            len(user_arguments_dict[upload_key]) == 1:
        output_objects.append({'object_type': 'error_ext',
                               'text': 'Only a single notebook can be uploaded'
                                       'at a time'})
        return (output_objects, returnvalues.CLIENT_ERROR)

    # Parse file format as json string
    # Remove trailing commas
    # TODO, ask jonas about standard way of sanitizing input on migrid
    formatted = user_arguments_dict[upload_key][0]
    logger.info("Formatted %s " % formatted)
    json_nb = None
    try:
        json_nb = json.loads(formatted)
    except Exception, err:
        logger.error("Failed to json load %s for %s uploaded by %s" %
                     (err, user_arguments_dict[upload_name], client_id))

    if json_nb is None:
        output_objects.append({'object_type': 'error_ext',
                               'text': 'Failed to parse the uploaded '
                                       'notebook'})
        return (output_objects, returnvalues.CLIENT_ERROR)

    # Validate that the notebook has the minimum amount of content,
    # with the correct types
    # TODO check for cell_type, code
    req_keys = [('cells', list), ('metadata', dict), ('nbformat', int)]
    incorrect_keys = {'missing': [], 'invalid': []}
    for key in req_keys:
        if key[0] not in json_nb:
            incorrect_keys['missing'].append(key[0])
        if key[0] in json_nb and not isinstance(json_nb[key[0]], key[1]):
            incorrect_keys['invalid'].append(key[0])

    if incorrect_keys['missing']:
        output_keys = ' '.join(incorrect_keys['missing'])
        output_objects.append({'object_type': 'error_text',
                               'text': 'Missing required fields in Notebook: '
                                       '%s' % output_keys})

    if incorrect_keys['invalid']:
        output_keys = ' '.join(incorrect_keys['invalid'])
        correct_types = '\n'.join([' is a '.join(key) for key in req_keys
                                  if key[0] in incorrect_keys['invalid']])
        output_objects.append({'object_type': 'error_text',
                               'text': 'The notebook had invalid fields: %s '
                                       ' requires that %s' %
                                       (output_keys, correct_types)})

    if incorrect_keys['missing'] or incorrect_keys['invalid']:
        return (output_objects, returnvalues.CLIENT_ERROR)

    logger.info("After invalid return")
    # Detect which kernel to use (what language is used)
    # As specified at
    # https://nbformat.readthedocs.io/en/latest
    # /format_description.html?highlight=language_info
    # language_info['name'] tells which language is used in the notebook
    if 'language_info' not in json_nb['metadata'] or 'name' not in \
            json_nb['metadata']['language_info']:
        output_objects.append({'object_type': 'error_text',
                               'text': 'The notebooks language is not '
                                       'specified. Please ensure that '
                                       'the notebook has a defined language'})
        return (output_objects, returnvalues.CLIENT_ERROR)

    lang = str(json_nb['metadata']['language_info']['name'])
    logger.info("After language_info check")

    # TODO, make configuration.valid_python_langauges
    valid_languages = ['python']
    if lang not in valid_languages:
        output_objects.append({'object_type': 'error_text',
                               'text': 'The provided notebook language %s'
                                       ' is not available. Please use one'
                                       ' of the following once: %s' %
                                       (lang, ' '.join(valid_languages))})
        return (output_objects, returnvalues.CLIENT_ERROR)

    # Extract code cells with code
    cells = []
    for cell in json_nb['cells']:
        if 'cell_type' in cell and cell['cell_type'] == 'code' \
                and 'source' in cell and cell['source']:
            n_cell = {
                'source': cell['source'],
                'metadata': cell['metadata']
            }
            cells.append(n_cell)

    if not cells:
        output_objects.append({'object_type': 'error_text',
                               'text': 'No non-empty code cells was '
                                       'found in %s' %
                                       user_arguments_dict[upload_name]})
        return (output_objects, returnvalues.CLIENT_ERROR)

    output_objects.append({'object_type': 'header', 'text':
                           ' Registering jupyter notebook'})

    pattern_file = {
        'name': user_arguments_dict[upload_name],
        'language': lang,
        'cells': cells
    }

    # Prepare json for writing.
    # TODO, make configuration.jupyter_patterns
    # The name of the directory to be used in both the users home
    # and the global state/jupyter_pattern_files directory which contains
    # symlinks to the former

    jup_dir_name = 'jupyter_patterns'
    jup_dir_path = os.path.join('/home/mig/state', jup_dir_name, client_dir)

    if not os.path.exists(jup_dir_path):
        os.makedirs(jup_dir_path)

    logger.info("regjupyterpattern as User: %s args %s:" %
                (client_id, user_arguments_dict))

    # Create unique_filename (session_id)
    unique_jup_name = generate_random_ascii(2 * session_id_bytes,
                                            charset='0123456789abcdef')

    pat_file_path = os.path.join(jup_dir_path, unique_jup_name + '.json')
    if os.path.exists(pat_file_path):
        logger.error("Error while registering a new jupyter pattern file: %s "
                     "a conflict in unique filenames was encountered" %
                     pat_file_path)
        output_objects.append({'object_type': 'error_text',
                               'text': 'The generated filename for your '
                                       'pattern notebook encountered a naming'
                                       'conflict, please try '
                                       're-uploading the notebook'})
        return (output_objects, returnvalues.SYSTEM_ERROR)

    logger.info("Writing content %s type: %s" % (pattern_file,
                                                 type(pattern_file)))
    # Save the pattern notebook
    wrote = False
    try:
        with open(pat_file_path, 'w') as j_file:
            j_file.write(str(pattern_file))
        logger.info("Created a new pattern notebook at: %s " %
                    pat_file_path)
        wrote = True
    except Exception, err:
        logger.error("Failed to write the jupyter pattern file: %s to disk "
                     " err: %s" % (pat_file_path, err))
        output_objects.append({'object_type': 'error_text',
                               'text': 'Failed to write the pattern notebook'
                                       ' to disk, '
                                       'please try re-uploading the notebook'})
    if not wrote:
        try:
            os.remove(pat_file_path)
        except Exception, err:
            logger.error("Failed to remove the failed jupyter pattern file %s"
                         " err: %s " % (pat_file_path, err))
        return (output_objects, returnvalues.SYSTEM_ERROR)

    output_objects.append({'object_type': 'text',
                           'text': 'Successfully registered the notebook %s '
                                   'as a pattern' %
                                   user_arguments_dict[upload_name]})
    return (output_objects, returnvalues.OK)