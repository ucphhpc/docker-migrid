Docker Swarm
============

In this section, an example will be prestented for how a Docker Swarm cluster could be configured.
The reason for creating such a cluster, is that it is a prerequisites for data processing services such a DAG or MODI.

Before we get started, ensure that you meet the Docker prerequisites mentioned in <getting-started/prerequisites.rst>

Creating a Cluster
------------------

To get a detailed tutorial for how a cluster is created please have a look at `Docker Swarm <https://docs.docker.com/engine/swarm/swarm-tutorial/create-swarm/>`_

The short edition of this, is first to initialize a particular host with the cluster. This will both create the cluster and establish the host as a Manager node in that cluster::
    docker swarm init --advertise-addr <MANAGER-IP>

The <MANAGER-IP> being the address of the host interface where the cluster should operate.

After this has been succesfully completed, if additional nodes are to be part of this cluster, they can now be added by generating a join command from the initial Manager node.
This is achieved by utilizing the `docker swarm join-token` command. There are two variants of this command, one for establing the additional node as either a Manager or a Worker node::

    # Generate the token for a Manager node
    docker swarm join-token manager
    To add a manager to this swarm, run the following command:

        docker swarm join --token <GENERATED-TOKEN> <MANAGER-IP:PORT>


    # Generate the token for a worker node
    docker swarm join-token worker
    To add a worker to this swarm, run the following command:

        docker swarm join --token <GENERATED-TOKEN> <MANAGER-IP:PORT>


After adding the required number of nodes, the final cluster configuration can be seen with the following command::

    docker node ls
    ID                            HOSTNAME         STATUS    AVAILABILITY   MANAGER STATUS   ENGINE VERSION
    otqkjun26to4mkxbfk5huuyfn     dag001           Ready     Active         Reachable        20.10.7
    fwms0jm2xrj5drl8hh5yx1v35     dag002           Ready     Active         Leader           20.10.7
    wsp9qrp94y3x2e3viqe2ckvjp     dag003           Ready     Active                          20.10.7

