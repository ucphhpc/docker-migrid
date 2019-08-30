#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# --- BEGIN_HEADER ---
#
# workflows - workflow functions
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

"""Workflow functions"""

import sys
import copy
import fcntl
import os
import time
import tempfile
import re
import h5py

from shared.base import client_id_dir, force_utf8_rec
from shared.conf import get_configuration_object
from shared.map import load_system_map
from shared.modified import check_workflow_p_modified, \
    check_workflow_r_modified, reset_workflow_p_modified, \
    reset_workflow_r_modified, mark_workflow_p_modified, \
    mark_workflow_r_modified
from shared.pwhash import generate_random_ascii
from shared.defaults import wp_id_charset, wp_id_length, wr_id_charset, \
    wr_id_length, session_id_length, session_id_charset
from shared.serial import dump, load, dumps
from shared.vgrid import vgrid_add_triggers, vgrid_remove_triggers, \
    vgrid_triggers
from shared.job import new_job, fields_to_mrsl, \
    get_job_ids_with_task_file_in_contents
from shared.fileio import delete_file, write_file, unpickle, \
    unpickle_and_change_status, send_message_to_grid_script, \
    makedirs_rec
from shared.validstring import possible_workflow_session_id
from shared.mrslkeywords import get_keywords_dict
from shared.pattern import Pattern, DEFAULT_JOB_FILE_INPUT, \
    DEFAULT_JOB_FILE_OUTPUT


NOT_ENABLED = 1
INVALID_SESSION_ID = 2
NOT_FOUND = 3
WORKFLOWS_ERRORS = (NOT_ENABLED, INVALID_SESSION_ID, NOT_FOUND)

WRITE_LOCK = 'write.lock'
WORKFLOW_PATTERN = 'workflowpattern'
WORKFLOW_RECIPE = 'workflowrecipe'
WORKFLOW_ANY = 'any'
WORKFLOW_API_DB_NAME = 'workflow_api_db'
WORKFLOW_TYPES = [WORKFLOW_PATTERN, WORKFLOW_RECIPE, WORKFLOW_ANY]
WORKFLOW_CONSTRUCT_TYPES = [WORKFLOW_PATTERN, WORKFLOW_RECIPE]
CELL_TYPE, CODE, SOURCE = 'cell_type', 'code', 'source'
WORKFLOW_PATTERNS, WORKFLOW_RECIPES, MODTIME, CONF = \
    ['__workflowpatterns__', '__workflow_recipes__', '__modtime__', '__conf__']
MAP_CACHE_SECONDS = 60

last_load = {WORKFLOW_PATTERNS: 0, WORKFLOW_RECIPES: 0}
last_refresh = {WORKFLOW_PATTERNS: 0, WORKFLOW_RECIPES: 0}
last_map = {WORKFLOW_PATTERNS: {}, WORKFLOW_RECIPES: {}}

BUFFER_FLAG = 'BUFFER_FLAG'

# a persistent correct pattern
VALID_PATTERN = {
    'object_type': str,
    'persistence_id': str,
    'owner': str,
    'vgrid': str,
    'name': str,
    'input_file': str,
    'output': dict,
    'trigger': dict,
    'trigger_paths': list,
    'recipes': list,
    'variables': dict,
}

# attributes that the user can externally provide
VALID_USER_PATTERN = {
    'vgrid': str,
    'name': str,
    'input_file': str,
    'output': dict,
    'trigger_paths': list,
    'recipes': list,
    'variables': dict
}

# Attributes that the user can provide via an update request
VALID_USER_UPDATE_PATTERN = {
    'persistence_id': str
}
VALID_USER_UPDATE_PATTERN.update(VALID_USER_PATTERN)

# a persistent correct recipe
VALID_RECIPE = {
    'object_type': str,
    'persistence_id': str,
    'owner': str,
    'vgrid': str,
    'name': str,
    'triggers': dict,
    'recipe': dict,
    'source': str
}

# Attributes that the user can externally provide
VALID_USER_RECIPE = {
    'vgrid': str,
    'name': str,
    'recipe': dict,
    'source': str
}

# Attributes that the user can provide via an update request
VALID_USER_UPDATE_RECIPE = {
    'persistence_id': str,
}
VALID_USER_UPDATE_RECIPE.update(VALID_USER_RECIPE)

# Only update the triggers if these variables are changed in a pattern
UPDATE_TRIGGER_PATTERN = [
    'inputs',
    'outputs',
    'recipes',
    'variables'
]

# Only update the triggers if these variables are changed in a recipe
UPDATE_TRIGGER_RECIPE = [
    'name',
    'recipe'
]

WF_INPUT = 'wf_input_file'


# TODO several of the following functions can probably be rolled together. If
#  at the end of implementation this is still the case then do so

def touch_workflow_sessions_db(configuration, force=False):
    """Create and save an empty workflow_sessions_db"""
    _logger = configuration.logger
    _logger.debug('WP: touch_workflow_sessions_db, '
                  'creating empty db if it does not exist')
    _db_path = configuration.workflows_db

    if os.path.exists(_db_path) and not force:
        _logger.debug('WP: touch_workflow_sessions_db, '
                      'db: %s already exists ' % _db_path)
        return False

    # Ensure the dirpath is available
    dir_path = os.path.dirname(_db_path)
    if not makedirs_rec(dir_path, configuration, accept_existing=True):
        _logger.debug('WP: touch_workflow_sessions_db, '
                      'failed to create dependent dir %s'
                      % dir_path)
        return False
    return save_workflow_sessions_db(configuration, {})


def delete_workflow_sessions_db(configuration):
    """Remove workflow_sessions_db"""
    _logger = configuration.logger
    _logger.debug('WP: touch_workflow_sessions_db, '
                  'creating empty db if it does not exist')
    _db_path = configuration.workflows_db
    return delete_file(_db_path, _logger)


def load_workflow_sessions_db(configuration):
    """Read in the workflow DB dictionary:
    Format is {session_id: 'owner': client_id}
    """
    _db_path = configuration.workflows_db
    return load(_db_path)


def save_workflow_sessions_db(configuration, workflow_sessions_db):
    """Read in the workflow session DB dictionary:
    Format is {session_id: 'owner': client_id}
    """
    _logger = configuration.logger
    _db_path = configuration.workflows_db

    try:
        dump(workflow_sessions_db, _db_path)
    except IOError as err:
        _logger.error('WP: save_workflow_sessions_db, '
                      'Failed to open %s, err: %s' % (_db_path, err))
        return False
    return True


def create_workflow_session_id(configuration, client_id):
    """ """
    _logger = configuration.logger

    # Generate session id
    workflow_session_id = new_workflow_session_id()
    db = load_workflow_sessions_db(configuration)
    db[workflow_session_id] = {'owner': client_id}
    saved = save_workflow_sessions_db(configuration, db)
    if not saved:
        _logger.error('WP: create_workflow_session_id, failed to add a '
                      'workflow session id for user: %s' % client_id)
        return False
    return workflow_session_id


def delete_workflow_session_id(configuration, workflow_session_id):
    """ """
    _logger = configuration.logger

    db = load_workflow_sessions_db(configuration)
    if workflow_session_id not in db:
        _logger.error('WP: delete_workflow_session_id, '
                      'failed to delete workflow_session_id: %s '
                      'was not found in db' % workflow_session_id)
        return False
    db.pop(workflow_session_id, None)
    return save_workflow_sessions_db(configuration, db)


def get_workflow_session_id(configuration, client_id):
    """ """
    _logger = configuration.logger
    db = load_workflow_sessions_db(configuration)
    for session_id, user_state in db.items():
        if user_state.get('owner', '') == client_id:
            return session_id
    return None


def new_workflow_session_id():
    """ """
    return generate_random_ascii(session_id_length,
                                 session_id_charset)


def __correct_wp(configuration, wp):
    """Validates that the workflow pattern object is correctly formatted"""
    _logger = configuration.logger
    contact_msg = "please contact support so that we can help resolve this " \
                  "issue"

    if not wp:
        msg = "A workflow pattern was not provided, " + contact_msg
        _logger.error("WP: __correct_wp, wp was not set '%s'" % wp)
        return (False, msg)

    if not isinstance(wp, dict):
        msg = "The workflow pattern was incorrectly formatted, " + contact_msg
        _logger.error("WP: __correct_wp, wp had an incorrect type '%s'" % wp)
        return (False, msg)

    msg = "The workflow pattern had an incorrect structure, " + contact_msg
    for k, v in wp.items():
        if k not in VALID_PATTERN:
            _logger.error("WP: __correct_wp, wp had an incorrect key '%s', "
                          "allowed are %s" % (k, VALID_PATTERN.keys()))
            return (False, msg)
        if not isinstance(v, VALID_PATTERN.get(k)):
            _logger.error("WP: __correct_wp, wp had an incorrect value type "
                          "'%s', on key '%s', valid is '%s'"
                          % (type(v), k, VALID_PATTERN[k]))
            return (False, msg)
    return (True, "")


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
        if not isinstance(v, VALID_RECIPE.get(k)):
            _logger.error("WR: __correct_wr, wr had an incorrect value type "
                          "%s, on key %s, valid is %s"
                          % (type(v), k, VALID_RECIPE[k]))
            return (False, msg)
    return (True, '')


def __load_wp(configuration, wp_path):
    """Load the workflow pattern from the specified path"""
    _logger = configuration.logger
    _logger.debug("WP: load_wp, wp_path: %s" % wp_path)

    if not os.path.exists(wp_path):
        _logger.error("WP: %s does not exist" % wp_path)
        return {}

    wp = None
    try:
        wp = load(wp_path, serializer='json')
    except Exception, err:
        configuration.logger.error('WP: could not open workflow pattern %s %s'
                                   % (wp_path, err))
    if wp and isinstance(wp, dict):
        # Ensure string type
        wp = force_utf8_rec(wp)
        correct, _ = __correct_wp(configuration, wp)
        if correct:
            return wp
    return {}


