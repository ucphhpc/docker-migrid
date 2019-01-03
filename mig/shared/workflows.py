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
import tempfile

from hashlib import sha256

from shared.base import client_id_dir
from shared.defaults import any_state, keyword_auto
from shared.events import get_path_expand_map
from shared.functional import REJECT_UNSET
from shared.map import load_system_map
from shared.modified import check_workflow_p_modified, \
    reset_workflow_p_modified, mark_workflow_p_modified
from shared.serial import dump
from shared.functionality.addvgridtrigger import main as add_vgrid_trigger_main

from shared.job import fill_mrsl_template, new_job

WRITE_LOCK = 'write.lock'
WORKFLOW_PATTERNS, MODTIME, CONF = ['__workflowpatterns__', '__modtime__',
                                    '__conf__']

MAP_CACHE_SECONDS = 60

last_load = {WORKFLOW_PATTERNS: 0}
last_refresh = {WORKFLOW_PATTERNS: 0}
last_map = {WORKFLOW_PATTERNS: {}}


def load_wp_map(configuration, do_lock=True):
    """Load map of workflow patterns. Uses a pickled
    dictionary for efficiency. Optional do_lock option is used to enable and
    disable locking during load.
    """
    return load_system_map(configuration, 'workflowpatterns', do_lock)


def refresh_wp_map(configuration):
    """Refresh map of workflow patterns. Uses a pickled dictionary for
    efficiency. Only update map for workflow patterns that appeared or
    disappeared after last map save.
    NOTE: Save start time so that any concurrent updates get caught next time
    """
    _logger = configuration.logger
    start_time = time.time()
    dirty = []
    map_path = os.path.join(configuration.mig_system_files,
                            'workflowpatterns.map')
    lock_path = map_path.replace('.map', '.lock')
    lock_handle = open(lock_path, 'a')
    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
    workflow_p_map, map_stamp = load_wp_map(configuration,
                                            do_lock=False)
    # Find all workflow patterns
    (load_status, all_wps) = list_wps(configuration)
    if not load_status:
        _logger.error('failed to load workflow patterns list: %s' % all_wps)
        return workflow_p_map

    for wp_dir, wp_file in all_wps:
        wp_mtime = os.path.getmtime(os.path.join(wp_dir, wp_file))

        # init first time
        workflow_p_map[wp_file] = workflow_p_map.get(wp_file, {})
        if CONF not in workflow_p_map[wp_file] or wp_mtime >= map_stamp:
            wp_conf = get_wp_conf(os.path.join(wp_dir, wp_file), configuration)
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
            _logger.error('could not save workflow patterns map, or %s' % err)
    last_refresh[WORKFLOW_PATTERNS] = start_time
    lock_handle.close()
    return workflow_p_map


def get_wp_map(configuration):
    """Returns the current map of workflow patterns and
    their configurations. Caches the map for load prevention with
    repeated calls within short time span.
    """
    _logger = configuration.logger
    if last_load[WORKFLOW_PATTERNS] + MAP_CACHE_SECONDS > time.time():
        _logger.debug('using workflows patterns map')
        return last_map[WORKFLOW_PATTERNS]
    modified_patterns, _ = check_workflow_p_modified(configuration)
    if modified_patterns:
        _logger.info('refreshing workflow patterns map (%s)'
                     % modified_patterns)
        map_stamp = time.time()
        workflow_p_map = refresh_wp_map(configuration)
        reset_workflow_p_modified(configuration)
    else:
        _logger.debug('no changes - not refreshing')
        workflow_p_map, map_stamp = load_wp_map(configuration)
    last_map[WORKFLOW_PATTERNS] = workflow_p_map
    last_refresh[WORKFLOW_PATTERNS] = map_stamp
    last_load[WORKFLOW_PATTERNS] = map_stamp
    return workflow_p_map


