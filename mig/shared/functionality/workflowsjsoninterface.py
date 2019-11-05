#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# --- BEGIN_HEADER ---
#
# workflowsjsoninterface.py - JSON interface for
# managing workflows via cgisid requests
# Copyright (C) 2003-2019  The MiG Project lead by Brian Vinter
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.
#
# -- END_HEADER ---
#

"""JSON interface for workflows related requests"""

import sys
import json
import shared.returnvalues as returnvalues
from shared.init import initialize_main_variables
from shared.safeinput import validated_input
from shared.job import get_jobs_with, JOB_TYPES, JOB
from shared.safeinput import valid_sid, valid_workflow_operation, \
    valid_workflow_type, valid_workflow_attributes, \
    InputException, REJECT_UNSET
from shared.workflows import WORKFLOW_TYPES, WORKFLOW_CONSTRUCT_TYPES, \
    WORKFLOW_PATTERN, valid_session_id, get_workflow_with,\
    load_workflow_sessions_db, create_workflow, delete_workflow,\
    update_workflow, touch_workflow_sessions_db, search_workflow, \
    WORKFLOW_ACTION_TYPES, WORKFLOW_SEARCH_TYPES

WORKFLOW_API_CREATE = 'create'
WORKFLOW_API_READ = 'read'
WORKFLOW_API_UPDATE = 'update'
WORKFLOW_API_DELETE = 'delete'

PATTERN_LIST = 'pattern_list'
RECIPE_LIST = 'recipe_list'

VALID_OPERATIONS = [WORKFLOW_API_CREATE, WORKFLOW_API_READ,
                    WORKFLOW_API_UPDATE, WORKFLOW_API_DELETE]

WORKFLOW_SIGNATURE = {
    'attributes': {},
    'type': REJECT_UNSET,
    'operation': REJECT_UNSET,
    'workflowsessionid': REJECT_UNSET
}

VALID_WORKFLOW_ATTRIBUTES = [
    'persistence_id',
    'vgrid',
    'name',
    'input_file',
    'input_paths'
    'output',
    'recipes',
    'variables',
    'parameterize_over'
]


def type_value_checker(type_value):
    """Validate that the provided workflow type is allowed"""
    valid_types = WORKFLOW_TYPES + WORKFLOW_ACTION_TYPES +\
                  WORKFLOW_SEARCH_TYPES + JOB_TYPES

    if type_value not in valid_types:
        raise ValueError("Workflow type '%s' is not valid"
                         % valid_types)


def operation_value_checker(operation_value):
    """Validate that the provided workflow operation is allowed"""
    if operation_value not in VALID_OPERATIONS:
        raise ValueError("Workflow operation '%s' is not valid")


WORKFLOW_TYPE_MAP = {
    'attributes': valid_workflow_attributes,
    'type': valid_workflow_type,
    'operation': valid_workflow_operation,
    'workflowsessionid': valid_sid
}

WORKFLOW_VALUE_MAP = {
    'type': type_value_checker,
    'operation': operation_value_checker,
}


# Workflow API functions
def workflow_api_create(configuration, workflow_session,
                        workflow_type=WORKFLOW_PATTERN, **workflow_attributes):
    """ """
    _logger = configuration.logger
    _logger.debug("W_API: create: (%s, %s, %s)" % (workflow_session,
                                                   workflow_type,
                                                   workflow_attributes))

    if workflow_type in WORKFLOW_CONSTRUCT_TYPES:
        return create_workflow(configuration,
                               workflow_session['owner'],
                               workflow_type=workflow_type,
                               **workflow_attributes)
    return (False, "Invalid workflow create api type: '%s', valid are: '%s'" %
            (workflow_type,
             ', '.join(WORKFLOW_CONSTRUCT_TYPES)))


def workflow_api_read(configuration, workflow_session,
                      workflow_type=WORKFLOW_PATTERN, **workflow_attributes):
    """ """
    logger = configuration.logger
    logger.debug("W_API: search: (%s, %s, %s)" % (workflow_session,
                                                  workflow_type,
                                                  workflow_attributes))
    if workflow_type in JOB_TYPES:
        first = False
        if workflow_type == JOB:
            first = True
        return get_jobs_with(workflow_session['owner'],
                             configuration.mrsl_files_dir,
                             logger,
                             first=first,
                             **workflow_attributes)
    elif workflow_type in WORKFLOW_TYPES:
        return get_workflow_with(configuration,
                                 workflow_session['owner'],
                                 user_query=True,
                                 workflow_type=workflow_type,
                                 **workflow_attributes)
    elif workflow_type in WORKFLOW_SEARCH_TYPES:
        return search_workflow(configuration,
                               workflow_session['owner'],
                               workflow_type=workflow_type,
                               **workflow_attributes)
    return (False, "Invalid workflow read api type: '%s', valid are: '%s'" %
            (workflow_type, ', '.join(WORKFLOW_TYPES + JOB_TYPES)))


