#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# --- BEGIN_HEADER ---
#
# jobsjsoninterface.py - JSON interface for
# managing jobs via cgisid requests
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

"""JSON interface for job related requests"""

import sys
import json
import shared.returnvalues as returnvalues

from shared.base import force_utf8_rec
from shared.init import initialize_main_variables
from shared.safeinput import REJECT_UNSET, valid_sid, validated_input, \
    html_escape, valid_job_id, valid_job_vgrid, valid_job_attributes, \
    valid_job_type, valid_job_operation
from shared.job import JOB_TYPES, JOB, QUEUE, get_job_with_id
from shared.workflows import WORKFLOW_TYPES, WORKFLOW_CONSTRUCT_TYPES, \
    WORKFLOW_PATTERN, valid_session_id, get_workflow_with,\
    load_workflow_sessions_db, create_workflow, delete_workflow,\
    update_workflow, touch_workflow_sessions_db, search_workflow, \
    WORKFLOW_ACTION_TYPES, WORKFLOW_SEARCH_TYPES
from shared.vgrid import get_vgrid_recent_jobs

JOB_API_CREATE = 'create'
JOB_API_READ = 'read'
JOB_API_UPDATE = 'update'
JOB_API_DELETE = 'delete'

PATTERN_LIST = 'pattern_list'
RECIPE_LIST = 'recipe_list'

VALID_OPERATIONS = [
    JOB_API_CREATE, JOB_API_READ, JOB_API_UPDATE, JOB_API_DELETE
]

JOB_SIGNATURE = {
    'attributes': {},
    'type': REJECT_UNSET,
    'operation': REJECT_UNSET,
    'workflowsessionid': REJECT_UNSET,
    'job_id': '',
    'vgrid': ''
}


def type_value_checker(type_value):
    """
    Validate that the provided job type is allowed. A ValueError
    Exception will be raised if type_value is invalid.
    :param type_value: The type to be checked. Valid types are 'job',
    and 'queue'
    :return: No return
    """
    valid_types = JOB_TYPES

    if type_value not in valid_types:
        raise ValueError("Workflow type '%s' is not valid"
                         % html_escape(valid_types))


def operation_value_checker(operation_value):
    """
    Validate that the provided job operation is allowed. A ValueError
    Exception will be raised if operation_value is invalid.
    :param operation_value: The operation to be checked. Valid operations are:
    'create', 'read', 'update' and 'delete'.
    :return: No return.
    """
    if operation_value not in VALID_OPERATIONS:
        raise ValueError("Workflow operation '%s' is not valid"
                         % html_escape(operation_value))


JOB_ATTRIBUTES_TYPE_MAP = {
    'job_id': valid_job_id,
    'vgrid': valid_job_vgrid
}


JOB_INPUT_TYPE_MAP = {
    'attributes': valid_job_attributes,
    'type': valid_job_type,
    'operation': valid_job_operation,
    'workflowsessionid': valid_sid
}

JOB_TYPE_MAP = dict(JOB_ATTRIBUTES_TYPE_MAP, **JOB_INPUT_TYPE_MAP)

JOB_VALUE_MAP = {
    'type': type_value_checker,
    'operation': operation_value_checker,
}


# Job API functions
def job_api_create(configuration, workflow_session, job_type=JOB,
                   **job_attributes):
    # """
    # Handler for 'create' calls to job API.
    # :param configuration: The MiG configuration object.
    # :param workflow_session: The MiG job session. This must contain the
    # key 'owner'
    # :param workflow_type: [optional] A MiG workflow construct type. This should
    # be one of 'workflowpattern' or 'workflowrecipe'. Default is
    # 'workflowpattern'.
    # :param workflow_attributes: dictionary of arguments used to create the
    # specified workflow object
    # :return: (Tuple (boolean, string) or function call to 'create_workflow')
    # if workflow_type is valid the function 'create_workflow' is called. Else,
    # a tuple is returned with a first value of False, and an explanatory error
    # message as the second value.
    # """
    # _logger = configuration.logger
    # _logger.debug("W_API: create: (%s, %s, %s)" % (workflow_session,
    #                                                workflow_type,
    #                                                workflow_attributes))
    #
    # if workflow_type in WORKFLOW_CONSTRUCT_TYPES:
    #     return create_workflow(configuration,
    #                            workflow_session['owner'],
    #                            workflow_type=workflow_type,
    #                            **workflow_attributes)
    # return (False, "Invalid workflow create api type: '%s', valid are: '%s'" %
    #         (workflow_type,
    #          ', '.join(WORKFLOW_CONSTRUCT_TYPES)))
    return (True, 'job_api_create response')