def __load_wr(configuration, wr_path):
    """Load the workflow recipe from the specified path"""
    _logger = configuration.logger
    _logger.debug("WR: load_wr, wr_path: %s" % wr_path)

    if not os.path.exists(wr_path):
        _logger.error("WR: %s does not exist" % wr_path)
        return {}

    wr = None
    try:
        wr = load(wr_path, serializer='json')
    except Exception, err:
        configuration.logger.error('WR: could not open workflow recipe %s %s'
                                   % (wr_path, err))
    if wr and isinstance(wr, dict):
        # Ensure string type
        wr = force_utf8_rec(wr)
        correct, _ = __correct_wr(configuration, wr)
        if correct:
            return wr
    return {}


def __load_map(configuration, workflow_type=WORKFLOW_PATTERN, do_lock=True):
    """Load map of workflow patterns. Uses a pickled
    dictionary for efficiency. Optional do_lock option is used to enable and
    disable locking during load.
    """
    if workflow_type == WORKFLOW_PATTERN:
        return load_system_map(configuration, 'workflowpatterns', do_lock)
    elif workflow_type == WORKFLOW_RECIPE:
        return load_system_map(configuration, 'workflowrecipes', do_lock)


def __refresh_map(configuration, workflow_type=WORKFLOW_PATTERN):
    """Refresh map of workflow objects. Uses a pickled dictionary for
    efficiency. Only update map for workflow objects that appeared or
    disappeared after last map save.
    NOTE: Save start time so that any concurrent updates get caught next time
    """
    _logger = configuration.logger
    _logger.debug("WP: __refresh_map workflow_type: %s" % workflow_type)

    start_time = time.time()
    dirty = []

    map_path = ''
    if workflow_type == WORKFLOW_PATTERN:
        map_path = os.path.join(configuration.mig_system_files,
                                'workflowpatterns.map')
    elif workflow_type == WORKFLOW_RECIPE:
        map_path = os.path.join(configuration.mig_system_files,
                                'workflowrecipes.map')
    lock_path = map_path.replace('.map', '.lock')
    lock_handle = open(lock_path, 'a')
    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)

    workflow_map, map_stamp = __load_map(
        configuration, workflow_type, do_lock=False)

    # Find all workflow objects
    (load_status, all_objects) = __list_path(configuration, workflow_type)
    if not load_status:
        _logger.warning('Workflows: failed to load list: %s' % all_objects)
        return workflow_map

    for workflow_dir, workflow_file in all_objects:
        workflow_map[workflow_file] = workflow_map.get(workflow_file, {})

        # the previous way of calculating wp_mtime isn't 'accurate' enough.
        # When identifying from pattern creation it takes lone enough some
        # overlap can occur. This has been changed to the new way shown below,
        # but the old method is left unless UNFORESEEN CONSEQUENCES OCCUR.
        wp_mtime = os.path.getmtime(os.path.join(workflow_dir, workflow_file))

        if CONF not in workflow_map[workflow_file] or wp_mtime >= map_stamp:
            workflow_object = ''
            if workflow_type == WORKFLOW_PATTERN:
                workflow_object = __load_wp(configuration,
                                            os.path.join(workflow_dir,
                                                         workflow_file))
            elif workflow_type == WORKFLOW_RECIPE:
                workflow_object = __load_wr(configuration,
                                            os.path.join(workflow_dir,
                                                         workflow_file))
            workflow_map[workflow_file][CONF] = workflow_object
            workflow_map[workflow_file][MODTIME] = map_stamp
            dirty.append([workflow_file])

    # Remove any missing workflow patterns from map
    missing_workflow = [workflow_file for workflow_file in workflow_map.keys()
                        if workflow_file not in [_workflow_file for
                                                 _workflow_path, _workflow_file
                                                 in all_objects]]

    for workflow_file in missing_workflow:
        del workflow_map[workflow_file]
        dirty.append([workflow_file])

    if dirty:
        try:
            dump(workflow_map, map_path)
            os.utime(map_path, (start_time, start_time))
            _logger.debug('Accessed map and updated to %.10f' % start_time)

        except Exception, err:
            _logger.error('Workflows: could not save map, or %s' % err)
    if workflow_type == WORKFLOW_PATTERN:
        last_refresh[WORKFLOW_PATTERNS] = start_time
    elif workflow_type == WORKFLOW_RECIPE:
        last_refresh[WORKFLOW_RECIPES] = start_time
    lock_handle.close()
    return workflow_map


def __list_path(configuration, workflow_type=WORKFLOW_PATTERN):
    """Returns a list of tuples, containing the path to the individual
    workflow objects and the actual objects. These can be either patterns or
    recipes: (path,wp)
    """
    _logger = configuration.logger
    _logger.debug("Workflows: __list_path")

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
            if workflow_type == WORKFLOW_PATTERN:
                client_home = get_workflow_pattern_home(
                    configuration, vgrid)
            elif workflow_type == WORKFLOW_RECIPE:
                client_home = get_workflow_recipe_home(
                    configuration, vgrid)
            else:
                return (False, "Invalid input. Must be 'pattern' or 'recipe'")
            if not os.path.exists(client_home):
                if not makedirs_rec(client_home, configuration):
                    return (False,
                            "Failed to setup required directory "
                            "for workflow %s" % workflow_type)
            dir_content = os.listdir(client_home)
            for entry in dir_content:
                # Skip dot files/dirs and the write lock
                if entry.startswith('.') or entry == WRITE_LOCK:
                    continue
                if os.path.isfile(os.path.join(client_home, entry)):
                    objects.append((client_home, entry))
                else:
                    _logger.warning('WP: %s in %s is not a plain file, '
                                    'move it?' % (entry, client_home))
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


def __query_workflow_map(configuration, client_id=None, first=False,
                         display_safe=False, workflow_type=WORKFLOW_PATTERN,
                         **kwargs):
    """"""
    _logger = configuration.logger
    _logger.debug('__query_workflow_map, client_id: %s, '
                  'workflow_type: %s, kwargs: %s' % (client_id, workflow_type,
                                                     kwargs))
    workflow_map = None
    if workflow_type == WORKFLOW_PATTERN:
        workflow_map = get_wp_map(configuration)

    if workflow_type == WORKFLOW_RECIPE:
        workflow_map = get_wr_map(configuration)

    if workflow_type == WORKFLOW_ANY:
        # Load every type into workflow_map
        workflow_map = get_wr_map(configuration)
        workflow_map.update(get_wp_map(configuration))

    if not workflow_map:
        _logger.debug("WP: __query_workflow_map, empty map retrieved: '%s'"
                      ", workflow_type: %s" % (workflow_map, workflow_type))
        return None

    if client_id:
        workflow_map = {k: v for k, v in workflow_map.items()
                        if v.get(CONF, None) and 'owner' in v[CONF]
                        and client_id == v[CONF]['owner']}

    matches = []
    for _, workflow in workflow_map.items():
        workflow_conf = workflow.get(CONF, None)
        if not workflow_conf:
            _logger.error('WP: __query_workflow_map, no configuration '
                          'present to build the workflow object from '
                          'workflow %s' % workflow)
            continue

        workflow_obj = __build_workflow_object(configuration,
                                               display_safe,
                                               workflow_conf['object_type'],
                                               **workflow_conf)
        if not workflow_obj:
            continue

        # Search with kwargs
        if kwargs:
            all_match = True
            for k, v in kwargs.items():
                # TODO, move v != "" to a search section that is intended
                # for outside API search. I.e. will do expansive search beyond
                # the exact value
                if (k not in workflow_obj[workflow_conf['object_type']]) or \
                        (workflow_obj[workflow_conf['object_type']][k] != v
                         and v != ""):
                    all_match = False
            if all_match:
                matches.append(workflow_obj[workflow_conf['object_type']])
        else:
            matches.append(workflow_obj[workflow_conf['object_type']])

    if matches:
        if first:
            return matches[0]
        else:
            return matches
    return None


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


def __build_workflow_object(configuration, display_safe=False,
                            workflow_type=WORKFLOW_PATTERN, **kwargs):
    _logger = configuration.logger
    workflow = {}
    if workflow_type == WORKFLOW_PATTERN:
        workflow_pattern = __build_wp_object(configuration, display_safe,
                                             **kwargs)
        if workflow_pattern:
            workflow.update({WORKFLOW_PATTERN: workflow_pattern})

    if workflow_type == WORKFLOW_RECIPE:
        workflow_recipe = __build_wr_object(configuration, display_safe,
                                            **kwargs)
        if workflow_recipe:
            workflow.update({WORKFLOW_RECIPE: workflow_recipe})

    if workflow:
        workflow['object_type'] = 'workflow'
    return workflow


def __build_wp_object(configuration, display_safe=False, **kwargs):
    """Build a workflow pattern object based on keyword arguments."""
    _logger = configuration.logger
    _logger.debug("WP: __build_wp_object, kwargs: %s" % kwargs)
    correct, _ = __correct_wp(configuration, kwargs)
    if not correct:
        return None

    wp_obj = {
        'object_type': kwargs.get('object_type', WORKFLOW_PATTERN),
        'persistence_id': kwargs.get('persistence_id',
                                     VALID_PATTERN['persistence_id']()),
        'owner': kwargs.get('owner', VALID_PATTERN['owner']()),
        'name': kwargs.get('name', VALID_PATTERN['name']()),
        'input_file': kwargs.get('input_file',
                                 VALID_PATTERN['input_file']()),
        'trigger_paths': kwargs.get('trigger_paths',
                                    VALID_PATTERN['trigger_paths']()),
        'output': kwargs.get('output', VALID_PATTERN['output']()),
        'recipes': kwargs.get('recipes', VALID_PATTERN['recipes']()),
        'variables': kwargs.get('variables', VALID_PATTERN['variables']()),
        'trigger': kwargs.get('trigger', VALID_PATTERN['trigger']()),
        'vgrid': kwargs.get('vgrid', VALID_PATTERN['vgrid']())
    }

    if display_safe:
        wp_obj.pop('owner', None)

    return wp_obj