def list_wps(configuration):
    """Returns a list of tuples, containing the path to the individual
    workflow patterns and the actual workflow pattern: (path,wp)
    """
    _logger = configuration.logger
    workflows = []
    if not os.path.exists(configuration.workflow_patterns_home):
        try:
            os.makedirs(configuration.workflow_patterns_home)
        except Exception, err:
            _logger.error('not able to create directory %s %s' %
                          (configuration.workflow_patterns_home, err))
            return (False, 'Failed to setup required directory for workflow '
                           'patterns')

    client_dirs = []
    try:
        client_dirs = os.listdir(configuration.workflow_patterns_home)
    except Exception, err:
        _logger.error('Failed to retrieve content inside %s %s' %
                      (configuration.workflow_patterns_home, err))

    for client_dir in client_dirs:
        dir_content = []
        client_path = os.path.join(configuration.workflow_patterns_home,
                                   client_dir)
        try:
            dir_content = os.listdir(client_path)
        except Exception, err:
            _logger.error('Failed to retrieve content inside %s %s'
                          % (client_path, err))
        for entry in dir_content:
            # Skip dot files/dirs and the write lock
            if entry.startswith('.') or entry == WRITE_LOCK:
                continue
            if os.path.isfile(os.path.join(client_path, entry)):
                workflows.append((client_path, entry))
            else:
                _logger.warning('%s in %s is not a plain file, move it?' %
                                (entry, client_path))
    return (True, workflows)


def get_wp_conf(wp_path, configuration):
    """Returns a dictionary containing the workflow pattern configuration"""
    try:
        with open(wp_path, 'r') as _wp_path:
            wp_conf = json.load(_wp_path)
            return wp_conf
    except Exception, err:
        configuration.logger.error('could not open workflow pattern %s %s' %
                                   (wp_path, err))
    return {}


# TODO, implement (ensure to mark map modified)
def delete_workflow_pattern(wp, configuration):
    pass


def create_workflow_pattern(client_id, wp, configuration):
    """ Creates a workflow patterns based on the passed wp object.
    Expects that the wp paramater is in a dictionary structure.
    Requires the following keys and structure:

    wp = {
        'name': 'string-name'
        'owner': 'string-owner',
        'recipes:' [],
        'input': [],
        'output': [],
        'type_filter': [],
        'variables': {}
        }

    The 'name' and 'owner' keys are required to be non-empty strings
    Every additional key should follow the defined types structure,
    if any of these is left out a default empty structure will be defined.
    An 'id' key however is not allowed since it is generated by the system.

    Additional keys/data are allowed and will be saved
    with the required information.
    
    Result is that a JSON object of the dictionary structure will be saved
    to the configuration.mig_system_files/client_dir/generated_id.json
    """

    # Prepare json for writing.
    # The name of the directory to be used in both the users home
    # and the global state/workflow_patterns_home directory
    client_dir = client_id_dir(client_id)
    _logger = configuration.logger
    _logger.info('%s is creating a workflow pattern from %s' % (client_id,
                                                                wp['name']))
    # TODO, move check typing to here (name, language, cells)
    # Based on the source, generate checksum as the id

    _logger.info("wp %s" % wp)

    checksum = sha256()
    code = ''
    for c in wp['notebook']['cells']:
        if 'source' in c:
            code = code.join(c['source'])
    
    if code:
        _logger.info("source: %s type: %s" % (code, type(code)))
        checksum.update(bytes(code))

    _logger.info("Code %s ", code)

    wp_home = os.path.join(configuration.workflow_patterns_home,
                           client_dir)
    if not os.path.exists(wp_home):
        try:
            os.makedirs(wp_home)
        except Exception, err:
            _logger.error("couldn't create workflow pattern directory %s %s" %
                          (wp_home, err))
            msg = "Couldn't create the required dependencies for " \
                  "your workflow pattern"
            return (False, msg)

    # Use unique id as filename as well
    wp_file_path = os.path.join(wp_home, wp['id'] + '.json')
    if os.path.exists(wp_file_path):
        _logger.error('workflow pattern unique filename conflict: %s '
                      % wp_file_path)
        msg = 'A workflow pattern conflict was encountered, ' \
              'please try an resubmit the pattern'
        return (False, msg)

    # Save the pattern
    wrote = False
    msg = ''
    try:
        with open(wp_file_path, 'w') as j_file:
            json.dump(wp, j_file)
        # Mark as modified
        mark_workflow_p_modified(configuration, wp['name'])
        wrote = True
    except Exception, err:
        _logger.error('failed to write workflow pattern %s to disk %s' % (
            wp_file_path, err))
        msg = 'Failed to save your workflow pattern, please try and resubmit it'

    if not wrote:
        # Ensure that the failed write does not stick around
        try:
            os.remove(wp_file_path)
        except Exception, err:
            _logger.error('failed to remove the dangling worklow pattern %s %s'
                          % (wp_file_path, err))
            msg += '\n Failed to cleanup after a failed workflow creation'
        return (False, msg)

    _logger.info('%s created a new pattern workflow at: %s ' %
                 (client_id, wp_file_path))
    return (True, '')


