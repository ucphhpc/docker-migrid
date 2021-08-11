Building
========

To build the Docker version of MiGrid, the repository provides a Makefile that helps you out.

Quick Start
-----------

If you are not interested in learning what goes into building the image, the easiest way to get started, is to simply run `make` inside the `docker-migrid` directory::

    make

This should produces the following output::

    rm -rf ./certs
    rm -rf ./httpd
    rm -rf ./mig
    rm -rf ./state
    if [ "$(docker volume ls -q -f 'name=docker-migrid*')" != "" ]; then\
            docker volume rm -f $(docker volume ls -q -f 'name=docker-migrid*');\
        fi
    mkdir -p certs
    mkdir -p httpd
    mkdir -p mig
    mkdir -p state
    docker-compose build
    WARNING: Python-dotenv could not parse statement starting at line 5
    devdns uses an image, skipping
    nginx-proxy uses an image, skipping
    Building migrid
    [+] Building 38.6s (13/75)
    ...

In addition to the above output, several build lines should follow as the Docker container image is being build.
The entire process should be succesfully completed, when the following lines have been printed::


     => => naming to docker.io/nielsbohr/migrid:basic                                                                                                0.0s
    Use 'docker scan' to run Snyk tests against images to find vulnerabilities and learn how to fix them


Additional Details
------------------

When building the Docker MiGrid container image, several things are being done in addition to just producing the target `docker-migrid` image.
An indication of this can be seen by investigating the `Makefile` itself::

    :docker-migrid username$cat Makefile
    NAME=docker-migrid
    OWNER=nielsbohr
    IMAGE=migrid
    BUILD_TYPE=basic
    # Enable that the builder should use buildkit
    # https://docs.docker.com/develop/develop-images/build_enhancements/
    DOCKER_BUILDKIT=1

    .PHONY:	all init build clean reset push

    all: clean init build

    init:
        mkdir -p certs
        mkdir -p httpd
        mkdir -p mig
        mkdir -p state

    build:
        docker-compose build ${ARGS}

    clean:
        rm -rf ./certs
        rm -rf ./httpd
        rm -rf ./mig
        rm -rf ./state
        if [ "$$(docker volume ls -q -f 'name=${NAME}*')" != "" ]; then\
            docker volume rm -f $$(docker volume ls -q -f 'name=${NAME}*');\
        fi

    dockerclean:
        docker image prune -f
        docker container prune -f
        docker volume prune -f

    reset:
        rm -rf ./certs
        rm -rf ./httpd
        rm -rf ./state
        if [ "$$(docker volume ls -q -f 'name=${NAME}*')" != "" ]; then\
            docker volume rm -f $$(docker volume ls -q -f 'name=${NAME}*');\
        fi

    push:
        docker push ${OWNER}/${IMAGE}:${BUILD_TYPE}

For starters, when `make` is being executed within the directory. The directory is firstly being cleaned of any old state data that might be hanging around from the last build.
This is achived by executing the `clean` target within the `Makefile`. The clean target removes the runtime directories and all of the associated docker volumes that is used to store persistent data between runtimes::


    :docker-migrid username$ make clean
    rm -rf ./certs
    rm -rf ./httpd
    rm -rf ./mig
    rm -rf ./state
    if [ "$(docker volume ls -q -f 'name=docker-migrid*')" != "" ]; then\
            docker volume rm -f $(docker volume ls -q -f 'name=docker-migrid*');\
    fi

Specifically, for building the `migrid` Docker image for the first time, an empty `mig` directory should be present inside the repository directory.

To accomplish this, the Makefile provides an init target, that creates the `mig` directory in addition to a set of directories that are required when the service is deployed.
An example output from running the `make init` can be seen below::

    $:docker-migrid username$ make init
    mkdir -p certs
    mkdir -p httpd
    mkdir -p mig
    mkdir -p state