def __build_wr_object(configuration, display_safe=False, **kwargs):
    """Build a workflow recipe object based on keyword arguments."""
    _logger = configuration.logger
    _logger.debug("WR: __build_wr_object, kwargs: %s" % kwargs)
    correct, _ = __correct_wr(configuration, kwargs)
    if not correct:
        return None

    wr_obj = {
        'object_type': kwargs.get('object_type', WORKFLOW_RECIPE),
        'persistence_id': kwargs.get('persistence_id',
                                     VALID_RECIPE['persistence_id']()),
        'owner': kwargs.get('owner', VALID_RECIPE['owner']()),
        'name': kwargs.get('name', VALID_RECIPE['name']()),
        'recipe': kwargs.get('recipe', VALID_RECIPE['recipe']()),
        'triggers': kwargs.get('triggers', VALID_RECIPE['triggers']()),
        'vgrid': kwargs.get('vgrid', VALID_RECIPE['vgrid']()),
        'source': kwargs.get('source', VALID_RECIPE['source']())
    }

    if display_safe:
        wr_obj.pop('owner', None)

    return wr_obj


def get_workflow_pattern_home(configuration, vgrid):
    """Returns the path of the directory storing patterns for a given vgrid"""
    _logger = configuration.logger
    vgrid_path = os.path.join(configuration.vgrid_files_home, vgrid)
    pattern_home = os.path.join(vgrid_path,
                                configuration.vgrid_workflow_patterns_home)
    return pattern_home


def get_workflow_recipe_home(configuration, vgrid):
    """Returns the path of the directory storing recipes for a given vgrid"""
    vgrid_path = os.path.join(configuration.vgrid_files_home, vgrid)
    recipe_home = os.path.join(vgrid_path,
                               configuration.vgrid_workflow_recipes_home)
    return recipe_home


def get_workflow_task_home(configuration, vgrid):
    """Returns the path of the directory storing tasks for a given vgrid"""
    vgrid_path = os.path.join(configuration.vgrid_files_home, vgrid)
    task_home = os.path.join(vgrid_path,
                             configuration.vgrid_workflow_tasks_home)
    return task_home


def get_workflow_buffer_home(configuration, vgrid):
    """Returns the path of the directory storing buffer files for a given
    vgrid"""
    vgrid_path = os.path.join(configuration.vgrid_files_home, vgrid)
    buffer_home = os.path.join(vgrid_path,
                               configuration.vgrid_workflow_buffer_home)
    return buffer_home


def get_wp_map(configuration):
    """Returns the current map of workflow patterns and
    their configurations. Caches the map for load prevention with
    repeated calls within short time span.
    """
    _logger = configuration.logger
    modified_patterns, _ = check_workflow_p_modified(configuration)
    if modified_patterns:
        map_stamp = time.time()
        workflow_p_map = __refresh_map(configuration)
        reset_workflow_p_modified(configuration)
    else:
        workflow_p_map, map_stamp = __load_map(configuration)
    last_map[WORKFLOW_PATTERNS] = workflow_p_map
    last_refresh[WORKFLOW_PATTERNS] = map_stamp
    last_load[WORKFLOW_PATTERNS] = map_stamp
    _logger.debug("WP: got: '%s' map" % workflow_p_map)
    return workflow_p_map


def get_wr_map(configuration):
    """Returns the current map of workflow recipes and
    their configurations. Caches the map for load prevention with
    repeated calls within short time span.
    """
    _logger = configuration.logger
    modified_recipes, _ = check_workflow_r_modified(configuration)
    if modified_recipes:
        map_stamp = time.time()
        workflow_r_map = __refresh_map(configuration,
                                       workflow_type=WORKFLOW_RECIPE)
        reset_workflow_r_modified(configuration)
    else:
        workflow_r_map, map_stamp = __load_map(configuration,
                                               workflow_type=WORKFLOW_RECIPE)
    last_map[WORKFLOW_RECIPES] = workflow_r_map
    last_refresh[WORKFLOW_RECIPES] = map_stamp
    last_load[WORKFLOW_RECIPES] = map_stamp
    _logger.debug("WR: got: '%s' map" % workflow_r_map)
    return workflow_r_map


def get_workflow_with(configuration, client_id=None, first=False,
                      display_safe=False, workflow_type=WORKFLOW_PATTERN,
                      **kwargs):
    _logger = configuration.logger
    _logger.debug('get_workflow_with, first: %s, client_id: %s,'
                  ' workflow_type: %s, kwargs: %s' %
                  (first, client_id, workflow_type, kwargs))
    if workflow_type not in WORKFLOW_TYPES:
        _logger.error('get_workflow_with, invalid workflow_type: %s '
                      'provided' % workflow_type)
        return None
    if not isinstance(kwargs, dict):
        _logger.error('wrong format supplied for %s', type(kwargs))
        return None

    return __query_workflow_map(configuration, client_id, first,
                                display_safe, workflow_type, **kwargs)


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


def create_workflow(configuration, client_id, workflow_type=WORKFLOW_PATTERN,
                    **kwargs):
    """ """
    _logger = configuration.logger
    vgrid = kwargs.get('vgrid', None)
    if not vgrid:
        msg = "A workflow create dependency was missing: 'vgrid'"
        _logger.error("create_workflow: 'vgrid' was not set: '%s'" % vgrid)
        return (False, msg)

    persistence_id = kwargs.get('persistence_id', None)
    if persistence_id:
        msg = "'persistence_id' cannot be manually set by a user. Are " \
              "you intending to update an existing pattern instead? "
        return (False, msg)

    if workflow_type == WORKFLOW_RECIPE:
        return __create_workflow_recipe_entry(configuration, client_id,
                                              vgrid, kwargs)

    return __create_workflow_pattern_entry(configuration, client_id,
                                           vgrid, kwargs)


def delete_workflow(configuration, client_id, workflow_type=WORKFLOW_PATTERN,
                    **kwargs):
    """ """
    _logger = configuration.logger
    vgrid = kwargs.get('vgrid', None)
    if not vgrid:
        msg = "A workflow removal dependency was missing: 'vgrid'"
        _logger.error("delete_workflow: 'vgrid' was not set %s" % vgrid)
        return (False, msg)

    persistence_id = kwargs.get('persistence_id', None)
    if not persistence_id:
        msg = "A workflow removal dependency was missing: 'persistence_id'"
        _logger.error("delete_workflow: 'persistence_id' was not set %s" %
                      persistence_id)
        return (False, msg)

    if workflow_type == WORKFLOW_RECIPE:
        return delete_workflow_recipe(configuration, client_id, vgrid,
                                      persistence_id)
    return delete_workflow_pattern(configuration, client_id, vgrid,
                                   persistence_id)


def update_workflow(configuration, client_id, workflow_type=WORKFLOW_PATTERN,
                    **kwargs):
    """ """
    _logger = configuration.logger
    vgrid = kwargs.get('vgrid', None)
    if not vgrid:
        msg = "A workflow update dependency was missing: 'vgrid'"
        _logger.error("update_workflow: 'vgrid' was not set: '%s'" % vgrid)
        return (False, msg)

    persistence_id = kwargs.get('persistence_id', None)
    if not persistence_id:
        msg = "Missing 'persistence_id' must be provided to update " \
              "a workflow object."
        return (False, msg)

    if workflow_type == WORKFLOW_RECIPE:
        return __update_workflow_recipe(configuration, client_id, vgrid,
                                        kwargs)

    return __update_workflow_pattern(configuration, client_id, vgrid,
                                     kwargs)


def delete_workflow_pattern(configuration, client_id, vgrid, persistence_id):
    """Delete a workflow pattern"""

    _logger = configuration.logger
    _logger.debug("WP: delete_workflow_pattern, client_id: %s, "
                  "persistence_id: %s" % (client_id, persistence_id))

    workflow = get_workflow_with(configuration, client_id=client_id,first=True,
                                 vgrid=vgrid, persistence_id=persistence_id)
    workflow_path = os.path.join(
        get_workflow_pattern_home(configuration, vgrid), persistence_id)

    if not workflow:
        msg = "A pattern with persistence_id: '%s' was not found " \
              % persistence_id
        _logger.error("WR: delete_workflow_pattern: '%s' wasn't found"
                      % persistence_id)
        # Ensure that that the persistence file dosen't stay around
        if os.path.exists(workflow_path):
            _logger.error("WR: delete_workflow_pattern: '%s' is gone but '%s'"
                          " still exist" % (persistence_id, workflow_path))
            if not delete_file(workflow_path, _logger):
                msg = "Internal deletion of '%s' failed" % persistence_id
                return (False, msg)
        return (False, msg)

    if workflow['trigger']:
        __rule_deletion_from_pattern(configuration, client_id, vgrid, workflow)

    if os.path.exists(workflow_path) and not delete_file(workflow_path,
                                                         _logger):
            msg = "Could not delete the pattern: '%s'" % persistence_id
            return (False, msg)

    mark_workflow_p_modified(configuration, persistence_id)
    return (True, 'Deleted pattern %s.' % workflow['persistence_id'])


