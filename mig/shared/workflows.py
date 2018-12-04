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

import os
import time
import fcntl

from shared.serial import load, dump
from shared.modified import check_workflow_p_modified, reset_workflow_p_modified

WRITE_LOCK = 'write.lock'
WORKFLOW_PATTERNS, MODTIME = ['__workflowpatterns__', '__modtime__']

MAP_CACHE_SECONDS = 60

last_load = {WORKFLOW_PATTERNS: 0}
last_refresh = {WORKFLOW_PATTERNS: 0}
last_map = {WORKFLOW_PATTERNS: {}}


def load_system_map(configuration, kind, do_lock):
    """Load map of given entities and their configuration. Uses a pickled
    dictionary for efficiency. The do_lock option is used to enable and
    disable locking during load.
    Entity IDs are stored in their raw (non-anonymized form).
    Returns tuple with map and time stamp of last map modification.
    Please note that time stamp is explicitly set to start of last update
    to make sure any concurrent updates get caught in next run.
    """
    map_path = os.path.join(configuration.mig_system_files, "%s.map" % kind)
    lock_path = os.path.join(configuration.mig_system_files, "%s.lock" % kind)
    if do_lock:
        lock_handle = open(lock_path, 'a')
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
    try:
        configuration.logger.info("before %s map load" % kind)
        entity_map = load(map_path)
        configuration.logger.info("after %s map load" % kind)
        map_stamp = os.path.getmtime(map_path)
    except IOError:
        configuration.logger.warn("No %s map to load" % kind)
        entity_map = {}
        map_stamp = -1
    if do_lock:
        lock_handle.close()
    return (entity_map, map_stamp)


def load_workflow_p_map(configuration, do_lock=True):
    """Load map of workflow patterns. Uses a pickled
    dictionary for efficiency. Optional do_lock option is used to enable and
    disable locking during load.
    """
    return load_system_map(configuration, 'workflowpatterns', do_lock)


def refresh_workflow_p_map(configuration):
    """Refresh map of workflow patterns. Uses a pickled dictionary for
    efficiency. Only update map for workflow patterns that appeared or
    disappeared after last map save.
    NOTE: Save start time so that any concurrent updates get caught next time
    """
    start_time = time.time()
    dirty = []
    map_path = os.path.join(configuration.mig_system_files,
                            'workflowpatterns.map')
    lock_path = map_path.replace('.map', '.lock')
    lock_handle = open(lock_path, 'a')
    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
    workflow_p_map, map_stamp = load_workflow_p_map(configuration,
                                                    do_lock=False)
    configuration.logger.info("After lock workflows")
    # Find all workflow patterns
    (load_status, all_wps) = list_workflow_patterns(configuration)
    configuration.logger.info("After list workflow patterns")
    if not load_status:
        configuration.logger.error("failed to load workflow patterns list: %s"
                                   % all_wps)
        return workflow_p_map
    for wp in all_wps:
        wp_path = os.path.join(configuration.workflow_patterns_home, wp)
        wp_mtime = os.path.getmtime(wp_path)

        # init first time
        workflow_p_map[wp] = workflow_p_map.get(wp, {})
        if wp_mtime >= map_stamp:
            workflow_p_map[wp][MODTIME] = map_stamp
            dirty.append([wp])

    # Remove any missing workflow patterns from map
    missing_wp = [wp for wp in workflow_p_map.keys()
                  if wp not in all_wps]

    for wp in missing_wp:
        del workflow_p_map[wp]
        dirty.append([wp])

    if dirty:
        try:
            dump(workflow_p_map, map_path)
            os.utime(workflow_p_map, (start_time, start_time))
        except Exception, err:
            configuration.logger.error("Could not save workflow patterns map"
                                       " %s" % err)
    last_refresh[WORKFLOW_PATTERNS] = start_time
    lock_handle.close()
    return workflow_p_map


def get_workflow_p_map(configuration):
    """Returns the current map of workflow patterns and
    their configurations. Caches the map for load prevention with
    repeated calls within short time span.
    """
    if last_load[WORKFLOW_PATTERNS] + MAP_CACHE_SECONDS > time.time():
        configuration.logger.debug("using workflows patterns map")
        return last_map[WORKFLOW_PATTERNS]
    modified_patterns, _ = check_workflow_p_modified(configuration)
    if modified_patterns:
        configuration.logger.info("refreshing workflow patterns map (%s)"
                                  % modified_patterns)
        map_stamp = time.time()
        workflow_p_map = refresh_workflow_p_map(configuration)
        reset_workflow_p_modified(configuration)
    else:
        configuration.logger.debug("No changes - not refreshing")
        workflow_p_map, map_stamp = load_workflow_p_map(configuration)
    last_map[WORKFLOW_PATTERNS] = workflow_p_map
    last_refresh[WORKFLOW_PATTERNS] = map_stamp
    last_load[WORKFLOW_PATTERNS] = map_stamp
    return workflow_p_map


def list_workflow_patterns(configuration):
    """Find all workflows patterns"""
    workflows = []
    if not os.path.exists(configuration.workflow_patterns_home):
        try:
            os.makedirs(configuration.workflow_patterns_home)
        except Exception, err:
            configuration.logger.error("workflows.py: not able to create "
                                       "directory %s: %s" %
                                       (configuration.workflow_patterns_home,
                                        err))
            return (False, "Failed to setup required directory for workflow "
                           "patterns")

    dir_content = []
    try:
        dir_content = os.listdir(configuration.workflow_patterns_home)
    except Exception, err:
        configuration.logger.error("Failed to retrieve content inside %s %s" %
                                   configuration.workflow_patterns_home, err)
    for entry in dir_content:
        # Skip dot files/dirs and the write lock
        if entry.startswith('.') or entry == WRITE_LOCK:
            continue
        if os.path.isfile(os.path.join(configuration.workflow_patterns_home,
                                       entry)):
            workflows.append(entry)
        else:
            configuration.logger.warning("%s in %s is not a plain file, "
                                         "move it?" %
                                         (entry,
                                          configuration.workflow_patterns_home))
    return (True, workflows)
