#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# --- BEGIN_HEADER ---
#
# redb - manage runtime environments
# Copyright (C) 2003-2016  The MiG Project lead by Brian Vinter
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
# -- END_HEADER ---
#

"""Manage all the available workflow patterns"""

import shared.returnvalues as returnvalues
from shared.base import extract_field
from shared.init import initialize_main_variables, find_entry
from shared.functional import validate_input_and_cert
from shared.workflows import get_wp_map, build_wp_object, CONF


operations = ['show']


def signature():
    """Signature of the main function"""
    defaults = {'operation': ['show']}
    return ['workflowpatterns', defaults]


def main(client_id, user_arguments_dict):
    """Main function used by front end"""

    (configuration, logger, output_objects, op_name) = \
        initialize_main_variables(client_id, op_header=False)
    defaults = signature()[1]
    title_entry = find_entry(output_objects, 'title')
    title_entry['text'] = 'Workflow Patterns'
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

    operation = accepted['operation'][-1]

    if operation not in operations:
        output_objects.append({'object_type': 'text',
                               'text': '''Operation must be one of %s.''' %
                               ', '.join(operations)})
        return (output_objects, returnvalues.OK)

    logger.info("%s %s being for %s" % (op_name, operation, client_id))

    output_objects.append({'object_type': 'header',
                           'text': 'Workflow Patterns'})

    output_objects.append({'object_type': 'text',
                           'text': 'Workflow Patterns that can be applied to '
                           'local vgrids, these can be applied '
                           'as plug and play templates where custom recipes '
                           'can be attached upon application, .... '
                            'TODO fill out'})

    # TODO link to external readthedocs
    output_objects.append({'object_type': 'link',
                           'destination': '',
                           'class': 'infolink iconspace',
                           'title': 'Redirect to Workflow Pattern '
                                    'documentation',
                           'text': 'ReadTheDocs about Workflow Patterns'})

    output_objects.append({'object_type': 'sectionheader',
                           'text': 'Registered Workflow Patterns'})

    workflow_patterns = []
    workflow_pattern_map = get_wp_map(configuration)
    logger.info("Found workflow patterns map: %s" % workflow_pattern_map)
    for wp_file, wp_content in workflow_pattern_map.items():
        if CONF in wp_content:
            wp_dict = wp_content[CONF]
            wp_obj = build_wp_object(configuration, wp_dict)
            wp_obj = {
                'object_type': str(wp_obj['object_type']),
                'id': str(wp_obj['id']),
                'owner': str(extract_field(wp_obj['owner'], 'email')),
                'name': str(wp_obj['name'])
            }
            logger.info("build wp_obj: %s" % wp_obj)
            if wp_obj:
                workflow_patterns.append(wp_obj)

    output_objects.append({'object_type': 'workflowpatterns',
                           'workflowpatterns': workflow_patterns})
    logger.info("%s %s end for %s" % (op_name, operation, client_id))
    return (output_objects, returnvalues.OK)