def delete_workflow_recipe(configuration, client_id, vgrid, persistence_id):
    """Delete a workflow recipe"""
    _logger = configuration.logger
    _logger.debug("WR: delete_workflow_recipe:, client_id: %s, "
                  "persistence_id: %s" % (client_id, persistence_id))

    workflow = get_workflow_with(configuration, client_id,
                                 workflow_type=WORKFLOW_RECIPE,
                                 first=True,
                                 vgrid=vgrid, persistence_id=persistence_id)
    workflow_path = os.path.join(get_workflow_recipe_home(configuration, vgrid)
                                 , persistence_id)
    if not workflow:
        msg = "A recipe with persistence_id: '%s' was not found " \
              % persistence_id
        _logger.error("WR: delete_workflow_recipe: '%s' wasn't found"
                      % persistence_id)
        # Ensure that that the persistence file dosen't stay around
        if os.path.exists(workflow_path):
            _logger.error("WR: delete_workflow_recipe: '%s' is gone but '%s'"
                          " still exist" % (persistence_id, workflow_path))
            if not delete_file(workflow_path, _logger):
                msg = "Internal deletion of '%s' failed" % persistence_id
                return (False, msg)
        return (False, msg)

    if workflow['triggers']:
        __rule_deletion_from_recipe(configuration, client_id, vgrid,
                                    workflow)

    if os.path.exists(workflow_path):
        if not delete_file(workflow_path, _logger):
            msg = "Could not delete the recipe: '%s'" % persistence_id
            return (False, msg)

    mark_workflow_r_modified(configuration, persistence_id)
    return (True, "Deleted recipe '%s'." % workflow['persistence_id'])


def __create_workflow_pattern_entry(configuration, client_id, vgrid, wp):
    """ Creates a workflow pattern based on the passed wp object.
    Requires the following keys and structure:

    pattern = {
        'owner': client_id,
        'input_file': input_str,
        'trigger_paths': trigger_list
        'output': output_dict,
        'recipes': recipes_list,
        'variables': variables_dict,
        'vgrid': vgrid_str
    }

    The 'owner' key is required to be non-empty string.
    If a 'name' is not provided a random one will be generated.
    Every additional key should follow the defined types structure,
    if any of these is left out a default empty structure will be defined.

    Additional keys/data are allowed and will be saved
    with the required information.
    """
    _logger = configuration.logger
    _logger.debug("WP: __create_workflow_pattern_entry, client_id: %s, wp: %s"
                  % (client_id, wp))

    if not isinstance(wp, dict):
        _logger.error("WP: __create_workflow_pattern_entry, incorrect 'wp' "
                      "structure '%s'" % type(wp))
        return (False, "Internal server error due to incorrect pattern "
                       "structure")

    for key, value in wp.items():
        if key not in VALID_USER_PATTERN:
            return (False, "key: '%s' is not allowed, valid includes '%s'" %
                    (key, ', '.join(VALID_USER_PATTERN.keys())))
        if not isinstance(value, VALID_USER_PATTERN.get(key)):
            return (False, "value: '%s' has an incorrect type: '%s', "
                           "requires: '%s'" % (value, type(value),
                                               VALID_USER_PATTERN.get(key)))

    persistence_id = generate_random_ascii(wp_id_length, charset=wr_id_charset)
    wp['object_type'] = WORKFLOW_PATTERN
    wp['persistence_id'] = persistence_id
    wp['owner'] = client_id
    wp['trigger'] = {}

    correct, msg = __correct_wp(configuration, wp)
    if not correct:
        return (correct, msg)

    wp_home = get_workflow_pattern_home(configuration, vgrid)
    if not os.path.exists(wp_home):
        if not makedirs_rec(wp_home, configuration):
            msg = "Couldn't create the required dependencies for " \
                  "your workflow pattern"
            return (False, msg)

    wp_file_path = os.path.join(wp_home, persistence_id)
    if os.path.exists(wp_file_path):
        _logger.error('WP: unique filename conflict: %s '
                      % wp_file_path)
        msg = 'A workflow pattern conflict was encountered, '
        'please try and resubmit the pattern'
        return (False, msg)

    # Save the pattern
    wrote = False
    msg = ''
    try:
        dump(wp, wp_file_path, serializer='json')

        # Mark as modified
        mark_workflow_p_modified(configuration, wp['persistence_id'])
        wrote = True
        _logger.debug("WP: new pattern created: '%s'." % wp['persistence_id'])
    except Exception, err:
        _logger.error(
            "WP: failed to write: '%s' to disk: '%s'" % (wp_file_path, err))
        msg = 'Failed to save your workflow pattern, '
        'please try and resubmit it'

    if not wrote:
        # Ensure that the failed write does not stick around
        if not delete_file(wp_file_path, _logger):
            msg += '\n Failed to cleanup after a failed workflow creation'
        return (False, msg)

    status, identification_msg = __rule_identification_from_pattern(
        configuration, client_id, wp, True)

    if not status:
        return (False, "Could not identify rules from pattern. %s"
                % identification_msg)

    _logger.info('WP: %s created at: %s ' % (client_id, wp_file_path))
    return (True, '%s' % wp['persistence_id'])


def __create_workflow_recipe_entry(configuration, client_id, vgrid, wr):
    """Creates a workflow recipe based on the passed wr object.
        Requires the following keys and structure:

        wr = {
            'owner': 'lient_id_str,
            'recipe': recipe_dict,
            'vgrid': 'vgrid_str
        }

        The 'owner' key is required to be non-empty string.
        If a 'name' is not provided a random one will be generated.
    """
    _logger = configuration.logger
    _logger.debug("WR: __create_workflow_recipe_entry, client_id: %s, wr: %s"
                  % (client_id, wr))

    if not isinstance(wr, dict):
        _logger.error("WR: __create_workflow_recipe_entry, incorrect 'wr' "
                      "structure '%s'" % type(wr))
        return (False, "Internal server error due to incorrect recipe "
                       "structure")

    for key, value in wr.items():
        if key not in VALID_USER_RECIPE:
            return (False, "key: '%s' is not allowed, valid includes '%s'" %
                    (key, ', '.join(VALID_USER_RECIPE.keys())))
        if not isinstance(value, VALID_USER_RECIPE.get(key)):
            return (False, "value: '%s' has an incorrect type: '%s', "
                           "requires: '%s'" % (value, type(value),
                                               VALID_USER_RECIPE.get(key)))

    persistence_id = generate_random_ascii(wr_id_length, charset=wr_id_charset)
    wr['object_type'] = WORKFLOW_RECIPE
    wr['persistence_id'] = persistence_id
    wr['owner'] = client_id

    correct, msg = __correct_wr(configuration, wr)
    if not correct:
        return (False, msg)

    # Verify that the recipe name is unique
    # Need this to ensure reasonable user friendliness of connecting recipes
    # to patterns via it's Pattern.recipes list
    existing_recipe = get_workflow_with(configuration,
                                        workflow_type=WORKFLOW_RECIPE,
                                        vgrid=vgrid, name=wr['name'])
    if existing_recipe:
        return (False, "An existing recipe in vgrid '%s'"
                       " already exist with name '%s'" % (vgrid, wr['name']))

    wr_home = get_workflow_recipe_home(configuration, vgrid)
    if not os.path.exists(wr_home):
        if not makedirs_rec(wr_home, configuration):
            msg = "Couldn't create the required dependencies for " \
                  "your workflow recipe"
            return (False, msg)

    wr_file_path = os.path.join(wr_home, persistence_id)
    if os.path.exists(wr_file_path):
        _logger.error('WR: unique filename conflict: %s '
                      % wr_file_path)
        msg = 'A workflow recipe conflict was encountered, '
        'please try and resubmit the recipe'
        return (False, msg)

    wrote = False
    msg = ''
    try:
        dump(wr, wr_file_path, serializer='json')

        # Mark as modified
        mark_workflow_r_modified(configuration, wr['persistence_id'])
        wrote = True
    except Exception, err:
        _logger.error('WR: failed to write %s to disk %s'
                      % (wr_file_path, err))
        msg = 'Failed to save your workflow recipe, '
        'please try and resubmit it'

    if not wrote:
        # Ensure that the failed write does not stick around
        if not delete_file(wr_file_path, _logger):
            msg += '\n Failed to cleanup after a failed workflow creation'
        return (False, msg)

    _logger.info('WR: %s created at: %s ' %
                 (client_id, wr_file_path))

    status, identification_msg = __rule_identification_from_recipe(
        configuration, client_id, wr, True)

    if not status:
        return (False, "Could not identify rules from recipe. %s"
                % identification_msg)

    return (True, "%s" % wr['persistence_id'])


