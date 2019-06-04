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
import pattern
from hashlib import sha256
import h5py

from shared.base import client_id_dir, force_utf8_rec
from shared.defaults import any_state, keyword_auto
from shared.events import get_path_expand_map
from shared.functional import REJECT_UNSET

from shared.base import client_id_dir, force_utf8_rec
from shared.fileio import write_file
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
from shared.job import fill_mrsl_template, new_job, fields_to_mrsl, \
    get_job_ids_with_task_file_in_contents
from shared.functionality.jobaction import main as jobaction
from shared.fileio import delete_file, send_message_to_grid_script, unpickle, \
    unpickle_and_change_status
from shared.mrslkeywords import get_keywords_dict
from shared.pattern import Pattern, DEFAULT_JOB_NAME

WRITE_LOCK = 'write.lock'
CELL_TYPE, CODE, SOURCE = 'cell_type', 'code', 'source'
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
    'input_file': str,
    'trigger_paths': list,
    'output': dict,
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
    'recipe': dict,
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

WF_INPUT = 'wf_input_file'


def __recipe_regex(name):
    # TODO improve this so it only matches valid functions
    # remove final character from signature regex as that is a bracket we can
    # do without
    return __recipe_signature_regex(name)[:-1] + "((\\n {4}.*)+))"