def job_api_read(configuration, workflow_session, job_type=JOB,
                 **job_attributes):
    # """
    # Handler for 'read' calls to workflow API.
    # :param configuration: The MiG configuration object.
    # :param workflow_session: The MiG workflow session. This must contain the
    # key 'owner'
    # :param workflow_type: [optional] A MiG workflow read type. This should
    # be one of 'job', 'queue', 'workflowpattern', 'workflowrecipe', 'any' or
    # 'pattern_graph'. Default is 'workflowpattern'.
    # :param workflow_attributes: dictionary of arguments used to select the
    # workflow object to read.
    # :return: (Tuple (boolean, string) or function call to 'get_jobs_with',
    # 'get_workflow_with' or 'search_workflow') If the given workflow_type is
    # either 'job' or 'queue' the function 'get_jobs_with' will be called. If
    # the given workflow type is either 'workflowpattern', 'workflowrecipe', or
    # 'any' the function 'get_workflow_with' is called. If the given
    # workflow_type is 'pattern_graph' the function 'search_workflow' is called.
    # If the given workflow_type is none of the above a tuple is returned with a
    # first value of False, and an explanatory error message as the second value.
    # """
    _logger = configuration.logger
    _logger.debug("J_API: search: (%s, %s, %s)"
                  % (workflow_session, job_type, job_attributes))

    if job_type == QUEUE:
        if 'vgrid' not in job_attributes:
            return (False, "Can't read job queue without 'vgrid' attribute")
        vgrid = job_attributes['vgrid']

        job_list = \
            get_vgrid_recent_jobs(configuration, vgrid, json_serializable=True)
        return  (True, job_list)
    else:
        if 'job_id' not in job_attributes:
            return (False, "Can't read single job without 'job_id' attribute")

        vgrid=None
        if 'vgrid' in job_attributes:
            vgrid = job_attributes['vgrid']

        return get_job_with_id(
            configuration,
            job_attributes['job_id'],
            client_id=workflow_session['owner'],
            vgrid=vgrid,
            only_user_jobs=False
        )


    # if job_type in JOB_TYPES:
    #     first = False
    #     if workflow_type == JOB:
    #         first = True
    #     return get_jobs_with(workflow_session['owner'],
    #                          configuration.mrsl_files_dir,
    #                          _logger,
    #                          first=first,
    #                          **workflow_attributes)
    # return (False, "Invalid workflow read api type: '%s', valid are: '%s'" %
    #         (workflow_type, ', '.join(WORKFLOW_TYPES + JOB_TYPES)))
    return (True, 'job_api_read response')


def job_api_update(configuration, workflow_session, job_type=JOB,
                   **job_attributes):
    # """
    # Handler for 'update' calls to workflow API.
    # :param configuration: The MiG configuration object.
    # :param workflow_session: The MiG workflow session. This must contain the
    # key 'owner'
    # :param workflow_type: [optional] A MiG workflow construct type. This should
    # be one of 'workflowpattern' or 'workflowrecipe'. Default is
    # 'workflowpattern'.
    # :param workflow_attributes: dictionary of arguments used to update the
    # specified workflow object. Must contain key 'vgrid'.
    # :return: (Tuple (boolean, string) or function call to 'update_workflow')
    # If the given workflow_type is valid the function 'update_workflow' will be
    # called. Else, a tuple is returned with a first value of False, and an
    # explanatory error message as the second value.
    # """
    # _logger = configuration.logger
    # _logger.debug("W_API: update: (%s, %s, %s)" % (workflow_session,
    #                                                workflow_type,
    #                                                workflow_attributes))
    #
    # if 'vgrid' not in workflow_attributes:
    #     return (False, "Can't create workflow %s without 'vgrid' attribute"
    #             % workflow_type)
    #
    # if workflow_type in WORKFLOW_CONSTRUCT_TYPES:
    #     return update_workflow(configuration, workflow_session['owner'],
    #                            workflow_type, **workflow_attributes)
    #
    # return (False, "Invalid workflow update api type: '%s', valid are: '%s'" %
    #         (workflow_type, ', '.join(WORKFLOW_CONSTRUCT_TYPES)))
    return (True, 'job_api_update response')


