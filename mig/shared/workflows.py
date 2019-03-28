#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# --- BEGIN_HEADER ---
#
# refunctions - runtime environment functions
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.
#
# -- END_HEADER ---
#

"""Workflow functions"""

import copy
import fcntl
import json
import os
import time
import tempfile
import re

from hashlib import sha256

from shared.base import client_id_dir, force_utf8_rec
from shared.defaults import any_state, keyword_auto
from shared.events import get_path_expand_map
from shared.functional import REJECT_UNSET

from shared.base import client_id_dir, force_utf8_rec
from shared.map import load_system_map
from shared.modified import check_workflow_p_modified, \
    check_workflow_r_modified, reset_workflow_p_modified, \
    reset_workflow_r_modified, mark_workflow_p_modified, \
    mark_workflow_r_modified
from shared.pwhash import generate_random_ascii
from shared.defaults import wp_id_charset, wp_id_length, wr_id_charset, \
    wr_id_length
from shared.serial import dump
from shared.functionality.addvgridtrigger import main as add_vgrid_trigger_main
from shared.vgrid import vgrid_add_triggers, vgrid_remove_triggers, \
    vgrid_is_trigger, vgrid_triggers
from shared.job import fill_mrsl_template, new_job, fields_to_mrsl
from shared.fileio import delete_file
from shared.mrslkeywords import get_keywords_dict


WRITE_LOCK = 'write.lock'
WORKFLOW_PATTERNS, WORKFLOW_RECIPES, MODTIME, CONF = \
    ['__workflowpatterns__', '__workflowrecipes__', '__modtime__', '__conf__']
MAP_CACHE_SECONDS = 60

last_load = {WORKFLOW_PATTERNS: 0, WORKFLOW_RECIPES: 0}
last_refresh = {WORKFLOW_PATTERNS: 0, WORKFLOW_RECIPES: 0}
last_map = {WORKFLOW_PATTERNS: {}, WORKFLOW_RECIPES: {}}

VALID_PATTERN = {
    'object_type': str,
    'persistence_id': str,
    'trigger': dict,
    'owner': str,
    'name': str,
    'inputs': str,
    'output': str,
    'recipes': list,
    'variables': dict,
    'vgrids': str
}

VALID_RECIPE = {
    'object_type': str,
    'persistence_id': str,
    'triggers': dict,
    'owner': str,
    'name': str,
    'recipe': str,
    'vgrids': str,
}

# only update the triggers if these variables are changed in a pattern
UPDATE_TRIGGER_PATTERN = [
    'inputs',
    'outputs',
    'recipes',
    'variables'
]

# only update the triggers if these variables are changed in a recipe
UPDATE_TRIGGER_RECIPE = [
    'name',
    'recipe'
]

WF_INPUT, WF_OUTPUT, WF_PATTERN_NAME = \
    'wf_input_file', 'wf_output_file', 'wf_pattern_name'

protected_pattern_variables = [WF_INPUT, WF_OUTPUT, WF_PATTERN_NAME]


# TODO several of the following functions can probably be rolled together. If
#  at the end of implementation this is still the case then do so


def __correct_wp(configuration, wp):
    """Validates that the workflow pattern object is correctly formatted"""
    _logger = configuration.logger
    contact_msg = "please contact support so that we can help resolve this " \
                  "issue"

    if not wp:
        msg = "A workflow pattern was not provided, " + contact_msg
        _logger.error("WP: __correct_wp, wp was not set %s" % wp)
        return (False, msg)

    if not isinstance(wp, dict):
        msg = "The workflow pattern was incorrectly formatted, " + contact_msg
        _logger.error("WP: __correct_wp, wp had an incorrect type %s" % wp)
        return (False, msg)

    msg = "The workflow pattern had an incorrect structure, " + contact_msg
    for k, v in wp.items():
        if k not in VALID_PATTERN:
            _logger.error("WP: __correct_wp, wp had an incorrect key %s, "
                          "allowed are %s" % (k, VALID_PATTERN.keys()))
            return (False, msg)
        if not isinstance(v, VALID_PATTERN[k]):
            _logger.error("WP: __correct_wp, wp had an incorrect value type "
                          "%s, on key %s, valid is %s"
                          % (type(v), k, VALID_PATTERN[k]))
            return (False, msg)
    return (True, '')


def __correct_wr(configuration, wr):
    """Validates that the workflow recipe object is correctly formatted"""
    _logger = configuration.logger
    contact_msg = "Please contact support so that we can help resolve this " \
                  "issue"

    if not wr:
        msg = "A workflow recipe was not provided, " + contact_msg
        _logger.error("WR: __correct_wr, wr was not set %s" % wr)
        return (False, msg)

    if not isinstance(wr, dict):
        msg = "The workflow recipe was incorrectly formatted, " + contact_msg
        _logger.error("WR: __correct_wr, wr had an incorrect type %s" % wr)
        return (False, msg)

    msg = "The workflow pattern had an incorrect structure, " + contact_msg
    for k, v in wr.items():
        if k not in VALID_RECIPE:
            _logger.error("WR: __correct_wr, wr had an incorrect key %s, "
                          "allowed are %s" % (k, VALID_RECIPE.keys()))
            return (False, msg)
        if not isinstance(v, VALID_RECIPE[k]):
            _logger.error("WP: __correct_wr, wr had an incorrect value type "
                          "%s, on key %s, valid is %s"
                          % (type(v), k, VALID_RECIPE[k]))
            return (False, msg)
    return (True, '')


# TODO, validate inputs paths
#  For now that they are paths inside the vgrid
def __valid_inputs(inputs):
    pass


# TODO, validate the output path
#  For now that it is a path inside the vgrid
def __valid_output(output):
    pass


def __load_wp(configuration, wp_path):
    """Load the workflow pattern from the specified path"""
    _logger = configuration.logger
    _logger.debug("WP: load_wp, wp_path: %s" % wp_path)

    if not os.path.exists(wp_path):
        _logger.error("WP: %s does not exist" % wp_path)
        return {}

    try:
        wp = None
        with open(wp_path, 'r') as _wp_path:
            wp = json.load(_wp_path)
    except Exception, err:
        configuration.logger.error('WP: could not open workflow pattern %s %s'
                                   %(wp_path, err))
    if wp and isinstance(wp, dict):
        # Ensure string type
        wp = force_utf8_rec(wp)
        correct, _ = __correct_wp(configuration, wp)
        if correct:
            _logger.debug('DElETE ME - loaded wp: ' + str(wp))
            return wp
    return {}


def __load_wr(configuration, wr_path):
    """Load the workflow recipe from the specified path"""
    _logger = configuration.logger
    _logger.debug("WR: load_wr, wr_path: %s" % wr_path)

    if not os.path.exists(wr_path):
        _logger.error("WR: %s does not exist" % wr_path)
        return {}

    try:
        wr = None
        with open(wr_path, 'r') as _wr_path:
            wr = json.load(_wr_path)
    except Exception, err:
        configuration.logger.error('WR: could not open workflow recipe %s %s'
                                   %(wr_path, err))
    if wr and isinstance(wr, dict):
        # Ensure string type
        wr = force_utf8_rec(wr)
        correct, _ = __correct_wr(configuration, wr)
        if correct:
            return wr
    return {}


