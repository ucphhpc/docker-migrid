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


"""General map helper functions"""

import os
import fcntl

from shared.serial import load


def load_system_map(configuration, kind, do_lock):
    """Load map of given kind and their configuration from the
    mig_system_files directory.
    Here the kind maps to what the mapfile is named.
    Uses a pickled dictionary for efficiency.
    The do_lock option is used to enable and disable locking during load.
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
        configuration.logger.info("map.py before %s map load" % kind)
        entity_map = load(map_path)
        configuration.logger.info("map.py after %s map load" % kind)

        map_stamp = os.path.getmtime(map_path)

        configuration.logger.info("DELETE ME - START POINT")
        configuration.logger.info("DELETE ME - map_stamp: " + str(map_stamp))
        configuration.logger.info("DELETE ME - map_path: " + str(map_path))
        configuration.logger.info("DELETE ME - entity_map: " + str(entity_map))
        configuration.logger.info("DELETE ME - END POINT")

    except IOError:
        configuration.logger.warn("No %s map to load" % kind)
        entity_map = {}
        map_stamp = -1
    if do_lock:
        lock_handle.close()
    return (entity_map, map_stamp)
