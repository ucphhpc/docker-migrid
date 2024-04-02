Prerequisites
=============

Docker
------

Because Docker MiGrid is based on deploying the various services with Docker.
The natural implication is that Docker has to be installed before it can be deployed.

Depending on which operating system you are thinking of deploying Docker Migrid to,
you have to follow the Docker installation guide that is applicable to your system.
Details on this can be found at::

    https://docs.docker.com/get-docker/


Docker-Compose
--------------

In addition to Docker, the deployment of Docker MiGrid is configured as such, that it expects you to deploy it 
with the `docker-compose` tool. Similarly to Docker, the installation guide for your particular system can be found at::

    https://docs.docker.com/compose/install/


With these items installed, you are now ready to build Docker MiGrid.


Docker-Swarm
------------

`Docker` and `Docker-Compose` are sufficient when data processing services like DAG or MODI are not planned to be part
of the deployed service. However, if the requirement of data processing via these services present itself, they both require that
their container services is deployed via `Docker Swarm`.

`Docker Swarm` is a multi-host orchestration framework that enables manages the health and lifetime of a particular service across a defined `Docker Swarm` cluster.

In terms of installation, the `Docker Swarm` capability is included by default in the regular `Docker` install,
so no additional steps are needed to be taken in that regard.

However, what is required is that the initial Swarm cluster is setup before any service can be deployed.
How this is achieved can be seen in the <configuration/docker_swarm> section.



Additional Notes
----------------

Note to self, validate that the CentOS 7 install works as expected