def __update_workflow_pattern(configuration, client_id, vgrid, wp):
    """Updates an already registered pattern with new variables. Only the
    variables to be updated are passed to the function
       """
    _logger = configuration.logger
    _logger.debug("WP: __update_workflow_pattern, client_id: %s, pattern: %s"
                  % (client_id, wp))

    if not isinstance(wp, dict):
        _logger.error("WR: __update_workflow_pattern, incorrect 'wp' "
                      "structure '%s'" % type(wp))
        return (False, "Internal server error due to incorrect pattern "
                       "structure")

    for key, value in wp.items():
        if key not in VALID_USER_UPDATE_PATTERN:
            return (False, "key: '%s' is not allowed, valid includes '%s'" %
                    (key, ', '.join(VALID_USER_UPDATE_PATTERN.keys())))
        if not isinstance(value, VALID_USER_UPDATE_PATTERN.get(key)):
            return (False, "value: '%s' has an incorrect type: '%s', "
                           "requires: '%s'" % (
                        value, type(value), VALID_USER_UPDATE_PATTERN.get(key)))

    persistence_id = wp.get('persistence_id', None)
    if not persistence_id:
        msg = "Missing 'persistence_id' must be provided to update " \
              "a workflow object."
        return (False, msg)

    pattern = get_workflow_with(configuration,
                                client_id,
                                first=True,
                                workflow_type=WORKFLOW_PATTERN,
                                persistence_id=wp['persistence_id'],
                                vgrid=vgrid)

    if not pattern:
        msg = 'Could not locate pattern'
        _logger.debug(msg)
        return (False, msg)
    _logger.debug("WP: __update_workflow_pattern, found pattern %s to update"
                  % pattern)

    if 'trigger' in pattern:
        _logger.debug("WP: __update_workflow_pattern, prexisting trigger %s" % pattern['trigger'])
        preexisting_trigger = pattern['trigger']
    else:
        preexisting_trigger = {}

    # don't update if the pattern is the same
    # TODO, also don't allow say update of persistence_id, owner
    to_edit = False
    for variable in wp.keys():
        if pattern[variable] != wp[variable]:
            to_edit = True
    if not to_edit:
        _logger.debug("Don't need to edit")
        return (False, 'Did not update pattern %s as contents '
                       'are identical. ' % pattern['name'])

    _logger.debug('update_workflow_pattern, got pattern: %s' % pattern)
    _logger.debug('update_workflow_pattern, applying variables: %s' % wp)

    for variable in wp.keys():
        pattern[variable] = wp[variable]

    _logger.debug('update_workflow_pattern, resulting pattern: %s' % pattern)

    correct, msg = __correct_wp(configuration, pattern)
    if not correct:
        _logger.debug('update_workflow_pattern, is no longer a correct pattern')
        return (False, msg)

    wp_home = get_workflow_pattern_home(configuration, vgrid)
    wp_file_path = os.path.join(wp_home, pattern['persistence_id'])

    # Save the pattern
    wrote = False
    msg = ''
    try:
        _logger.debug('update_workflow_pattern, attempting to dump')
        dump(pattern, wp_file_path, serializer='json')

        # Mark as modified
        mark_workflow_p_modified(configuration, pattern['persistence_id'])
        wrote = True
        _logger.debug('marking editted pattern %s as modified'
                      % pattern['persistence_id'])
    except Exception, err:
        _logger.error('WP: failed to write %s to disk %s' % (
            wp_file_path, err))
        msg = 'Failed to save your workflow pattern, '
        'please try and resubmit it'

    # This will want changed, we don't want to delete a working recipe just
    # because we can't updated it
    if not wrote:
        # Ensure that the failed write does not stick around
        if not delete_file(wp_file_path, _logger):
            msg += '\n Failed to cleanup after a failed workflow creation'
        return (False, msg)

    # if there is a trigger then delete the old one and start a new one.
    if preexisting_trigger:
        if any([i in wp for i in UPDATE_TRIGGER_PATTERN]):
            _logger.debug('replacing old trigger')
            __rule_deletion_from_pattern(
                configuration, client_id, vgrid, pattern)
            __rule_identification_from_pattern(
                configuration, client_id, pattern, True)

    _logger.info('WP: %s updated at: %s ' % (client_id, wp_file_path))
    return (True, 'Updated pattern %s. ' % pattern['persistence_id'])


def __update_workflow_recipe(configuration, client_id, vgrid, wr):
    """Updates an already registered recipe with new variables. Only the
    variables to be updated are passed to the function
       """

    _logger = configuration.logger
    _logger.debug("WR: update_workflow_recipe, client_id: %s, recipe: %s"
                  % (client_id, wr))

    if not isinstance(wr, dict):
        _logger.error("WR: __update_workflow_recipe, incorrect 'wr' "
                      "structure '%s'" % type(wr))
        return (False, "Internal server error due to incorrect recipe "
                       "structure")

    for key, value in wr.items():
        if key not in VALID_USER_UPDATE_RECIPE:
            return (False, "key: '%s' is not allowed, valid includes '%s'" %
                    (key, ', '.join(VALID_USER_UPDATE_RECIPE.keys())))
        if not isinstance(value, VALID_USER_UPDATE_RECIPE.get(key)):
            return (False, "value: '%s' has an incorrect type: '%s', "
                           "requires: '%s'" % (
                        value, type(value), VALID_USER_UPDATE_RECIPE.get(key)))

    persistence_id = wr.get('persistence_id', None)
    if not persistence_id:
        msg = "Missing 'persistence_id' must be provided to update " \
              "a workflow object."
        return (False, msg)

    recipe = get_workflow_with(configuration,
                               client_id,
                               first=True,
                               workflow_type=WORKFLOW_RECIPE,
                               persistence_id=wr['persistence_id'],
                               vgrid=vgrid)

    for variable in wr.keys():
        recipe[variable] = wr[variable]

    correct, msg = __correct_wr(configuration, recipe)
    if not correct:
        return (correct, msg)

    wr_home = get_workflow_recipe_home(configuration, vgrid)
    wr_file_path = os.path.join(wr_home, recipe['persistence_id'])
    wrote = False

    msg = ''
    try:
        dump(recipe, wr_file_path, serializer='json')

        # Mark as modified
        mark_workflow_r_modified(configuration, recipe['persistence_id'])
        wrote = True
    except Exception, err:
        _logger.error('WR: failed to write %s to disk %s' % (
            wr_file_path, err))
        msg = "Failed to save your workflow recipe, "
        "please try and resubmit it"

    # This will want changed, we don't want to delete a working recipe just
    # because we can't update it
    if not wrote:
        # Ensure that the failed write does not stick around
        if not delete_file(wr_file_path, _logger):
            msg += "\n Failed to cleanup after a failed workflow update"
        return (False, msg)

    # if there is a trigger then delete the old one and start a new one.
    if recipe['triggers']:
        if any([i in wr for i in UPDATE_TRIGGER_RECIPE]):
            __rule_deletion_from_recipe(
                configuration, client_id, vgrid, recipe)
            __rule_identification_from_recipe(
                configuration, client_id, recipe, True)

    _logger.info('WR: %s updated at: %s ' %
                 (client_id, wr_file_path))
    return (True, "Updated recipe %s. " % recipe['persistence_id'])


def __rule_identification_from_pattern(configuration, client_id,
                                       workflow_pattern, apply_retroactive):
    """Identifies if a task can be created, given a stated pattern"""

    _logger = configuration.logger
    _logger.info("WP: looking for recipes to attach to the new pattern '%s'" %
                 workflow_pattern['persistence_id'])

    # Currently multiple recipes are crudely chained together. This will need
    # to be altered once we move into other languages than python.
    missed_recipes = []
    recipe_list = []
    vgrid = workflow_pattern['vgrid']
    # Check if defined recipes exist already within system
    # Preload all recipes
    recipes = get_workflow_with(configuration, vgrid=vgrid,
                                workflow_type=WORKFLOW_RECIPE)

    if not recipes:
        return (True, "Vgrid '%s' has no existing recipes that "
                      "can be attached to pattern: '%s'" % (
            vgrid, workflow_pattern['persistence_id']))

    # If any recipes exist in that vgrid
    for recipe_name in workflow_pattern['recipes']:
        _logger.info("looking for recipe: %s" % recipe_name)
        recipe_list.extend([recipe for recipe in recipes
                       if recipe['name'] == recipe_name])

        if recipe_name not in recipe_list:
            missed_recipes.append(recipe_name)

    if not recipe_list:
        return (True, "No recipes found that matches pattern: '%s'"
                      " specified recipes: '%s'" % (
            workflow_pattern['persistence_id'], workflow_pattern['recipes']))

    if missed_recipes:
        return (True, "Could not find all required recipes. Missing: 's'"
                % missed_recipes)

    if recipe_list:
        (trigger_status, trigger_msg) = create_trigger(
            configuration, _logger, vgrid, client_id, workflow_pattern,
            recipe_list, apply_retroactive)

        if not trigger_status:
            return False, "Could not create trigger: '%s' for pattern: '%s'" %\
            (trigger_msg, workflow_pattern['persistence_id'])
        return True, "Trigger created from pattern: '%s'. " % \
               workflow_pattern['persistence_id']


def __rule_identification_from_recipe(configuration, client_id,
                                      workflow_recipe, apply_retroactive):
    """Identifies if a task can be created, given a stated recipe"""

    _logger = configuration.logger
    _logger.info('%s is identifying any possible tasks from recipe creation '
                '%s' % (client_id, workflow_recipe['persistence_id']))
    vgrid = workflow_recipe['vgrid']
    matching_patterns = []
    # Get all patterns within the vgrid
    patterns = get_workflow_with(configuration, vgrid=vgrid)

    # Check if patterns exist already within system that need this recipe
    if not patterns:
        return (True, "Vgrid '%s' has no existing patterns that "
                      "could contain recipe: '%s'" % (
                        vgrid, workflow_recipe['name']))
    for pattern in patterns:
        if workflow_recipe['name'] in pattern['recipes']:
            matching_patterns.append(pattern)

    activatable_patterns = []
    incomplete_patterns = []
    # now check all matching patterns have all their recipes
    # Preload all recipes
    recipes = get_workflow_with(configuration, vgrid=vgrid)
    for pattern in matching_patterns:
        # Currently multiple recipes are crudely chained together. This will
        # need to be altered eventually.
        recipe_list = []
        missed_recipes = []
        # Check if defined recipes exist already within system
        for recipe_name in pattern['recipes']:
            recipe_list = [recipe for recipe in recipes
                           if recipe['name'] == recipe_name]
            if recipe_name not in recipe_list:
                missed_recipes.append(recipe_name)
        if not missed_recipes:
            _logger.info(
                'All recipes found within trying to create trigger for recipe '
                + pattern['name'] + ' and inputs at '
                + str(pattern['trigger_paths']))

            (trigger_status, trigger_msg) = create_trigger(
                configuration, _logger, vgrid, client_id, pattern, recipe_list,
                apply_retroactive)

            if not trigger_status:
                incomplete_patterns.append(pattern['name'])
            else:
                activatable_patterns.append(pattern['name'])

    msg = " %d trigger(s) created from recipe %s. " \
          % (len(activatable_patterns), workflow_recipe['name'])
    if len(incomplete_patterns) > 0:
        msg += " There are %d additional patterns(s) recipes that use this " \
               "recipe, but are waiting for additional recipes before " \
               "activation" % len(incomplete_patterns)
    return True, msg


