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

import fcntl
import json
import os
import time
import tempfile

from hashlib import sha256

from shared.base import client_id_dir, force_utf8_rec
from shared.defaults import any_state, keyword_auto
from shared.events import get_path_expand_map
from shared.functional import REJECT_UNSET

from shared.base import client_id_dir, force_utf8_rec
from shared.map import load_system_map
from shared.modified import check_workflow_p_modified, \
    reset_workflow_p_modified, mark_workflow_p_modified, \
    mark_workflow_r_modified
from shared.pwhash import generate_random_ascii
from shared.defaults import wp_id_charset, wp_id_length, wr_id_charset, \
    wr_id_length
from shared.serial import dump
from shared.functionality.addvgridtrigger import main as add_vgrid_trigger_main

from shared.job import fill_mrsl_template, new_job
from shared.fileio import delete_file

WRITE_LOCK = 'write.lock'
WORKFLOW_PATTERNS, MODTIME, CONF = ['__workflowpatterns__', '__modtime__',
                                    '__conf__']
MAP_CACHE_SECONDS = 60

last_load = {WORKFLOW_PATTERNS: 0}
last_refresh = {WORKFLOW_PATTERNS: 0}
last_map = {WORKFLOW_PATTERNS: {}}

valid_wp = {'persistence_id': str,
            'owner': str,
            'name': str,
            'inputs': list,
            'output': str,
            'type_filter': list,
            'recipes': list,
            'variables': dict}


valid_wr = {'persistence_id': str,
            'owner': str,
            'name': str,
            'recipe': str}


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
        if k not in valid_wp:
            _logger.error("WP: __correct_wp, wp had an incorrect key %s, "
                          "allowed are %s" % (k, valid_wp.keys()))
            return (False, msg)
        if not isinstance(v, valid_wp[k]):
            _logger.error("WP: __correct_wp, wp had an incorrect value type "
                          "%s, on key %s, valid is %s"
                          % (type(v), k, valid_wp[k]))
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
        if k not in valid_wr:
            _logger.error("WR: __correct_wr, wr had an incorrect key %s, "
                          "allowed are %s" % (k, valid_wr.keys()))
            return (False, msg)
        if not isinstance(v, valid_wr[k]):
            _logger.error("WP: __correct_wr, wr had an incorrect value type "
                          "%s, on key %s, valid is %s"
                          % (type(v), k, valid_wr[k]))
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
            return wp
    return {}


def __load_wp_map(configuration, do_lock=True):
    """Load map of workflow patterns. Uses a pickled
    dictionary for efficiency. Optional do_lock option is used to enable and
    disable locking during load.
    """
    _logger = configuration.logger
    _logger.debug("WP: __load_wp_map")
    return load_system_map(configuration, 'workflowpatterns', do_lock)


def __refresh_wp_map(configuration):
    """Refresh map of workflow patterns. Uses a pickled dictionary for
    efficiency. Only update map for workflow patterns that appeared or
    disappeared after last map save.
    NOTE: Save start time so that any concurrent updates get caught next time
    """
    _logger = configuration.logger
    _logger.debug("WP: __refresh_wp_map")

    start_time = time.time()
    dirty = []
    map_path = os.path.join(configuration.mig_system_files,
                            'workflowpatterns.map')
    lock_path = map_path.replace('.map', '.lock')
    lock_handle = open(lock_path, 'a')
    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
    workflow_p_map, map_stamp = __load_wp_map(configuration,
                                              do_lock=False)
    # Find all workflow patterns
    (load_status, all_wps) = __list_path_wps(configuration)
    if not load_status:
        _logger.warning('WP: failed to load list: %s' % all_wps)
        return workflow_p_map

    for wp_dir, wp_file in all_wps:
        wp_mtime = os.path.getmtime(os.path.join(wp_dir, wp_file))

        # init first time
        workflow_p_map[wp_file] = workflow_p_map.get(wp_file, {})
        if CONF not in workflow_p_map[wp_file] or wp_mtime >= map_stamp:
            wp = __load_wp(configuration, os.path.join(wp_dir, wp_file))
            workflow_p_map[wp_file][CONF] = wp
            workflow_p_map[wp_file][MODTIME] = map_stamp
            dirty.append([wp_file])

    # Remove any missing workflow patterns from map
    missing_wp = [wp_file for wp_file in workflow_p_map.keys()
                  if wp_file not in [_wp_file for _wp_path, _wp_file in
                                     all_wps]]

    for wp_file in missing_wp:
        del workflow_p_map[wp_file]
        dirty.append([wp_file])

    if dirty:
        try:
            dump(workflow_p_map, map_path)
            os.utime(map_path, (start_time, start_time))
        except Exception, err:
            _logger.error('WP: could not save map, or %s' % err)
    last_refresh[WORKFLOW_PATTERNS] = start_time
    lock_handle.close()
    return workflow_p_map


