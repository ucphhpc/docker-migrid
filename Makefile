OWNER=nielsbohr
IMAGE=migrid
TAG=edge

all: clean build push

build:
	mkdir -p ./certs
	mkdir -p ./httpd
	mkdir -p ./mig
	mkdir -p ./state
	docker build -t ${OWNER}/${IMAGE}:${TAG} .

clean:
	rm -rf ./certs
	rm -rf ./httpd
	rm -rf ./mig
	rm -rf ./state
	if [ "$$(docker volume ls -q -f 'name=docker-migrid*')" != "" ]; then\
		docker volume rm -f $$(docker volume ls -q -f 'name=docker-migrid*');\
	fi
push:
	docker push ${OWNER}/${IMAGE}:${TAG}
