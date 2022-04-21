PACKAGE_NAME=docker-migrid
PACKAGE_NAME_FORMATTED=$(subst -,_,$(PACKAGE_NAME))
OWNER=ucphhpc
IMAGE=$(PACKAGE_NAME)
# Enable that the builder should use buildkit
# https://docs.docker.com/develop/develop-images/build_enhancements/
DOCKER_BUILDKIT=1
BUILD_TYPE=basic

.PHONY: all init dockerbuild dockerclean dockerpush clean dist distclean
.PHONY: install uninstall installcheck check

all: init dockerbuild

init:
ifeq ($(shell test -e defaults.env && echo yes), yes)
ifneq ($(shell test -e .env && echo yes), yes)
		ln -s defaults.env .env
endif
endif
ifeq (,$(wildcard ./docker-compose.yml))
	@echo
	@echo "*** No docker-compose.yml selected - defaulting to migrid.test ***"
	@echo
	ln -s docker-compose_migrid.test.yml docker-compose.yml
	@sleep 5
endif
	mkdir -p certs
	mkdir -p httpd
	mkdir -p mig
	mkdir -p state

dockerbuild:
	docker-compose build $(ARGS) 

dockerclean:
	docker rmi -f $(OWNER)/$(IMAGE):$(BUILD_TYPE)

dockerpush:
	docker push $(OWNER)/$(IMAGE):$(BUILD_TYPE)

clean:
	$(MAKE) dockerclean
	$(MAKE) distclean
	rm -fr ./mig

distclean:
	rm -rf ./certs
	mkdir -p ./httpd
	chmod -R u+w ./httpd
	rm -fr ./httpd
	mkdir -p ./state
	chmod -R u+w ./state
	rm -rf ./state
	if [ "$$(docker volume ls -q -f 'name=${NAME}*')" != "" ]; then\
		docker volume rm -f $$(docker volume ls -q -f 'name=${NAME}*');\
	fi
	rm -f .env docker-compose.yml

uninstallcheck:
### PLACEHOLDER (it's purpose is to uninstall depedencies for check) ###

installcheck:
### PLACEHOLDER (this will install the dependencies for check) ###

check:
### PLACEHOLDER (this will run the repo's self-tests) ###