def workflow_api_update(configuration, workflow_session,
                        workflow_type=WORKFLOW_PATTERN, **workflow_attributes):
    """ """
    _logger = configuration.logger
    _logger.debug("W_API: update: (%s, %s, %s)" % (workflow_session,
                                                   workflow_type,
                                                   workflow_attributes))

    if 'vgrid' not in workflow_attributes:
        return (False, "Can't create workflow %s without 'vgrid' attribute"
                % workflow_type)

    if workflow_type in WORKFLOW_CONSTRUCT_TYPES:
        return update_workflow(configuration, workflow_session['owner'],
                               workflow_type, **workflow_attributes)

    return (False, "Invalid workflow update api type: '%s', valid are: '%s'" %
            (workflow_type, ', '.join(WORKFLOW_CONSTRUCT_TYPES)))


# TODO, support deleting every workflow in vgrid without name
def workflow_api_delete(configuration, workflow_session,
                        workflow_type=WORKFLOW_PATTERN, **workflow_attributes):
    """ """
    _logger = configuration.logger
    _logger.debug("W_API: delete: (%s, %s, %s)" % (workflow_session,
                                                   workflow_type,
                                                   workflow_attributes))

    if 'persistence_id' not in workflow_attributes:
        return (False, "Can't delete workflow without 'persistence_id' "
                       "attribute"
                % workflow_attributes)

    if workflow_type in WORKFLOW_CONSTRUCT_TYPES:
        return delete_workflow(configuration, workflow_session['owner'],
                               workflow_type, **workflow_attributes)

    return (False, "Invalid workflow update api type: '%s', valid are: '%s'" %
            (workflow_type, ', '.join(WORKFLOW_CONSTRUCT_TYPES)))