def __list_path_wps(configuration):
    """Returns a list of tuples, containing the path to the individual
    workflow patterns and the actual workflow pattern: (path,wp)
    """
    _logger = configuration.logger
    _logger.debug("WP: __list_path_wps")

    wp_home = configuration.workflow_patterns_home
    workflows = []
    if not os.path.exists(wp_home):
        try:
            os.makedirs(wp_home)
        except Exception, err:
            _logger.error('WP: not able to create directory %s %s' %
                          (wp_home, err))
            return (False, 'Failed to setup required directory for workflow '
                           'patterns')

    client_dirs = os.listdir(wp_home)
    for client_dir in client_dirs:
        dir_content = []
        client_path = os.path.join(wp_home,
                                   client_dir)
        dir_content = os.listdir(client_path)
        for entry in dir_content:
            # Skip dot files/dirs and the write lock
            if entry.startswith('.') or entry == WRITE_LOCK:
                continue
            if os.path.isfile(os.path.join(client_path, entry)):
                workflows.append((client_path, entry))
            else:
                _logger.warning('WP: %s in %s is not a plain file, move it?' %
                                (entry, client_path))
    return (True, workflows)


def __query_map_for(configuration, client_id=None, **kwargs):
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
        if CONF in wp_content:
            wp_obj = __build_wp_object(configuration, **wp_content[CONF])
            _logger.debug("WP: wp_obj %s" % wp_obj)
            if not wp_obj:
                continue
            if kwargs:
                for k, v in kwargs.items():
                    if k in wp_obj and v == wp_obj[k]:
                        matches.append(wp_obj)
            else:
                matches.append(wp_obj)
    return matches


def __query_map_for_first(configuration, client_id=None, **kwargs):
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
            if kwargs:
                for k, v in kwargs.items():
                    if k in wp_obj and v == wp_obj[k]:
                        return wp_obj
            else:
                return wp_obj
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
                                     valid_wp['persistence_id']()),
        'owner': kwargs.get('owner', valid_wp['owner']()),
        'name': kwargs.get('name', valid_wp['name']()),
        'inputs': kwargs.get('inputs', valid_wp['inputs']()),
        'output': kwargs.get('output', valid_wp['output']()),
        'type_filter': kwargs.get('type_filter',
                                  valid_wp['type_filter']()),
        'recipes': kwargs.get('recipes', valid_wp['recipes']()),
        'variables': kwargs.get('variables', valid_wp['variables']())
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
                                     valid_wp['persistence_id']()),
        'owner': kwargs.get('owner', valid_wp['owner']()),
        'name': kwargs.get('name', valid_wp['name']()),
        'recipe': kwargs.get('recipe', valid_wp['recipe']())
    }
    return wr_obj


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
        workflow_p_map = __refresh_wp_map(configuration)
        reset_workflow_p_modified(configuration)
    else:
        _logger.debug('WP: no changes - not refreshing')
        workflow_p_map, map_stamp = __load_wp_map(configuration)
    last_map[WORKFLOW_PATTERNS] = workflow_p_map
    last_refresh[WORKFLOW_PATTERNS] = map_stamp
    last_load[WORKFLOW_PATTERNS] = map_stamp
    return workflow_p_map


