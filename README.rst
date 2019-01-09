=============
docker-migrid
=============

A containerized version of the middleware `Minimum Intrusion Grid (MiG) <https://sourceforge.net/projects/migrid/>`_ system.

------------
Introduction
------------

To start with, general documentation about the MiG
can be found at the `Wiki <https://sourceforge.net/p/migrid/wiki/WelcomePage/>`_.

This repo provides a standard setup of this system in a containerized environment
with the intent of making local development easier.

It does this by implementing a container stack of 3 docker services.
Namely ``devdns``, ``migrid``, ``nginx-proxy`` as defined in the ``docker-compose.yml`` file.

``devdns`` provides a local DNS server that has a predefined A record
that specifies that the URL ``migrid.test`` can be found on the host
itself, i.e. localhost.

``migrid`` provides the actual MiG server setup,
for now it runs the httpd and grid_openid.py service to provide the general
data management portal and local openid authentication. By default the service is
configured to use the basic IDMC html skin which is
tailored towards managing imaging data.
A live version of this can be seen at `IDMC <http://www.idmc.dk>`_.

Lastly the ``nginx-proxy`` service ensures forwarding of port 80/443 requests
to the designated ``migrid`` httpd virtualhost.

---------------
Getting Started
---------------

To begin with the migrid docker image should be built with::

    make


Beyond creating the image, the build target will also
create 4 directories in the root path of the repo, namely::

    certs
    httpd
    mig
    state

These directories are used by the ``migrid`` service as volume mount sources
for the current configuration/state files of the services.

Futhermore, to make the DNS resolution work properly for discovering ``migrid.test``
as a local URL. The host device should be configured so that it queries the
localhost ``devdns`` service before any external nameserver.
E.g. on a OSX or Linux system either through dnsmasq::

    # append to end of dnsmasq.conf
    address=/.test/127.0.0.1

or resolv.conf::

    # prepend before other nameservers
    nameserver 127.0.0.1


---------------
Start the stack
---------------

After the initial build has been made, the service stack can be deployed locally
via `docker-compose <https://docs.docker.com/compose/>`_, i.e.::

    docker-compose up -d

Which will spawn and detach the 3 services as defined by the ``docker-compose.yml`` file.
In addition the ``migrid`` service will setup the 4 prebuild directories
and subsequently execute the ``docker-entry.sh`` bash file which will also act
as the main process of the service, which includes monitoring that the
launched processes are running.

This should make the ``migrid`` service available at the ``migrid.test`` URL.

In addition the entry file also supports the creation of a development user
on the migrid system via the ``-u`` (username) and ``-p`` (password) flags.
By default the ``docker-compose.yml`` provides a default ``dev@dev.dk`` user by
executing the docker-entry.sh as (from ``docker-compose.yml``)::

    command: /app/docker-entry.sh -u dev@dev.dk -p Passw0rd123

Note! This must be changed if ever deployed on a production system.

--------------
Stop the stack
--------------

To stop the stack, simply use the default::

    docker-compose down

In addition, if the current state directories should be reset used::

    make clean

Which will both delete the 4 directories and the docker volumes that binds
them to the ``migrid`` service.
