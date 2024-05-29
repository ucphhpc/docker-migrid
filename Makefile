.PHONY: all init initservices initbuild initdirs initcomposevars clean warning
.PHONY: dockerclean dockervolumeclean distclean stateclean dockerbuild dockerpush
.PHONY: up stop down
.PHONY: test-doc
.ONESHELL:

PACKAGE_NAME=docker-migrid
PACKAGE_NAME_FORMATTED=$(subst -,_,$(PACKAGE_NAME))
IMAGE=migrid
OWNER ?= ucphhpc
SHELL=/bin/bash

# Enable that the builder should use buildkit
# https://docs.docker.com/develop/develop-images/build_enhancements/
DOCKER_BUILDKIT=1
# NOTE: dynamic lookup with docker as default and fallback to podman
DOCKER = $(shell which docker 2>/dev/null || which podman 2>/dev/null)
# if docker compose plugin is not available, try old docker-compose/podman-compose
ifeq (, $(${DOCKER} help|grep compose))
	DOCKER_COMPOSE = $(shell which docker-compose 2>/dev/null || which podman-compose 2>/dev/null)
else
	DOCKER_COMPOSE = docker compose
endif
$(echo ${DOCKER_COMPOSE} >/dev/null)

define DOCKER_COMPOSE_SHARED_HEADER
services:
  migrid-shared:
    image: ucphhpc/migrid$${CONTAINER_TAG}
    build:
      context: ./
      dockerfile: Dockerfile
      args:
endef
export DOCKER_COMPOSE_SHARED_HEADER

ifeq ("$(wildcard .env)",".env")
	include .env
endif

# Full dockerclean needs CONTAINER_TAG defined
ifeq ("CONTAINER_TAG","")
	CONTAINER_TAG=":${MIG_GIT_BRANCH}"
endif


all: init dockerbuild

init:	initbuild initdirs initcomposevars
	@echo "using ${DOCKER_COMPOSE} as compose command"

initbuild:
ifeq (,$(wildcard ./Dockerfile))
	@echo
	@echo "*** No Dockerfile selected - defaulting to centos7 ***"
	@echo
	ln -s Dockerfile.centos7 Dockerfile
	@sleep 2
endif
ifeq (,$(wildcard ./.env))
	@echo
	@echo "*** No deployment environment selected - defaulting to development ***"
	@echo
	ln -s development.env .env
	@sleep 2
endif
ifeq (,$(wildcard ./docker-compose.yml))
	@echo
	@echo "*** No docker-compose.yml selected - defaulting to development ***"
	@echo
	ln -s docker-compose_development.yml docker-compose.yml
	@sleep 2
endif
	sed 's@#unset @unset @g;s@#export @export @g' migrid-httpd.env > migrid-httpd-init.sh

initdirs:
	mkdir -p external-certificates
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

initcomposevars:
	@echo "creating env variable map in docker-compose_shared.yml"
	@[ -f .env ] || echo "ERROR: no .env file found. Run 'make init' first."
	@echo "$$DOCKER_COMPOSE_SHARED_HEADER" > docker-compose_shared.yml
	@grep -v '\(^#.*\|^$$\)' .env >> docker-compose_shared.yml
	@sed -E -i 's!^([^=]*)=.*!        - \1=\$$\{\1\}!' docker-compose_shared.yml

initservices:
	@ENABLED_SERVICES="migrid"
	@for service in $$(${DOCKER_COMPOSE} config --services 2>/dev/null); do
		# NOTE: Enable alle non-migrid services found in docker-compose file
		@if [[ "$${service:0:6}" != "migrid" ]]; then
			@ENABLED_SERVICES+=" $$service"
		@fi
		@if [[ "$$service" == "migrid-openid" \
				&& "${ENABLE_OPENID}" == "True" ]]; then
			@ENABLED_SERVICES+=" $$service"
		@fi
		@if [[ "$$service" == "migrid-sftp" ]]; then
				@if [[ "${ENABLE_SFTP}" == "True" \
						|| "${ENABLE_SFTP_SUBSYS}" == "True" ]]; then
					@ENABLED_SERVICES+=" $$service"
				@fi
		@fi
		@if [[ "$$service" == "migrid-ftps" \
				&& "${ENABLE_FTPS}" == "True" ]]; then
			@ENABLED_SERVICES+=" $$service"
		@fi
		@if [[ "$$service" == "migrid-webdavs" \
				&& "${ENABLE_DAVS}" == "True" ]]; then
			@ENABLED_SERVICES+=" $$service"
		@fi
		@if [[ "$$service" == "migrid-lustre-quota" \
				&& "${ENABLE_QUOTA}" == "True" ]]; then
			@ENABLED_SERVICES+=" $$service"
		@fi
	@done;
	@echo $$ENABLED_SERVICES > ./.enabled_services