def get_wp_with(configuration, first=True, client_id=None, **kwargs):
    """Returns a clients workflow pattern with a field_name"""
    _logger = configuration.logger
    _logger.debug("WP: get_wp_with, client_id: %s, kwargs: %s"
                  % (client_id, kwargs))
    if not isinstance(kwargs, dict):
        _logger.error('WP: wrong format supplied for %s', type(kwargs))
        return None
    if first:
        wp = __query_map_for_first(configuration, client_id, **kwargs)
    else:
        wp = __query_map_for(configuration, client_id, **kwargs)
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
        wr = __query_map_for_first(configuration, client_id, **kwargs)
    else:
        wr = __query_map_for(configuration, client_id, **kwargs)
    return wr


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

    wp_path = os.path.join(configuration.workflow_patterns_home, client_dir,
                           persistence_id)
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
    wr = get_wp_with(configuration, client_id=client_id, name=name)
    persistence_id = wr['persistence_id']

    wr_path = os.path.join(configuration.workflow_recipes_home, client_dir,
                           persistence_id)
    if not os.path.exists(wr_path):
        msg = "The '%s' workflow recipe dosen't appear to exist" % name
        _logger.error("WR: can't delete %s it dosen't exist" % wr_path)
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
        'inputs': [],
        'output': '',
        'type_filter': [],
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

    wp_home = os.path.join(configuration.workflow_patterns_home,
                           client_dir)
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
    # Save the pattern
    wrote = False
    msg = ''
    try:
        with open(wp_file_path, 'w') as j_file:
            json.dump(wp, j_file, indent=0)

        # Mark as modified
        mark_workflow_p_modified(configuration, wp['persistence_id'])
        wrote = True
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


# TODO, implement
def update_workflow_pattern(configuration, client_id, name):
    """Update a workflow pattern"""
    pass


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
        return (False, msg)

    correct, msg = __correct_wr(configuration, wr)
    if not correct:
        return (correct, msg)

    # TODO check for create required keys
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
            return (False, msg)

    wr_home = os.path.join(configuration.workflow_recipes_home,
                           client_dir)
    if not os.path.exists(wr_home):
        try:
            os.makedirs(wr_home)
        except Exception, err:
            _logger.error("WR: couldn't create directory %s %s" %
                          (wr_home, err))
            msg = "Couldn't create the required dependencies for " \
                  "your workflow recipe"
            return (False, msg)

    persistence_id = generate_random_ascii(wr_id_length, charset=wr_id_charset)
    wr_file_path = os.path.join(wr_home, persistence_id)

    if os.path.exists(wr_file_path):
        _logger.error('WR: unique filename conflict: %s '
                      % wr_file_path)
        msg = 'A workflow recipe conflict was encountered, '
        'please try and resubmit the recipe'
        return (False, msg)

    wr['persistence_id'] = persistence_id
    # Save the recipe
    wrote = False
    msg = ''
    try:
        with open(wr_file_path, 'w') as j_file:
            json.dump(wr, j_file, indent=0)

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
        return (False, msg)

    _logger.info('WR: %s created at: %s ' %
                 (client_id, wr_file_path))
    return (True, '')

    pass


def get_recipe_from_file(configuration, recipe_file):
    """"""
    # TODO, find out which type of recipe it is
    _logger = configuration.logger
    try:
        with open(recipe_file) as raw_recipe:
            json_recipe = json.load(raw_recipe)
            return json_recipe
    except Exception as err:
        _logger.error("Failed to json load: %s from: %s " % (err, recipe_file))
    return {}


def get_pattern_from_file(configuration, pattern_file):
    """"""
    # TODO, find out which type of recipe it is
    _logger = configuration.logger
    try:
        with open(pattern_file) as raw_recipe:
            json_recipe = json.load(raw_recipe)
            return json_recipe
    except Exception as err:
        _logger.error("Failed to json load: %s from: %s " % (err, pattern_file))
    return {}


