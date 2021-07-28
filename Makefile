NAME=docker-migrid
OWNER=nielsbohr
IMAGE=migrid
BUILD_TYPE=basic
CHECKOUT=5205
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
	docker-compose build --build-arg CHECKOUT=${CHECKOUT} ${ARGS}

clean:
	rm -rf ./certs
	rm -rf ./httpd
	rm -rf ./mig
	rm -rf ./state
	if [ "$$(docker volume ls -q -f 'name=${NAME}*')" != "" ]; then\
		docker volume rm -f $$(docker volume ls -q -f 'name=${NAME}*');\
	fi

reset:
	rm -rf ./certs
	rm -rf ./httpd
	rm -rf ./state
	if [ "$$(docker volume ls -q -f 'name=${NAME}*')" != "" ]; then\
		docker volume rm -f $$(docker volume ls -q -f 'name=${NAME}*');\
	fi

push:
	docker push ${OWNER}/${IMAGE}:${BUILD_TYPE}