def __load_map(configuration, to_load, do_lock=True):
    """Load map of workflow patterns. Uses a pickled
    dictionary for efficiency. Optional do_lock option is used to enable and
    disable locking during load.
    """
    _logger = configuration.logger
    _logger.debug("Workflows: __load_map")
    if to_load == 'pattern':
        return load_system_map(configuration, 'workflowpatterns', do_lock)
    elif to_load == 'recipe':
        return load_system_map(configuration, 'workflowrecipes', do_lock)


def __refresh_map(configuration, to_refresh):
    """Refresh map of workflow objects. Uses a pickled dictionary for
    efficiency. Only update map for workflow objects that appeared or
    disappeared after last map save.
    NOTE: Save start time so that any concurrent updates get caught next time
    """
    _logger = configuration.logger
    _logger.debug("Workflows: __refresh_map")

    start_time = time.time()
    dirty = []
    map_path = ''
    if to_refresh == 'pattern':
        map_path = os.path.join(configuration.mig_system_files,
                            'workflowpatterns.map')
    elif to_refresh == 'recipe':
        map_path = os.path.join(configuration.mig_system_files,
                            'workflowrecipes.map')
    lock_path = map_path.replace('.map', '.lock')
    lock_handle = open(lock_path, 'a')
    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)

    workflow_map, map_stamp = __load_map(configuration, to_refresh,
                                             do_lock=False)

    _logger.debug('DELETE ME - workflow_map: ' + str(workflow_map))
    _logger.debug('DELETE ME - map_stamp: ' + str(map_stamp))

    # Find all workflow objectss
    (load_status, all_objects) = __list_path(configuration, to_refresh)
    _logger.debug('DELETE ME - load_status: ' + str(load_status))
    _logger.debug('DELETE ME - all_objects: ' + str(all_objects))
    if not load_status:
        _logger.warning('Workflows: failed to load list: %s' % all_objects)
        return workflow_map

    for workflow_dir, workflow_file in all_objects:
        _logger.debug('DELETE ME - workflow_dir: ' + str(workflow_dir))
        _logger.debug('DELETE ME - workflow_file: ' + str(workflow_file))
        wp_mtime = os.path.getmtime(os.path.join(workflow_dir, workflow_file))
        _logger.debug('DELETE ME - wp_mtime : ' + str(wp_mtime))
        _logger.debug('DELETE ME - map_stamp: ' + str(map_stamp))
        _logger.debug('DELETE ME - raw wp_mtime : %s' % wp_mtime)
        _logger.debug('DELETE ME - raw map_stamp: %s' % map_stamp)
        _logger.debug('DELETE ME - 10dp wp_mtime : %.10f' % wp_mtime)
        _logger.debug('DELETE ME - 10dp map_stamp: %.10f' % map_stamp)

        # init first time
        workflow_map[workflow_file] = workflow_map.get(workflow_file, {})
        if CONF not in workflow_map[workflow_file]:
            _logger.debug('DELETE ME - CONF is not in workflow_map[workflow_file]: ' + str(workflow_map[workflow_file]))
        if wp_mtime >= map_stamp:
            _logger.debug('DELETE ME - wp_mtime is greater than or equal to map_stamp: ' + str(wp_mtime) + ' ' + str(map_stamp))
        _logger.debug(str(wp_mtime >= map_stamp))

        if CONF not in workflow_map[workflow_file] or wp_mtime >= map_stamp:
            object = ''
            if to_refresh == 'pattern':
                object = __load_wp(configuration, os.path.join(workflow_dir,
                                                               workflow_file))
                _logger.debug(
                    'DELETE ME - pattern object: ' + str(object))
            elif to_refresh == 'recipe':
                object = __load_wr(configuration, os.path.join(workflow_dir,
                                                               workflow_file))
                _logger.debug(
                    'DELETE ME - recipe object: ' + str(object))
            workflow_map[workflow_file][CONF] = object
            workflow_map[workflow_file][MODTIME] = map_stamp
            dirty.append([workflow_file])

    # Remove any missing workflow patterns from map
    missing_workflow = [workflow_file for workflow_file in workflow_map.keys()
                  if workflow_file not in [_workflow_file for _workflow_path, _workflow_file in
                                     all_objects]]

    for workflow_file in missing_workflow:
        del workflow_map[workflow_file]
        dirty.append([workflow_file])

    if dirty:
        try:
            dump(workflow_map, map_path)
            os.utime(map_path, (start_time, start_time))
        except Exception, err:
            _logger.error('Workflows: could not save map, or %s' % err)
    if to_refresh == 'pattern':
        last_refresh[WORKFLOW_PATTERNS] = start_time
    elif to_refresh == 'recipe':
        last_refresh[WORKFLOW_RECIPES] = start_time
    lock_handle.close()
    return workflow_map


def __list_path(configuration, to_get):
    """Returns a list of tuples, containing the path to the individual
    workflow objects and the actual objects. These can be either patterns or
    recipes: (path,wp)
    """
    _logger = configuration.logger
    _logger.debug("Workflows: __list_path")

    # patterns = []
    objects = []
    # Note that this is currently listing all objects for all users. This
    # might want to be altered to only the current user and global? That might
    # be to much needless processing if multiple users are using the system at
    # once though. Talk to Jonas/Martion about this. Also note this system is
    # terrible
    user_home_dir = configuration.user_home
    client_dirs = os.listdir(user_home_dir)
    client_dirs.remove('no_grid_jobs_in_grid_scheduler')
    for client_dir in client_dirs:
        if os.path.isdir(os.path.join(user_home_dir, client_dir)):
            client_home = ''
            if to_get == 'pattern':
                client_home = get_workflow_pattern_home(configuration, client_dir)
            elif to_get == 'recipe':
                client_home = get_workflow_recipe_home(configuration, client_dir)
            else:
                return (False, "Invalid input. Must be 'pattern' or 'recipe'")
            if not os.path.exists(client_home):
                try:
                    os.makedirs(client_home)
                    _logger.debug('create client dir: ' + client_home)
                except Exception, err:
                    _logger.error('WP: not able to create directory %s %s' %
                                  (client_home, err))
                    return (
                    False, 'Failed to setup required directory for workflow ' +
                            to_get)
            dir_content = os.listdir(client_home)
            for entry in dir_content:
                # Skip dot files/dirs and the write lock
                if entry.startswith('.') or entry == WRITE_LOCK:
                    continue
                if os.path.isfile(os.path.join(client_home, entry)):
                    objects.append((client_home, entry))
                else:
                    _logger.warning('WP: %s in %s is not a plain file, move it?' %
                                    (entry, client_home))
    return (True, objects)