def __rule_deletion_from_pattern(configuration, client_id, vgrid, wp):
    """Given a stated pattern is to be deleted, deletes any jobs from the
    queue and updates any recipes accordingly"""

    _logger = configuration.logger

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
                    delete_trigger(
                        configuration, client_id, vgrid_name, trigger_id)
                break

        # delete the reference to the trigger for these recipes
        for recipe_id in recipe_list:
            recipe = get_wr_with(
                configuration, client_id=client_id, persistence_id=recipe_id,
                vgrid=vgrid)
            new_recipe_variables = {
                'triggers': recipe['triggers']
            }
            new_recipe_variables['triggers'].pop(
                str(vgrid_name + trigger_id), None)

            new_recipe_variables['persistence_id'] = recipe['persistence_id']
            __update_workflow_recipe(
                configuration, client_id, vgrid, new_recipe_variables)


def __rule_deletion_from_recipe(configuration, client_id, vgrid, wr):
    """Given a stated recipe is to be deleted, deletes any jobs from the
        queue and updates any patterns accordingly"""

    _logger = configuration.logger

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
                        wp = {'persistence_id': trigger['pattern'],
                              'trigger': {}}
                        __update_workflow_pattern(configuration, client_id,
                                                  vgrid, wp)

                    if 'recipes' in trigger.keys():
                        recipe_list = trigger['recipes']
                        delete_trigger(
                            configuration, client_id, vgrid_name, trigger_id)
                    break

            # delete the reference to the trigger for these recipes
            for recipe_name in recipe_list:
                recipe = get_wr_with(
                    configuration, client_id=client_id,
                    persistence_id=recipe_name, vgrid=vgrid)
                new_recipe_variables = {
                    'triggers': recipe['triggers']
                }
                new_recipe_variables['triggers'].pop(
                    str(vgrid_name + trigger_id), None)
                new_recipe_variables['persistence_id'] = recipe['persistence_id']
                __update_workflow_recipe(
                    configuration, client_id, vgrid, new_recipe_variables)


def reset_user_workflows(configuration, client_id):
    _logger = configuration.logger

    workflows = get_workflow_with(configuration, client_id,
                                  workflow_type=WORKFLOW_ANY)
    _logger.debug("Resetting user: '%s' workflows, current: '%s'" %
                  (client_id, workflows))
    # No workflows for user, nothing to reset
    if not workflows:
        return True

    for workflow in workflows:
        if not delete_workflow(configuration, client_id,
                               workflow['object_type'], **workflow):
            return False
    return True


def reset_vgrid_workflows(configuration, vgrid):
    _logger = configuration.logger

    workflows = get_workflow_with(configuration, workflow_type=WORKFLOW_ANY,
                                  vgrid=vgrid)
    _logger.debug("Resetting vgrid: '%s' workflows, current: '%s'" %
                  (vgrid, workflows))
    if not workflows:
        return True

    for workflow in workflows:
        if not delete_workflow(configuration, workflow['owner'],
                               workflow['object_type'], **workflow):
            return False
    return True


def create_workflow_task_file(configuration, client_id, vgrid, notebook,
                              variables):
    # If we don't want users to combine recipes, then remove this
    # functionality as it is just replication of data for no reason
    """Creates a task file. This is the actual notebook to be run on the
    resource. A new notebook is required as users can potentially combine
    multiple notebooks into one super notebook, and may in future define
    recipes not within notebooks."""

    _logger = configuration.logger

    task_home = get_workflow_task_home(configuration, vgrid)
    if not os.path.exists(task_home):
        if not makedirs_rec(task_home, configuration):
            msg = "Couldn't create the required dependencies for " \
                  "your workflow task"
            return False, msg

    # TODO improve this
    # placeholder for unique name generation.
    file_name = generate_random_ascii(
        wr_id_length, charset=wr_id_charset) + ".ipynb"
    task_file_path = os.path.join(task_home, file_name)
    while os.path.exists(task_file_path):
        file_name = generate_random_ascii(wr_id_length, charset=wr_id_charset)
        task_file_path = os.path.join(task_home, file_name)
    notebook_json = dumps(notebook, serializer='json')
    wrote = write_file(notebook_json, task_file_path, _logger,
                       make_parent=False)

    if not wrote:
        msg = "Failed to create task file. "
        # Ensure that the failed write does not stick around
        if not delete_file(task_file_path, _logger):
            msg += "Failed to cleanup after a failed workflow creation"
        return False, msg

    _logger.info('WT: %s created at: %s ' % (client_id, task_file_path))
    return True, task_file_path


def create_workflow_buffer_file(configuration, client_id, vgrid,
                                trigger_paths, apply_retroactive):
    """Creates a hdf5 buffer file. This is used to combine data inputs from
    several hdf5 files into one buffered file that can be sent to a job as a
    single input."""

    _logger = configuration.logger

    _logger.debug("Creating buffer file. client_id: %s, vgrid: %s, "
                  "trigger_paths: %s, apply_retroactive: %s"
                  % (client_id, vgrid, trigger_paths, apply_retroactive))

    buffer_home = get_workflow_buffer_home(configuration, vgrid)
    if not os.path.exists(buffer_home):
        if not makedirs_rec(buffer_home, configuration):
            msg = "Couldn't create the required dependencies for " \
                  "your workflow task"
            return False, msg

    # TODO improve this
    # placeholder for unique name generation.
    file_name = generate_random_ascii(
        wr_id_length, charset=wr_id_charset) + ".hdf5"

    buffer_file_path = os.path.join(buffer_home, file_name)
    while os.path.exists(buffer_file_path):
        file_name = generate_random_ascii(wr_id_length, charset=wr_id_charset)
        buffer_file_path = os.path.join(buffer_home, file_name)

    _logger.debug("Creating buffer file called %s" % file_name)

    wrote = False
    try:
        with h5py.File(buffer_file_path, 'w') as h5_buffer_file:
            _logger.debug("Creating h5py file")
            for path in trigger_paths:
                _logger.debug("Addressing path: %s" % path)
                h5_buffer_file.create_group(path)
                h5_buffer_file.get(path).attrs[BUFFER_FLAG] = 0
                if apply_retroactive:
                    file_path = os.path.join(
                        configuration.vgrid_files_home, vgrid, path)
                    _logger.debug("file_path: %s" % file_path)
                    file_extension = file_path[file_path.rfind('.'):]
                    _logger.debug("file_extension: %s" % file_extension)

                    if os.path.isfile(file_path) and file_extension == '.hdf5':
                        _logger.debug("file %s is present and correct"
                                      % file_path)
                        with h5py.File(file_path, 'r') as h5_data_file:
                            _logger.debug("Opened %s, which has keys: %s"
                                  % (file_path, h5_data_file.keys()))
                            for data_key in h5_data_file.keys():
                                _logger.debug("Copying: %s" % data_key)
                                h5_buffer_file.copy(
                                    h5_data_file[data_key],
                                    path + "/" + data_key)

        wrote = True
    except Exception, err:
        _logger.error('WB: failed to write %s to disk %s'
                      % (buffer_file_path, err))
        msg = 'Failed to save your workflow buffer file, please try and ' \
              'resubmit it. '

    if not wrote:
        # Ensure that the failed write does not stick around
        if not delete_file(buffer_file_path, _logger):
            msg += 'Failed to cleanup after a failed workflow creation. '
        return False, msg

    _logger.info('WB: %s created at: %s ' %
                 (client_id, buffer_file_path))
    return True, buffer_file_path


def delete_trigger(configuration, client_id, vgrid_name, trigger_id):
    """Deletes a trigger and any jobs currently queued that were scheduled by
    this trigger"""

    _logger = configuration.logger
    # FIXME, Do string interpolation instead of concatenation
    _logger.info('delete_trigger client_id: ' + client_id + ' vgrid_name: '
                 + vgrid_name + ' trigger_id: ' + trigger_id)

    (got_triggers, all_triggers) = vgrid_triggers(vgrid_name, configuration)

    if not got_triggers:
        _logger.debug('Could not load triggers')

    trigger_to_delete = None
    for trigger in all_triggers:
        if trigger['rule_id'] == trigger_id:
            trigger_to_delete = trigger

    if trigger_to_delete:
        task_file = trigger_to_delete['task_file']
        mrsl_dir = configuration.mrsl_files_dir
        matching_jobs = get_job_ids_with_task_file_in_contents(
            client_id, task_file, mrsl_dir, _logger)

        new_state = 'CANCELED'
        client_dir = client_id_dir(client_id)
        for job_id in matching_jobs:
            file_path = os.path.join(
                configuration.mrsl_files_dir, client_dir, job_id + '.mRSL')
            job = unpickle(file_path, _logger)

            if not job:
                _logger.error('Could not open job file')
                continue

            possible_cancel_states = ['PARSE', 'QUEUED', 'RETRY', 'EXECUTING',
                                      'FROZEN']

            if not job['STATUS'] in possible_cancel_states:
                _logger.error('Could not cancel job with status '
                              + job['STATUS'])
                continue

            if not unpickle_and_change_status(file_path, new_state, _logger):
                _logger.error('%s could not cancel job: %s'
                              % (client_id, job_id))

            if not job.has_key('UNIQUE_RESOURCE_NAME'):
                job['UNIQUE_RESOURCE_NAME'] = 'UNIQUE_RESOURCE_NAME_NOT_FOUND'
            if not job.has_key('EXE'):
                job['EXE'] = 'EXE_NAME_NOT_FOUND'

            message = 'JOBACTION ' + job_id + ' ' \
                      + job['STATUS'] + ' ' + new_state + ' ' \
                      + job['UNIQUE_RESOURCE_NAME'] + ' ' \
                      + job['EXE'] + '\n'
            if not send_message_to_grid_script(message, _logger,
                                               configuration):
                _logger.error('%s failed to send message to grid script: %s'
                              % (client_id, message))
    (rm_status, rm_msg) = vgrid_remove_triggers(
        configuration, vgrid_name, [trigger_id])
    if not rm_status:
        _logger.error('%s failed to remove trigger: %s' % (client_id, rm_msg))


