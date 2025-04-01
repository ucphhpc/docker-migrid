#!/bin/bash

# Launches one or more of the apache web server and the migrid daemons as
# specified in the provided RUN_SERVICES environment.
# Continuously checks whether the selected services are still alive.

CHECKCONF=0
KEEPALIVE=0
VERSIONINFO=0

# Make sure requested timezone is actually used everywhere for consistent 
# log time stamps.
if [ -z "$TZ" ]; then
    echo "INFO: TZ env unset - fall back to default UTC timezone"
else
    TZBASE="/usr/share/zoneinfo"
    TZPATH="$TZBASE/$TZ"
    if [ -e "$TZPATH" ]; then
        echo "INFO: Enforcing timezone $TZ ($TZPATH)"
        rm -f /etc/timezone
        echo "$TZ" > /etc/timezone
        rm -f /etc/localtime
        ln -s "$TZPATH" /etc/localtime
    else
        echo "ERROR: unsupported timezone $TZ ($TZPATH) - fall back to UTC"
    fi
fi

if [ -z "${USER}" ]; then
    echo "Failed to start because the USER environment variable is not set and is required"
    exit 1
fi

if ! id "${USER}" >/dev/null 2>&1; then
    echo "Failed to start because the USER environment variable is set to a user that does not exist: ${USER}"
    exit 1
fi

if [ -z "${MIG_ROOT}" ]; then
    echo "Failed to start because the MIG_ROOT environment variable is not set and is required"
    exit 1
fi

if [ ! -d "${MIG_ROOT}" ]; then
    echo "Failed to start because the MIG_ROOT environment is set, but the directory: ${MIG_ROOT} does not exist"
    exit 1
fi


# Create any user requested
while getopts cku:p:s:V option; do
    case "${option}" in
        c) CHECKCONF=1;;
        k) KEEPALIVE=1;;
        u) USERNAME=${OPTARG};;
        p) PASSWORD=${OPTARG};;
        s) SVCLOGINS=${OPTARG};;
        V) VERSIONINFO=1;;
        *) echo "unknown option: $option";;
    esac
done

# Display active OS and migrid version to ease support
if [ $VERSIONINFO -eq 1 ]; then
  if [ -x /usr/bin/lsb_release ]; then
    OSVERSION=$(/usr/bin/lsb_release -d -s)
  elif [ -e /etc/redhat-release ]; then
    OSVERSION=$(cat /etc/redhat-release)
  elif [ -e /etc/debian_version ]; then
    OSVERSION=$(cat /etc/debian_version)
  else
    OSVERSION="Unknown OS"
  fi
  if [ -e /home/mig/active-migrid-version.txt ]; then
    MIGRIDVERSION=$(cat /home/mig/active-migrid-version.txt)
  else
    MIGRIDVERSION="Unknown migrid version"
  fi
  echo "Container running on ${OSVERSION}"
  echo "using ${MIGRIDVERSION}"
fi

# Run self-test if requested to ease support
if [ $CHECKCONF -eq 1 ]; then
  echo "Container self-test of migrid configuration"
  su - "$USER" -c "echo 'n' | ${MIG_ROOT}/mig/server/checkconf.py"
fi

# Ensure the MiG users database is present
# TODO, when a specific script for initializing the database is available
# this should be used instead.
su - "$USER" -c "${MIG_ROOT}/mig/server/migrateusers.py"