def __query_map_for_patterns(configuration, client_id=None, **kwargs):
    """"""
    _logger = configuration.logger
    _logger.debug("WP: query_map, client_id: %s, kwargs: %s" % (client_id,
                                                                kwargs))
    wp_map = get_wp_map(configuration)
    if client_id:
        wp_map = {k: v for k, v in wp_map.items()
                  if CONF in v and 'owner' in v[CONF]
                  and client_id == v[CONF]['owner']}

    matches = []
    for _, wp_content in wp_map.items():
        _logger.debug("WP: looking at: " + str(wp_content))

        if CONF in wp_content:
            wp_obj = __build_wp_object(configuration, **wp_content[CONF])
            _logger.debug("WP: wp_obj %s" % wp_obj)
            if not wp_obj:
                _logger.debug("WP: wasn't a wp object")
                continue

            all_match = True
            for k, v in kwargs.items():
                if (k not in wp_obj) or (wp_obj[k] != v):
                    all_match = False
            if all_match:
                matches.append(wp_obj)
            # if kwargs:
            #     _logger.debug("WP: got some kwargs")
            #     for k, v in kwargs.items():
            #         _logger.debug("WP: k: " + str(k))
            #         _logger.debug("WP: v: " + str(v))
            #         if k in wp_obj and v == wp_obj[k]:
            #             _logger.debug("WP: matches! : " + str(wp_obj))
            #             matches.append(wp_obj)
            # else:
            #     matches.append(wp_obj)
    return matches


def __query_map_for_recipes(configuration, client_id=None, **kwargs):
    """"""
    _logger = configuration.logger
    _logger.debug("WR: query_map, client_id: %s, kwargs: %s" % (client_id,
                                                                kwargs))
    wr_map = get_wr_map(configuration)
    if client_id:
        wr_map = {k: v for k, v in wr_map.items()
                  if CONF in v and 'owner' in v[CONF]
                  and client_id == v[CONF]['owner']}

    matches = []
    for _, wr_content in wr_map.items():
        if CONF in wr_content:
            wr_obj = __build_wr_object(configuration, **wr_content[CONF])
            _logger.debug("WR: wr_obj %s" % wr_obj)
            if not wr_obj:
                continue
            all_match = True
            for k, v in kwargs.items():
                if (k not in wr_obj) or (wr_obj[k] != v):
                    all_match = False
            if all_match:
                matches.append(wr_obj)
            # if kwargs:
            #     for k, v in kwargs.items():
            #         if k in wr_obj and v == wr_obj[k]:
            #             matches.append(wr_obj)
            # else:
            #     matches.append(wr_obj)
    return matches


def __query_map_for_first_patterns(configuration, client_id=None, **kwargs):
    """"""
    _logger = configuration.logger
    _logger.debug("WP: query_map_first, client_id: %s, kwargs: %s"
                  % (client_id, kwargs))
    wp_map = get_wp_map(configuration)
    if client_id:
        wp_map = {k: v for k, v in wp_map.items()
                  if CONF in v and 'owner' in v[CONF]
                  and client_id == v[CONF]['owner']}

    for _, wp_content in wp_map.items():
        if CONF in wp_content:
            wp_obj = __build_wp_object(configuration, **wp_content[CONF])
            _logger.debug("WP: wp_obj %s" % wp_obj)
            if not wp_obj:
                continue
            all_match = True
            for k, v in kwargs.items():
                if (k not in wp_obj) or (wp_obj[k] != v):
                    all_match = False
            if all_match:
                return wp_obj
            # if kwargs:
            #     for k, v in kwargs.items():
            #         if k in wp_obj and v == wp_obj[k]:
            #             return wp_obj
            # else:
            #     return wp_obj
    return None


def __query_map_for_first_recipes(configuration, client_id=None, **kwargs):
    """"""
    _logger = configuration.logger
    _logger.debug("WR: query_map_first, client_id: %s, kwargs: %s"
                  % (client_id, kwargs))
    wr_map = get_wr_map(configuration)
    if client_id:
        wr_map = {k: v for k, v in wr_map.items()
                  if CONF in v and 'owner' in v[CONF]
                  and client_id == v[CONF]['owner']}

    for _, wr_content in wr_map.items():
        if CONF in wr_content:
            wr_obj = __build_wr_object(configuration, **wr_content[CONF])
            _logger.debug("WR: wr_obj %s" % wr_obj)
            if not wr_obj:
                continue
            all_match = True
            for k, v in kwargs.items():
                if (k not in wr_obj) or (wr_obj[k] != v):
                    all_match = False
            if all_match:
                return wr_obj
            # if kwargs:
            #     for k, v in kwargs.items():
            #         if k in wr_obj and v == wr_obj[k]:
            #             return wr_obj
            # else:
            #     return wr_obj
    return None


def __build_wp_object(configuration, **kwargs):
    """Build a workflow pattern object based on keyword arguments."""
    _logger = configuration.logger
    _logger.debug("WP: __build_wp_object, kwargs: %s" % kwargs)
    correct, _ = __correct_wp(configuration, kwargs)
    if not correct:
        return None

    wp_obj = {
        'object_type': 'workflowpattern',
        'persistence_id': kwargs.get('persistence_id',
                                     VALID_PATTERN['persistence_id']()),
        'owner': kwargs.get('owner', VALID_PATTERN['owner']()),
        'name': kwargs.get('name', VALID_PATTERN['name']()),
        'inputs': kwargs.get('inputs', VALID_PATTERN['inputs']()),
        'output': kwargs.get('output', VALID_PATTERN['output']()),
        'recipes': kwargs.get('recipes', VALID_PATTERN['recipes']()),
        'variables': kwargs.get('variables', VALID_PATTERN['variables']()),
        'trigger': kwargs.get('trigger', VALID_PATTERN['trigger']()),
        'vgrids': kwargs.get('vgrids', VALID_PATTERN['vgrids']())
    }
    return wp_obj


def __build_wr_object(configuration, **kwargs):
    """Build a workflow recipe object based on keyword arguments."""
    _logger = configuration.logger
    _logger.debug("WR: __build_wr_object, kwargs: %s" % kwargs)
    correct, _ = __correct_wr(configuration, kwargs)
    if not correct:
        return None

    wr_obj = {
        'object_type': 'workflowrecipe',
        'persistence_id': kwargs.get('persistence_id',
                                     VALID_RECIPE['persistence_id']()),
        'owner': kwargs.get('owner', VALID_RECIPE['owner']()),
        'name': kwargs.get('name', VALID_RECIPE['name']()),
        'recipe': kwargs.get('recipe', VALID_RECIPE['recipe']()),
        'triggers': kwargs.get('triggers', VALID_RECIPE['triggers']()),
        'vgrids': kwargs.get('vgrids', VALID_RECIPE['vgrids']())
    }
    return wr_obj


def get_workflow_pattern_home(configuration, client_dir):
    user_home_dir = os.path.join(configuration.user_home, client_dir)
    pattern_home = user_home_dir + configuration.workflow_patterns_home
    return pattern_home


def get_workflow_recipe_home(configuration, client_dir):
    user_home_dir = os.path.join(configuration.user_home, client_dir)
    recipe_home = user_home_dir + configuration.workflow_recipes_home
    return recipe_home


def get_workflow_task_home(configuration, client_dir):
    user_home_dir = os.path.join(configuration.user_home, client_dir)
    task_home = user_home_dir + configuration.workflow_tasks_home
    return task_home


