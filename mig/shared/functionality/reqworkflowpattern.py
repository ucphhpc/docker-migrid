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
Register a workflow pattern and attach
optional uploaded recipes to the pattern.

TODO finish description
"""
import json

import shared.returnvalues as returnvalues
from shared.base import valid_dir_input
from shared.defaults import csrf_field, wp_id_length, wp_id_charset
from shared.pwhash import generate_random_ascii
from shared.init import initialize_main_variables
from shared.handlers import safe_handler, get_csrf_limit
from shared.functional import validate_input_and_cert
from shared.workflows import create_workflow_pattern
from shared.safeinput import REJECT_UNSET, VALID_SAFE_PATH_CHARACTERS

def signature():
    """Signaure of the main function"""

    defaults = {
        'input': REJECT_UNSET,
        'output': REJECT_UNSET,
        'type-filter': REJECT_UNSET,
        'recipes': [''],
        'recipesfilename': ['']
    }
    return ['registerpattern', defaults]


def handle_form_input(configuration, file, user_arguments_dict):
    """Retrieve the recipe file"""
    pass

def get_uploaded_recipes(configuration, user_arguments_dict, upload_key, upload_names):
    """"""
    # TODO, find out which type of recipe it is
    _logger = configuration.logger
    json_recipes = []
    recipes = user_arguments_dict[upload_key]
    for recipe in recipes:
        json_recipe = None
        try:
            json_recipe = json.loads(recipe, encoding='utf-8')
            if json_recipe:
                json_recipe['name'] = upload_names
                json_recipes.append(json_recipe)
        except Exception, err:
            _logger.error("Failed to json load: %s from: %s " %
                        (err, user_arguments_dict[recipe_key]))
            return []
    return json_recipes
    
def valid_recipes(configuration, recipes):
        # Validate that the recipe has the minimum amount of content,
    # with the correct types
    # TODO check for cell_type, code
    # TODO check for 'source' in each cell

    req_keys = [('cells', list), ('metadata', dict), ('nbformat', int)]
    incorrect_keys = {'missing': [], 'invalid': []}

    for recipe in recipes:
        for key in req_keys:
            if key[0] not in recipe:
                incorrect_keys['missing'].append(key[0])
            if key[0] in recipe and not isinstance(recipe[key[0]], key[1]):
                incorrect_keys['invalid'].append(key[0])

        if incorrect_keys['missing']:
            output_keys = ' '.join(incorrect_keys['missing'])
            output_objects.append({'object_type': 'error_text',
                                'text': 'Missing required fields in Recipe: '
                                        '%s' % output_keys})

    if incorrect_keys['invalid']:
        output_keys = ' '.join(incorrect_keys['invalid'])
        correct_types = '\n'.join([' is a '.join(key) for key in req_keys
                                  if key[0] in incorrect_keys['invalid']])
        output_objects.append({'object_type': 'error_text',
                               'text': 'The recipe had invalid fields: %s '
                                       ' requires that %s' %
                                       (output_keys, correct_types)})

    if incorrect_keys['missing'] or incorrect_keys['invalid']:
        return (output_objects, returnvalues.CLIENT_ERROR)

    # Detect which kernel to use (what language is used)
    # As specified at
    # https://nbformat.readthedocs.io/en/latest
    # /format_description.html?highlight=language_info
    # language_info['name'] tells which language is used in the recipe
    if 'language_info' not in json_nb['metadata'] or 'name' not in \
            json_nb['metadata']['language_info']:
        output_objects.append({'object_type': 'error_text',
                               'text': 'The recipe\'s language is not '
                                       'specified. Please ensure that '
                                       'the recipe has a defined language'})
        return (output_objects, returnvalues.CLIENT_ERROR)

    lang = str(json_nb['metadata']['language_info']['name'])
    logger.info("After language_info check")

    # TODO, make configuration.valid_recipe_langauges
    valid_languages = ['python']
    if lang not in valid_languages:
        output_objects.append({'object_type': 'error_text',
                               'text': 'The provided recipe language %s'
                                       ' is not available. Please use one'
                                       ' of the following once: %s' %
                                       (lang, ' '.join(valid_languages))})
        return (output_objects, returnvalues.CLIENT_ERROR)

    return False


def get_tags_from_cell(cell):
    """Returns a list of tags from a notebook cell"""
    if 'metadata' in cell and isinstance(cell['metadata'], dict):
        if 'tags' in cell['metadata'] and isinstance(cell['metadata']['tags'], list):
            return cell['metadata']['tags']
    return None

def get_recipes_parameters(configuration, json_nb):
    """Returns a dict of cells that contain recipes and parameters from the ipynb notebook.
    This is based on whether the cell dictionary has a key with
    the follwing format:
         'metadata': {'tags': ['recipe']}
    or
        'metadata': {'tags': ['parameters']}
    This is based on ipynb cell tagging.
    e.g. https://github.com/jupyterlab/jupyterlab-celltags"""

    rp_cells = {'recipes': [], 'parameters': {}}
    if 'cells' in json_nb and isinstance(json_nb['cells'], list):
        for cell in json_nb['cells']:
            tags = get_tags_from_cell(cell)
            if tags:
                _ = [rp_cells['recipes'].append(cell['source']) if t == 'recipe'
                else rp_cells['parameters'].update(get_declarations_dict(configuration,cell['source']))
                if t == 'parameters' else None for t in tags]
    return rp_cells


