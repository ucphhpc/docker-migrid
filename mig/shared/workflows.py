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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
# -- END_HEADER ---
#

"""Workflow functions"""

import fcntl
import json
import os
import time

from shared.base import client_id_dir
from shared.map import load_system_map
from shared.modified import check_workflow_p_modified, \
    reset_workflow_p_modified, mark_workflow_p_modified
from shared.pwhash import generate_random_ascii
from shared.defaults import wp_id_charset, wp_id_length
from shared.serial import dump

WRITE_LOCK = 'write.lock'
WORKFLOW_PATTERNS, MODTIME, CONF = ['__workflowpatterns__', '__modtime__',
                                    '__conf__']
MAP_CACHE_SECONDS = 60

last_load = {WORKFLOW_PATTERNS: 0}
last_refresh = {WORKFLOW_PATTERNS: 0}
last_map = {WORKFLOW_PATTERNS: {}}


def __load_wp_map(configuration, do_lock=True):
    """Load map of workflow patterns. Uses a pickled
    dictionary for efficiency. Optional do_lock option is used to enable and
    disable locking during load.
    """
    _logger = configuration.logger
    # _logger.debug("WP: load_wp_map")
    return load_system_map(configuration, 'workflowpatterns', do_lock)


def __refresh_wp_map(configuration):
    """Refresh map of workflow patterns. Uses a pickled dictionary for
    efficiency. Only update map for workflow patterns that appeared or
    disappeared after last map save.
    NOTE: Save start time so that any concurrent updates get caught next time
    """
    _logger = configuration.logger
    # _logger.debug("WP: regresh_wp_map")

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
            wp_conf = get_wp_conf(configuration, os.path.join(wp_dir, wp_file))
            workflow_p_map[wp_file][CONF] = wp_conf
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
    # _logger.debug("WP: list_wps")

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
    _logger.debug("WP: query_map, user: %s, kwargs: %s" % (client_id,
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
    _logger.debug("WP: query_map_first, user: %s, kwargs: %s" % (client_id,
                                                                 kwargs))
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
    _logger.debug("WP: build_wp_object with kwargs: %s" % kwargs)
    if not isinstance(kwargs, dict):
        _logger.warning("WP: type provided was not a dict %s " % type(kwargs))
        return None

    wp_obj = {
        'object_type': 'workflowpattern',
        'name': kwargs.get('name', ''),
        'owner': kwargs.get('owner', ''),
        'type_filter': kwargs.get('type_filter', ''),
        'inputs': kwargs.get('inputs', ''),
        'output': kwargs.get('output', '')
    }
    return wp_obj


def get_wp_map(configuration):
    """Returns the current map of workflow patterns and
    their configurations. Caches the map for load prevention with
    repeated calls within short time span.
    """
    _logger = configuration.logger
    # _logger.debug("WP: get_wp_map")

    if last_load[WORKFLOW_PATTERNS] + MAP_CACHE_SECONDS > time.time():
        _logger.debug('WP: using map')
        return last_map[WORKFLOW_PATTERNS]
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


def get_wp_conf(configuration, wp_path):
    """Returns a dictionary containing the workflow pattern configuration"""
    _logger = configuration.logger
    # _logger.debug("WP: get_wp_conf")

    try:
        with open(wp_path, 'r') as _wp_path:
            wp_conf = json.load(_wp_path)
            return wp_conf
    except Exception, err:
        configuration.logger.error('WP: could not open workflow pattern %s %s' %
                                   (wp_path, err))
    return {}


def get_wp_with(configuration, first=True, client_id=None, **kwargs):
    """Returns a clients workflow pattern with a field_name"""
    _logger = configuration.logger
    # _logger.debug("WP: get_client_wp_with")
    if not isinstance(kwargs, dict):
        _logger.error('WP: wrong format supplied for %s', type(kwargs))
        return None
    if first:
        wp = __query_map_for_first(configuration, client_id, **kwargs)
    else:
        wp = __query_map_for(configuration, client_id, **kwargs)
    return wp


# TODO, implement (ensure to mark map modified)
def delete_workflow_pattern(configuration, wp):
    _logger = configuration.logger
    # _logger.debug("WP: delete_workflow_pattern")
    pass


def create_workflow_pattern(configuration, client_id, wp):
    """ Creates a workflow patterns based on the passed wp object.
    Expects that the wp paramater is in a dictionary structure.
    Requires the following keys and structure:

    wp = {
        'name': 'pattern-name'
        'owner': 'string-owner',
        'input': [],
        'output': [],
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
    _logger.info("WP: create_workflow_pattern, user: %s, wp: %s"
                 % (client_id, wp))

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

    # TODO, move check typing to here
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

    file_name = generate_random_ascii(wp_id_length, charset=wp_id_charset)
    wp_file_path = os.path.join(wp_home, file_name + '.json')
    if os.path.exists(wp_file_path):
        _logger.error('WP: unique filename conflict: %s '
                      % wp_file_path)
        msg = 'A workflow pattern conflict was encountered, '
        'please try an resubmit the pattern'
        return (False, msg)

    # Save the pattern
    wrote = False
    msg = ''
    try:
        with open(wp_file_path, 'w') as j_file:
            json.dump(wp, j_file, indent=0)
        # Mark as modified
        mark_workflow_p_modified(configuration, wp['name'])
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


# TODO, Register a workflow from a pattern json file
def register_workflow_from_pattern(configuration, client_id, wp):
    pass
