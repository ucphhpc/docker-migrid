#!/bin/bash

# Launches the MiG web interface and the underlying services
# Continuously checks for whether the services are still alive

# Load required httpd environment vars
source httpd.env

/usr/sbin/httpd -k start
status=$?
if [ $status -ne 0 ]; then
    echo "Failed to start httpd: $status"
    exit $status
fi

/etc/init.d/migrid start openid
ps aux | grep openid | grep -q -v grep
status=$?
if [ $status -ne 0 ]; then
    echo "Failed to start openid: $status"
    exit $status
fi

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
