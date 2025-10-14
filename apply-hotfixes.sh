#!/bin/bash
#
# Apply all hot-fixes in specified folder

APPLIED_DIR="/tmp/hotfixes-applied"
HOTFIXES_DIR="/hotfixes"
if [ $# -gt 0 ]; then
    HOTFIXES_DIR="$1"
fi
PATCH_SOURCE="${HOTFIXES_DIR}/patches"
SCRIPT_SOURCE="${HOTFIXES_DIR}/scripts"
PATCHES_APPLIED="${APPLIED_DIR}/patches"
SCRIPTS_APPLIED="${APPLIED_DIR}/scripts"

if [ -d "${HOTFIXES_DIR}" ]; then
    echo "DEBUG: Applying hot-fixes available in ${HOTFIXES_DIR}"
    mkdir -p ${PATCHES_APPLIED} ${SCRIPTS_APPLIED}
    if [ -d "${PATCH_SOURCE}" ]; then
        echo "DEBUG: Applying any patches available in ${PATCH_SOURCE}"
        for PATCH_PATH in "${PATCH_SOURCE}"/* ; do
            PATCH_NAME=$(basename "${PATCH_PATH}")
            if [ ! -f "${PATCH_PATH}" ]; then
                # skip anything but files
                continue
            fi
            if [ -f "${PATCHES_APPLIED}/${PATCH_NAME}" ]; then
                echo "DEBUG: skip already applied patch: ${PATCH_NAME}"
            else
                echo "Applying patch ${PATCH_PATH}"
                patch -d / -p0 < "${PATCH_PATH}" && \
                    cp "${PATCH_PATH}" "${PATCHES_APPLIED}/"
            fi
        done
    fi
    if [ -d "${SCRIPT_SOURCE}" ]; then
        echo "Applying any scripts available in ${SCRIPT_SOURCE}"
        for SCRIPT_PATH in "${SCRIPT_SOURCE}"/* ; do
            SCRIPT_NAME=$(basename "${SCRIPT_PATH}")
            if [ ! -f "${SCRIPT_PATH}" ]; then
                # skip anything but files
                continue
            fi
            if [ -f "${SCRIPTS_APPLIED}/${SCRIPT_NAME}" ]; then
                echo "DEBUG: skip already applied script: ${SCRIPT_NAME}"
            else
                echo "Running script ${SCRIPT_PATH}"
                ${SCRIPT_PATH} && \
                    cp "${SCRIPT_PATH}" "${SCRIPTS_APPLIED}/"
            fi
        done
    fi
    echo "DEBUG: Applied hot-fixes available in ${HOTFIXES_DIR}"
else
    echo "WARNING: no such hot-fixes folder ${HOTFIXES_DIR}"
    exit 1
fi
exit 0

