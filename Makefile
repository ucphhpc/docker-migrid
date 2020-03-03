OWNER=nielsbohr
IMAGE=migrid
TAG=edge

CHECKOUT=4588

all: init build

init:
	mkdir -p certs
	mkdir -p httpd
	mkdir -p mig
	mkdir -p state
	mkdir -p MiG-exe

build:
	docker build -t ${OWNER}/${IMAGE}:${TAG} --build-arg CHECKOUT=${CHECKOUT} .

clean:
	rm -rf ./certs
	rm -rf ./httpd
	rm -rf ./mig
	rm -rf ./state
	rm -fr ./MiG-exe
	if [ "$$(docker volume ls -q -f 'name=migrid-service*')" != "" ]; then\
		docker volume rm -f $$(docker volume ls -q -f 'name=migrid-service*');\
	fi
	if [ "$$(docker volume ls -q -f 'name=_MiG')" != "" ]; then\
		docker volume rm -f $$(docker volume ls -q -f 'name=_MiG');\
	fi

reset:
	rm -rf ./certs
	rm -rf ./httpd
	rm -rf ./state
	rm -fr ./MiG-exe
	if [ "$$(docker volume ls -q -f 'name=migrid-service*')" != "" ]; then\
		docker volume rm -f $$(docker volume ls -q -f 'name=migrid-service*');\
	fi
	if [ "$$(docker volume ls -q -f 'name=_MiG')" != "" ]; then\
		docker volume rm -f $$(docker volume ls -q -f 'name=_MiG');\
	fi

push:
	docker push ${OWNER}/${IMAGE}:${TAG}
