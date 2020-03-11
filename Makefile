NAME=docker-migrid
OWNER=nielsbohr
IMAGE=migrid
TAG=edge
CHECKOUT=4634

.PHONY:	all init build clean reset push

all: clean init build

init:
	mkdir -p certs
	mkdir -p httpd
	mkdir -p mig
	mkdir -p state

build:
	docker build -t ${OWNER}/${IMAGE}:${TAG} --build-arg CHECKOUT=${CHECKOUT} ${ARGS} .

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
	docker push ${OWNER}/${IMAGE}:${TAG}