def create_trigger(configuration, logger, vgrid, client_id, pattern,
                   recipe_list, apply_retroactive):
    """Start the process of creating a new MiG trigger. Determine if the
    presented pattern requires a single or multi input trigger and act
    accordingly"""

    if len(pattern['trigger_paths']) > 1:
        add_status, add_msg = create_multi_input_trigger(
            configuration, logger, vgrid, client_id, pattern, recipe_list,
            apply_retroactive)

    else:
        add_status, add_msg = create_single_input_trigger(
            configuration, logger, vgrid, client_id, pattern, recipe_list,
            apply_retroactive)

    return add_status, add_msg


# TODO move this to a buffer module
def get_buffer_paths(h5_file, root, paths):
    if BUFFER_FLAG in h5_file.attrs.keys():
        paths.append(str(root))
        if len(h5_file.keys() == 0):
            return

    for key in h5_file:
        # print('key: %s' % key)
        path = os.path.join(root, key)
        # print('path: %s' % path)
        get_buffer_paths(h5_file[key], path, paths)


def create_single_input_trigger(configuration, _logger, vgrid, client_id,
                                pattern, recipe_list, apply_retroactive):
    """Creates a single input trigger. This is the standard trigger for the
    system, with a single file triggering a job. A corresponding task file is
    created that will be used by any triggered jobs as the actual job code.

    If apply_retroactive, then the trigger will attempt to trigger jobs for
    any currently existing files that match the given pattern's trigger path"""

    cells = []
    recipe_ids = []
    for recipe in recipe_list:
        recipe_ids.append(recipe['persistence_id'])
        cells.extend(recipe['recipe']['cells'])

    # TODO, fix metadata hack of just using the last one
    # This field is required by papermill for it to parameterize the
    # notebook correctly
    _logger.info("WP: recipe_list %s before complete_notebook" % recipe_list)

    # TODO This is a horrible hack but I'm leaving in 10 mins so it'll do for
    #  now :p DO NOT DEPLOY THIS
    metadata_hack = {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "astra"
        },
        "language_info": {
            "codemirror_mode": {
                "name": "ipython",
                "version": 3
            },
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.6.7"
        }
    }
    complete_notebook = {
        "cells": cells,
        "metadata": metadata_hack,
        "nbformat": 4,
        "nbformat_minor": 2
    }

    (task_file_status, msg) = create_workflow_task_file(
        configuration, client_id, vgrid, complete_notebook,
        pattern['variables'])

    if not task_file_status:
        return False, msg

    task_path = msg.replace(configuration.vgrid_files_home, "")
    if task_path.startswith('/'):
        task_path = task_path[1:]

    output_files_string = ''
    for key, value in pattern['output'].items():
        if output_files_string != '':
            output_files_string += '\n'
        updated_value = value.replace('*', '+TRIGGERPREFIX+')
        updated_value = os.path.join(vgrid, updated_value)
        output_files_string += (key + ' ' + updated_value)

    input_file_name = pattern['input_file']
    input_file_path = pattern['trigger_paths'][0]

    execute_string = 'papermill %s %s' \
                     % (DEFAULT_JOB_FILE_INPUT, DEFAULT_JOB_FILE_OUTPUT)
    for variable, value in pattern['variables'].items():
        execute_string += ' -p %s %s' % (variable, value)
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
        # TODO, this is too low,
        # Possibly have to think of a better solution
        'CPUTIME': [
            "30"
        ],
        'RETRIES': [
            "0"
        ],
        'INPUTFILES': [
            "+TRIGGERPATH+ " + input_file_name
        ],
        'OUTPUTFILES': [
            output_files_string
        ],
        'EXECUTABLES': [
            task_path + " " + DEFAULT_JOB_FILE_INPUT
        ]
    }

    external_dict = get_keywords_dict(configuration)
    mrsl = fields_to_mrsl(configuration, arguments_dict, external_dict)
    # TODO replace with dict to mrsl as a string
    # this mrsl file is not the one used for actual job creation. Just used as
    # a simple way of getting mrsl formatted text for argument_string.
    try:
        (mrsl_filehandle, mrsl_real_path) = tempfile.mkstemp(text=True)
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
    # NOTE, for now set the settle_time to 1s
    # To avoid double schedulling of triggered create/modified
    # events on the same operation (E.g. copy a file into the dir)
    rule_dict = {
        'rule_id': trigger_id,
        'vgrid_name': vgrid,
        'changes': ['created', 'modified'],
        'run_as': client_id,
        'action': 'submit',
        # arguments doesn't seem to be necessary at all, at least when created
        # with this method
        'arguments': [],
        'path': input_file_path,
        'rate_limit': '',
        'settle_time': '1s',
        'match_files': True,
        'match_dirs': False,
        # possibly should be False instead. Investigate
        'match_recursive': True,
        'templates': [arguments_string],
        'pattern': pattern['persistence_id'],
        'recipes': recipe_ids,
        'task_file': task_path
    }

    (add_status, add_msg) = vgrid_add_triggers(
        configuration, vgrid, [rule_dict], update_id=None, rank=None)

    # TODO, switch to pattern.update({})
    new_pattern_variables = {
        'trigger': {
            'vgrid': vgrid,
            'trigger_id': trigger_id
        },
        'persistence_id': pattern['persistence_id']
    }

    __update_workflow_pattern(configuration, client_id,
                              vgrid, new_pattern_variables)

    for recipe in recipe_list:
        new_recipe_variables = {
            'triggers': recipe['triggers'],
            'persistence_id': recipe['persistence_id']
        }
        new_recipe_variables['triggers'][str(vgrid + trigger_id)] = {
            'vgrid': vgrid,
            'trigger_id': trigger_id
        }
        __update_workflow_recipe(
            configuration, client_id, vgrid, new_recipe_variables)

    # TODO investigate why things only update properly if we don't immediately
    #  refresh
    _logger.info("DELETE ME - getting maps")
    get_wp_map(configuration)
    get_wr_map(configuration)
    _logger.info("DELETE ME - refreshing maps")
    __refresh_map(configuration, WORKFLOW_PATTERN)
    __refresh_map(configuration, WORKFLOW_RECIPE)

    # probably do this somewhere else, but it'll do for now
    # check for pre-existing files that could trip the trigger
    vgrid_files_home = os.path.join(configuration.vgrid_files_home, vgrid)

    # if required, then apply retroactively to existing files
    if apply_retroactive:
        for root, dirs, files in os.walk(vgrid_files_home, topdown=False):
            for name in files:
                file_path = os.path.join(root, name)
                prefix = name
                if '.' in prefix:
                    prefix = prefix[:prefix.index('.')]
                regex_path = os.path.join(vgrid_files_home, input_file_path)

                if re.match(regex_path, file_path):
                    relative_path = file_path.replace(
                        configuration.vgrid_files_home, '')
                    buffer_home = get_workflow_buffer_home(
                        configuration, vgrid)

                    # If we have a buffer file, only schedule a job if its full
                    if re.match(buffer_home, file_path):
                        _logger.debug('is a buffer file')
                        with h5py.File(file_path, 'r') as buffer_file:

                            # TODO check this
                            buffer_paths = []
                            get_buffer_paths(buffer_file, '', buffer_paths)
                            _logger.debug('buffer_paths: %s' % buffer_paths)

                            for path in buffer_paths:
                                if len(buffer_file.get(path).keys()) == 0:
                                    _logger.debug('skipping new job creation '
                                                  'as buffer is not complete')
                                    return add_status, add_msg

                    file_arguments_dict = copy.deepcopy(arguments_dict)
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

                    mrsl = fields_to_mrsl(
                        configuration, file_arguments_dict, external_dict)
                    (file_handle, real_path) = tempfile.mkstemp(text=True)
                    os.write(file_handle, mrsl)
                    os.close(file_handle)
                    _logger.debug('applying rule retroactively to create new '
                                  'job for: ' + real_path)
                    new_job(real_path, client_id, configuration, False, True)
    return add_status, add_msg


