PACKAGE_NAME=docker-migrid
PACKAGE_NAME_FORMATTED=$(subst -,_,$(PACKAGE_NAME))
IMAGE=migrid
OWNER ?= ucphhpc

BUILD_TYPE=basic
# Enable that the builder should use buildkit
# https://docs.docker.com/develop/develop-images/build_enhancements/
DOCKER_BUILDKIT=1
# NOTE: dynamic lookup with docker as default and fallback to podman
DOCKER = $(shell which docker || which podman)
# if compose is not found, try to use it as plugin, eg. RHEL8
DOCKER_COMPOSE = $(shell which docker-compose || which podman-compose || echo 'docker compose')
$(echo ${DOCKER_COMPOSE} >/dev/null)

.PHONY:	all init dockerbuild dockerclean dockerpush clean dist distclean
.PHONY:	stateclean warning
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
	mkdir -p log/migrid
	mkdir -p log/migrid-io
	mkdir -p log/migrid-openid
	mkdir -p log/migrid-sftp
	mkdir -p log/migrid-webdavs
	mkdir -p log/migrid-ftps
	sed 's@#unset @unset @g;s@#export @export @g' migrid-httpd.env > migrid-httpd-init.sh

dockerbuild:
	${DOCKER_COMPOSE} build $(ARGS)

dockerclean:
	# remove latest image and dangling cache entries
	${DOCKER_COMPOSE} down || true
	${DOCKER} rmi -f $(OWNER)/$(IMAGE):$(BUILD_TYPE)
	# remove dangling images and build cache
	${DOCKER} image prune -f

dockerpush:
	${DOCKER} push $(OWNER)/$(IMAGE):$(BUILD_TYPE)

clean:
	rm -fr ./mig
	rm -fr ./httpd

stateclean: warning
	rm -rf ./state

# IMPORTANT: this target is meant to reset the dir to a pristine checkout
#            and thus runs full clean up of even the state dir with user data
#            Be careful NOT to use it on production systems!
distclean: stateclean dockerclean clean
	rm -rf ./certs
	rm -rf ./log
        # TODO: is something like this still needed to clean up completely?
        # It needs to NOT greedily remove ALL local volumes if so!
        #if [ "$$(${DOCKER} volume ls -q -f 'name=${PACKAGE_NAME}*')" != "" ]; then\
        #	${DOCKER} volume rm -f $$(${DOCKER} volume ls -q -f 'name=${PACKAGE_NAME}*');\
        #fi
	rm -f .env docker-compose.yml

warning:
	@echo
	@echo "*** WARNING ***"
	@echo "*** Deleting ALL local state data ***"
	@echo
	@echo "Are you sure? [y/N]" && read ans && [ $${ans:-N} = y ]

uninstallcheck:
### PLACEHOLDER (it's purpose is to uninstall depedencies for check) ###

installcheck:
### PLACEHOLDER (this will install the dependencies for check) ###

check:
### PLACEHOLDER (this will run the repo's self-tests) ###