def get_wp_map(configuration):
    """Returns the current map of workflow patterns and
    their configurations. Caches the map for load prevention with
    repeated calls within short time span.
    """
    _logger = configuration.logger
    _logger.debug("WP: get_wp_map")
    # TODO, if deletion has happend don't use cache
    # if last_load[WORKFLOW_PATTERNS] + MAP_CACHE_SECONDS > time.time():
    #    _logger.debug('WP: using map')
    #    return last_map[WORKFLOW_PATTERNS]
    modified_patterns, _ = check_workflow_p_modified(configuration)
    if modified_patterns:
        _logger.info('WP: refreshing map (%s)'
                     % modified_patterns)
        map_stamp = time.time()
        workflow_p_map = __refresh_map(configuration, 'pattern')
        reset_workflow_p_modified(configuration)
    else:
        _logger.debug('WP: no changes - not refreshing')
        workflow_p_map, map_stamp = __load_map(configuration, 'pattern')
    last_map[WORKFLOW_PATTERNS] = workflow_p_map
    last_refresh[WORKFLOW_PATTERNS] = map_stamp
    last_load[WORKFLOW_PATTERNS] = map_stamp
    return workflow_p_map


def get_wr_map(configuration):
    """Returns the current map of workflow recipes and
    their configurations. Caches the map for load prevention with
    repeated calls within short time span.
    """
    _logger = configuration.logger
    _logger.debug("WR: get_wr_map")
    modified_recipes, _ = check_workflow_r_modified(configuration)
    if modified_recipes:
        _logger.info('WR: refreshing map (%s)'
                     % modified_recipes)
        map_stamp = time.time()
        workflow_r_map = __refresh_map(configuration, 'recipe')
        reset_workflow_r_modified(configuration)
    else:
        _logger.debug('WR: no changes - not refreshing')
        workflow_r_map, map_stamp = __load_map(configuration, 'recipe')
    last_map[WORKFLOW_RECIPES] = workflow_r_map
    last_refresh[WORKFLOW_RECIPES] = map_stamp
    last_load[WORKFLOW_RECIPES] = map_stamp
    _logger.debug('WR: wr_map: - ' + str(workflow_r_map))
    return workflow_r_map


def get_wp_with(configuration, first=True, client_id=None, **kwargs):
    """Returns a clients workflow pattern with a field_name"""
    _logger = configuration.logger
    _logger.debug("WP: get_wp_with, client_id: %s, kwargs: %s"
                  % (client_id, kwargs))
    if not isinstance(kwargs, dict):
        _logger.error('WP: wrong format supplied for %s', type(kwargs))
        return None
    if first:
        wp = __query_map_for_first_patterns(configuration, client_id, **kwargs)
    else:
        wp = __query_map_for_patterns(configuration, client_id, **kwargs)
    return wp


def get_wr_with(configuration, first=True, client_id=None, **kwargs):
    """Returns a clients workflow recipe with a field_name"""
    _logger = configuration.logger
    _logger.debug("WR: get_wr_with, client_id: %s, kwargs: %s"
                  % (client_id, kwargs))
    if not isinstance(kwargs, dict):
        _logger.error('WR: wrong format supplied for %s', type(kwargs))
        return None
    if first:
        wr = __query_map_for_first_recipes(configuration, client_id, **kwargs)
    else:
        wr = __query_map_for_recipes(configuration, client_id, **kwargs)
    return wr


def get_pattern(map_object):
    """ Function to return a pattern object from a map entry. This will strip
    off any system metadata"""
    return map_object[CONF]


def get_recipe(map_object):
    """ Function to return a recipe object from a map entry. This will strip
        off any system metadata"""
    return map_object[CONF]


def delete_workflow_pattern(configuration, client_id, name):
    """Delete a workflow pattern"""
    _logger = configuration.logger
    _logger.debug("WP: delete_workflow_pattern, client_id: %s, name: %s"
                  % (client_id, name))
    if not client_id:
        msg = "A workflow pattern removal dependency was missing"
        _logger.error("WP: delete_workflow, cliend_id was not set %s" %
                      client_id)
        return (False, msg)
    if not name:
        msg = "A workflow pattern removal dependency was missing"
        _logger.error("WP: delete_workflow, name was not set %s" % name)
        return (False, msg)

    client_dir = client_id_dir(client_id)
    wp = get_wp_with(configuration, client_id=client_id, name=name)
    persistence_id = wp['persistence_id']

    if wp['trigger']:
        rule_deletion_from_pattern(configuration, client_id, wp)

    wp_path = os.path.join(get_workflow_pattern_home(
        configuration, client_dir), persistence_id)
    if not os.path.exists(wp_path):
        msg = "The '%s' workflow pattern dosen't appear to exist" % name
        _logger.error("WP: can't delete %s it dosen't exist" % wp_path)
        return (False, msg)

    if not delete_file(wp_path, configuration.logger):
        msg = "Could not delete the '%s' workflow pattern"
        return (False, msg)
    mark_workflow_p_modified(configuration, persistence_id)


    return (True, '')


def delete_workflow_recipe(configuration, client_id, name):
    """Delete a workflow recipe"""
    _logger = configuration.logger
    _logger.debug("WR: delete_workflow_recipe, client_id: %s, name: %s"
                  % (client_id, name))
    if not client_id:
        msg = "A workflow recipe removal dependency was missing"
        _logger.error("WR: delete_recipe, cliend_id was not set %s" %
                      client_id)
        return (False, msg)
    if not name:
        msg = "A workflow recipe removal dependency was missing"
        _logger.error("WR: delete_recipe, name was not set %s" % name)
        return (False, msg)

    client_dir = client_id_dir(client_id)
    wr = get_wr_with(configuration, client_id=client_id, name=name)
    persistence_id = wr['persistence_id']

    _logger.debug("DELETE ME wr: - " + str(wr))

    if wr['triggers']:
        rule_deletion_from_recipe(configuration, client_id, wr)

    if not wr:
        msg = "The '%s' workflow recipe dosen't appear to exist" % name
        _logger.error("WR: can't delete %s it dosen't exist" % name)
        return (False, msg)

    wr_path = os.path.join(get_workflow_recipe_home(
        configuration, client_dir), persistence_id)
    if not os.path.exists(wr_path):
        msg = "The '%s' workflow recipe has been moved/deleted already" % name
        _logger.error("WR: can't delete %s it no longer exists" % wr_path)
        return (False, msg)

    if not delete_file(wr_path, configuration.logger):
        msg = "Could not delete the '%s' workflow recipe"
        return (False, msg)
    mark_workflow_r_modified(configuration, persistence_id)
    return (True, '')


