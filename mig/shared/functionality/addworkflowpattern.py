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
from shared.defaults import csrf_field, wp_id_charset, wp_id_length
from shared.init import initialize_main_variables
from shared.handlers import safe_handler, get_csrf_limit
from shared.functional import validate_input_and_cert
from shared.workflows import create_workflow_pattern, \
    rule_identification_from_pattern, protected_pattern_variables, \
    get_wp_with, update_workflow_pattern, WF_PATTERN_NAME
from shared.safeinput import REJECT_UNSET
from shared.pwhash import generate_random_ascii


def signature():
    """Signaure of the main function"""

    defaults = {
        'vgrid_name': REJECT_UNSET,
        'wp_name': [''],
        'wp_inputs': REJECT_UNSET,
        'wp_output': REJECT_UNSET,
        'wp_recipes': [''],
        'wp_variables': ['']
    }
    return ['registerpattern', defaults]


def get_tags_from_cell(cell):
    """Returns a list of tags from a notebook cell"""
    if 'metadata' in cell and isinstance(cell['metadata'], dict):
        if 'tags' in cell['metadata'] and \
                isinstance(cell['metadata']['tags'], list):
            return cell['metadata']['tags']
    return None


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

    logger.debug("DELETE ME - " + str(user_arguments_dict))
    logger.debug("DELETE ME - " + str(op_name))

    # TODO probably do this somewhere else? seems like this might have come up
    #  by now
    # convert recipes into list of entries

    listable = ['wp_recipes', 'wp_variables', 'wp_output']
    for list in listable:
        seperated_recipes = []
        for entry in user_arguments_dict[list]:
            # TODO change this to regex to account for spaces etc
            if ';' in entry:
                split_entry = entry.split(';')
                for split in split_entry:
                    seperated_recipes.append(split)
            else:
                seperated_recipes.append(entry)
        user_arguments_dict[list] = seperated_recipes

    logger.debug("addworkflowpattern, user_arguments_dict: " +
                 str(user_arguments_dict))

    # TODO, ask Jonas about recipe content validation
    #  skipping validation on recipe uploads for now

    (validate_status, accepted) = validate_input_and_cert(
        user_arguments_dict,
        defaults,
        output_objects,
        client_id,
        configuration,
        allow_rejects=False,
    )
    if not validate_status:
        return (accepted, returnvalues.CLIENT_ERROR)
    logger.debug("addworkflowpattern, client_id: %s accepted %s" %
                 (client_id, accepted))

    # Extract inputs, output and type-filter
    pattern_name, inputs_name, output_name, recipe_name, variables_name, \
    vgrid_name = 'wp_name', 'wp_inputs', 'wp_output', 'wp_recipes', \
                 'wp_variables', 'vgrid_name'

    logger.debug("addworkflowpattern, accepted: " + str(accepted))

    input = accepted[inputs_name][-1]
    output_list = accepted[output_name]
    recipes = accepted[recipe_name]
    variables_list = accepted[variables_name]
    name = accepted[pattern_name][-1]
    vgrid = accepted[vgrid_name][-1]

    logger.debug('pattern name: ' + str(name))
    if name == '':
        name = generate_random_ascii(wp_id_length, charset=wp_id_charset)

    paths = [input]

    if not safe_handler(configuration, 'post', op_name, client_id,
                        get_csrf_limit(configuration), accepted):
        output_objects.append(
            {'object_type': 'error_text', 'text': '''Only accepting
            CSRF-filtered POST requests to prevent unintended updates'''
             })
        return (output_objects, returnvalues.CLIENT_ERROR)

    # sort out variables
    variables_dict = {}
    for variable in protected_pattern_variables:
        if variable == WF_PATTERN_NAME:
            variables_dict[variable] = '\"' + name + '\"'
        else:
            variables_dict[variable] = '\"' + str(variable) + '\"'
    if variables_list != ['']:
        for variable in variables_list:
            try:
                split = variable.split('=')
                key, value = split[0], split[1]

                if key in protected_pattern_variables:
                    output_objects.append({'object_type': 'error_text', 'text':
                        '''variable %s is already defined by the system and 
                        cannot be defined by a user. Please rename your 
                        variable''' % key})
                    return (output_objects, returnvalues.CLIENT_ERROR)
                if key in variables_dict.keys():
                    output_objects.append({'object_type': 'error_text', 'text':
                        '''variable %s is defined multiple times. Please only 
                        define a variable once''' % key})
                    return (output_objects, returnvalues.CLIENT_ERROR)
                variables_dict[key] = value
            except:
                output_objects.append({'object_type': 'error_text', 'text':
                    '''variable %s is incorrectly formatted. Should be one 
                    assignment of the form a=1''' % variable})
                return (output_objects, returnvalues.CLIENT_ERROR)

    # TODO sort this out properly
    output_dict = {}
    if output_list != ['']:
        for output in output_list:
            logger.debug('DELETE ME output: ' + str(output))
            try:
                tuple = output.split('=')
                logger.debug('DELETE ME tuple: ' + str(tuple))
                key, value = tuple[0], tuple[1]

                if key in protected_pattern_variables:
                    output_objects.append({'object_type': 'error_text', 'text':
                        '''variable %s is already defined by the system and 
                        cannot be defined by a user. Please rename your 
                        output file''' % key})
                    return (output_objects, returnvalues.CLIENT_ERROR)
                if key in output_dict.keys():
                    output_objects.append({'object_type': 'error_text', 'text':
                        '''output %s is defined multiple times. Please only 
                        define an output once''' % key})
                    return (output_objects, returnvalues.CLIENT_ERROR)
                if key in variables_dict.keys():
                    output_objects.append({'object_type': 'error_text', 'text':
                        '''output %s is defined as a variable. Please only 
                        define a variable once''' % key})
                    return (output_objects, returnvalues.CLIENT_ERROR)
                if '*' not in value:
                    output_objects.append({'object_type': 'text', 'text':
                        '''output file name %s is hard coded and will always 
                        be overwritten by the most recent job to compete. If 
                        this is not desired use a * character for dynamic name 
                        creation''' % value})

                output_dict[key] = value
                variables_dict[key] = "'" + key + "'"
                paths.append(value)
            except:
                output_objects.append({'object_type': 'error_text', 'text':
                    '''output_list %s is incorrectly formatted. Should be one 
                    assignment of the form file=dir/file.txt''' % output})
                return (output_objects, returnvalues.CLIENT_ERROR)

    logger.debug("DELETE ME - addworkflowpattern, variables_dict: " + str(variables_dict))

    logger.debug("DELETE ME - paths: " + str(paths))
    for path in paths:
        if not valid_dir_input(configuration.user_home, path):
            logger.warning(
                'possible illegal directory traversal '
                'attempt pattern_dirs: %s' % path)
            output_objects.append({'object_type': 'error_text',
                                   'text': 'The path given: %s'
                                   ' is illgally formatted' % path})
            return (output_objects, returnvalues.CLIENT_ERROR)

    output_objects.append({'object_type': 'header', 'text':
                           ' Registering Pattern'})
    pattern = {
        'owner': client_id,
        'inputs': input,
        'output': output_dict,
        'recipes': recipes,
        'variables': variables_dict,
        'vgrids': vgrid
    }

    logger.debug("addworkflowpattern, created pattern: " + str(pattern))

    # Add optional userprovided name
    if name:
        pattern['name'] = name
        existing_pattern = get_wp_with(configuration,
                                       client_id=client_id,
                                       name=name,
                                       vgrids=vgrid)
        if existing_pattern is not None:
            logger.debug("addworkflowpattern, DELETE ME - existing patterns: "
                         + str(existing_pattern))
            persistence_id = existing_pattern['persistence_id']
            updated, msg = update_workflow_pattern(configuration,
                                                   client_id,
                                                   vgrid,
                                                   pattern,
                                                   persistence_id)
            if not updated:
                output_objects.append({'object_type': 'error_text',
                                       'text': msg})
                return (output_objects, returnvalues.SYSTEM_ERROR)
            output_objects.append({'object_type': 'text',
                                   'text': "Successfully updated the pattern"})
            return (output_objects, returnvalues.OK)

    created, msg = create_workflow_pattern(configuration,
                                           client_id,
                                           vgrid,
                                           pattern)
    if not created:
        output_objects.append({'object_type': 'error_text',
                               'text': msg})
        return (output_objects, returnvalues.SYSTEM_ERROR)

    output_objects.append({'object_type': 'text',
                           'text': "Successfully registered the pattern"})

    activatable, msg = rule_identification_from_pattern(configuration,
                                                        client_id,
                                                        pattern,
                                                        True)

    if activatable:
        output_objects.append({'object_type': 'text',
                               'text': "All required recipes are present, "
                                       "pattern is activatable"})
    else:
        output_objects.append({'object_type': 'text', 'text': msg})

    output_objects.append({'object_type': 'link',
                           'destination': 'vgridman.py',
                           'text': 'Back to the vgrid overview'})

    return (output_objects, returnvalues.OK)
