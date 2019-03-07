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
from shared.workflows import create_workflow_pattern, \
    rule_identification_from_pattern
from shared.safeinput import REJECT_UNSET


def signature():
    """Signaure of the main function"""

    defaults = {
        'vgrid_name': REJECT_UNSET,
        'wp_name': [''],
        'wp_inputs': REJECT_UNSET,
        'wp_output': REJECT_UNSET,
        'wp_recipes': ['']
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
    logger.debug("addworkflowpattern, cliend_id: %s accepted %s" %
                 (client_id, accepted))

    # Extract inputs, output and type-filter
    pattern_name, inputs_name, output_name, type_filter_name, recipe_name, \
    vgrid_name = 'wp_name', 'wp_inputs', 'wp_output', 'wp_type_filters', \
            'wp_recipes', 'vgrid_name'

    logger.debug("addworkflowpattern, accepted: " + str(accepted))

    inputs = accepted[inputs_name]
    output = accepted[output_name][-1]
    recipes = accepted[recipe_name]
    pattern_name = accepted[pattern_name][-1]
    vgrid = accepted[vgrid_name][-1]

    paths = inputs + [output]
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

    output_objects.append({'object_type': 'header', 'text':
                           ' Registering Pattern'})
    pattern = {
        'owner': client_id,
        'inputs': inputs,
        'output': output,
        'recipes': recipes
    }

    logger.debug("addworkflowpattern, created pattern: " + str(pattern))

    # Add optional userprovided name
    if pattern_name:
        pattern['name'] = pattern_name

    created, msg = create_workflow_pattern(configuration,
                                           client_id,
                                           pattern)
    if not created:
        output_objects.append({'object_type': 'error_text',
                               'text': msg})
        return (output_objects, returnvalues.SYSTEM_ERROR)

    output_objects.append({'object_type': 'text',
                           'text': "Successfully registered the pattern"})

    activatable, msg = rule_identification_from_pattern(configuration,
                                                    client_id, pattern, vgrid)

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
