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
    su - $USER -c "$MIG_ROOT/mig/server/deleteuser.py -i /C=dk/ST=dk/L=NA/O=org/OU=NA/CN=devuser/emailAddress=$USERNAME"
    su - $USER -c "$MIG_ROOT/mig/server/createuser.py devuser org dk dk $USERNAME foo $PASSWORD"
    echo "Ensure correct permissions for $USERNAME"
    chown $USER:$USER $MIG_ROOT/mig/server/MiG-users.db
    chmod 644 $MIG_ROOT/mig/server/MiG-users.db
    chown -R $USER:$USER $MIG_ROOT/state
fi

# Load required httpd environment vars
source migrid-httpd.env

/usr/sbin/httpd -k start
status=$?
if [ $status -ne 0 ]; then
    echo "Failed to start httpd: $status"
    exit $status
fi

# Start every service for now
# TODO make individual checks for each service
/etc/init.d/migrid start openid
ps aux | grep openid | grep -q -v grep
status=$?
if [ $status -ne 0 ]; then
    echo "Failed to start openid: $status"
    exit $status
fi

/etc/init.d/migrid start sftpsubsys
ps aux | grep sshd | grep -q -v grep
status=$?
if [ $status -ne 0 ]; then
    echo "Failed to start sshd: $status"
    exit $status
fi

while sleep 60; do
    ps aux | grep openid | grep -q -v grep
    OPENID_STATUS=$?
    
    if [ $OPENID_STATUS -ne 0 ]; then
        echo "OpenID service failed."
        exit 1
    fi

    ps aux | grep sshd | grep -q -v grep
    SFTP_STATUS=$?
    
    if [ $SFTP_STATUS -ne 0 ]; then
        echo "sshd service failed."
        exit 1
    fi

    ps aux | grep httpd | grep -q -v grep
    HTTPD_STATUS=$?

    if [ $HTTPD_STATUS -ne 0 ]; then
        echo "Httpd service failed."
        exit 1
    fi
done
