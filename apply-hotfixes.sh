#!/bin/bash
#
# Apply all hot-fixes in specified folder

APPLIED_DIR="/tmp/hotfixes-applied"
HOTFIXES_DIR="${HOTFIXES_DIR:-/hotfixes}"
if [ $# -gt 0 ]; then
    HOTFIXES_DIR="$1"
fi
PATCH_SOURCE="${HOTFIXES_DIR}/patches"
SCRIPT_SOURCE="${HOTFIXES_DIR}/scripts"
PATCHES_APPLIED="${APPLIED_DIR}/patches"
SCRIPTS_APPLIED="${APPLIED_DIR}/scripts"
LOGFILE="/var/log/migrid-container-hotfixes.log"

touch ${LOGFILE}
if [ -d "${HOTFIXES_DIR}" ]; then
    echo "$(date) $(hostname): Applying hot-fixes available in ${HOTFIXES_DIR}" \
        >> ${LOGFILE}
    mkdir -p ${PATCHES_APPLIED} ${SCRIPTS_APPLIED}
    if [ -d "${PATCH_SOURCE}" ]; then
        #echo "DEBUG: Applying any patches available in ${PATCH_SOURCE}"
        for PATCH_PATH in "${PATCH_SOURCE}"/* ; do
            PATCH_NAME=$(basename "${PATCH_PATH}")
            if [ ! -f "${PATCH_PATH}" ]; then
                # skip anything but files
                continue
            fi
            if [ -f "${PATCHES_APPLIED}/${PATCH_NAME}" ]; then
                echo "$(date) $(hostname): Skip already applied patch: ${PATCH_NAME}" \
                    >> ${LOGFILE}
            else
                echo "$(date) $(hostname): Applying patch ${PATCH_PATH}" \
                    >> ${LOGFILE} 2>&1
                patch -d / -p0 < "${PATCH_PATH}" >> ${LOGFILE} 2>&1
                ret=$?
                echo "$(date) $(hostname): Applied patch: ${PATCH_PATH}: $ret" \
                    >> ${LOGFILE}
                [ "$ret" -eq 0 ] \
                    && cp "${PATCH_PATH}" "${PATCHES_APPLIED}/" >> ${LOGFILE} 2>&1
            fi
        done
    fi
    if [ -d "${SCRIPT_SOURCE}" ]; then
        #echo "DEBUG: Applying any scripts available in ${SCRIPT_SOURCE}"
        for SCRIPT_PATH in "${SCRIPT_SOURCE}"/* ; do
            SCRIPT_NAME=$(basename "${SCRIPT_PATH}")
            if [[ ! -f "${SCRIPT_PATH}" && ! -x "${SCRIPT_PATH}" ]]; then
                # skip anything but executable files
                continue
            fi
            if [ -f "${SCRIPTS_APPLIED}/${SCRIPT_NAME}" ]; then
                echo "$(date) $(hostname): Skip already applied script: ${SCRIPT_NAME}" \
                    >> ${LOGFILE}
            else
                echo "$(date) $(hostname): Running script ${SCRIPT_PATH}" >> ${LOGFILE}
                ${SCRIPT_PATH} >> ${LOGFILE} 2>&1 
                ret=$?
                echo "$(date) $(hostname): Finished script ${SCRIPT_PATH}: $ret" >> ${LOGFILE}
                [ "$ret" -eq 0 ] \
                    && cp "${SCRIPT_PATH}" "${SCRIPTS_APPLIED}/"
            fi
        done
    fi
    #echo "DEBUG: Applied hot-fixes available in ${HOTFIXES_DIR}"
    exit 0
else
    echo "WARNING: no such hot-fixes folder ${HOTFIXES_DIR}" >> ${LOGFILE}
    exit 1
fi