def main(client_id, user_arguments_dict):
    """Main function used by front end"""
    # Ensure that the output format is in JSON
    user_arguments_dict['output_format'] = ['json']
    user_arguments_dict.pop('__DELAYED_INPUT__', None)

    (configuration, logger, output_objects, op_name) = \
        initialize_main_variables(client_id, op_title=False, op_header=False,
                                  op_menu=False)
    logger.debug("Workflowsjsoninterface.py entry %s" % output_objects)

    # Add allow Access-Control-Allow-Origin to headers
    # Required to allow Jupyter Widget from localhost to request against the
    # API
    output_objects[0]['headers'].append(('Access-Control-Allow-Origin', '*'))
    output_objects[0]['headers'].append(('Access-Control-Allow-Headers',
                                         'Content-Type'))
    output_objects[0]['headers'].append(('Access-Control-Max-Age', 600))
    output_objects[0]['headers'].append(('Access-Control-Allow-Methods',
                                         'POST, OPTIONS'))
    output_objects[0]['headers'].append(('Content-Type', 'application/json'))

    if not configuration.site_enable_workflows:
        output_objects.append({
            'object_type': 'error_text',
            'text': 'Workflows are not enabled on this system'})
        return (output_objects, returnvalues.SYSTEM_ERROR)

    # Input data
    data = sys.stdin.read()
    try:
        json_data = json.loads(data, object_pairs_hook=str_hook)
    except ValueError:
        msg = "An invalid format was supplied to: '%s', requires a JSON " \
              "compatible format" % op_name
        logger.error(msg)
        output_objects.append({'object_type': 'error_text',
                               'text': msg})
        return (output_objects, returnvalues.CLIENT_ERROR)

    # IMPORTANT!! Do not access the json_data input before it has been
    # validated by validated_input.
    accepted, rejected = validated_input(
        json_data, WORKFLOW_SIGNATURE,
        type_override=WORKFLOW_TYPE_MAP,
        value_override=WORKFLOW_VALUE_MAP)

    if not accepted or rejected:
        logger.error("A validation error occurred: '%s'" % rejected)
        msg = "Invalid input was supplied to the workflow API: %s" % rejected
        # Transform error messages to something more readable

        output_objects.append({'object_type': 'error_text', 'text': msg})
        return (output_objects, returnvalues.CLIENT_ERROR)

    # If key not present set default signature
    json_data.update({k: v for k, v in DEFAULT_SIGNATURE.items()
                      if k not in json_data})

    # Ensure only valid keys and value types are present in json_data
    for key, value in json_data.items():
        if key not in VALID_SIGNATURE_JSON_TYPES:
            output_objects.append(
                {'object_type': 'error_text',
                 'text': "Invalid key: '%s', was sent to workflows API,"
                         " allowed are: '%s'"
                         % (key, ','.join(VALID_SIGNATURE_JSON_TYPES.keys()))})
            return (output_objects, returnvalues.CLIENT_ERROR)
        if not isinstance(value, VALID_SIGNATURE_JSON_TYPES.get(key)):
            output_objects.append(
                {'object_type': 'error_text',
                 'text': "Invalid type: '%s' for key: '%s', requires: '%s'"
                         % (type(value), key,
                            VALID_SIGNATURE_JSON_TYPES.get(key))})
            return (output_objects, returnvalues.CLIENT_ERROR)

    # Validate that the json_data values are allowed
    for key, _filter in VALID_SIGNATURE_FILTER_MAP.items():
        value = json_data.get(key)
        # List of allowed values
        if isinstance(_filter, (list, tuple)) and value not in _filter:
            output_objects.append(
                {'object_type': 'error_text',
                 'text': "Invalid value: '%s' for key: '%s', allowed are: '%s'"
                         % (value, key, ','.join(_filter))})
            return (output_objects, returnvalues.CLIENT_ERROR)

        if callable(_filter):
            try:
                _filter(value)
            except InputException:
                output_objects.append(
                    {'object_type': 'error_text',
                     'text': "Invalid value: '%s' for key: '%s', failed on a "
                             "preset filter for that attribute type"
                             % (value, key)})
                return (output_objects, returnvalues.CLIENT_ERROR)

    logger.debug('Executing: %s, accepted: %s' % (op_name, json_data))

    workflow_attributes = json_data.get('attributes', None)
    workflow_type = json_data.get('type', None)
    operation = json_data.get('operation', None)
    workflow_session_id = json_data.get('workflowsessionid', None)

    if not valid_session_id(configuration, workflow_session_id):
        output_objects.append({'object_type': 'error_text',
                               'text': 'Invalid workflowsessionid',
                               'error_code': INVALID_SESSION_ID})
        return (output_objects, returnvalues.CLIENT_ERROR)

    # workflow_session_id symlink points to the vGrid it gives access to
    workflow_sessions_db = []
    try:
        workflow_sessions_db = load_workflow_sessions_db(configuration)
    except IOError as err:
        logger.debug("Workflow sessions db didn't load, creating new db")
        if not touch_workflow_sessions_db(configuration, force=True):
            output_objects.append(
                {'object_type': 'error_text',
                 'text': "Internal sessions db failure, please contact "
                         "an admin to resolve this issue."})
            return (output_objects, returnvalues.SYSTEM_ERROR)
        else:
            # Try reload
            workflow_sessions_db = load_workflow_sessions_db(configuration)

    if workflow_session_id not in workflow_sessions_db:
        output_objects.append({'object_type': 'error_text',
                               'error_text': 'Invalid workflowsessionid',
                               'error_code': INVALID_SESSION_ID})
        return (output_objects, returnvalues.CLIENT_ERROR)

    workflow_session = workflow_sessions_db.get(workflow_session_id)
    logger.info('workflowjsoninterface found %s' % workflow_session)
    # Create
    if operation == WORKFLOW_API_CREATE:
        created, msg = workflow_api_create(configuration,
                                           workflow_session,
                                           workflow_type,
                                           **workflow_attributes)
        if not created:
            output_objects.append({'object_type': 'error_text',
                                   'text': msg})
            logger.error("Returning error msg '%s'" % msg)
            return (output_objects, returnvalues.CLIENT_ERROR)
        output_objects.append({'object_type': 'workflows',
                               'text': msg})
        return (output_objects, returnvalues.OK)
    # Read
    if operation == WORKFLOW_API_READ:
        workflows = workflow_api_read(configuration, workflow_session,
                                      workflow_type, **workflow_attributes)
        # TODO change this to distinguish between incorrect attributes and
        #  just empty vgrids
        if not workflows:
            output_objects.append(
                {'object_type': 'error_text',
                 'text': 'Failed to find a workflow you own with '
                         'attributes: %s' % workflow_attributes,
                 'error_code': NOT_FOUND})
            return (output_objects, returnvalues.OK)

        output_objects.append({'object_type': 'workflows',
                               'workflows': workflows})
        return (output_objects, returnvalues.OK)

    # Update
    if operation == WORKFLOW_API_UPDATE:
        updated, msg = workflow_api_update(configuration, workflow_session,
                                           workflow_type,
                                           **workflow_attributes)
        if not updated:
            output_objects.append({'object_type': 'error_text',
                                   'text': msg})
            return (output_objects, returnvalues.OK)
        output_objects.append({'object_type': 'workflows',
                               'text': msg})
        return (output_objects, returnvalues.OK)

    # Delete
    if operation == WORKFLOW_API_DELETE:
        deleted, msg = workflow_api_delete(configuration, workflow_session,
                                           workflow_type,
                                           **workflow_attributes)
        if not deleted:
            output_objects.append({'object_type': 'error_text',
                                   'text': msg})
            return (output_objects, returnvalues.OK)
        output_objects.append({'object_type': 'workflows', 'text': msg})
        return (output_objects, returnvalues.OK)

    output_objects.append({'object_type': 'error_text',
                           'text': 'You are out of bounds here'})
    return (output_objects, returnvalues.CLIENT_ERROR)