def job_api_delete(configuration, workflow_session, job_type=JOB,
                   **job_attributes):
    # """
    # Handler for 'delete' calls to workflow API.
    # :param configuration: The MiG configuration object.
    # :param workflow_session: The MiG workflow session. This must contain the
    # key 'owner'
    # :param workflow_type: [optional] A MiG workflow construct type. This should
    # be one of 'workflowpattern' or 'workflowrecipe'. Default is
    # 'workflowpattern'.
    # :param workflow_attributes: dictionary of arguments used to update the
    # specified workflow object. Must contain key 'persistence_id'.
    # :return: (Tuple (boolean, string) or function call to 'delete_workflow')
    # If the given workflow_type is valid the function 'delete_workflow' will be
    # called. Else, a tuple is returned with a first value of False, and an
    # explanatory error message as the second value.
    # """
    # _logger = configuration.logger
    # _logger.debug("W_API: delete: (%s, %s, %s)" % (workflow_session,
    #                                                workflow_type,
    #                                                workflow_attributes))
    #
    # if 'persistence_id' not in workflow_attributes:
    #     return (False, "Can't delete workflow without 'persistence_id' "
    #                    "attribute"
    #             % workflow_attributes)
    #
    # if workflow_type in WORKFLOW_CONSTRUCT_TYPES:
    #     return delete_workflow(configuration, workflow_session['owner'],
    #                            workflow_type, **workflow_attributes)
    #
    # return (False, "Invalid workflow update api type: '%s', valid are: '%s'" %
    #         (workflow_type, ', '.join(WORKFLOW_CONSTRUCT_TYPES)))
    return (True, 'job_api_delete response')