# Create a default account (Use service owner account)
if [ "$USERNAME" != "" ] && [ "$PASSWORD" != "" ]; then
    # createuser.py Usage:
    # [OPTIONS] [FULL_NAME ORGANIZATION STATE COUNTRY EMAIL COMMENT PASSWORD]
    # Create with renew flag to avoid partial clean up which is particularly
    # tricky in gdp mode where project sub-users may exist.
    echo "Creating or renewing user: $USERNAME"
    su - "$USER" -c "${MIG_ROOT}/mig/server/createuser.py -r 'Test User' 'Test Org' NA DK $USERNAME 'Created upon docker entry' $PASSWORD"
    echo "Ensure correct permissions for $USERNAME"
    # NOTE: user database moved to state since June 13th 2022
    LEGACY_DB_PATH="${MIG_ROOT}/mig/server/MiG-users.db"
    if [ -e "${LEGACY_DB_PATH}" ]; then
        chown "$USER":"$USER" "${LEGACY_DB_PATH}"
        chmod 644 "${LEGACY_DB_PATH}"
    fi
    chown -R "$USER":"$USER" "${MIG_ROOT}/state"
    # If GDP mode skip SVCLOGINS as they have no effect (chkenabled returns 0 if enabled)
    su - "$USER" -c "PYTHONPATH=${MIG_ROOT} ${MIG_ROOT}/mig/server/chkenabled.py gdp" > /dev/null
    GDP=$?
    if [ "$GDP" -ne 0 ]; then 
        for PROTO in ${SVCLOGINS}; do
            echo "Add $PROTO password login for $USERNAME"
            su - "$USER" -c "python ${MIG_ROOT}/mig/cgi-bin/fakecgi.py ${MIG_ROOT}/mig/cgi-bin/settingsaction.py POST \"topic=${PROTO}&output_format=text&password=${PASSWORD}\" \"/C=DK/ST=NA/L=NA/O=Test Org/OU=NA/CN=Test User/emailAddress=${USERNAME}\" admin 127.0.0.1 True" | grep 'Exit code: 0 ' || \
            echo "Failed to set $PROTO password login"
        done
    fi
fi

# Adjust IO session cleanup to match actual services
SESSCLEANUP="/etc/cron.daily/migstateclean"
echo "Setting MiG state cleanup"
if [ -f "$SESSCLEANUP" ]; then
    protos=""
    for svc in ${RUN_SERVICES}; do
        if [[ "$svc" == "webdavs" ]]; then
            protos="davs $protos"
        elif [[ "$svc" == "ftps" ]]; then
            protos="ftps $protos"
        elif [[ "$svc" == "sftp"* \
		        && ! "$protos" == *"sftp"* ]] ; then
            protos="sftp $protos"
        fi
    done
    if [ -z "$protos" ]; then
        echo "Disabling IO session cleanup"
        sed -i 's/^SESSCLEANUP=\".*\"/SESSCLEANUP=\"\"/g' "$SESSCLEANUP"
    else
	protos="${protos%?}"
        echo "Enabling IO session cleanup for: $protos"
        cmd="sed -i 's/^SESSCLEANUP=\".*\"/SESSCLEANUP=\"$protos\"/g' \"$SESSCLEANUP\""
	eval "$cmd"
    fi
fi

echo "Run services: ${RUN_SERVICES}"
CHK_SERVICES=""
for svc in ${RUN_SERVICES}; do
    if [ "$svc" = "httpd" ]; then
        # Load required httpd environment vars
        source migrid-httpd-init.sh

	# Use simple apache init wrapper to allow restart without systemd need
        service apache-minimal start
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
        # limit the amout of open files for rsyslog due to
        # https://github.com/rsyslog/rsyslog/issues/5158#issuecomment-1708760846
        ( ulimit -n 1024; /usr/sbin/rsyslogd )
        status=$?
        if [ $status -ne 0 ]; then
            echo "Failed to start $svc: $status"
            exit $status
        else
            CHK_SERVICES="${CHK_SERVICES} $svc"
        fi
    elif [ "$svc" = "crond" ]; then
        # TODO: can we switch to proper service start?
        #service crond start
        /usr/sbin/crond
        status=$?
        if [ $status -ne 0 ]; then
            echo "Failed to start $svc: $status"
            exit $status
        else
            CHK_SERVICES="${CHK_SERVICES} $svc"
        fi
    else
        # Start requested migrid daemons individually and detect if enabled
        service migrid startdaemon "$svc"
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
if [ -z "${CHK_SERVICES}" ]; then
    KEEP_RUNNING=0
else
    KEEP_RUNNING=1
fi
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
        elif [ "$svc" = "crond" ]; then
            PROCNAME="$svc"
            PROCUSER="root"
        else
            PROCNAME="$svc"
            PROCUSER=$USER
        fi
        pgrep -U "$PROCUSER" -f "$PROCNAME" > /dev/null
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