def build_wp_object(configuration, wp_dict):
    """Build a workflow pattern object based on wp_dict input,
    expects that wp_dict has the following keys."""
    wp_obj = {
        'object_type': 'workflowpattern',
        'id': wp_dict.get('id', ''),
        'owner': wp_dict.get('owner', ''),
        'name': wp_dict.get('name', '')
    }
    return wp_obj


def rule_identification_from_pattern(client_id, workflow_pattern, configuration):
    # TODO finish this
    """identifies if a task can be created, following the creation or
    editing of a pattern . This pattern is read in as the object
    workflow_pattern and is expected in the format."""

    # work out recipe directory
    client_dir = client_id_dir(client_id)
    recipe_dir_path = os.path.join(configuration.workflow_recipes_home, client_dir)

    # setup logger
    _logger = configuration.logger
    _logger.info('%s is identifying any possible tasks from pattern creation '
                 '%s' % (client_id, workflow_pattern['name']))

    # Currently multiple recipes are crudely chained together. This will need
    # to be altered once we move into other languages than python.
    complete_recipe = ''
    got_all_recipes = True
    # Check if defined recipes exist already within system
    for pattern_recipe in workflow_pattern['recipes']:
        got_this_recipe = False
        # TODO this will almost certainly need altered once recipes have been
        #  implemented
        # This assumes that recipes are saved as their name.
        for recipe in os.listdir(recipe_dir_path):
            if pattern_recipe == recipe:
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

    # if all recipes are present then check for data files
    if got_all_recipes and complete_recipe != '':
        pass
        # Generate rule from pattern and recipe

        # this doesn't seem true.
        # TODO work this out according to grid_events lines 1574 to 1581
        rule_dir_path = client_dir

        user_arguments_dict = {
#            '_csrf':['14e3ec5513c0080d14519445ed73c2f598bb43762e02519e06845e78cc820530'],
            'vgrid_name': REJECT_UNSET,
            'rule_id': [keyword_auto],
            'path': [''],
            'changes': [any_state],
            'action': [keyword_auto],
            'arguments': [''],
            'rate_limit': [''],
            'settle_time': [''],
            'match_files': ['True'],
            'match_dirs': ['False'],
            'match_recursive': ['False'],
            'rank': [''],
        }
        add_vgrid_trigger_main(client_id, user_arguments_dict)

        # initial_data = []
        # for input_dir in workflow_pattern['input']:
        #     full_input_path = os.path.join(client_dir, input_dir)
        #     for root, dirs, files in os.walk(full_input_path, topdown=False):
        #         for name in files:
        #             initial_data.append(os.path.join(root, name))
        # for data in initial_data:
        #     # start setting up to create new jobs
        #     mrsl_fd = tempfile.NamedTemporaryFile(delete=False)
        #     mrsl_path = mrsl_fd.name
        #
        #     base_dir = os.path.join(configuration.vgrid_files_home)
        #     rel_src = data[len(base_dir):].lstrip(os.sep)
        #
        #     expand_map = get_path_expand_map(rel_src, rule, state)
        #     mrsl_fd.truncate(0)
        #
        #     if not fill_mrsl_template(
        #             job_template,
        #             mrsl_fd,
        #             rel_src,
        #             state,
        #             rule,
        #             expand_map,
        #             configuration,
        #     ):
        #         raise Exception('fill template failed')
        #     # get a job id
        #     (success, msg, jobid) = new_job(
        #         mrsl_path,
        #         client_id,
        #         configuration,
        #         False,
        #         returnjobid=True)
        #     if success:
        #         self.__add_trigger_job_ent(configuration,
        #                                    event, rule, jobid)
        #
        #         logger.info('(%s) submitted job for %s: %s'
        #                     % (pid, target_path, msg))
        #         self.__workflow_info(configuration,
        #                              rule['vgrid_name'],
        #                              'submitted job for %s: %s' %
        #                              (rel_src, msg))
        #     else:
        #         raise Exception(msg)
        #
        # # Generate Tasks if possible
        # for data in initial_data:
        #     pass

    # if we didn't find all the required recipes
    else:
        _logger.info("Did not find all the necessary recipes for pattern " + workflow_pattern['name'])


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