def __recipe_signature_regex(name):
    # TODO improve this so it only matches valid functions
    return "(def \\s*" + name + "*\\(.*\\):\\n*)"

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

    msg = "The workflow recipe had an incorrect structure, " + contact_msg
    for k, v in wr.items():
        if k not in VALID_RECIPE:
            _logger.error("WR: __correct_wr, wr had an incorrect key %s, "
                          "allowed are %s" % (k, VALID_RECIPE.keys()))
            return (False, msg)
        if not isinstance(v, VALID_RECIPE[k]):
            _logger.error("WR: __correct_wr, wr had an incorrect value type "
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
        workflow_map[workflow_file] = workflow_map.get(workflow_file, {})

        _logger.debug('DELETE ME - workflow_dir: ' + str(workflow_dir))
        _logger.debug('DELETE ME - workflow_file: ' + str(workflow_file))
        # the previous way of calculating wp_mtime isn't 'accurate' enough.
        # When identifying from pattern creation it takes lone enough some
        # overlap can occur. This has been changed to the new way shown below,
        # but the old method is left unless UNFORESEEN CONSEQUENCES OCCUR.
        wp_mtime = os.path.getmtime(os.path.join(workflow_dir, workflow_file))
        _logger.debug('DELETE ME - wp_mtime : ' + str(wp_mtime))
        _logger.debug('DELETE ME - map_stamp: ' + str(map_stamp))
        _logger.debug('DELETE ME - raw wp_mtime : %s' % wp_mtime)
        _logger.debug('DELETE ME - raw map_stamp: %s' % map_stamp)
        _logger.debug('DELETE ME - 10dp wp_mtime : %.10f' % wp_mtime)
        _logger.debug('DELETE ME - 10dp map_stamp: %.10f' % map_stamp)

        # init first time
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
            _logger.debug('DELETE ME - updating __modtime__ on ' + str(workflow_file) + ' to %.10f' % map_stamp)
            dirty.append([workflow_file])

    # Remove any missing workflow patterns from map
    missing_workflow = [workflow_file for workflow_file in workflow_map.keys()
                  if workflow_file not in [_workflow_file for _workflow_path, _workflow_file in
                                     all_objects]]

    for workflow_file in missing_workflow:
        del workflow_map[workflow_file]
        dirty.append([workflow_file])

    if dirty:
        _logger.debug('DELETE ME - dirty: ' + str(dirty))
        try:
            dump(workflow_map, map_path)
            os.utime(map_path, (start_time, start_time))
            _logger.debug('Accessed map and updated to %.10f' % start_time)

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
    # be too much needless processing if multiple users are using the system at
    # once though. Talk to Jonas/Martin about this. Also note this system is
    # terrible
    vgrid_files_home = configuration.vgrid_files_home
    vgrid_dirs = os.listdir(vgrid_files_home)
    for vgrid in vgrid_dirs:
        if os.path.isdir(os.path.join(vgrid_files_home, vgrid)):
            client_home = ''
            if to_get == 'pattern':
                client_home = get_workflow_pattern_home(
                    configuration, vgrid)
            elif to_get == 'recipe':
                client_home = get_workflow_recipe_home(
                    configuration, vgrid)
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
        'input_file': kwargs.get('input_file', VALID_PATTERN['input_file']()),
        'trigger_paths': kwargs.get('trigger_paths', VALID_PATTERN['trigger_paths']()),
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


def get_workflow_pattern_home(configuration, vgrid):
    vgrid_dir = os.path.join(configuration.vgrid_files_home, vgrid)
    pattern_home = os.path.join(vgrid_dir + configuration.workflow_patterns_home)
    return pattern_home


def get_workflow_recipe_home(configuration, vgrid):
    vgrid_dir = os.path.join(configuration.vgrid_files_home, vgrid)
    recipe_home = os.path.join(vgrid_dir + configuration.workflow_recipes_home)
    return recipe_home


def get_workflow_task_home(configuration, vgrid):
    vgrid_dir = os.path.join(configuration.vgrid_files_home, vgrid)
    task_home = os.path.join(vgrid_dir + configuration.workflow_tasks_home)
    return task_home


def get_workflow_buffer_home(configuration, vgrid):
    vgrid_dir = os.path.join(configuration.vgrid_files_home, vgrid)
    buffer_home = os.path.join(vgrid_dir + configuration.workflow_buffer_home)
    return buffer_home


def get_wp_map(configuration):
    """Returns the current map of workflow patterns and
    their configurations. Caches the map for load prevention with
    repeated calls within short time span.
    """
    _logger = configuration.logger
    _logger.debug("WP: get_wp_map")
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


def delete_workflow_pattern(configuration, client_id, vgrid, name):
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

    wp = get_wp_with(configuration,
                     client_id=client_id,
                     name=name,
                     vgrids=vgrid)
    persistence_id = wp['persistence_id']

    if wp['trigger']:
        __rule_deletion_from_pattern(configuration, client_id, vgrid, wp)

    wp_path = os.path.join(
        get_workflow_pattern_home(configuration, vgrid),
        persistence_id
    )
    if not os.path.exists(wp_path):
        msg = "The '%s' workflow pattern dosen't appear to exist" % name
        _logger.error("WP: can't delete %s it dosen't exist" % wp_path)
        return (False, msg)

    if not delete_file(wp_path, configuration.logger):
        msg = "Could not delete the '%s' workflow pattern"
        return (False, msg)
    mark_workflow_p_modified(configuration, persistence_id)

    return (True, 'Deleted pattern %s.' % wp['name'])


def delete_workflow_recipe(configuration, client_id, vgrid, name):
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

    wr = get_wr_with(configuration,
                     client_id=client_id,
                     name=name,
                     vgrids=vgrid)
    persistence_id = wr['persistence_id']

    _logger.debug("DELETE ME wr: - " + str(wr))

    if wr['triggers']:
        __rule_deletion_from_recipe(configuration, client_id, vgrid, wr)

    if not wr:
        msg = "The '%s' workflow recipe dosen't appear to exist" % name
        _logger.error("WR: can't delete %s it dosen't exist" % name)
        return (False, msg)

    wr_path = os.path.join(get_workflow_recipe_home(configuration, vgrid),
                           persistence_id)
    if not os.path.exists(wr_path):
        msg = "The '%s' workflow recipe has been moved/deleted already" % name
        _logger.error("WR: can't delete %s it no longer exists" % wr_path)
        return (False, msg)

    if not delete_file(wr_path, configuration.logger):
        msg = "Could not delete the '%s' workflow recipe"
        return (False, msg)
    mark_workflow_r_modified(configuration, persistence_id)
    return (True, 'Deleted recipe %s.' % wr['name'])


def __create_workflow_pattern(configuration, client_id, vgrid, wp):
    """ Creates a workflow patterns based on the passed wp object.
    Requires the following keys and structure:

    pattern = {
        'owner': client_id,
        'inputs': input_dict,
        'output': output_dict,
        'recipes': recipes_list,
        'variables': variables_dict,
        'vgrids': vgrid
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

    wp_home = get_workflow_pattern_home(configuration, vgrid)
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
    return (True, 'Created pattern %s.' % wp['name'])


def __create_workflow_recipe(configuration, client_id, vgrid, wr):
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

    wr_home = get_workflow_recipe_home(configuration, vgrid)

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
    return True, 'Created recipe %s.' % wr['name']


def __update_workflow_pattern(configuration, client_id, vgrid,
                            new_pattern_variables, persistence_id):
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
                          persistence_id=persistence_id,
                          vgrids=vgrid)

    if not pattern:
        msg = 'Could not locate pattern'
        _logger.debug(msg)
        return(False, msg)

    if 'trigger' in pattern:
        preexisting_trigger = pattern['trigger']
    else:
        preexisting_trigger = False

    # don't update if the recipe is the same
    to_edit = False
    for variable in new_pattern_variables.keys():
        if pattern[variable] != new_pattern_variables[variable]:
            to_edit = True
    if not to_edit:
        return False, 'Did not update pattern %s as contents are identical.' % \
               pattern['name']

    _logger.debug('update_workflow_pattern, got pattern: ' + str(pattern))
    _logger.debug('update_workflow_pattern, applying variables: '
                  + str(new_pattern_variables))

    for variable in new_pattern_variables.keys():
        pattern[variable] = new_pattern_variables[variable]

    _logger.debug('update_workflow_pattern, resulting pattern: ' + str(pattern))

    correct, msg = __correct_wp(configuration, pattern)
    if not correct:
        return (correct, msg)

    wp_home = get_workflow_pattern_home(configuration, vgrid)
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
            __rule_deletion_from_pattern(configuration, client_id, vgrid, pattern)
            __rule_identification_from_pattern(configuration, client_id, pattern, True)

    _logger.info('WP: %s updated at: %s ' % (client_id, wp_file_path))
    return (True, 'Updated pattern %s.' % pattern['name'])


def __update_workflow_recipe(configuration, client_id, vgrid,
                           new_recipe_variables, persistence_id):
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
                         persistence_id=persistence_id,
                         vgrids=vgrid)

    _logger.debug('DELETE ME - pre-updated recipe:' + str(recipe))
    _logger.debug('DELETE ME - recipe suggestion:' + str(new_recipe_variables))

    # don't update if the recipe is the same
    to_edit = False
    for variable in new_recipe_variables.keys():
        if recipe[variable] != new_recipe_variables[variable]:
            to_edit = True
    if not to_edit:
        return False, 'Did not update recipe %s as contents are identical.' % recipe['name']

    for variable in new_recipe_variables.keys():
        recipe[variable] = new_recipe_variables[variable]

    correct, msg = __correct_wr(configuration, recipe)
    if not correct:
        return correct, msg

    wr_home = get_workflow_recipe_home(configuration, vgrid)
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
            __rule_deletion_from_recipe(configuration, client_id, vgrid, recipe)
            __rule_identification_from_recipe(configuration, client_id, recipe, True)

    _logger.info('WR: %s updated at: %s ' %
                 (client_id, wr_file_path))
    return True, 'Updated recipe %s.' % recipe['name']


def __rule_identification_from_pattern(configuration, client_id,
                                     workflow_pattern, apply_retroactive):
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
                 'at ' + str(workflow_pattern['trigger_paths']))

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
    return True, 'Trigger created from pattern %s.' % workflow_pattern['name']


def __rule_identification_from_recipe(configuration, client_id,
                                    workflow_recipe, apply_retroactive):
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
        return False, 'No appropriate patterns to check for recipe %s' % workflow_recipe['name']
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
                                 name=recipe_name,
                                 vgrids=vgrid)
            if recipe:
                recipe_list.append(recipe)
            else:
                missed_recipes.append(recipe_name)
        if not missed_recipes:
            _logger.info('DELETE ME - pattern:' + str(pattern))

            _logger.info(
                'All recipes found within trying to create trigger for recipe '
                + pattern['name'] + ' and inputs at ' + str(pattern['trigger_paths']))

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
    msg = " %d trigger(s) created from recipe %s." % (len(activatable_patterns), workflow_recipe['name'])
    if len(incomplete_patterns) > 0:
        msg += " There are %d additional patterns(s) recipes that use this recipe, but are waiting for additional recipes before activation" % len(incomplete_patterns)
    return True, msg


def __rule_deletion_from_pattern(configuration, client_id, vgrid, wp):
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
                    delete_trigger(configuration,
                                   client_id,
                                   vgrid_name,
                                   trigger_id)
                break

        # delete the reference to the trigger for these recipes
        for recipe_id in recipe_list:
            recipe = get_wr_with(configuration,
                                 client_id=client_id,
                                 persistence_id=recipe_id,
                                 vgrids=vgrid)
            new_recipe_variables = {
                'triggers': recipe['triggers']
            }
            new_recipe_variables['triggers'].pop(str(vgrid_name + trigger_id), None)
            __update_workflow_recipe(configuration, client_id, vgrid, new_recipe_variables, recipe['persistence_id'])


def __rule_deletion_from_recipe(configuration, client_id, vgrid, wr):
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
                        __update_workflow_pattern(configuration, client_id, vgrid, new_pattern_variables, pattern_id)

                    if 'recipes' in trigger.keys():
                        recipe_list = trigger['recipes']
                        delete_trigger(configuration,
                                       client_id,
                                       vgrid_name,
                                       trigger_id)
                    break

            _logger.debug("DELETE ME rule_deletion_from_recipe about to start "
                          "updating trigger list: " + str(recipe_list))
            # delete the reference to the trigger for these recipes
            for recipe_name in recipe_list:
                _logger.debug("DELETE ME rule_deletion_from_recipe "
                              "considering " + recipe_name)
                recipe = get_wr_with(configuration,
                                     client_id=client_id,
                                     persistence_id=recipe_name,
                                     vgrids=vgrid)
                _logger.debug("DELETE ME rule_deletion_from_recipe recipe: "
                              + str(recipe))
                new_recipe_variables = {
                    'triggers': recipe['triggers']
                }
                new_recipe_variables['triggers'].pop(
                    str(vgrid_name + trigger_id),
                    None)
                __update_workflow_recipe(configuration, client_id, vgrid, new_recipe_variables, recipe['persistence_id'])


def create_workflow_task_file(configuration, client_id, vgrid, notebook,
                              variables):
    _logger = configuration.logger
    _logger.debug("DELETE ME - variables: " + str(variables))

    task_home = get_workflow_task_home(configuration, vgrid)
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
                ".ipynb"
    task_file_path = os.path.join(task_home, file_name)
    while os.path.exists(task_file_path):
        file_name = generate_random_ascii(wr_id_length, charset=wr_id_charset)
        task_file_path = os.path.join(task_home, file_name)

    notebook_json = json.dumps(notebook)
    wrote = write_file(notebook_json, task_file_path, _logger, make_parent=False)

    if not wrote:
        # Ensure that the failed write does not stick around
        try:
            os.remove(task_file_path)
        except Exception, err:
            _logger.error('WT: failed to remove the dangling task file: %s %s'
                          % (task_file_path, err))
        return False, 'Failed to cleanup after a failed workflow creation'

    _logger.info('WT: %s created at: %s ' % (client_id, task_file_path))
    return True, task_file_path


def create_workflow_buffer_file(configuration, client_id, vgrid, trigger_paths, input_file, apply_retroactive):
    _logger = configuration.logger
    _logger.debug("DELETE ME - trigger_paths: " + str(trigger_paths))

    buffer_home = get_workflow_buffer_home(configuration, vgrid)
    _logger.debug("DELETE ME - buffer_home: " + str(buffer_home))
    if not os.path.exists(buffer_home):
        try:
            os.makedirs(buffer_home)
        except Exception, err:
            _logger.error("WT: couldn't create directory %s %s" %
                          (buffer_home, err))
            msg = "Couldn't create the required dependencies for " \
                  "your workflow task"
            return False, msg

    # TODO improve this
    # placeholder for unique name generation.
    file_name = generate_random_ascii(wr_id_length, charset=wr_id_charset) + \
                ".hdf5"
    buffer_file_path = os.path.join(buffer_home, file_name)
    while os.path.exists(buffer_file_path):
        file_name = generate_random_ascii(wr_id_length, charset=wr_id_charset)
        buffer_file_path = os.path.join(buffer_home, file_name)

    wrote = False
    try:
        with h5py.File(buffer_file_path, 'w') as h5_buffer_file:
            for path in trigger_paths:
                h5_buffer_file.create_group(path)
                _logger.debug("DELETE ME - created buffer entry: %s" % path)
                if apply_retroactive:
                    file_path = os.path.join(configuration.vgrid_files_home, vgrid, path)
                    _logger.debug("DELETE ME - looking for retroactive buffered file: " + str(file_path))
                    file_extension = file_path[file_path.rfind('.'):]
                    if os.path.isfile(file_path) and file_extension == '.hdf5':
                        with h5py.File(file_path, 'r') as h5_data_file:
                            print("Opened %s, which has keys: %s" % (file_path, h5_data_file.keys()))
                            for data_key in h5_data_file.keys():
                                h5_buffer_file.copy(h5_data_file[data_key], path + "/" + data_key)

        wrote = True
    except Exception, err:
        _logger.error('WB: failed to write %s to disk %s' % (buffer_file_path, err))
        msg = 'Failed to save your workflow buffer file, please try and resubmit it'

    if not wrote:
        # Ensure that the failed write does not stick around
        try:
            os.remove(buffer_file_path)
        except Exception, err:
            _logger.error('WB: failed to remove the dangling buffer file: %s '
                          '%s' % (buffer_file_path, err))
            msg = 'Failed to cleanup after a failed workflow creation'
        return False, msg

    _logger.info('WB: %s created at: %s ' %
                 (client_id, buffer_file_path))
    return True, buffer_file_path


def delete_trigger(configuration, client_id, vgrid_name, trigger_id):
    logger = configuration.logger
    logger.info('delete_trigger client_id: ' + client_id + ' vgrid_name: '
                 + vgrid_name + ' trigger_id: ' + trigger_id)

    # get trigger task file
    (got_triggers, all_triggers) = vgrid_triggers(vgrid_name, configuration)

    if not got_triggers:
        logger.debug('Could not load triggers')

    logger.debug('DELETE ME - all_triggers' + str(all_triggers))
    trigger_to_delete = None
    for trigger in all_triggers:
        if trigger['rule_id'] == trigger_id:
            trigger_to_delete = trigger
            logger.debug('DELETE ME - trigger_to_delete'
                         + str(trigger_to_delete))

    # TODO keep working on this
    if trigger_to_delete:
        logger.debug('DELETE ME - finding jobs to cancel')
        task_file = trigger_to_delete['task_file']
        mrsl_dir = configuration.mrsl_files_dir
        matching_jobs = get_job_ids_with_task_file_in_contents(client_id,
                                                               task_file,
                                                               mrsl_dir,
                                                               logger)
        logger.debug('DELETE ME - matching_jobs' + str(matching_jobs))

        new_state = 'CANCELED'
        client_dir = client_id_dir(client_id)
        for job_id in matching_jobs:
            logger.debug('DELETE ME - found job ' + str(job_id))

            file_path = os.path.join(configuration.mrsl_files_dir, client_dir, job_id + '.mRSL')
            job = unpickle(file_path, logger)

            if not job:
                logger.error('Could not open job file')
                continue

            logger.debug('DELETE ME - looking for file at ' + file_path)

            possible_cancel_states = ['PARSE', 'QUEUED', 'RETRY', 'EXECUTING',
                                      'FROZEN']

            if not job['STATUS'] in possible_cancel_states:
                logger.error('Could not cancel job with status '
                             + job['STATUS'])
                continue

            if not unpickle_and_change_status(file_path, new_state, logger):
                logger.error('%s could not cancel job: %s' % (client_id, job_id))

            if not job.has_key('UNIQUE_RESOURCE_NAME'):
                job['UNIQUE_RESOURCE_NAME'] = 'UNIQUE_RESOURCE_NAME_NOT_FOUND'
            if not job.has_key('EXE'):
                job['EXE'] = 'EXE_NAME_NOT_FOUND'

            message = 'JOBACTION ' + job_id + ' ' \
                      + job['STATUS'] + ' ' + new_state + ' ' \
                      + job['UNIQUE_RESOURCE_NAME'] + ' ' \
                      + job['EXE'] + '\n'
            if not send_message_to_grid_script(message, logger, configuration):
                logger.error('%s failed to send message to grid script: %s' %
                         (client_id, message))
    (rm_status, rm_msg) = vgrid_remove_triggers(configuration,
                                                vgrid_name,
                                                [trigger_id])
    if not rm_status:
        logger.error('%s failed to remove trigger: %s' %
                      (client_id, rm_msg))


def create_trigger(configuration, _logger, vgrid, client_id, pattern,
                    recipe_list, apply_retroactive):

    # TODO update the recipe with the arguments from the pattern before
    #  sending off for task creation

    _logger.debug("DELETE ME - given pattern: " + str(pattern))
    _logger.debug("DELETE ME - given recipes: " + str(recipe_list))

    if len(pattern['trigger_paths']) > 1:
        _logger.debug("DELETE ME - before create_multi_input_trigger")
        add_status, add_msg = create_multi_input_trigger(configuration,
                                                         _logger,
                                                         vgrid,
                                                         client_id,
                                                         pattern,
                                                         recipe_list,
                                                         apply_retroactive)
    else:
        add_status, add_msg = create_single_input_trigger(configuration,
                                                          _logger,
                                                          vgrid,
                                                          client_id,
                                                          pattern,
                                                          recipe_list,
                                                          apply_retroactive)

    return add_status, add_msg


def create_single_input_trigger(configuration, _logger, vgrid, client_id,
                                pattern, recipe_list, apply_retroactive):
    _logger.debug("DELETE ME - given pattern: " + str(pattern))
    _logger.debug("DELETE ME - given recipes: " + str(recipe_list))

    complete_recipe = ''
    cells = []
    recipe_ids = []
    for recipe in recipe_list:
        recipe_ids.append(recipe['persistence_id'])
        cells = cells + recipe['recipe']['cells']
        # for cell in recipe['recipe']['cells']:
        #     complete_recipe += line
    # TODO do we want to preserve more data here?
    complete_notebook = {
        "cells": cells,
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 2
    }

    (task_file_status, msg) = create_workflow_task_file(configuration,
                                                        client_id,
                                                        vgrid,
                                                        complete_notebook,
                                                        pattern['variables'])
    if not task_file_status:
        return False, msg

    _logger.debug("DELETE ME - task_file_status: " + str(task_file_status))
    _logger.debug("DELETE ME - msg: " + str(msg))
    task_path = msg.replace(configuration.vgrid_files_home, "")
    if task_path.startswith('/'):
        task_path = task_path[1:]

    output_files_string = ''
    for key, value in pattern['output'].items():
        if output_files_string != '':
            output_files_string += '\n'
        # TODO take this out and just use existing name pulling system
        updated_value = value.replace('*', '+TRIGGERPREFIX+')
        updated_value = os.path.join(vgrid, updated_value)
        output_files_string += (key + ' ' + updated_value)

    input_file_name = pattern['input_file']
    input_file_path = pattern['trigger_paths'][0]

    execute_string = 'papermill %s %s -p' % (DEFAULT_JOB_NAME, DEFAULT_JOB_NAME)
    for variable, value in pattern['variables'].items():
        execute_string += ' %s %s' % (variable, value)
    arguments_dict = {
        'EXECUTE': [
            execute_string,
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
        'INPUTFILES': [
            "+TRIGGERPATH+ " + input_file_name
        ],
        'OUTPUTFILES': [
            output_files_string
        ],
        'EXECUTABLES': [
            task_path + " " + DEFAULT_JOB_NAME
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
        'changes': ['created', 'modified'],
        'run_as': client_id,
        'action': 'submit',
        # arguments doesn't seem to be necessary at all, at least when created
        # with this method
        'arguments': [],
        # 'arguments': ['sampleMRSL.mRSL'],
        'path': input_file_path,
        'rate_limit': '',
        'settle_time': '',
        'match_files': True,
        'match_dirs': False,
        # possibly should be False instead. Investigate
        'match_recursive': True,
        'templates': [arguments_string],
        # be careful here. Not sure if this will have unintended consequences
        'pattern': pattern['persistence_id'],
        'recipes': recipe_ids,
        'task_file': task_path
    }

    _logger.debug("DELETE ME - rule_dict: " + str(rule_dict))

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

    __update_workflow_pattern(configuration, client_id, vgrid, new_pattern_variables, pattern['persistence_id'])

    _logger.debug("DELETE ME - recipe_list: " + str(recipe_list))

    for recipe in recipe_list:
        _logger.debug("DELETE ME - recipe: " + str(recipe))

        new_recipe_variables = {
            'triggers': recipe['triggers']
        }
        new_recipe_variables['triggers'][str(vgrid + trigger_id)] = {
            'vgrid': vgrid,
            'trigger_id': trigger_id
        }
        __update_workflow_recipe(configuration, client_id, vgrid, new_recipe_variables, recipe['persistence_id'])

    # TODO investigate why things only update properly if we don't immediately
    #  refresh
    __refresh_map(configuration, 'pattern')
    __refresh_map(configuration, 'recipe')

    # probably do this somewhere else, but it'll do for now
    # check for pre-existing files that could trip the trigger
    vgrid_files_home = os.path.join(configuration.vgrid_files_home, vgrid)

    # if required, then apply retroactively to existing files
    _logger.debug("DELETE ME - considering retroactive applications")
    if apply_retroactive:
        _logger.debug("DELETE ME - look into retroactive")
        _logger.debug("DELETE ME - vgrid_files_home: " + str(vgrid_files_home))
        _logger.debug("DELETE ME - input_file_path: " + str(input_file_path))
        _logger.debug("DELETE ME - check against: " + str(os.path.join(vgrid_files_home, input_file_path)))

        for root, dirs, files in os.walk(vgrid_files_home, topdown=False):
            for name in files:
                file_path = os.path.join(root, name)
                prefix = name
                if '.' in prefix:
                    prefix = prefix[:prefix.index('.')]
                _logger.debug("DELETE ME - file_path: " + str(file_path))
                regex_path = os.path.join(vgrid_files_home, input_file_path)

                _logger.debug("DELETE ME - regex_path: " + str(regex_path))
                if re.match(regex_path, file_path):
                    _logger.debug("DELETE ME - match found")
                    relative_path = file_path.replace(configuration.vgrid_files_home, '')

                    # TODO only schedule job is buffer file is full
                    buffer_home = get_workflow_buffer_home(configuration, vgrid)
                    _logger.debug("DELETE ME - buffer home")
                    # If we have a buffer file, only schedule a job if its full
                    if re.match(buffer_home, file_path):
                        with h5py.File(file_path, 'a') as buffer_file:
                            expected_data_files = buffer_file
                            for key in expected_data_files:
                                _logger.debug('key: %s with data: %s' % (key, len(expected_data_files[key].keys())))
                                if len(expected_data_files[key].keys()) == 0:
                                    _logger.debug('skipping new job creation as buffer is not complete')
                                    return add_status, add_msg

                    file_arguments_dict = copy.deepcopy(arguments_dict)
                    _logger.debug("DELETE ME - file_arguments_dict: %s" % str(file_arguments_dict))
                    for argument in file_arguments_dict.keys():
                        for index, element in enumerate(
                                file_arguments_dict[argument]):
                            if '+TRIGGERPATH+' in element:
                                file_arguments_dict[argument][index] = \
                                    file_arguments_dict[argument][index] \
                                        .replace('+TRIGGERPATH+',
                                                 relative_path)
                            if '+TRIGGERFILENAME+' in element:
                                file_arguments_dict[argument][index] = \
                                    file_arguments_dict[argument][index] \
                                        .replace('+TRIGGERFILENAME+', name)
                            if '+TRIGGERPREFIX+' in element:
                                file_arguments_dict[argument][index] = \
                                    file_arguments_dict[argument][index] \
                                        .replace('+TRIGGERPREFIX+', prefix)
                            if '+TRIGGERVGRIDNAME+' in element:
                                file_arguments_dict[argument][index] = \
                                    file_arguments_dict[argument][index] \
                                        .replace('+TRIGGERVGRIDNAME+', vgrid)

                    mrsl = fields_to_mrsl(configuration,
                                          file_arguments_dict,
                                          external_dict)
                    (file_handle, real_path) = tempfile.mkstemp(text=True)
                    # relative_path = os.path.basename(real_path)
                    os.write(file_handle, mrsl)
                    os.close(file_handle)
                    _logger.debug('applying rule retroactively to create new '
                                  'job for: ' + real_path)
                    new_job(real_path, client_id, configuration, False, True)
    return add_status, add_msg


def create_multi_input_trigger(configuration, _logger, vgrid, client_id,
                               pattern, recipe_list, apply_retroactive):
    _logger.debug("DELETE ME - create_multi_input_trigger")
    _logger.debug("DELETE ME - pattern: " + str(pattern))

    (file_status, msg) = create_workflow_buffer_file(configuration,
                                                     client_id,
                                                     vgrid,
                                                     pattern['trigger_paths'],
                                                     pattern['input_file'],
                                                     apply_retroactive)

    _logger.debug("DELETE ME - buffer_file_status: " + str(file_status))
    _logger.debug("DELETE ME - msg: " + str(msg))
    vgrid_path = os.path.join(configuration.vgrid_files_home, vgrid)
    buffer_path = msg.replace(vgrid_path, "")
    _logger.debug("DELETE ME - buffer_path: " + str(buffer_path))
    if buffer_path.startswith('/'):
        buffer_path = buffer_path[1:]

    if not file_status:
        return False, msg

    pattern['trigger_paths'] = [buffer_path]

    add_status, add_msg = create_single_input_trigger(configuration,
                                                      _logger,
                                                      vgrid,
                                                      client_id,
                                                      pattern,
                                                      recipe_list,
                                                      apply_retroactive)

    # if not add_status:
    return add_status, add_msg


def scrape_for_workflow_objects(configuration, client_id, vgrid, notebook, name):

    _logger = configuration.logger
    _logger.debug("scrape_for_workflow_objects, client_id: %s, notebook: %s"
                  % (client_id, notebook))

    if not client_id:
        msg = "A workflow creation dependency was missing"
        _logger.error("scrape_for_workflow_object, client_id was not set %s"
                      % client_id)
        return False, msg

    cells = notebook['cells']
    code = ''
    for cell_dict in cells:
        # only look at code cells
        if cell_dict[CELL_TYPE] == CODE:
            for code_line in cell_dict[SOURCE]:
                # better to keep all as one string or to add it line by line?
                code += code_line.encode('ascii')
            # add extra newline to break up different code blocks
            code += "\n"

    starting_variables = dir()
    pattern_count = 0
    recipe_count = 0
    feedback = ''

    try:
        _logger.debug("starting source inspection")
        exec(code)

        new_variables = dir()
        for item in starting_variables:
            if item in new_variables:
                new_variables.remove(item)
        new_variables.remove('starting_variables')


        for variable_name in new_variables:
            variable = locals()[variable_name]
            _logger.debug("looking at variable: %s of type %s" % (variable, type(variable)))

            # python 3
            # if type(variable) == Pattern:
            #     pattern_count += 1
            # python 2
            if isinstance(variable, Pattern):
                _logger.debug("Found a pattern whilst scraping: %s" % variable_name)

                pattern_count += 1

                pattern_dict = {
                    'name': variable.name,
                    'input_file': variable.input_file,
                    'trigger_paths': variable.trigger_paths,
                    'recipes': variable.recipes,
                    'vgrids': vgrid,
                    'owner': client_id,
                    'output': variable.outputs,
                    'variables': variable.variables
                }
                status, msg = define_pattern(configuration, client_id, vgrid, pattern_dict)

                if not status:
                    return (False, msg)
                feedback += "\n%s" % msg

    except Exception as exception:
        _logger.error("Error encountered whilst running source: %s", exception)
        # Re-add this later once it is decided what we're doing with existing notebooks
        # return(False, exception.message)

    if pattern_count == 0:
        _logger.debug("Found no patterns, notebook %s is being registered as a recipe" % name)

        recipe_count += 1

        if '.ipynb' in name:
            name = name.replace('.ipynb', '')


        recipe_dict = {
            'name': name,
            'recipe': notebook,
            'owner': client_id,
            'vgrids': vgrid
        }
        status, msg = \
            define_recipe(configuration, client_id, vgrid, recipe_dict)

        if not status:
            return (False, msg)
        feedback += "\n%s" % msg


    count_msg = '%d patterns and %d recipes were found.' % \
          (pattern_count, recipe_count)

    _logger.debug("Scraping complete.")

    return (True, "%s\n%s" % (feedback, count_msg))


def define_pattern(configuration, client_id, vgrid, pattern):
    _logger = configuration.logger
    _logger.debug("WP: define_pattern, client_id: %s, pattern: %s"
                  % (client_id, pattern))

    if not client_id:
        msg = "A workflow pattern create dependency was missing"
        _logger.error("client_id was not set %s" %
                      client_id)
        return (False, msg)

    correct, msg = __correct_wp(configuration, pattern)
    if not correct:
        return (correct, msg)

    if 'name' not in pattern:
        pattern['name'] = generate_random_ascii(wp_id_length, charset=wp_id_charset)
    else:
        existing_pattern = get_wp_with(configuration,
                                client_id=client_id,
                                name=pattern['name'],
                                vgrids=vgrid)
        if existing_pattern:
            # _logger.error("WP: a pattern with name: %s already exists: %s"
            #               % (pattern['name'], client_id))
            # msg = 'You already have a workflow pattern with the name %s' \
            #       % pattern['name']
            persistence_id = existing_pattern['persistence_id']
            status, msg = __update_workflow_pattern(configuration, client_id, vgrid, pattern, persistence_id)

            return (True, msg)

    # TODO apply this to pattern as well
    # need to still check variables as they might not match exactly
    clients_patterns = get_wp_with(configuration,
                                   client_id=client_id,
                                   first=False,
                                   owner=client_id,
                                   trigger_paths=pattern['trigger_paths'],
                                   output=pattern['output'],
                                   vgrids=pattern['vgrids'])
    _logger.debug('clients_patterns: ' + str(clients_patterns))
    _logger.debug('pattern: ' + str(pattern))
    for pattern in clients_patterns:
        pattern_matches = True
        for variable in pattern['variables'].keys():
            _logger.debug("DELETE ME looking at variable " + str(variable))
            try:
                if pattern['variables'][variable] \
                        != pattern['variables'][variable]:
                    pattern_matches = False
                    _logger.debug("DELETE ME doesn't match")
            except KeyError:
                pattern_matches = False
        if pattern_matches:
            _logger.error("An identical pattern already exists")
            msg = 'You already have a workflow pattern with identical ' \
                  'characteristics to %s' % pattern['name']
            return (False, msg)
        else:
            _logger.debug('patterns are not identical')

    _, creation_msg = __create_workflow_pattern(configuration, client_id, vgrid, pattern)

    _, identification_msg = __rule_identification_from_pattern(configuration, client_id, pattern, True)

    return (True, "%s%s" % (creation_msg, identification_msg))


def define_recipe(configuration, client_id, vgrid, recipe):
    _logger = configuration.logger
    _logger.debug("WR: define_recipe, client_id: %s, recipe: %s"
                  % (client_id, recipe))

    if not client_id:
        msg = "A workflow recipe creation dependency was missing"
        _logger.error("client_id was not set %s" % client_id)
        return False, msg

    correct, msg = __correct_wr(configuration, recipe)
    if not correct:
        return correct, msg

    if 'name' not in recipe:
        recipe['name'] = generate_random_ascii(wr_id_length, charset=wr_id_charset)
    else:
        existing_recipe = get_wr_with(configuration,
                                      client_id=client_id,
                                      name=recipe['name'],
                                      vgrids=vgrid)
        if existing_recipe:
            # _logger.error("A recipe with name: %s already exists: %s"
            #               % (recipe['name'], client_id))
            # msg = 'You already have a workflow recipe with the name %s' \
            #       % recipe['name']
            persistence_id = existing_recipe['persistence_id']
            status, msg = __update_workflow_recipe(configuration, client_id, vgrid, recipe, persistence_id)
            return (True, msg)

    _, creation_msg = __create_workflow_recipe(configuration, client_id, vgrid, recipe)

    _, identification_msg = __rule_identification_from_recipe(configuration, client_id, recipe, True)

    return (True, "%s%s" % (creation_msg, identification_msg))
