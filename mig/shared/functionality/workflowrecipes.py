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

"""Manage all the available workflow recipes"""

import shared.returnvalues as returnvalues
from shared.base import extract_field
from shared.init import initialize_main_variables, find_entry
from shared.html import themed_styles, man_base_html, confirm_js, \
    jquery_ui_js, html_post_helper
from shared.handlers import get_csrf_limit, csrf_field
from shared.pwhash import make_csrf_token
from shared.functional import validate_input_and_cert
from shared.workflows import get_wr_with, CONF


list_operations = ['list']
allowed_operations = list_operations


def signature():
    """Signature of the main function"""
    defaults = {'operation': allowed_operations}
    return ['workflowrecipes', defaults]


def workflow_recipes_table(configuration,
                           client_id,
                           output_objects,
                           vgrid=None):
    output_objects.append({'object_type': 'sectionheader',
                           'text': 'Registered Workflow Recipes'})

    # Post token
    csrf_limit = get_csrf_limit(configuration)
    form_method = 'post'
    target_op = 'rmworkflowrecipe'
    csrf_token = make_csrf_token(configuration, form_method, target_op,
                                 client_id, csrf_limit)
    helper = html_post_helper(target_op, '%s.py' % target_op,
                              {'wr_name': '__DYNAMIC__',
                               'vgrid': '__DYNAMIC__',
                               csrf_field: csrf_token})

    workflow_recipes = []
    if vgrid:
        wrs = get_wr_with(configuration,
                          first=False,
                          vgrid=vgrid)
    else:
        wrs = get_wr_with(configuration,
                          first=False,
                          client_id=client_id)
    if wrs:
        output_objects.append({'object_type': 'html_form',
                               'text': helper})

    for wr in wrs:
        # TODO dont' type cast
        #  add recipes and variables

        if wr.get('owner'):
            email = extract_field(wr['owner'], 'email')
            if email:
                wr['owner'] = email

        # Prepare for display, cast to string
        wr = {
            'object_type': wr['object_type'],
            'name': wr['name'],
            'recipe': wr['recipe'],
            'triggers': wr['triggers']
        }

        # Prepare name link
        wr['namelink'] = {'object_type': 'link',
                          'destination': 'showworkflowrecipe.py?wr_name=%s'
                                         % wr['name'],
                          'class': 'workflowlink',
                          'title': 'Show Workflow Recipe',
                          'text': '%s' % wr['name']}
        # TODO add link to delete pattern
        wr['delwrlink'] = {'object_type': 'link',
                           'destination': "javascript: confirmDialog(%s, '%s', "
                                          "%s, %s);" % (target_op, "Really "
                                          "remove workflow recipe %s ?" %
                                          wr['name'], 'undefined', {'wr_name':
                                          wr['name'], 'vgrid': vgrid}),
                                          'class': 'removelink '
                                          'iconspace', 'title': 'Remove '
                                          'workflow recipe %s' % wr['name'],
                                          'text': ''}
        if wr:
            workflow_recipes.append(wr)

    output_objects.append({'object_type': 'workflowrecipes',
                           'workflowrecipes': workflow_recipes})


def main(client_id, user_arguments_dict):
    """Main function used by front end"""
    (configuration, logger, output_objects, op_name) = \
        initialize_main_variables(client_id, op_header=False)
    defaults = signature()[1]
    title_entry = find_entry(output_objects, 'title')
    title_entry['text'] = 'Workflow Recipes'
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

    if operation not in allowed_operations:
        output_objects.append({'object_type': 'error_text', 'text':
                               '''Operation must be one of %s.''' %
                               ', '.join(allowed_operations)})
        return (output_objects, returnvalues.OK)

    # Setup style and js (need confirm dialog)
    title_entry['style'] = themed_styles(configuration)
    (add_import, add_init, add_ready) = confirm_js(configuration)
    title_entry['javascript'] = jquery_ui_js(configuration, add_import,
                                             add_init, add_ready)
    output_objects.append({'object_type': 'html_form',
                           'text': man_base_html(configuration)})

    # default to list
    output_objects.append({'object_type': 'header',
                           'text': 'Workflow Recipes'})

    # TODO link to external readthedocs
    output_objects.append({'object_type': 'link',
                           'destination': '',
                           'class': 'infolink iconspace',
                           'title': 'Redirect to Workflow Recipe '
                           'documentation',
                           'text': 'ReadTheDocs about Workflow Recipes'})

    workflow_recipes_table(configuration, client_id, output_objects)

    return (output_objects, returnvalues.OK)
