# docker-migrid

A Dockerized version of the middelware `Migrid <https://sourceforge.net/projects/mig-idl/>`_

Generates 3 volumes that contain the configuration files for the system:

    certs
    httpd
    mig-conf

These can be used to customize the default generated configuration.
This includes the basic IDMC html skin which is
tailored towards local development and testing.

Architecture


By default the MiG system provides ways for authentication
such as x509 certificates and local/external openid.
The default deployment is here configured for openid signup
and authentication via the `http://migrid.test` url provided