up:	initcomposevars initservices
	${DOCKER_COMPOSE} up -d $(file < ./.enabled_services)

down:	initcomposevars
	# NOTE: To surpress podman warnings about missing containers use:
	# ${DOCKER_COMPOSE} down $(file < ./.enabled_services)
	# NOTE: 'docker-compose down' doesn't support a list of services
	${DOCKER_COMPOSE} down

dockerbuild: init
	${DOCKER_COMPOSE} build $(ARGS)

dockerclean: initcomposevars
	# remove latest image and dangling cache entries
	${DOCKER_COMPOSE} down || true
	${DOCKER} rmi -f $(OWNER)/$(IMAGE)${CONTAINER_TAG}
	# remove dangling images and build cache
	${DOCKER} image prune -f
	${DOCKER} builder prune -f || true

logs:	initcomposevars
	${DOCKER_COMPOSE} logs

dockerpush:
	${DOCKER} push $(OWNER)/$(IMAGE)${CONTAINER_TAG}

dockervolumeclean:
	@if [ "$$(${DOCKER} volume ls -q -f 'name=${PACKAGE_NAME}*')" != "" ]; then \
		echo "Removing volumes with name ${PACKAGE_NAME}*:"; \
		${DOCKER} volume rm -f $$(${DOCKER} volume ls -q -f 'name=${PACKAGE_NAME}*'); \
	fi

clean:
	rm -f docker-compose_shared.yml
	rm -fr ./mig
	rm -fr ./httpd
	# NOTE: certs may be injected or symlink to externally maintained dir.
	#       Only remove it here if that's not the case.
	[ -L ./certs ] || [ -f ./certs/.persistent ] || rm -fr ./certs

stateclean: warning
	rm -rf ./state

# IMPORTANT: this target is meant to reset the dir to a pristine checkout
#            and thus runs full clean up of even the state dir with user data
#            Be careful NOT to use it on production systems!
distclean: stateclean clean dockerclean dockervolumeclean
	rm -fr ./external-certificates
	rm -rf ./log
	# NOTE: certs remove in clean is conditional - always remove it here
	rm -fr ./certs
	rm -f .env docker-compose.yml

warning:
	@echo
	@echo "*** WARNING ***"
	@echo "*** Deleting ALL local state data ***"
	@echo
	@echo "Are you sure? [y/N]" && read ans && [ $${ans:-N} = y ]

test-doc:
	@shopt -s extglob; \
	for i in $$( grep -hv '\(^#.*\|^$$\)' !(migrid-httpd).env | sed -E 's!^([^=]*)=.*$$!\1!g' | sort | uniq ) ; do \
		grep -q "$$i" doc/source/sections/configuration/variables.rst \
		|| missing+=( "$$i" ) ; \
	done; \
	[ "$${#missing[@]}" != "0" ] && echo "ERROR: Missing documentation in doc/source/sections/configuration/variables.rst for:" \
	&& for i in $${missing[@]}; do \
		echo "  $$i"; \
	done && exit 1 \
	|| echo "OK: found all environment variables in documentation" && exit 0

test:
	@cd tests; \
		export DOCKER=${DOCKER}; \
		err=0; \
		for test in test-*.sh ; do \
			bash ./$${test} || err=$$?; \
			if [ $$err != 0 ]; then \
				cat $${test}.log; \
				exit $$err; \
			fi; \
		done;