def create_workflow_pattern(configuration, client_id, wp):
    """ Creates a workflow patterns based on the passed wp object.
    Requires the following keys and structure:

    wp = {
        'name': 'pattern-name'
        'owner': 'string-owner',
        'inputs': '',
        'recipes': [],
        'output': ''
    }

    The 'owner' key is required to be non-empty string.
    If a 'name' is not provided a random one will be generated.
    Every additional key should follow the defined types structure,
    if any of these is left out a default empty structure will be defined.

    Additional keys/data are allowed and will be saved
    with the required information.

    Result is that a JSON object of the dictionary structure will be saved
    to the configuration.mig_system_files/client_dir/generated_id.json
    """

    # Prepare json for writing.
    # The name of the directory to be used in both the users home
    # and the global state/workflow_patterns_home directory
    _logger = configuration.logger
    _logger.debug("WP: create_workflow_pattern, client_id: %s, wp: %s"
                  % (client_id, wp))

    if not client_id:
        msg = "A workflow pattern create dependency was missing"
        _logger.error("WP: create_workflow, client_id was not set %s" %
                      client_id)
        return (False, msg)

    correct, msg = __correct_wp(configuration, wp)
    if not correct:
        return (correct, msg)

    # TODO check for create required keys
    client_dir = client_id_dir(client_id)
    if 'name' not in wp:
        wp['name'] = generate_random_ascii(wp_id_length, charset=wp_id_charset)
    else:
        wp_exists = get_wp_with(configuration, client_id=client_id,
                                name=wp['name'])
        if wp_exists:
            _logger.error("WP: a wp with name: %s already exists: %s"
                          % (wp['name'], client_id))
            msg = 'You already have a workflow pattern with the name %s' \
                  % wp['name']
            return (False, msg)

    # TODO apply this to pattern as well
    # need to still check variables as they might not match exactly
    clients_patterns = get_wp_with(configuration,
                                   client_id=client_id,
                                   first=False,
                                   owner=client_id,
                                   inputs=wp['inputs'],
                                   output=wp['output'],
                                   vgrids=wp['vgrids'])
    _logger.debug('clients_patterns: ' + str(clients_patterns))
    _logger.debug('wp: ' + str(wp))
    for pattern in clients_patterns:
        pattern_matches = True
        for variable in wp['variables'].keys():
            # ignore wf_pattern_name variable
            if variable != WF_PATTERN_NAME:
                _logger.debug("DELETE ME looking at variable " + str(variable))
                try:
                    if pattern['variables'][variable] \
                            != wp['variables'][variable]:
                        pattern_matches = False
                        _logger.debug("DELETE ME doesn't match")
                except KeyError:
                    pattern_matches = False
        if pattern_matches:
            _logger.error("WP: an identical pattern already exists")
            msg = 'You already have a workflow pattern with identical ' \
                  'characteristics'
            return (False, msg)
        else:
            _logger.debug('patterns are not identical')

    wp_home = get_workflow_pattern_home(configuration, client_dir)
    if not os.path.exists(wp_home):
        try:
            os.makedirs(wp_home)
        except Exception, err:
            _logger.error("WP: couldn't create directory %s %s" %
                          (wp_home, err))
            msg = "Couldn't create the required dependencies for " \
                  "your workflow pattern"
            return (False, msg)

    persistence_id = generate_random_ascii(wp_id_length, charset=wp_id_charset)
    wp_file_path = os.path.join(wp_home, persistence_id)

    if os.path.exists(wp_file_path):
        _logger.error('WP: unique filename conflict: %s '
                      % wp_file_path)
        msg = 'A workflow pattern conflict was encountered, '
        'please try an resubmit the pattern'
        return (False, msg)

    wp['persistence_id'] = persistence_id
    wp['trigger'] = {}
    # Save the pattern
    wrote = False
    msg = ''
    try:
        with open(wp_file_path, 'w') as j_file:
            json.dump(wp, j_file, indent=0)

        # Mark as modified
        mark_workflow_p_modified(configuration, wp['persistence_id'])
        wrote = True
        _logger.debug('marking new pattern ' + wp['persistence_id'] +
                      ' as modified')
    except Exception, err:
        _logger.error('WP: failed to write %s to disk %s' % (
            wp_file_path, err))
        msg = 'Failed to save your workflow pattern, '
        'please try and resubmit it'

    if not wrote:
        # Ensure that the failed write does not stick around
        try:
            os.remove(wp_file_path)
        except Exception, err:
            _logger.error('WP: failed to remove the dangling wp: %s %s'
                          % (wp_file_path, err))
            msg += '\n Failed to cleanup after a failed workflow creation'
        return (False, msg)

    _logger.info('WP: %s created at: %s ' %
                 (client_id, wp_file_path))
    return (True, '')


def create_workflow_recipe(configuration, client_id, wr):
    """Creates a workflow recipe based on the passed wr object.
        Requires the following keys and structure:

        wr = {
            'name': 'pattern-name'
            'owner': 'string-owner',
            'recipe': 'recipe-as-string'
        }

        The 'owner' key is required to be non-empty string.
        If a 'name' is not provided a random one will be generated.

        Result is that a JSON object of the dictionary structure will be saved
        to the configuration.mig_system_files/client_dir/generated_id.json
    """

    # Prepare json for writing.
    # The name of the directory to be used in both the users home
    # and the global state/workflow_recipes_home directory
    _logger = configuration.logger
    _logger.debug("WR: create_workflow_recipe, client_id: %s, wr: %s"
                  % (client_id, wr))

    if not client_id:
        msg = "A workflow recipe creation dependency was missing"
        _logger.error(
            "WR: creating_recipe, client_id was not set %s" % client_id)
        return False, msg

    correct, msg = __correct_wr(configuration, wr)
    if not correct:
        return correct, msg

    # TODO update how this is done

    # TODO make this work. Currently allowing multiple recipes with the same
    #  name
    client_dir = client_id_dir(client_id)
    if 'name' not in wr:
        wr['name'] = generate_random_ascii(wr_id_length, charset=wr_id_charset)
    else:
        wr_exists = get_wr_with(configuration, client_id=client_id,
                                name=wr['name'])
        if wr_exists:
            _logger.error("WR: a wr with name: %s already exists: %s"
                          % (wr['name'], client_id))
            msg = 'You already have a workflow recipe with the name %s' \
                  % wr['name']
            return False, msg

    wr_home = get_workflow_recipe_home(configuration, client_dir)
    # wr_home = os.path.join(configuration.workflow_recipes_home,
    #                        client_dir)
    _logger.debug("DELETE ME - wr_home: " + str(wr_home))
    if not os.path.exists(wr_home):
        try:
            os.makedirs(wr_home)
        except Exception, err:
            _logger.error("WR: couldn't create directory %s %s" %
                          (wr_home, err))
            msg = "Couldn't create the required dependencies for " \
                  "your workflow recipe"
            return False, msg

    persistence_id = generate_random_ascii(wr_id_length, charset=wr_id_charset)
    wr_file_path = os.path.join(wr_home, persistence_id)

    if os.path.exists(wr_file_path):
        _logger.error('WR: unique filename conflict: %s '
                      % wr_file_path)
        msg = 'A workflow recipe conflict was encountered, '
        'please try and resubmit the recipe'
        return False, msg

    wr['persistence_id'] = persistence_id
    wr['triggers'] = {}
    # Save the recipe
    wrote = False
    _logger.debug('DELETE ME - wr to be saved:' + str(wr))

    msg = ''
    try:
        with open(wr_file_path, 'w') as j_file:
            json.dump(wr, j_file, indent=0)

        _logger.debug('DELETE ME - marking recipe as modified')
        # Mark as modified
        mark_workflow_r_modified(configuration, wr['persistence_id'])
        wrote = True
    except Exception, err:
        _logger.error('WR: failed to write %s to disk %s' % (
            wr_file_path, err))
        msg = 'Failed to save your workflow recipe, '
        'please try and resubmit it'

    if not wrote:
        # Ensure that the failed write does not stick around
        try:
            os.remove(wr_file_path)
        except Exception, err:
            _logger.error('WR: failed to remove the dangling wr: %s %s'
                          % (wr_file_path, err))
            msg += '\n Failed to cleanup after a failed workflow creation'
        return False, msg

    _logger.info('WR: %s created at: %s ' %
                 (client_id, wr_file_path))
    return True, ''


