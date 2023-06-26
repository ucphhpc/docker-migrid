Minimum intrusion Grid
======================

MiG or The Minimum intrusion Grid can be configured in a number of ways.

To generate a configuration for the MiG service, one should make use of the `generateconfs.py` Python script
that by default is located in the `~/mig/server/install` directory.

The implementation is based on having a central MiGserver.conf configuration that is typically located
in the `~/mig/server` directory. The other important aspect of configuring the MiG, is the associated Apache service which is
configured via a number of Apache configuration files.

These Apache configuration files are placed in the default configuration path for the HTTP service.
Which for CentOS/Rocky Linux is `/etc/httpd`.