def main(client_id, user_arguments_dict):
    """
    Main function used by front end.
    :param client_id: A MiG user.
    :param user_arguments_dict: A JSON message sent to the MiG. This will be
    parsed and if valid, the relevant API handler functions are called to
    generate meaningful output.
    :return: (Tuple (list, Tuple(integer,string))) Returns a tuple with the
    first value being a list of output objects generated by the call. The
    second value is also a tuple used for error code reporting, with the first
    value being an error code and the second being a brief explanation.
    """
    # Ensure that the output format is in JSON
    user_arguments_dict['output_format'] = ['json']
    user_arguments_dict.pop('__DELAYED_INPUT__', None)
    (configuration, logger, output_objects, op_name) = \
        initialize_main_variables(client_id, op_title=False, op_header=False,
                                  op_menu=False)

    logger.info("Got job json request for client '%s' with arguments '%s'"
                % (client_id, user_arguments_dict))

    # Add allow Access-Control-Allow-Origin to headers
    # Required to allow Jupyter Widget from localhost to request against the
    # API
    # TODO, possibly restrict allowed origins
    output_objects[0]['headers'].append(('Access-Control-Allow-Origin', '*'))
    output_objects[0]['headers'].append(('Access-Control-Allow-Headers',
                                         'Content-Type'))
    output_objects[0]['headers'].append(('Access-Control-Max-Age', 600))
    output_objects[0]['headers'].append(('Access-Control-Allow-Methods',
                                         'POST, OPTIONS'))
    output_objects[0]['headers'].append(('Content-Type', 'application/json'))

    # if not configuration.site_enable_workflows:
    #     output_objects.append({
    #         'object_type': 'error_text',
    #         'text': 'Workflows are not enabled on this system'})
    #     return (output_objects, returnvalues.SYSTEM_ERROR)

    # Input data
    data = sys.stdin.read()
    try:
        json_data = json.loads(data, object_hook=force_utf8_rec)
    except ValueError:
        msg = "An invalid format was supplied to: '%s', requires a JSON " \
              "compatible format" % op_name
        logger.error(msg)
        output_objects.append({'object_type': 'error_text',
                               'text': msg})
        return (output_objects, returnvalues.CLIENT_ERROR)

    logger.info("Extracted json data: '%s'" % (json_data))

    # IMPORTANT!! Do not access the json_data input before it has been
    # validated by validated_input.
    accepted, rejected = validated_input(
        json_data, JOB_SIGNATURE,
        type_override=JOB_TYPE_MAP,
        value_override=JOB_VALUE_MAP,
        list_wrap=True)

    if not accepted or rejected:
        logger.error("A validation error occurred: '%s'" % rejected)
        msg = "Invalid input was supplied to the job API: %s" % rejected
        # TODO, Transform error messages to something more readable
        output_objects.append({'object_type': 'error_text', 'text': msg})
        return (output_objects, returnvalues.CLIENT_ERROR)

    job_attributes = json_data.get('attributes', None)
    job_type = json_data.get('type', None)
    operation = json_data.get('operation', None)
    workflow_session_id = json_data.get('workflowsessionid', None)

    if not valid_session_id(configuration, workflow_session_id):
        output_objects.append({'object_type': 'error_text',
                               'text': 'Invalid workflowsessionid'})
        return (output_objects, returnvalues.CLIENT_ERROR)

    # workflow_session_id symlink points to the vGrid it gives access to
    workflow_sessions_db = []
    try:
        workflow_sessions_db = load_workflow_sessions_db(configuration)
    except IOError:
        logger.debug("Workflow sessions db didn't load, creating new db")
        if not touch_workflow_sessions_db(configuration, force=True):
            output_objects.append(
                {'object_type': 'error_text',
                 'text': "Internal sessions db failure, please contact "
                         "an admin at '%s' to resolve this issue." %
                         configuration.admin_email})
            return (output_objects, returnvalues.SYSTEM_ERROR)
        else:
            # Try reload
            workflow_sessions_db = load_workflow_sessions_db(configuration)

    if workflow_session_id not in workflow_sessions_db:
        # TODO, Log this in the auth logger,
        # Also track multiple attempts from the same IP
        output_objects.append({'object_type': 'error_text',
                               'text': 'Invalid workflowsessionid'})
        return (output_objects, returnvalues.CLIENT_ERROR)

    workflow_session = workflow_sessions_db.get(workflow_session_id)
    logger.info('jobsjsoninterface found %s' % workflow_session)
    # Create
    if operation == JOB_API_CREATE:
        created, msg = job_api_create(configuration, workflow_session,
                                      job_type, **job_attributes)
        if not created:
            output_objects.append({'object_type': 'error_text',
                                   'text': msg})
            logger.error("Returning error msg '%s'" % msg)
            return (output_objects, returnvalues.CLIENT_ERROR)
        output_objects.append({'object_type': 'text', 'text': msg})
        return (output_objects, returnvalues.OK)
    # Read
    if operation == JOB_API_READ:
        jobs, msg = job_api_read(configuration, workflow_session,
                                 job_type, **job_attributes)
        if not jobs:
            output_objects.append(
                {'object_type': 'error_text',
                 'text': msg})
            return (output_objects, returnvalues.OK)

        output_objects.append({'object_type': 'job_list', 'jobs': msg})
        return (output_objects, returnvalues.OK)

    # Update
    if operation == JOB_API_UPDATE:
        updated, msg = job_api_update(configuration, workflow_session,
                                      job_type, **job_attributes)
        if not updated:
            output_objects.append({'object_type': 'error_text',
                                   'text': msg})
            return (output_objects, returnvalues.OK)
        output_objects.append({'object_type': 'text', 'text': msg})
        return (output_objects, returnvalues.OK)

    # Delete
    if operation == JOB_API_DELETE:
        deleted, msg = job_api_delete(configuration, workflow_session,
                                      job_type, **job_attributes)
        if not deleted:
            output_objects.append({'object_type': 'error_text',
                                   'text': msg})
            return (output_objects, returnvalues.OK)
        output_objects.append({'object_type': 'text', 'text': msg})
        return (output_objects, returnvalues.OK)

    output_objects.append({'object_type': 'error_text',
                           'text': 'You are out of bounds here'})
    return (output_objects, returnvalues.CLIENT_ERROR)