def update_workflow_pattern(configuration, client_id, new_pattern_variables, persistence_id):
    _logger = configuration.logger
    _logger.debug("WP: update_workflow_pattern, client_id: %s, pattern: %s"
                  % (client_id, persistence_id))

    if not client_id:
        msg = "A workflow pattern create dependency was missing"
        _logger.error("WP: update_workflow_pattern, client_id was not set %s" %
                      client_id)
        return (False, msg)

    pattern = get_wp_with(configuration,
                           client_id=client_id,
                           first=True,
                           owner=client_id,
                           persistence_id=persistence_id)

    if 'trigger' in pattern:
        preexisting_trigger = pattern['trigger']
    else:
        preexisting_trigger = False

    _logger.debug('update_workflow_pattern, got pattern: ' + str(pattern))
    _logger.debug('update_workflow_pattern, applying variables: '
                  + str(new_pattern_variables))

    for variable in new_pattern_variables.keys():
        pattern[variable] = new_pattern_variables[variable]

    _logger.debug('update_workflow_pattern, resulting pattern: ' + str(pattern))

    correct, msg = __correct_wp(configuration, pattern)
    if not correct:
        return (correct, msg)

    # TODO check for create required keys
    client_dir = client_id_dir(client_id)
    wp_home = get_workflow_pattern_home(configuration, client_dir)
    wp_file_path = os.path.join(wp_home, persistence_id)

    pattern['persistence_id'] = persistence_id
    # Save the pattern
    wrote = False
    msg = ''
    try:
        with open(wp_file_path, 'w') as j_file:
            json.dump(pattern, j_file, indent=0)

        # Mark as modified
        mark_workflow_p_modified(configuration, pattern['persistence_id'])
        wrote = True
        _logger.debug('marking editted pattern ' + pattern['persistence_id'] +
                      ' as modified')
    except Exception, err:
        _logger.error('WP: failed to write %s to disk %s' % (
            wp_file_path, err))
        msg = 'Failed to save your workflow pattern, '
        'please try and resubmit it'

    # This will want changed, we don't want to delete a working recipe just
    # because we can't updated it
    if not wrote:
        # Ensure that the failed write does not stick around
        try:
            os.remove(wp_file_path)
        except Exception, err:
            _logger.error('WP: failed to remove the dangling wp: %s %s'
                          % (wp_file_path, err))
            msg += '\n Failed to cleanup after a failed workflow creation'
        return (False, msg)


    # if there is a trigger then delete the old one and start a new one.
    if preexisting_trigger:
        if any([i in new_pattern_variables for i in UPDATE_TRIGGER_PATTERN]):
            _logger.debug('replacing old trigger')
            rule_deletion_from_pattern(configuration, client_id, pattern)
            rule_identification_from_pattern(configuration, client_id, pattern, True)

    _logger.info('WP: %s updated at: %s ' %
                 (client_id, wp_file_path))
    return (True, '')


def update_workflow_recipe(configuration, client_id, new_recipe_variables, persistence_id):
    """Update a workflow recipe"""

    _logger = configuration.logger
    _logger.debug("WR: update_workflow_recipe, client_id: %s, recipe: %s"
                  % (client_id, persistence_id))

    if not client_id:
        msg = "A workflow recipe update dependency was missing"
        _logger.error(
            "WR: update_workflow_recipe, client_id was not set %s" % client_id)
        return False, msg

    recipe = get_wr_with(configuration,
                         client_id=client_id,
                         first=True,
                         owner=client_id,
                         persistence_id=persistence_id)

    for variable in new_recipe_variables.keys():
        recipe[variable] = new_recipe_variables[variable]

    correct, msg = __correct_wr(configuration, recipe)
    if not correct:
        return correct, msg

    client_dir = client_id_dir(client_id)
    wr_home = get_workflow_recipe_home(configuration, client_dir)
    wr_file_path = os.path.join(wr_home, persistence_id)

    recipe['persistence_id'] = persistence_id
    # Save the recipe
    wrote = False
    _logger.debug('DELETE ME - wr to be saved:' + str(recipe))

    msg = ''
    try:
        with open(wr_file_path, 'w') as j_file:
            json.dump(recipe, j_file, indent=0)

        _logger.debug('DELETE ME - marking recipe as modified')
        # Mark as modified
        mark_workflow_r_modified(configuration, recipe['persistence_id'])
        wrote = True
    except Exception, err:
        _logger.error('WR: failed to write %s to disk %s' % (
            wr_file_path, err))
        msg = 'Failed to save your workflow recipe, '
        'please try and resubmit it'

    # This will want changed, we don't want to delete a working recipe just
    # because we can't update it
    if not wrote:
        # Ensure that the failed write does not stick around
        try:
            os.remove(wr_file_path)
        except Exception, err:
            _logger.error('WR: failed to remove the dangling wr: %s %s'
                          % (wr_file_path, err))
            msg += '\n Failed to cleanup after a failed workflow update'
        return False, msg

    # if there is a trigger then delete the old one and start a new one.
    if recipe['triggers']:
        if any([i in new_recipe_variables for i in UPDATE_TRIGGER_RECIPE]):
            rule_deletion_from_recipe(configuration, client_id, recipe)
            rule_identification_from_recipe(configuration, client_id, recipe, True)

    _logger.info('WR: %s updated at: %s ' %
                 (client_id, wr_file_path))
    return True, ''


def rule_identification_from_pattern(configuration,
                                     client_id,
                                     workflow_pattern,
                                     apply_retroactive):
    """identifies if a task can be created, following the creation or
    editing of a pattern ."""

    # setup logger
    _logger = configuration.logger
    _logger.info('%s is identifying any possible tasks from pattern creation '
                 '%s: %s' % (client_id, workflow_pattern['name'],
                             str(workflow_pattern)))

    # Currently multiple recipes are crudely chained together. This will need
    # to be altered once we move into other languages than python.
    missed_recipes = []
    recipe_list = []
    vgrid = workflow_pattern['vgrids']
    # Check if defined recipes exist already within system
    for recipe_name in workflow_pattern['recipes']:
        _logger.info("looking for recipe :" + recipe_name)

        recipe = get_wr_with(configuration,
                             client_id=client_id,
                             first=True,
                             name=recipe_name,
                             vgrids=vgrid)
        _logger.info("recipe :" + str(recipe))

        if recipe:
            recipe_list.append(recipe)
            _logger.info("found and adding recipe :" + recipe_name)
        else:
            missed_recipes.append(recipe_name)
    if missed_recipes:
        return (False, 'Could not find all required recipes. Missing: ' +
                str(missed_recipes))

    _logger.info('All recipes found within trying to create trigger '
                 'for pattern ' + workflow_pattern['name'] + ' and inputs '
                 'at ' + str(workflow_pattern['inputs']))

    # TODO do not create these triggers quite yet. possibly wait for some
    #  activation toggle?

    (trigger_status, trigger_msg) = create_trigger(configuration,
                                                   _logger,
                                                   vgrid,
                                                   client_id,
                                                   workflow_pattern,
                                                   recipe_list,
                                                   apply_retroactive)

    if not trigger_status:
        return False, 'Could not create trigger for pattern. ' + trigger_msg
    return True, 'Trigger created'


