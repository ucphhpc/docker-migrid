NAME=docker-migrid
OWNER=ucphhpc
IMAGE=migrid
BUILD_TYPE=basic
# Enable that the builder should use buildkit
# https://docs.docker.com/develop/develop-images/build_enhancements/
DOCKER_BUILDKIT=1

.PHONY:	all init build clean reset push

all: init build

init:
ifeq (,$(wildcard ./.env))
	ln -s defaults.env .env
endif
ifeq (,$(wildcard ./docker-compose.yml))
	echo
	echo "*** No docker-compose.yml selected - defaulting to migrid.test ***"
	echo
	ln -s docker-compose_migrid.test.yml docker-compose.yml
	sleep 5
endif
	mkdir -p certs
	mkdir -p httpd
	mkdir -p mig
	mkdir -p state

build:
	docker-compose build ${ARGS}

clean:
	rm -rf ./httpd
	rm -rf ./mig
	if [ "$$(docker volume ls -q -f 'name=${NAME}*')" != "" ]; then\
		docker volume rm -f $$(docker volume ls -q -f 'name=${NAME}*');\
	fi

dockerclean:
	docker image prune -f
	docker container prune -f
	docker volume prune -f

distclean: dockerclean clean
	rm -rf ./certs
	mkdir -p ./state
	chmod -R u+w ./state
	rm -rf ./state
	if [ "$$(docker volume ls -q -f 'name=${NAME}*')" != "" ]; then\
		docker volume rm -f $$(docker volume ls -q -f 'name=${NAME}*');\
	fi
	rm -f .env docker-compose.yml

reset: distclean


push:
	docker push ${OWNER}/${IMAGE}:${BUILD_TYPE}
