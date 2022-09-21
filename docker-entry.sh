#!/bin/bash

# Launches one or more of the apache web server and the migrid daemons as
# specified in the provided RUN_SERVICES environment.
# Continuously checks whether the selected services are still alive.

KEEPALIVE=0

# Create any user requested
while getopts ku:p:s: option; do
    case "${option}" in
        k) KEEPALIVE=1;;
        u) USERNAME=${OPTARG};;
        p) PASSWORD=${OPTARG};;
        s) SVCLOGINS=${OPTARG};;
    esac
done

# Create a default account (Use service owner account)
if [ "$USERNAME" != "" ] && [ "$PASSWORD" != "" ]; then
    # Ensure the database is present
    su - $USER -c "${MIG_ROOT}/mig/server/migrateusers.py"
    # createuser.py Usage:
    # [OPTIONS] [FULL_NAME ORGANIZATION STATE COUNTRY EMAIL COMMENT PASSWORD]
    # Create with renew flag to avoid partial clean up which is particularly
    # tricky in gdp mode where project sub-users may exist.
    echo "Creating or renewing user: $USERNAME"
    su - $USER -c "${MIG_ROOT}/mig/server/createuser.py -r 'Test User' 'Test Org' NA DK $USERNAME 'Created upon docker entry' $PASSWORD"
    echo "Ensure correct permissions for $USERNAME"
    # NOTE: user database moved to state since June 13th 2022
    LEGACY_DB_PATH="${MIG_ROOT}/mig/server/MiG-users.db"
    if [ -e "${LEGACY_DB_PATH}" ]; then
        chown $USER:$USER ${LEGACY_DB_PATH}
        chmod 644 ${LEGACY_DB_PATH}
    fi
    chown -R $USER:$USER ${MIG_ROOT}/state
    # If GDP mode skip SVCLOGINS as they have no effect (chkenabled returns 0 if enabled)
    su - $USER -c "PYTHONPATH=${MIG_ROOT} ${MIG_ROOT}/mig/server/chkenabled.py gdp" > /dev/null
    GDP=$?
    if [ "$GDP" -ne 0 ]; then 
        for PROTO in ${SVCLOGINS}; do
            echo "Add $PROTO password login for $USERNAME"
            su - $USER -c "python ${MIG_ROOT}/mig/cgi-bin/fakecgi.py ${MIG_ROOT}/mig/cgi-bin/settingsaction.py POST \"topic=${PROTO}&output_format=text&password=${PASSWORD}\" \"/C=DK/ST=NA/L=NA/O=Test Org/OU=NA/CN=Test User/emailAddress=${USERNAME}\" admin 127.0.0.1 True" | grep 'Exit code: 0 ' || \
            echo "Failed to set $PROTO password login"
        done
    fi
fi

echo "Run services: ${RUN_SERVICES}"
CHK_SERVICES=""
for svc in ${RUN_SERVICES}; do
    if [ "$svc" = "httpd" ]; then
        # Load required httpd environment vars
        source migrid-httpd-init.sh

        # TODO: can we switch to proper service start?
        #service httpd start
        /usr/sbin/httpd -k start
        status=$?
        if [ $status -ne 0 ]; then
            echo "Failed to start $svc: $status"
            exit $status
        else
            CHK_SERVICES="${CHK_SERVICES} $svc"
        fi
    elif [ "$svc" = "rsyslogd" ]; then
        # TODO: can we switch to proper service start?
        #service rsyslog start
        /usr/sbin/rsyslogd
        status=$?
        if [ $status -ne 0 ]; then
            echo "Failed to start $svc: $status"
            exit $status
        else
            CHK_SERVICES="${CHK_SERVICES} $svc"
        fi
    else
        # Start requested migrid daemons individually and detect if enabled
        service migrid startdaemon $svc
        status=$?
        # Returns 42 on disabled
        if [ "$status" -eq 42 ]; then
            echo "Skip disabled $svc service"
        elif [ "$status" -ne 0 ]; then
            echo "Failed to start migrid $svc service: $status"
            exit $status
        else
            CHK_SERVICES="${CHK_SERVICES} $svc"
        fi
    fi
done

# Keep monitoring any active services 
KEEP_RUNNING=1
EXIT_CODE=0
# Check launched services
while [ ${KEEP_RUNNING} -eq 1 ]; do
    sleep 120
    for svc in ${CHK_SERVICES}; do
        if [ "$svc" = "sftpsubsys" ]; then
            PROCNAME="MiG-sftp-subsys"
            PROCUSER="root"
        elif [ "$svc" = "rsyslogd" ]; then
            PROCNAME="$svc"
            PROCUSER="root"
        else
            PROCNAME="$svc"
            PROCUSER=$USER
        fi
        pgrep -U $PROCUSER -f "$PROCNAME" > /dev/null
        SVC_STATUS=$?
        if [ "$SVC_STATUS" -ne 0 ]; then
            echo "$svc service failed."
            if [ $KEEPALIVE -eq 0 ]; then
                KEEP_RUNNING=0
                EXIT_CODE=1
                break
            else
                echo "keepalive despite $svc service failed."
                sleep 900
            fi
        fi
        # Throttle down 
        sleep 1
    done
done

exit $EXIT_CODE
