#!/bin/bash

# Launches the MiG web interface and the underlying services
# Continuously checks for whether the services are still alive

while getopts u:p: option
do
case "${option}" in
u) USERNAME=${OPTARG};;
p) PASSWORD=${OPTARG};;
esac
done

# Create a default account (Use service owner account)
if [ "$USERNAME" != "" ] && [ "$PASSWORD" != "" ]; then
    echo "Creating $USERNAME"
    # Ensure the database is present
    su - $USER -c "$MIG_ROOT/mig/server/migrateusers.py"
    # createuser.py Usage:
    # [OPTIONS] [FULL_NAME ORGANIZATION STATE COUNTRY EMAIL COMMENT PASSWORD]
    su - $USER -c "$MIG_ROOT/mig/server/createuser.py -r devuser org dk dk $USERNAME foo $PASSWORD"
    echo "Ensure correct permissions for $USERNAME"
    chown $USER:$USER $MIG_ROOT/mig/server/MiG-users.db
    chmod 644 $MIG_ROOT/mig/server/MiG-users.db
    chown -R $USER:$USER $MIG_ROOT/state
fi

# Start rsyslog
#/usr/sbin/rsyslogd

# Load required httpd environment vars
source migrid-httpd.env

/usr/sbin/httpd -k start
HTTPD_STATUS=$?
if [ $HTTPD_STATUS -ne 0 ]; then
    echo "Failed to start httpd: $HTTPD_STATUS"
    exit $HTTPD_STATUS
fi

# Start every service for now
# TODO make individual checks for each service
/etc/init.d/migrid start openid
ps aux | grep openid | grep -q -v grep
OPENID_STATUS=$?
if [ $OPENID_STATUS -ne 0 ]; then
    echo "Failed to start openid: $OPENID_STATUS"
    exit $OPENID_STATUS
fi

/etc/init.d/migrid start sftp
ps aux | grep grid_sftp.py | grep -v -q grep
SFTP_STATUS=$?
if [ $SFTP_STATUS -ne 0 ]; then
    echo "Failed to start sshd: $SFTP_STATUS"
    exit $SFTP_STATUS
fi

# Start every service for now
# TODO make individual checks for each service
/etc/init.d/migrid start script
ps aux | grep script | grep -q -v grep
status=$?
if [ $status -ne 0 ]; then
    echo "Failed to start script: $status"
    exit $status
fi

# Start every service for now
# TODO make individual checks for each service
/etc/init.d/migrid start events
ps aux | grep events | grep -q -v grep
status=$?
if [ $status -ne 0 ]; then
    echo "Failed to start events: $status"
    exit $status
fi

while sleep 60; do
    ps aux | grep httpd | grep -q -v grep
    HTTPD_STATUS=$?
    if [ $HTTPD_STATUS -ne 0 ]; then
        echo "Httpd service failed."
        exit $HTTPD_STATUS
    fi

    ps aux | grep openid | grep -q -v grep
    OPENID_STATUS=$?
    if [ $OPENID_STATUS -ne 0 ]; then
        echo "OpenID service failed."
        exit $OPENID_STATUS
    fi

    ps aux | grep grid_sftp.py | grep -v -q grep
    SFTP_STATUS=$?
    if [ $SFTP_STATUS -ne 0 ]; then
        echo "sshd service failed."
        exit $SFTP_STATUS
    fi
    
    ps aux | grep script | grep -q -v grep
    SCRIPT_STATUS=$?
    if [ $SCRIPT_STATUS -ne 0 ]; then
        echo "Script service failed."
        exit $SCRIPT_STATUS
    fi

    ps aux | grep events | grep -q -v grep
    EVENTS_STATUS=$?
    if [ $EVENTS_STATUS -ne 0 ]; then
        echo "Events service failed."
        exit $EVENTS_STATUS
    fi
done