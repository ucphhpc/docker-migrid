#!/bin/bash

# Launches the MiG web interface and the underlying services
# Continuously checks for whether the services are still alive

# Lookup DOMAIN dynamically from MiGserver.conf
DOMAIN="$(egrep '^server_fqdn' $MIG_ROOT/mig/server/MiGserver.conf | cut -d ' ' -f 3)"

# Map external addresses to local IPs for daemons to bind to if it isn't
# already exposed with docker-compose network alias.
DAEMONFQDN="io.${DOMAIN}"
DAEMONIP=$(getent hosts ${DAEMONFQDN}|cut -d ' ' -f 1)
FOUNDIP=0
for LOCALIP in $(ifconfig | grep inet | grep -v '127.0.0.' | cut -d ' ' -f 10); do
    if [ ${LOCALIP} = ${DAEMONIP} ]; then
        echo "Found existing local IP for daemons"
        FOUNDIP=1
    fi
done
if [ ${FOUNDIP} -eq 0 ]; then
    echo "Add local IP alias for daemons"
    echo "${LOCALIP}	${DAEMONFQDN}" >> /etc/hosts
fi
echo "Binding daemons to IP: $(getent hosts ${DAEMONFQDN}|cut -d ' ' -f 1)"

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

# TODO: can we switch to proper service start?
#service httpd start
/usr/sbin/httpd -k start
status=$?
if [ $status -ne 0 ]; then
    echo "Failed to start httpd: $status"
    exit $status
fi

# Start every service for now
service migrid start
status=$?
if [ $status -ne 0 ]; then
    echo "Failed to start migrid services: $status"
    exit $status
fi

# Check core services
while sleep 60; do
    ps aux | grep openid | grep -q -v grep
    OPENID_STATUS=$?
    if [ $OPENID_STATUS -ne 0 ]; then
        echo "OpenID service failed."
        exit 1
    fi

    ps aux | grep httpd | grep -q -v grep
    HTTPD_STATUS=$?
    if [ $HTTPD_STATUS -ne 0 ]; then
        echo "Httpd service failed."
        exit 1
    fi
done