def rule_identification_from_recipe(configuration,
                                    client_id,
                                    workflow_recipe,
                                    apply_retroactive):
    # TODO finish this
    """identifies if a task can be created, following the creation or
    editing of a recipe . This pattern is read in as the object
    workflow_recipe and is expected in the format."""

    # setup logger
    _logger = configuration.logger
    _logger.info('%s is identifying any possible tasks from recipe creation '
                 '%s' % (client_id, workflow_recipe['name']))
    vgrid = workflow_recipe['vgrids']
    matching_patterns = []
    patterns = get_wp_with(configuration,
                           client_id=client_id,
                           first=False,
                           owner=client_id,
                           vgrids=vgrid)

    # Check if patterns exist already within system that need this recipe
    if not patterns:
        _logger.info('DELETE ME - no appropriate patterns to check')
        return [], []
    for pattern in patterns:
        _logger.info('DELETE ME - pattern: ' + str(pattern))

        if workflow_recipe['name'] in pattern['recipes']:
            matching_patterns.append(pattern)

    activatable_patterns = []
    incomplete_patterns = []
    # now check all matching patterns have all their recipes
    for pattern in matching_patterns:
        # Currently multiple recipes are crudely chained together. This will
        # need to be altered eventually.
        recipe_list = []
        missed_recipes = []
        # Check if defined recipes exist already within system
        for recipe_name in pattern['recipes']:
            recipe = get_wr_with(configuration,
                                 client_id=client_id,
                                 name=recipe_name)
            if recipe:
                recipe_list.append(recipe)
            else:
                missed_recipes.append(recipe_name)
        if not missed_recipes:
            _logger.info('DELETE ME - pattern:' + str(pattern))

            _logger.info(
                'All recipes found within trying to create trigger for recipe'
                + pattern['name'] + ' and inputs at ' + str(pattern['inputs']))

            # TODO do not create these triggers quite yet. possibly wait for
            #  some activation toggle?

            (trigger_status, trigger_msg) = create_trigger(configuration,
                                                           _logger,
                                                           vgrid,
                                                           client_id,
                                                           pattern,
                                                           recipe_list,
                                                           apply_retroactive)

            if not trigger_status:
                incomplete_patterns.append(str(pattern['name']))
            else:
                activatable_patterns.append(str(pattern['name']))
    return activatable_patterns, incomplete_patterns


def rule_deletion_from_pattern(configuration, client_id, wp):
    _logger = configuration.logger

    _logger.debug("DELETE ME wp[trigger]: - " + str(wp['trigger']))
    vgrid_name = wp['trigger']['vgrid']
    trigger_id = wp['trigger']['trigger_id']

    # TODO must be a better way to get an individual trigger
    status, trigger_list = vgrid_triggers(vgrid_name, configuration)
    if status:
        recipe_list = []
        for trigger in trigger_list:
            if trigger['rule_id'] == trigger_id:
                if 'recipes' in trigger.keys():
                    recipe_list = trigger['recipes']
                    (rm_status, rm_msg) = vgrid_remove_triggers(
                        configuration, vgrid_name, [trigger_id])
                    if not rm_status:
                        _logger.error('%s failed to remove trigger: %s' %
                                      (client_id, rm_msg))
                    _logger.info('%s removed trigger: %s' % (client_id,
                                                             trigger_id))
                break

        # delete the reference to the trigger for these recipes
        for recipe_id in recipe_list:
            recipe = get_wr_with(configuration,
                                 client_id=client_id,
                                 persistence_id=recipe_id)
            new_recipe_variables = {
                'triggers': recipe['triggers']
            }
            new_recipe_variables['triggers'].pop(str(vgrid_name + trigger_id),
                                                 None)
            update_workflow_recipe(configuration,
                                   client_id,
                                   new_recipe_variables,
                                   recipe['persistence_id'])


def rule_deletion_from_recipe(configuration, client_id, wr):
    _logger = configuration.logger

    _logger.debug("DELETE ME wr[triggers]: - " + str(wr['triggers']))
    for trigger_key in wr['triggers'].keys():
        vgrid_name = wr['triggers'][trigger_key]['vgrid']
        trigger_id = wr['triggers'][trigger_key]['trigger_id']

        # TODO must be a better way to get an individual trigger
        status, trigger_list = vgrid_triggers(vgrid_name, configuration)
        if status:
            recipe_list = []
            for trigger in trigger_list:
                if trigger['rule_id'] == trigger_id:
                    # update pattern reference to trigger
                    if 'pattern' in trigger.keys():
                        pattern_id = trigger['pattern']
                        new_pattern_variables = {
                            'trigger': {}
                        }
                        update_workflow_pattern(configuration,
                                                client_id,
                                                new_pattern_variables,
                                                pattern_id)

                    if 'recipes' in trigger.keys():
                        recipe_list = trigger['recipes']
                        (rm_status, rm_msg) = vgrid_remove_triggers(
                            configuration, vgrid_name, [trigger_id])
                        if not rm_status:
                            _logger.error('%s failed to remove trigger: %s' %
                                          (client_id, rm_msg))
                        _logger.info('%s removed trigger: %s' % (client_id,
                                                                 trigger_id))
                    break

            _logger.debug("DELETE ME rule_deletion_from_recipe about to start updating trigger list: " + str(recipe_list))
            # delete the reference to the trigger for these recipes
            for recipe_name in recipe_list:
                _logger.debug(
                    "DELETE ME rule_deletion_from_recipe considering " + recipe_name)
                recipe = get_wr_with(configuration,
                                     client_id=client_id,
                                     persistence_id=recipe_name)
                _logger.debug(
                    "DELETE ME rule_deletion_from_recipe recipe: " + str(recipe))
                new_recipe_variables = {
                    'triggers': recipe['triggers']
                }
                new_recipe_variables['triggers'].pop(
                    str(vgrid_name + trigger_id),
                    None)
                update_workflow_recipe(configuration,
                                       client_id,
                                       new_recipe_variables,
                                       recipe['persistence_id'])


def create_workflow_task_file(configuration, client_id, complete_recipe,
                              variables):
    _logger = configuration.logger
    _logger.debug("DELETE ME - variables: " + str(variables))

    client_dir = client_id_dir(client_id)
    task_home = get_workflow_task_home(configuration, client_dir)
    if not os.path.exists(task_home):
        try:
            os.makedirs(task_home)
        except Exception, err:
            _logger.error("WT: couldn't create directory %s %s" %
                          (task_home, err))
            msg = "Couldn't create the required dependencies for " \
                  "your workflow task"
            return False, msg

    # TODO improve this
    # placeholder for unique name generation.
    file_name = generate_random_ascii(wr_id_length, charset=wr_id_charset) + \
                ".py"
    task_file_path = os.path.join(task_home, file_name)
    while os.path.exists(task_file_path):
        file_name = generate_random_ascii(wr_id_length, charset=wr_id_charset)
        task_file_path = os.path.join(task_home, file_name)

    task = ''
    # add variables into recipe
    for variable in variables.keys():
        task += variable + " = " + str(variables[variable]) + "\n"
    task += complete_recipe

    wrote = False
    msg = ''
    try:
        with open(task_file_path, 'w') as new_file:
            new_file.write(task)
        # Mark as modified. Don't do this? We shouldn't modify this . . .
        # mark_workflow_r_modified(configuration, wr['persistence_id'])
        wrote = True
    except Exception, err:
        _logger.error('WT: failed to write %s to disk %s' % (
            task_file_path, err))
        msg = 'Failed to save your workflow task, '
        'please try and resubmit it'

    if not wrote:
        # Ensure that the failed write does not stick around
        try:
            os.remove(task_file_path)
        except Exception, err:
            _logger.error('WT: failed to remove the dangling task file: %s %s'
                          % (task_file_path, err))
            msg += '\n Failed to cleanup after a failed workflow creation'
        return False, msg

    _logger.info('WT: %s created at: %s ' %
                 (client_id, task_file_path))
    return True, task_file_path


