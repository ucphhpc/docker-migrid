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

import re
import shared.returnvalues as returnvalues

from shared.base import valid_dir_input
from shared.defaults import csrf_field, wp_id_charset, wp_id_length
from shared.init import initialize_main_variables
from shared.handlers import safe_handler, get_csrf_limit
from shared.functional import validate_input_and_cert
from shared.workflows import define_pattern
from shared.safeinput import REJECT_UNSET
from shared.pwhash import generate_random_ascii


# TODO, regexes are usually defined in shared.defaults
NUM_REGEX = "[0123456789]+"
TEXT_REGEX = "[A-z_]+"
SPACE_REGEX = "[ \n\t]*"
MULTI_REGEX = "<" + NUM_REGEX \
              + SPACE_REGEX \
              + "," \
              + SPACE_REGEX \
              + NUM_REGEX \
              + SPACE_REGEX \
              + "," \
              + SPACE_REGEX \
              + TEXT_REGEX \
              + ">"

PATTERN_NAME, INPUTS_NAME, OUTPUT_NAME, RECIPE_NAME, VARIABLES_NAME, \
    VGRID_NAME = 'wp_name', 'wp_inputs', 'wp_output', 'wp_recipes', \
                 'wp_variables', 'vgrid_name'


def signature():
    """Signature of the main function"""

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
    """Returns a dictionary with the variable declarations in the list
    Expects that code is a list of strings"""
    declarations = {}
    _logger = configuration.logger
    for line in code:
        if isinstance(line, (unicode, str)):
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

    # TODO probably do this somewhere else? seems like this might have come up
    #  by now
    # convert recipes into list of entries
    sequences = [INPUTS_NAME, OUTPUT_NAME, RECIPE_NAME, VARIABLES_NAME]

    for sec in sequences:
        seperated_collection = []
        for entry in user_arguments_dict[sec]:
            # TODO change this to regex to account for spaces etc
            if ';' in entry:
                split_entry = entry.split(';')
                for split in split_entry:
                    seperated_collection.append(split)
            else:
                seperated_collection.append(entry)
        user_arguments_dict[sec] = seperated_collection

    logger.debug("addworkflowpattern, user_arguments_dict: " +
                 str(user_arguments_dict))

    # Extract inputs, output and type-filter
    # TODO, ask Jonas about recipe content validation
    #  skipping validation on recipe uploads for now

    singleInput = True
    # determine if single or multi input pattern
    if INPUTS_NAME in user_arguments_dict \
            and re.search(MULTI_REGEX, user_arguments_dict[INPUTS_NAME][-1]):
        singleInput = False
        output_objects.append(
            {'object_type': 'text', 'text': '''Multi-input pattern detected'''
             })
        logger.debug("addworkflowpattern, multi input pattern detected due to:"
                     " %s" % user_arguments_dict[INPUTS_NAME][-1])

    if singleInput:
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
    else:
        input_as_given = user_arguments_dict[INPUTS_NAME][-1].replace(' ', '')
        parameter_string = re.search(MULTI_REGEX, input_as_given).group(0)

        split = input_as_given.split(parameter_string)
        input_start = split[0]
        input_end = split[1]

        parameter_matches = re.findall(NUM_REGEX, parameter_string)

        first_index = int(parameter_matches[0])
        index_count = int(parameter_matches[1])

        user_arguments_dict[INPUTS_NAME] = []
        for x in range(index_count):
            input_path = '%s%s%s' % \
                         (input_start, (first_index + x), input_end)
            user_arguments_dict[INPUTS_NAME].append(input_path)

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

    logger.debug("addworkflowpattern, accepted: " + str(accepted))

    inputs_list = accepted[INPUTS_NAME]
    output_list = accepted[OUTPUT_NAME]
    recipes = accepted[RECIPE_NAME]
    variables_list = accepted[VARIABLES_NAME]
    name = accepted[PATTERN_NAME][-1]
    vgrid = accepted[VGRID_NAME][-1]

    logger.debug('pattern name: ' + str(name))
    if name == '':
        name = generate_random_ascii(wp_id_length, charset=wp_id_charset)

    if not safe_handler(configuration, 'post', op_name, client_id,
                        get_csrf_limit(configuration), accepted):
        output_objects.append(
            {'object_type': 'error_text', 'text': '''Only accepting
            CSRF-filtered POST requests to prevent unintended updates'''
             })
        return (output_objects, returnvalues.CLIENT_ERROR)

    # sort out variables
    variables_dict = {}
    if variables_list != ['']:
        for variable in variables_list:
            try:
                split = variable.split('=')
                key, value = split[0], split[1]

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

    paths = []
    output_dict = {}
    if output_list != ['']:
        for output in output_list:
            try:
                split = output.split('=')
                key, value = split[0], split[1]

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
                        creation. For example 'some_dir_name/*.txt' will match 
                        any .txt files in the some_dir_name directory'''
                        % value})

                output_dict[key] = value
                variables_dict[key] = "'" + key + "'"
                paths.append(value)
            except:
                output_objects.append({'object_type': 'error_text', 'text':
                    '''output list %s is incorrectly formatted. Should be one 
                    assignment of the form file=dir/file.txt''' % output})
                return (output_objects, returnvalues.CLIENT_ERROR)
    input_dict = {}
    if inputs_list != ['']:
        for input in inputs_list:
            # try:
            split = input.split('=')
            key, value = split[0], split[1]

            if key in variables_dict.keys():
                output_objects.append({'object_type': 'error_text', 'text':
                    '''input %s is defined as a variable. Please only 
                    define a variable once''' % key})
                return (output_objects, returnvalues.CLIENT_ERROR)
            if '*' not in value:
                output_objects.append({'object_type': 'text', 'text':
                    '''input file name %s is hard coded and will always 
                    read the same specific file. If this is not desired 
                    use a * character for dynamic name creation. For 
                    example 'some_dir_name/*.txt' will match any .txt 
                    files in the some_dir_name directory'''
                    % value})

            input_dict[key] = value
            variables_dict[key] = "'" + key + "'"
            paths.append(value)
            # except:
            #     output_objects.append({'object_type': 'error_text', 'text':
            #         '''input list %s is incorrectly formatted. Should be one
            #         assignment of the form file=dir/file.txt''' % input})
            #     return (output_objects, returnvalues.CLIENT_ERROR)

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

    # TODO sort out variables with strings

    pattern = {
        'owner': client_id,
        'trigger_paths': inputs_list,
        'output': output_dict,
        'recipes': recipes,
        'variables': variables_dict,
        'vgrids': vgrid
    }

    logger.debug("addworkflowpattern, created pattern: " + str(pattern))

    status, msg = define_pattern(configuration, client_id, vgrid, pattern)

    output_objects.append({'object_type': 'link',
                           'destination': 'vgridman.py',
                           'text': 'Back to the vgrid overview'})

    return (output_objects, returnvalues.OK)
