NAME=docker-migrid
OWNER=nielsbohr
IMAGE=migrid
BUILD_TYPE=basic
BUILD_TARGET=development
DOMAIN=migrid.test
MIG_SVN_REV=5243
EMULATE_FLAVOR=idmc
EMULATE_FQDN=idmc.dk
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
	docker-compose build --build-arg BUILD_TYPE=${BUILD_TYPE} --build-arg BUILD_TARGET=${BUILD_TARGET} --build-arg DOMAIN=${DOMAIN} --build-arg MIG_SVN_REV=${MIG_SVN_REV} --build-arg EMULATE_FLAVOR=${EMULATE_FLAVOR} --build-arg EMULATE_FQDN=${EMULATE_FQDN} ${ARGS}

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
