PACKAGE_NAME=docker-migrid
PACKAGE_NAME_FORMATTED=$(subst -,_,$(PACKAGE_NAME))
OWNER=ucphhpc
IMAGE=$(PACKAGE_NAME)
BUILD_TYPE=basic
# Enable that the builder should use buildkit
# https://docs.docker.com/develop/develop-images/build_enhancements/
DOCKER_BUILDKIT=1

.PHONY:	all init dockerbuild dockerclean dockerpush clean dist distclean
.PHONY: install uninstall installcheck check

all: init dockerbuild

init:
ifeq (,$(wildcard ./Dockerfile))
	ln -s Dockerfile.centos7 Dockerfile
endif
ifeq (,$(wildcard ./.env))
	ln -s defaults.env .env
endif
ifeq (,$(wildcard ./docker-compose.yml))
	@echo
	@echo "*** No docker-compose.yml selected - defaulting to migrid.test ***"
	@echo
	@ln -s docker-compose_migrid.test.yml docker-compose.yml
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
	rm -fr ./mig
	rm -fr ./httpd

# IMPORTANT: this target is meant to reset the dir to a pristine checkout
#            and thus runs full clean up of even the state dir with user data
#            Be careful NOT to use it on production systems!
distclean: dockerclean clean
	@echo
	@echo "*** WARNING ***"
	@echo "*** Deleting ALL local state data in 10 seconds ***"
	@echo "*** Hit Ctrl-C to abort to preserve any local user and cert data ***"
	@echo
	@sleep 10
	rm -rf ./certs
	mkdir -p ./state
	chmod -R u+w ./state
	rm -rf ./state
        # TODO: is something like this still needed to clean up completely?
        # It needs to NOT greedily remove ALL local volumes if so!
	#if [ "$$(docker volume ls -q -f 'name=${NAME}*')" != "" ]; then\
	#	docker volume rm -f $$(docker volume ls -q -f 'name=${PACKAGE_NAME}*');\
	#fi
	rm -f .env docker-compose.yml

uninstallcheck:
### PLACEHOLDER (it's purpose is to uninstall depedencies for check) ###

installcheck:
### PLACEHOLDER (this will install the dependencies for check) ###

check:
### PLACEHOLDER (this will run the repo's self-tests) ###
