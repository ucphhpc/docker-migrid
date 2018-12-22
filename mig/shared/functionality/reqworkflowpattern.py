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
from shared.defaults import csrf_field
from shared.init import initialize_main_variables
from shared.handlers import safe_handler, get_csrf_limit
from shared.functional import validate_input_and_cert
from shared.workflows import create_workflow_pattern
from shared.safeinput import REJECT_UNSET


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


def get_recipes_from_upload(configuration, user_arguments_dict, upload_key):
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
                json_recipes.append(json_recipe)
        except Exception as err:
            _logger.error("Failed to json load: %s from: %s " %
                          (err, user_arguments_dict[upload_key]))
            return []
    return json_recipes


def valid_recipe(configuration, recipe):
    """ Validate that the recipe has the
    minimum amount of content, with the correct types.
    """
    # TODO check for cell_type, code
    # TODO check for 'source' in each cell
    _logger = configuration.logger
    req_keys = [('cells', list), ('metadata', dict), ('nbformat', int)]
    incorrect_keys = {'missing': [], 'invalid': []}
    failed_msgs = []
    for key in req_keys:
        if key[0] not in recipe:
            incorrect_keys['missing'].append(key[0])
        if key[0] in recipe and not isinstance(recipe[key[0]], key[1]):
            incorrect_keys['invalid'].append(key[0])

    if incorrect_keys['missing']:
        output_keys = ' '.join(incorrect_keys['missing'])
        failed_msgs.append('Recipe %s the following required field: %s'
                           % (recipe['name'], output_keys))

    if incorrect_keys['invalid']:
        output_keys = ' '.join(incorrect_keys['invalid'])
        correct_types = '\n'.join([' is a '.join(key) for key in req_keys
                                   if key[0] in incorrect_keys['invalid']])
        failed_msgs.append('Recipe %s had invalid fields: %s '
                           ' requires that %s ' % (recipe['name'],
                                                   output_keys,
                                                   correct_types))

    # Detect which kernel to use (what language is used)
    # As specified at
    # https://nbformat.readthedocs.io/en/latest
    # /format_description.html?highlight=language_info
    # language_info['name'] tells which language is used in the recipe
    if 'language_info' not in recipe['metadata'] or 'name' not in \
            recipe['metadata']['language_info']:
        failed_msgs.append('Recipe %s language is not specified')

    lang = recipe['metadata']['language_info']['name']

    # TODO, make configuration.valid_recipe_langauges
    valid_languages = ['python']
    if lang not in valid_languages:
        output_lang = ' '.join(valid_languages)
        failed_msgs.append('Recipe %s defined langauge is not supported. '
                           ' Please use one of the following: %s'
                           % (recipe['name'], output_lang))
    if failed_msgs:
        return False, failed_msgs
    return True, []


def get_tags_from_cell(cell):
    """Returns a list of tags from a notebook cell"""
    if 'metadata' in cell and isinstance(cell['metadata'], dict):
        if 'tags' in cell['metadata'] and \
                isinstance(cell['metadata']['tags'], list):
            return cell['metadata']['tags']
    return None


def get_recipe_parameters(configuration, recipe):
    """Returns a dict of cells that contain recipes
    and parameters from the ipynb notebook.
    This is based on whether the cell dictionary has a key with
    the follwing format:
         'metadata': {'tags': ['recipe']}
    or
        'metadata': {'tags': ['parameters']}
    This is based on ipynb cell tagging.
    e.g. https://github.com/jupyterlab/jupyterlab-celltags"""

    rec_param = {'recipes': [], 'parameters': {}}
    if 'cells' in recipe and isinstance(recipe['cells'], list):
        for cell in recipe['cells']:
            tags = get_tags_from_cell(cell)
            if tags:
                [rec_param['recipes'].append(cell['source'])
                 if t == 'recipe' else rec_param['parameters'].update(
                    get_declarations_dict(configuration, cell['source'])
                ) if t == 'parameters' else None for t in tags]
    return rec_param


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
                              'more than a single assignments in line: %s'
                              % line)
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
    # TODO switch to acceped
    logger.debug("reqworkflowpattern as User: %s accepted %s" %
                 (client_id, user_arguments_dict))

    # Extract inputs, output and type-filter
    pattern_name, inputs_name, output_name, type_filter_name = 'name', 'input', \
        'output', 'type-filter'
    upload_key, upload_name = 'recipes', 'recipesfilename'

    inputs = user_arguments_dict[inputs_name]
    output = user_arguments_dict[output_name]
    type_filter = user_arguments_dict[type_filter_name]
    recipe_name = user_arguments_dict[upload_name]
    pattern_name = user_arguments_dict[pattern_name][0]

    paths = inputs + output
    for path in paths:
        if not valid_dir_input(configuration.user_home, path):
            logger.warning(
                'possible illegal directory traversal'
                'attempt pattern_dirs: %s' % path)
            output_objects.append({'object_type': 'error_text',
                                   'text': 'The path given: %s'
                                   ' is illgally formatted' % path})
            return (output_objects, returnvalues.CLIENT_ERROR)

    if not safe_handler(configuration, 'post', op_name, client_id,
                        get_csrf_limit(configuration), accepted):
        output_objects.append(
            {'object_type': 'error_text', 'text': '''Only accepting
            CSRF-filtered POST requests to prevent unintended updates'''
             })
        return (output_objects, returnvalues.CLIENT_ERROR)

    # Optional recipes
    recipes_n_parameters = []
    recipes = get_recipes_from_upload(configuration,
                                      user_arguments_dict, upload_key)
    if recipes:
        for recipe in recipes:
            valid, msgs = valid_recipe(configuration, recipe)
            if valid:
                # Extract recipe and parameter cells from recipe
                recipe_n_parameters = get_recipe_parameters(
                    configuration, recipe)
                if not recipe_n_parameters['recipes']:
                    output_objects.append({'object_type': 'error_text',
                                           'text': 'No recipe cells were '
                                           'found in %s' %
                                           user_arguments_dict[upload_name]})
                    return (output_objects, returnvalues.CLIENT_ERROR)
                recipes_n_parameters.append(recipe_n_parameters)
            else:
                for msg in msgs:
                    output_objects.append({'object_type': 'error_text',
                                           'text': msg})
                    return (output_objects, returnvalues.CLIENT_ERROR)
    elif not recipes:
        output_objects.append({'object_type': 'error_text',
                               'text': 'Failed to readin the uploaded '
                                       'recipe %s' % recipe_name})
        return (output_objects, returnvalues.CLIENT_ERROR)

    output_objects.append({'object_type': 'header', 'text':
                           ' Registering Pattern'})
    pattern = {
        'owner': client_id,
        'inputs': inputs,
        'output': output,
        'type_filter': type_filter,
    }
    # Add optional userprovided name
    if pattern_name:
        pattern['name'] = pattern_name
    # Add optional recipes
    if recipes and recipes_n_parameters:
        combined_rp = {}
        for rp in recipes_n_parameters:
            for k, v in rp.items():
                if k not in combined_rp:
                    combined_rp[k] = v
                else:
                    combined_rp.update(rp)
        pattern['recipes'] = combined_rp['recipes']
        pattern['variables'] = combined_rp['parameters']

    created, msg = create_workflow_pattern(configuration,
                                           client_id,
                                           pattern)
    if not created:
        output_objects.append({'object_type': 'error_text',
                               'text': msg})
        return (output_objects, returnvalues.SYSTEM_ERROR)

    output_objects.append({'object_type': 'text',
                           'text': 'Successfully registered the pattern'})

    # TODO if recipes exists (Attach to pattern)
    return (output_objects, returnvalues.OK)
