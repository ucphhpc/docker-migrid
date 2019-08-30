#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# --- BEGIN_HEADER ---
#
# showre - Display a runtime environment
# Copyright (C) 2003-2017  The MiG Project lead by Brian Vinter
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

"""Display information about a particular workflow recipe"""
import shared.returnvalues as returnvalues
from shared.functional import validate_input_and_cert, REJECT_UNSET
from shared.html import themed_styles
from shared.init import initialize_main_variables, find_entry
from shared.workflows import get_workflow_with, WORKFLOW_RECIPE


def signature():
    """Signature of the main function"""

    defaults = {'persistence_id': REJECT_UNSET,
                'vgrid': REJECT_UNSET}
    return ['workflowrecipe', defaults]


def main(client_id, user_arguments_dict):
    """Main function used by front end"""

    (configuration, logger, output_objects, op_name) = \
        initialize_main_variables(client_id, op_header=False)
    defaults = signature()[1]
    title_entry = find_entry(output_objects, 'title')
    title_entry['text'] = 'Show Workflow Recipe Details'
    (validate_status, accepted) = validate_input_and_cert(
        user_arguments_dict,
        defaults,
        output_objects,
        client_id,
        configuration,
        allow_rejects=False,
    )
    logger.info("show workflowrecipe entry as '%s'" % client_id)

    if not validate_status:
        return (accepted, returnvalues.CLIENT_ERROR)
    persistence_id = accepted['persistence_id'][-1]
    vgrid = accepted['vgrid'][-1]

    workflow = get_workflow_with(configuration, first=True,
                                 display_safe=True,
                                 workflow_type=WORKFLOW_RECIPE,
                                 vgrid=vgrid,
                                 persistence_id=persistence_id)

    if not workflow:
        output_objects.append({'object_type': 'error_text',
                               'text': 'Could not load the '
                               'workflow recipe'})
        return (output_objects, returnvalues.CLIENT_ERROR)

    # Prepare for display
    title_entry['style'] = themed_styles(configuration)
    output_objects.append({'object_type': 'header',
                           'text': "Show '%s' details" % workflow['name']})
    logger.info("showworkflowrecipe wr: %s" % workflow)
    output_objects.append({'object_type': 'workflowrecipe',
                           'workflowrecipe': workflow})
    logger.info("show workflowrecipe end as '%s'" % client_id)
    return (output_objects, returnvalues.OK)
