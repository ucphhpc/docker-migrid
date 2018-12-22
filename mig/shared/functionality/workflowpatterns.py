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
from shared.workflows import get_wp_with, CONF


operations = ['list']


def signature():
    """Signature of the main function"""
    defaults = {'operation': operations}
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
    logger.info("%s %s being for %s" % (op_name, operation, client_id))

    if operation == 'show':
        wp_name = ''
        wp = get_wp_with(configuration, client_id=client_id, name=wp_name)
        if wp:
            fill_helpers = {'name': wp['name'],
                            'owner': wp['owner'],
                            'type_filter': wp['type_filter'],
                            'inputs': wp['inputs'],
                            'output': wp['output']}
            output_objects.append({'object_type': 'header',
                                   'text': 'Workflow Pattern %(name)s'
                                   % fill_helpers})
            output_objects.append({'object_type': 'text',
                                   'text': 'Information about pattern X'})
            output_objects.append({'object_type': 'text',
                                   'text': 'Name: %(name)s <br/> '
                                   'Owner: %(owner)s <br/> '
                                   'Inputs: %(inputs)s <br/> '
                                   'Output: %(output)s <br/> '
                                   'Type-filter: %(type_filter)s <br/>'
                                   % fill_helpers})
            return (output_objects, returnvalues.OK)
        logger.info("could not find a workflow pattern with %s name" % wp_name)

    # default to list
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
    wps = get_wp_with(configuration, first=False, client_id=client_id)
    for wp in wps:
        # TODO dont' type cast
        #  add recipes and variables
        if wp.get('owner'):
            email = extract_field(wp['owner'], 'email')
            if email:
                wp['owner'] = email

        # Prepare for display, cast to string
        wp = {k: str(', '.join(v)) if isinstance(v, list) else str(v)
              for k, v in wp.items()}

        logger.debug("Workflow patterns wp %s" % wp)
        # Prepare name link
        wp['namelink'] = {'object_type': 'link',
                          'destination': 'showworkflowpattern.py?wp_name=%s'
                          % wp['name'],
                          'class': 'workflowlink',
                          'title': 'Show Workflow Pattern',
                          'text': '%s' % wp['name']}
        # TODO add link to delete pattern
        if wp:
            workflow_patterns.append(wp)

    output_objects.append({'object_type': 'workflowpatterns',
                           'workflowpatterns': workflow_patterns})
    return (output_objects, returnvalues.OK)