def get_declarations_dict(configuration, code):
    """Returns a dictionary with the variable declartions in the list
    Expects that code is a list of strings"""
    declarations = {}
    _logger = configuration.logger
    for line in code:
        if isinstance(line, unicode) or isinstance(line, str):
            line = line.replace(" ", "")
            lines = line.split("=")
            if len(lines) == 2:
                declarations.update({lines[0]: lines[1]})
            else:
                _logger.error('get_declarations_dict, either none or '
                'more than a single assignments in line: %s' % line)
    return declarations


def main(client_id, user_arguments_dict):
    (configuration, logger, output_objects, op_name) = \
            initialize_main_variables(client_id, op_header=False)
    defaults = signature()[1]

    # TODO, add the signature keys to guess_type in safeinput.py
    #  Validate user_arguments_dict: input, ouput, type-filter, 
    #  recipes, recipesfilename
    validate_args = {
        'input': [''],
        'output': [''],
        'type-filter': [''],
        csrf_field: ['AllowMe'],
    }
    validate_args[csrf_field] = user_arguments_dict.get(csrf_field, ['AllowMe'])
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
    logger.debug("reqworkflowpattern as User: %s accepted %s" %
                (client_id, accepted))

    # Extract inputs, output and type-filter
    inputs_name, output_name, type_filter_name = 'input', 'output', 'type-filter'
    upload_key, upload_name = 'recipes', 'recipesfilename'

    inputs = user_arguments_dict[inputs_name]
    output = user_arguments_dict[output_name]
    type_filter = user_arguments_dict[type_filter_name]
    recipe_name = user_arguments_dict[upload_name]

    paths = inputs + output
    for path in paths:
        if not valid_dir_input(configuration.user_home, path):
            logger.warning(
                "possible illegal directory traversal attempt pattern_dirs '%s'"
                % path)
            output_objects.append({'object_type': 'error_text', 'text'
                                : 'The path given: "%s" is illgally formatted'
                                % path})
            return (output_objects, returnvalues.CLIENT_ERROR)

    if not safe_handler(configuration, 'post', op_name, client_id,
                        get_csrf_limit(configuration), accepted):
        output_objects.append(
            {'object_type': 'error_text', 'text': '''Only accepting
            CSRF-filtered POST requests to prevent unintended updates'''
             })
        return (output_objects, returnvalues.CLIENT_ERROR)

    # Optional recipes
    recipes_n_parameters = {}
    recipes = get_uploaded_recipes(configuration, user_arguments_dict, upload_key, upload_name)
    if recipes and valid_recipes(configuration, recipes):
        # Extract recipe and parameter cells from recipe
        recipes_n_parameters = get_recipes_parameters(configuration, recipes)
        if not recipes_n_parameters['recipes']:
            output_objects.append({'object_type': 'error_text',
                            'text': 'No recipe cells were found '
                                    'found in %s' %
                                    user_arguments_dict[upload_name]})
            return (output_objects, returnvalues.CLIENT_ERROR)
    elif not recipes:
        output_objects.append({'object_type': 'error_text',
                               'text': 'Failed to parse the uploaded '
                                       'recipe'})
        return (output_objects, returnvalues.CLIENT_ERROR)

    output_objects.append({'object_type': 'header', 'text':
                           ' Registering Pattern'})

    pattern = {
        'owner': client_id,
        'inputs': inputs,
        'output': output,
        'type_filter': type_filter,
    }
    # Add optional recipes
    if recipes and recipes_n_parameters:
        pattern.update({
            'recipes': recipes_n_parameters['recipes'],
            'variables': recipes_n_parameters['parameters']
        })

    created, msg = create_workflow_pattern(client_id, pattern, configuration)
    if not created:
        output_objects.append({'object_type': 'error_text',
                               'text': msg})
        return (output_objects, returnvalues.SYSTEM_ERROR)

    output_objects.append({'object_type': 'text',
                           'text': 'Successfully registered the pattern'})

    # TODO if recipes exists (Attach to pattern)
    
    return (output_objects, returnvalues.OK)