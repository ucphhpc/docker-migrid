OWNER=nielsbohr
IMAGE=migrid
TAG=edge

CHECKOUT=4207

all: init build

init:
	mkdir -p ./{certs,httpd,mig,state}

build:
	docker build -t ${OWNER}/${IMAGE}:${TAG} --build-arg MIG_CHECKOUT=${CHECKOUT} .

clean:
	rm -rf ./certs
	rm -rf ./httpd
	rm -rf ./mig
	rm -rf ./state
	if [ "$$(docker volume ls -q -f 'name=migrid-service*')" != "" ]; then\
		docker volume rm -f $$(docker volume ls -q -f 'name=migrid-service*');\
	fi

reset:
	rm -rf ./certs
	rm -rf ./httpd
	rm -rf ./state
	if [ "$$(docker volume ls -q -f 'name=migrid-service*')" != "" ]; then\
		docker volume rm -f $$(docker volume ls -q -f 'name=migrid-service*');\
	fi

push:
	docker push ${OWNER}/${IMAGE}:${TAG}