def create_trigger(configuration, _logger, vgrid, client_id, pattern,
                    recipe_list, apply_retroactive):

    # TODO update the recipe with the arguments from the pattern before
    #  sending off for task creation

    _logger.debug("DELETE ME - given pattern: " + str(pattern))
    _logger.debug("DELETE ME - given recipes: " + str(recipe_list))

    complete_recipe = ''
    recipe_ids = []
    for recipe in recipe_list:
        recipe_ids.append(recipe['persistence_id'])
        for line in recipe['recipe']:
            complete_recipe += line

    (task_file_status, msg) = create_workflow_task_file(configuration,
                                                        client_id,
                                                        complete_recipe,
                                                        pattern['variables'])
    if not task_file_status:
        return False, msg

    _logger.debug("DELETE ME - task_file_status: " + str(task_file_status))
    _logger.debug("DELETE ME - msg: " + str(msg))
    client_dir = client_id_dir(client_id)
    user_home_dir = os.path.join(configuration.user_home, client_dir)
    task_path = msg.replace(user_home_dir, "")

    arguments_dict = {
        'EXECUTE': [
            "python wf_job.py",
        ],
        'NOTIFY': [
            "email: SETTINGS",
            "jabber: SETTINGS"
        ],
        'MEMORY': [
            "1024"
        ],
        'DISK': [
            "1"
        ],
        'CPUTIME': [
            "30"
        ],
        'RETRIES': [
            "1"
        ],
        'OUTPUTFILES': [
            WF_OUTPUT + " " + os.path.join("+TRIGGERVGRIDNAME+",
                                         os.path.join(pattern['output'],
                                                      "+TRIGGERFILENAME+")),
        ],
        'INPUTFILES': [
            "+TRIGGERPATH+ " + WF_INPUT,
        ],
        'EXECUTABLES': [
            task_path + " wf_job.py"
        ]
    }
    external_dict = get_keywords_dict(configuration)
    mrsl = fields_to_mrsl(configuration, arguments_dict, external_dict)
    # TODO replace with dict to mrsl as a string
    # this mrsl file is not the one used for actual job creation. Just used as
    # a simple way of getting mrsl formatted text for argument_string.
    try:
        (mrsl_filehandle, mrsl_real_path) = tempfile.mkstemp(text=True)
        # mrsl_relative_path = os.path.basename(mrsl_real_path)
        os.write(mrsl_filehandle, mrsl)
        os.close(mrsl_filehandle)
    except Exception, err:
        msg = "Failed to create temporary mRSL file"
        _logger.error(msg + ": " + str(err))
        return False, msg

    mrsl_file = open(mrsl_real_path, 'r')
    arguments_string = ''
    arguments_string += mrsl_file.read()
    mrsl_file.close()

    trigger_id = "%d" % (time.time() * 1E8)
    rule_dict = {
        'rule_id': trigger_id,
        'vgrid_name': vgrid,
        # will only set up for first input directory. would like more
        'path': pattern['inputs'],
        'changes': ['created', 'modified'],
        'run_as': client_id,
        'action': 'submit',
        # arguments doesn't seem to be necessary at all, at least when created
        # with this method
        'arguments': [],
        # 'arguments': ['sampleMRSL.mRSL'],
        'rate_limit': '',
        'settle_time': '',
        'match_files': True,
        'match_dirs': False,
        # possibly should be False instead. Investigate
        'match_recursive': True,
        'templates': [arguments_string],
        # be careful here. Not sure if this will have unintended consequences
        'pattern': pattern['persistence_id'],
        'recipes': recipe_ids
    }

    # _logger.debug("DELETE ME - rule_dict: " + str(rule_dict))

    (add_status, add_msg) = vgrid_add_triggers(configuration,
                                               vgrid,
                                               [rule_dict],
                                               update_id=None,
                                               rank=None)

    _logger.debug("DELETE ME - add_status: " + str(add_status))
    _logger.debug("DELETE ME - add_msg: " + str(add_msg))

    # mark pattern and recipes as having created this trigger
    _logger.debug("DELETE ME - pattern: " + str(pattern))

    _logger.debug("DELETE ME - updating pattern and recipe(s) with trigger "
                  "reference")

    new_pattern_variables = {
        'trigger': {
            'vgrid': vgrid,
            'trigger_id': trigger_id
        }
    }
    update_workflow_pattern(configuration,
                            client_id,
                            new_pattern_variables,
                            pattern['persistence_id'])
    for recipe in recipe_list:
        new_recipe_variables = {
            'triggers': recipe['triggers']
        }
        new_recipe_variables['triggers'][str(vgrid + trigger_id)] = {
            'vgrid': vgrid,
            'trigger_id': trigger_id
        }
        update_workflow_recipe(configuration,
                               client_id,
                               new_recipe_variables,
                               recipe['persistence_id'])

    # probably do this somewhere else, but it'll do for now
    # check for pre-existing files that could trip the trigger
    vgrid_files_home = os.path.join(configuration.vgrid_files_home, vgrid)
    input_dir = pattern['inputs']
    regex = re.compile(os.path.join(vgrid_files_home, input_dir))

    # if required, then apply retoractively to existing files
    if apply_retroactive:
        for root, dirs, files in os.walk(vgrid_files_home, topdown=False):
            for name in files:
                file_path = os.path.join(root, name)
                if regex.match(file_path):
                    relative_path = file_path.replace(
                        configuration.vgrid_files_home, ''
                    )
                    file_arguments_dict = copy.deepcopy(arguments_dict)
                    for argument in file_arguments_dict.keys():
                        for index, element in enumerate(
                                file_arguments_dict[argument]):
                            if '+TRIGGERPATH+' in element:
                                file_arguments_dict[argument][index] = \
                                    file_arguments_dict[argument][index]\
                                        .replace('+TRIGGERPATH+', relative_path)
                            if '+TRIGGERFILENAME+' in element:
                                file_arguments_dict[argument][index] = \
                                    file_arguments_dict[argument][index]\
                                        .replace('+TRIGGERFILENAME+', name)
                            if '+TRIGGERVGRIDNAME+' in element:
                                file_arguments_dict[argument][index] = \
                                    file_arguments_dict[argument][index].replace(
                                        '+TRIGGERVGRIDNAME+', vgrid)
                    mrsl = fields_to_mrsl(configuration, file_arguments_dict, external_dict)
                    (file_handle, real_path) = tempfile.mkstemp(text=True)
                    # relative_path = os.path.basename(real_path)
                    os.write(file_handle, mrsl)
                    os.close(file_handle)
                    _logger.debug('applying rule retroactively to create new '
                                  'job for: ' + real_path)
                    new_job(real_path, client_id, configuration, False, True)

    return add_status, add_msg

