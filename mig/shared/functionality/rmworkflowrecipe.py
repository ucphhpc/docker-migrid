#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# --- BEGIN_HEADER ---
#
# rm - backend to remove files/directories in user home
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.
#
# -- END_HEADER ---
#

""" Module that enables a user to delete their own workflow recipes """


import shared.returnvalues as returnvalues
from shared.init import initialize_main_variables
from shared.functional import validate_input_and_cert, REJECT_UNSET
from shared.workflows import delete_workflow_recipe, get_workflow_with,\
    WORKFLOW_RECIPE


def signature():
    """Signature of the main function"""

    defaults = {
        'persistence_id': REJECT_UNSET,
        'vgrid': REJECT_UNSET
    }
    return ['', defaults]


def main(client_id, user_arguments_dict, environ=None):
    """Main function used by front end"""

    (configuration, logger, output_objects, op_name) = \
        initialize_main_variables(client_id, op_header=False,
                                  op_menu=client_id)

    logger.debug("called rmworkflowrecipe %s" % user_arguments_dict)
    defaults = signature()[1]
    (validate_status, accepted) = validate_input_and_cert(
        user_arguments_dict,
        defaults,
        output_objects,
        client_id,
        configuration,
        allow_rejects=False)
    if not validate_status:
        return (accepted, returnvalues.CLIENT_ERROR)

    persistence_id = accepted['persistence_id'][-1]
    vgrid = accepted['vgrid'][-1]

    success, msg = delete_workflow_recipe(configuration,
                                          client_id,
                                          vgrid,
                                          persistence_id)
    if not success:
        output_objects.append({'object_type': 'error_text',
                               'text': msg})
        return (output_objects, returnvalues.SYSTEM_ERROR)

    output_objects.append({'object_type': 'text',
                           'text': "%s" % msg})
    output_objects.append({'object_type': 'link',
                           'destination': 'workflowrecipes.py',
                           'text': "Back to the overview."})
    return (output_objects, returnvalues.OK)
