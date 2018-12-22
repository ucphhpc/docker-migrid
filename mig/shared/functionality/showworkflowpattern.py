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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
# -- END_HEADER ---
#

"""Display information about a particular workflow pattern"""
import os
import shared.returnvalues as returnvalues

from shared.base import valid_dir_input
from shared.functional import validate_input_and_cert, REJECT_UNSET
from shared.html import themed_styles
from shared.init import initialize_main_variables, find_entry
from shared.workflows import get_wp_with


def signature():
    """Signature of the main function"""

    defaults = {'wp_name': REJECT_UNSET}
    return ['workflowpattern', defaults]


def main(client_id, user_arguments_dict):
    """Main function used by front end"""

    (configuration, logger, output_objects, op_name) = \
        initialize_main_variables(client_id, op_header=False)
    defaults = signature()[1]
    title_entry = find_entry(output_objects, 'title')
    title_entry['text'] = 'Show Workflow Pattern Details'
    (validate_status, accepted) = validate_input_and_cert(
        user_arguments_dict,
        defaults,
        output_objects,
        client_id,
        configuration,
        allow_rejects=False,
    )
    logger.info("show workflowpattern entry as '%s'" % client_id)

    if not validate_status:
        return (accepted, returnvalues.CLIENT_ERROR)
    wp_name = accepted['wp_name'][-1]

    wp_client_home = os.path.join(configuration.workflow_patterns_home,
                                  client_id)
    if not valid_dir_input(wp_client_home, wp_name):
        logger.warning(
            "possible illegal directory traversal attempt '%s'"
            % wp_name)
        output_objects.append({'object_type': 'error_text',
                               'text': 'Illegal workflow '
                               'pattern name: "%s"' % wp_name})
        return (output_objects, returnvalues.CLIENT_ERROR)

    wp = get_wp_with(configuration, client_id=client_id, name=wp_name)
    if not wp:
        logger.warning("could not load workflow pattern with name %s" % wp_name)
        output_objects.append({'object_type': 'error_text',
                               'text': 'Could not load the '
                               'workflow pattern with name %s' % wp_name})
        return (output_objects, returnvalues.CLIENT_ERROR)

    # Prepare for display
    wp = {k: str(', '.join(v)) if isinstance(v, list) else str(v)
          for k, v in wp.items()}

    title_entry['style'] = themed_styles(configuration)
    output_objects.append({'object_type': 'header',
                           'text': 'Show workflow pattern details'})

    output_objects.append(wp)
    logger.info("show workflowpattern end as '%s'" % client_id)
    return (output_objects, returnvalues.OK)