def create_multi_input_trigger(configuration, _logger, vgrid, client_id,
                               pattern, recipe_list, apply_retroactive):
    """Creates a multi input trigger. A buffer file is created to combine all
    the pattern's trigger paths into a single file which can act as the input
    for a single input trigger."""

    (file_status, msg) = create_workflow_buffer_file(
        configuration, client_id, vgrid, pattern['trigger_paths'],
        apply_retroactive)

    vgrid_path = os.path.join(configuration.vgrid_files_home, vgrid)
    buffer_path = msg.replace(vgrid_path, "")
    if buffer_path.startswith('/'):
        buffer_path = buffer_path[1:]

    if not file_status:
        return (False, msg)

    pattern['trigger_paths'] = [buffer_path]

    add_status, add_msg = create_single_input_trigger(
        configuration, _logger, vgrid, client_id, pattern, recipe_list,
        apply_retroactive)

    # if not add_status:
    return (add_status, add_msg)


def import_notebook_as_recipe(configuration, client_id, vgrid, notebook, name):
    """Reads a provided notebook in as a recipe"""
    if '.ipynb' in name:
        name = name.replace('.ipynb', '')

    # TODO, feels like a contradition that you define the
    # recipe_dict with a 'recipe' key but

    recipe_dict = {
        'name': name,
        'recipe': notebook,
        'owner': client_id,
        'vgrid': vgrid
    }
    status, msg = define_recipe(
        configuration, client_id, vgrid, recipe_dict)

    if not status:
        return (False, msg)
    return (True, msg)


def scrape_for_workflow_objects(configuration, client_id, vgrid, notebook,
                                name):
    """Scrapes a given jupyter notebook for defined workflow patterns. If
    none are found then the notebook is assumed to be  a recipe and so is
    registered as such"""

    _logger = configuration.logger
    _logger.debug("scrape_for_workflow_objects, client_id: %s, notebook: %s"
                  % (client_id, notebook))

    if not client_id:
        msg = "A workflow creation dependency was missing"
        _logger.error("scrape_for_workflow_object, client_id was not set %s"
                      % client_id)
        return (False, msg)

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
        # HACK, Don't do this, eventhough it's executed as
        # the mig user and not root
        # It still has a ton of permissions.
        # It's okay for the job engine to execute 'code' since it
        # is sandboxed in terms of
        # syscall it can make
        # Also in general we should never use exec() unless there is
        # no other way
        # And we have complete control over what 'code' will be
        exec(code)

        new_variables = dir()
        for item in starting_variables:
            if item in new_variables:
                new_variables.remove(item)
        new_variables.remove('starting_variables')

        for variable_name in new_variables:
            variable = locals()[variable_name]
            _logger.debug("looking at variable: %s of type %s"
                          % (variable, type(variable)))

            # python 3
            # if type(variable) == Pattern:
            #     pattern_count += 1
            #
            #     pattern_dict = {
            #         'name': variable.name,
            #         'input_file': variable.input_file,
            #         'trigger_paths': variable.trigger_paths,
            #         'recipes': variable.recipes,
            #         'vgrid': vgrid,
            #         'owner': client_id,
            #         'output': variable.outputs,
            #         'variables': variable.variables
            #     }
            #     status, msg = define_pattern(configuration, client_id, vgrid,
            #                                  pattern_dict)
            #
            #     if not status:
            #         return (False, msg)
            #     feedback += "\n%s" % msg

            # python 2
            if isinstance(variable, Pattern):
                _logger.debug("Found a pattern whilst scraping: %s"
                              % variable_name)

                pattern_count += 1

                pattern_dict = {
                    'name': variable.name,
                    'input_file': variable.input_file,
                    'trigger_paths': variable.trigger_paths,
                    'recipes': variable.recipes,
                    'vgrid': vgrid,
                    'owner': client_id,
                    'output': variable.outputs,
                    'variables': variable.variables
                }

                status, msg = define_pattern(
                    configuration, client_id, vgrid, pattern_dict)

                if not status:
                    return (False, msg)
                feedback += "\n%s" % msg

    except Exception as exception:
        _logger.error('Error encountered whilst running source: %s' % exception)

    if pattern_count == 0:
        _logger.debug('Found no patterns, notebook %s is being registered as '
                      'a recipe' % name)
        status, feedback = import_notebook_as_recipe(configuration, client_id,
                                                     vgrid, notebook, name)
        if status:
            recipe_count += 1

    count_msg = "%d patterns and %d recipes were found. " % \
                (pattern_count, recipe_count)
    _logger.debug('Scraping complete. ')

    return (True, "%s\n%s" % (feedback, count_msg))


def define_pattern(configuration, client_id, vgrid, pattern):
    """Defines a workflow pattern. First this creates a pattern entry, then
    any triggers are identified"""

    _logger = configuration.logger
    _logger.debug("WP: define_pattern, client_id: %s, pattern: %s"
                  % (client_id, pattern))

    if not client_id:
        msg = "A workflow pattern create dependency was missing"
        _logger.error("client_id was not set %s" % client_id)
        return (False, msg)

    if 'owner' not in pattern:
        pattern['owner'] = client_id

    if 'object_type' not in pattern:
        pattern['object_type'] = WORKFLOW_PATTERN

    correct, msg = __correct_wp(configuration, pattern)
    if not correct:
        return (correct, msg)

    if 'name' not in pattern:
        pattern['name'] = generate_random_ascii(
            wp_id_length, charset=wp_id_charset)
    else:
        existing_pattern = get_wp_with(
            configuration, client_id=client_id, name=pattern['name'],
            vgrid=vgrid)
        if existing_pattern:
            pattern['persistence_id'] = existing_pattern['persistence_id']
            # TODO, Why do you need to update a pattern you just extracted
            status, msg = __update_workflow_pattern(
                configuration, client_id, vgrid, pattern)
            return (True, msg)

    # TODO apply this to pattern as well
    # need to still check variables as they might not match exactly
    clients_patterns = get_wp_with(
        configuration, client_id=client_id, first=False, owner=client_id,
        trigger_paths=pattern['trigger_paths'], output=pattern['output'],
        vgrid=pattern['vgrid'])

    _logger.debug('clients_patterns: %s' % clients_patterns)
    _logger.debug('pattern: %s' % pattern)

    # TODO, rework this
    for client_pattern in clients_patterns:
        pattern_matches = True
        try:
            if client_pattern['input_file'] != pattern['input_file']:
                pattern_matches = False
            if client_pattern['trigger_paths'] != pattern['trigger_paths']:
                pattern_matches = False
            if client_pattern['outputs'] != pattern['outputs']:
                pattern_matches = False
            if client_pattern['recipes'] != pattern['recipes']:
                pattern_matches = False
            if client_pattern['variables'] != pattern['variables']:
                pattern_matches = False
        except KeyError:
            pattern_matches = False
        if pattern_matches:
            _logger.error('An identical pattern already exists')
            msg = "You already have a workflow pattern with identical " \
                  "characteristics to %s" % pattern['name']
            return (False, msg)
        else:
            _logger.debug('patterns are not identical')

    status, creation_msg = __create_workflow_pattern_entry(
        configuration, client_id, vgrid, pattern)

    if not status:
        return (False, "Could not create workflow pattern. %s" % creation_msg)

    status, identification_msg = __rule_identification_from_pattern(
        configuration, client_id, pattern, True)

    if not status:
        return (False, "Could not identify rules from pattern. %s"
                % identification_msg)

    return (True, "%s%s" % (creation_msg, identification_msg))


def define_recipe(configuration, client_id, vgrid, recipe):
    """Defines a workflow recipe. First this creates a recipe entry, then
        any triggers are identified"""

    _logger = configuration.logger
    _logger.debug('WR: define_recipe, client_id: %s, recipe: %s'
                  % (client_id, recipe))

    if not client_id:
        msg = "A workflow recipe creation dependency was missing"
        _logger.error('client_id was not set %s' % client_id)
        return (False, msg)

    if 'owner' not in recipe:
        recipe['owner'] = client_id

    if 'object_type' not in recipe:
        recipe['object_type'] = WORKFLOW_RECIPE

    correct, msg = __correct_wr(configuration, recipe)
    if not correct:
        return correct, msg

    if 'name' not in recipe:
        recipe['name'] = generate_random_ascii(
            wr_id_length, charset=wr_id_charset)
    else:
        existing_recipe = get_wr_with(
            configuration, client_id=client_id, name=recipe['name'],
            vgrid=vgrid)
        if existing_recipe:
            recipe['persistence_id'] = existing_recipe['persistence_id']
            status, msg = __update_workflow_recipe(
                configuration, client_id, vgrid, recipe)

            return True, msg

    status, creation_msg = __create_workflow_recipe_entry(
        configuration, client_id, vgrid, recipe)

    if not status:
        return (False, "Could not create workflow recipe. %s" % creation_msg)

    status, identification_msg = __rule_identification_from_recipe(
        configuration, client_id, recipe, True)

    if not status:
        return (False, "Could not identify rules from recipe. %s"
                % identification_msg)

    return (True, "%s%s" % (creation_msg, identification_msg))


def valid_session_id(configuration, workflow_session_id):
    """Validates that the workflow_session_id id is of the
    correct structure"""
    _logger = configuration.logger
    if not workflow_session_id:
        return False

    _logger.debug('WP: valid_session_id, checking %s'
                  % workflow_session_id)
    return possible_workflow_session_id(configuration, workflow_session_id)


if __name__ == '__main__':
    conf = get_configuration_object()
    args = sys.argv[1:]
    if args:
        if args[0] == 'create_workflow_session_id':
            touch_workflow_sessions_db(conf)
            client_id = "/C=dk/ST=dk/L=NA/O=org/OU=NA/CN=" \
                        "devuser/emailAddress=dev@dev.dk"
            if not get_workflow_session_id(conf, client_id):
                create_workflow_session_id(conf, client_id)
        if args[0] == 'workflow_sessions':
            sessions_db = load_workflow_sessions_db(conf)
            print(sessions_db)
        if args[0] == 'delete_workflow_sessions':
            delete_workflow_sessions_db(conf)
