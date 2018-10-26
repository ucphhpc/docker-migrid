# Setup timezone
export TZ=Europe/Copenhagen
# Load required httpd environment vars
source /etc/sysconfig/httpd
/usr/sbin/httpd -k start