def rule_identification_from_pattern(configuration, client_id,
                                     workflow_pattern):
    """identifies if a task can be created, following the creation or
    editing of a pattern ."""

    # work out recipe directory
    client_dir = client_id_dir(client_id)
    recipe_dir_path = os.path.join(configuration.workflow_recipes_home,
                                   client_dir)

    # setup logger
    _logger = configuration.logger
    _logger.info('%s is identifying any possible tasks from pattern creation '
                 '%s' % (client_id, workflow_pattern['name']))

    # Currently multiple recipes are crudely chained together. This will need
    # to be altered once we move into other languages than python.
    complete_recipe = ''
    missed_recipes = []
    # Check if defined recipes exist already within system
    for recipe_name in workflow_pattern['recipes']:
        _logger.info("DELETE ME - looking for recipe " + recipe_name)
        got_this_recipe = False
        # This assumes that recipes are saved as their name.
        for recipe in os.listdir(recipe_dir_path):
            _logger.info("DELETE ME - looking at file " + recipe)
            recipe_path = os.path.join(recipe_dir_path, recipe)
            recipe = get_recipe_from_file(configuration, recipe_path)
            if recipe:
                if recipe['name'] == recipe_name:
                    for line in recipe['recipe']:
                        complete_recipe += line
                    got_this_recipe = True
        if not got_this_recipe:
            missed_recipes.append(recipe_name)
    if missed_recipes:
        return (False, 'Could not find all required recipes. Missing: ' +
                str(missed_recipes))
    return (True, 'All recipes found')


    # # if all recipes are present then check for data files
    # if got_all_recipes and complete_recipe != '':
    #     pass
    #     # Generate rule from pattern and recipe
    #
    #     rule_dir_path = client_dir
    #
    #     # TODO work this out according to grid_events lines 1574 to 1581
    #     user_arguments_dict = {
    #         'vgrid_name': REJECT_UNSET,
    #         'rule_id': [keyword_auto],
    #         'path': [''],
    #         'changes': [any_state],
    #         'action': [keyword_auto],
    #         'arguments': [''],
    #         'rate_limit': [''],
    #         'settle_time': [''],
    #         'match_files': ['True'],
    #         'match_dirs': ['False'],
    #         'match_recursive': ['False'],
    #         'rank': [''],
    #     }
    #     add_vgrid_trigger_main(client_id, user_arguments_dict)
    #
    # # if we didn't find all the required recipes
    # else:
    #     _logger.info("Did not find all the necessary recipes for pattern " +
    #                  workflow_pattern['name'])


def rule_identification_from_recipe(client_id, workflow_recipe, configuration):
    # TODO finish this
    """identifies if a task can be created, following the creation or
    editing of a recipe . This pattern is read in as the object
    workflow_recipe and is expected in the format."""

    # work out pattern directory
    client_dir = client_id_dir(client_id)
    pattern_dir_path = os.path.join(configuration.workflow_patterns_home,
                                   client_dir)
    recipe_dir_path = os.path.join(configuration.workflow_recipes_home,
                                   client_dir)

    # setup logger
    _logger = configuration.logger
    _logger.info('%s is identifying any possible tasks from recipe creation '
                 '%s' % (client_id, workflow_recipe['name']))

    matching_patterns = []
    # Check if patterns exist already within system that need this recipe
    for pattern_file in os.listdir(pattern_dir_path):
        # convert stored pattern into object
        try:
            with open(pattern_file, 'r') as raw_pattern:
                pattern = json.load(raw_pattern)
                if workflow_recipe['name'] in pattern['recipes']:
                    matching_patterns.append(pattern)
        except Exception, err:
            _logger.error('failed to parse pattern file ' + pattern_file)

    # now check all matching patterns have all their recipes
    for pattern in matching_patterns:
        complete_recipe = ''
        got_all_recipes = True
        # TODO this will almost certainly need altered once recipes have been
        #  implemented
        # This assumes that recipes are saved as their name.
        for recipe in os.listdir(recipe_dir_path):
            got_this_recipe = False
            if recipe in pattern['recipes']:
                try:
                    recipe_path = os.path.join(recipe_dir_path, recipe)
                    with open(recipe_path) as input_file:
                        for line in input_file:
                            complete_recipe += line
                    got_this_recipe = True
                except Exception:
                    _logger.error('')
            if not got_this_recipe:
                got_all_recipes = False

        # if all recipes are present then we can update rules
        if got_all_recipes and complete_recipe != '':
            pass
            # Generate rule from pattern and recipe


