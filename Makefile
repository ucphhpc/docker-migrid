OWNER=nielsbohr
IMAGE=migrid
TAG=edge
CHECKOUT=4207

build:
	mkdir -p ./certs
	mkdir -p ./httpd
	mkdir -p ./mig
	mkdir -p ./state
	docker build -t ${OWNER}/${IMAGE}:${TAG} --build-arg MIG_CHECKOUT=${CHECKOUT} .

clean:
	rm -rf ./certs
	rm -rf ./httpd
	rm -rf ./mig
	rm -rf ./state
	if [ "$$(docker volume ls -q -f 'name=docker-migrid*')" != "" ]; then\
		docker volume rm -f $$(docker volume ls -q -f 'name=docker-migrid*');\
	fi

reset:
	rm -rf ./certs
	rm -rf ./httpd
	rm -rf ./state
	if [ "$$(docker volume ls -q -f 'name=docker-migrid*')" != "" ]; then\
		docker volume rm -f $$(docker volume ls -q -f 'name=docker-migrid*');\
	fi

push:
	docker push ${OWNER}/${IMAGE}:${TAG}

all: clean build
