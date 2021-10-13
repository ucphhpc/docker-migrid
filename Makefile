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
	mkdir -p ./state
	chmod -R u+w ./state
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
	mkdir -p ./state
	chmod -R u+w ./state
	rm -rf ./state
	if [ "$$(docker volume ls -q -f 'name=${NAME}*')" != "" ]; then\
		docker volume rm -f $$(docker volume ls -q -f 'name=${NAME}*');\
	fi

push:
	docker push ${OWNER}/${IMAGE}:${BUILD_TYPE}
