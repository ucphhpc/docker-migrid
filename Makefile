.PHONY: all init initservices initbuild initdirs initcomposevars clean
.PHONY: distclean sitestateclean sitedataclean dockerclean dockervolumeclean
.PHONY: wipesitestatewarning wipesitedatawarning dockerbuild dockerpush
.PHONY: up stop down
.PHONY: test-doc test-doc-full
.ONESHELL:

PACKAGE_NAME=$(shell basename $$(pwd))
PACKAGE_NAME_FORMATTED=$(subst -,_,$(PACKAGE_NAME))
IMAGE=migrid
OWNER?=ucphhpc
SHELL=/bin/bash
BUILD_ARGS?=
DOCKER_COMPOSE_BUILD_ARGS?=
DETACH?=-d
RUN_ARGS?=${DETACH}

# Enable that the builder should use buildkit
# https://docs.docker.com/develop/develop-images/build_enhancements/
DOCKER_BUILDKIT=1
# NOTE: dynamic lookup with docker as default and fallback to podman
DOCKER = $(shell which docker 2>/dev/null || which podman 2>/dev/null)
# if docker compose plugin is not available, try old docker-compose/podman-compose
ifeq (, $(shell ${DOCKER} help|grep compose))
	DOCKER_COMPOSE = $(shell which docker-compose 2>/dev/null || which podman-compose 2>/dev/null)
else
	DOCKER_COMPOSE = ${DOCKER} compose
endif
$(echo ${DOCKER_COMPOSE} >/dev/null)

-include .env

# If the CONTAINER_REGISTRY is not set/found in the .env file
# then default to docker.io
ifeq ($(CONTAINER_REGISTRY),)
	CONTAINER_REGISTRY = docker.io
endif

# Full dockerclean needs CONTAINER_TAG defined
ifeq ($(CONTAINER_TAG),)
	CONTAINER_TAG = $(shell egrep '^ARG MIG_GIT_BRANCH=' Dockerfile | sed 's/.*=/:/g')
endif

# NOTE: reuse network from active docker-compose in build to limit netfs interference
DOCKER_COMPOSE_BUILD_NET=$(shell egrep 'network(|_mode):' docker-compose.yml 2> /dev/null|egrep -v '^\#'|tail -n 1|sed 's/.*network.*:/network:/g')

# Path helpers to init after loading .env
LOG_ROOT?=log
VOLATILE_ROOT?=volatile
PERSISTENT_ROOT?=persistent

define DOCKER_COMPOSE_SHARED_HEADER
services:
  migrid-shared:
    image: $${CONTAINER_REGISTRY}/ucphhpc/migrid$${CONTAINER_TAG}
    build:
      context: ./
      dockerfile: Dockerfile
      $(DOCKER_COMPOSE_BUILD_NET)
      args:
endef
export DOCKER_COMPOSE_SHARED_HEADER


all: init dockerbuild

init: initbuild initdirs
	@echo "using ${DOCKER_COMPOSE} as compose command"

initbuild: Dockerfile .env docker-compose.yml migrid-httpd-init.sh
	@echo "initialised environment for build"

Dockerfile:
	@echo
	@echo "*** No Dockerfile selected - defaulting to rocky9 ***"
	@echo
	ln -s Dockerfile.rocky9 Dockerfile
	@sleep 2

.env:
	@echo
	@echo "*** No deployment environment selected - defaulting to development ***"
	@echo
	ln -s development.env .env
	@sleep 2

docker-compose.yml:
	@echo
	@echo "*** No docker-compose.yml selected - defaulting to development ***"
	@echo
	ln -s docker-compose_development.yml docker-compose.yml
	@sleep 2

migrid-httpd-init.sh:
	sed 's@#unset @unset @g;s@#export @export @g' migrid-httpd.env > migrid-httpd-init.sh

initdirs: initcomposevars
	mkdir -p external-certificates
	mkdir -p certs
	mkdir -p httpd
	mkdir -p mig
	mkdir -p state
	mkdir -p ${VOLATILE_ROOT}/mig_system_run
	mkdir -p ${VOLATILE_ROOT}/openid_store
	mkdir -p ${PERSISTENT_ROOT}/freeze_home
	mkdir -p ${PERSISTENT_ROOT}/mrsl_files
	mkdir -p ${PERSISTENT_ROOT}/resource_home
	mkdir -p ${PERSISTENT_ROOT}/re_home
	mkdir -p ${PERSISTENT_ROOT}/sharelink_home
	mkdir -p ${PERSISTENT_ROOT}/events_home
	mkdir -p ${PERSISTENT_ROOT}/sitestats_home
	mkdir -p ${PERSISTENT_ROOT}/sandbox_home
	mkdir -p ${PERSISTENT_ROOT}/sss_home
	mkdir -p ${PERSISTENT_ROOT}/workflows_db_home
	mkdir -p ${PERSISTENT_ROOT}/workflows_home
	mkdir -p ${PERSISTENT_ROOT}/user_db_home
	mkdir -p ${PERSISTENT_ROOT}/user_home
	mkdir -p ${PERSISTENT_ROOT}/user_settings
	mkdir -p ${PERSISTENT_ROOT}/vgrid_files_home
	mkdir -p ${PERSISTENT_ROOT}/vgrid_files_readonly
	mkdir -p ${PERSISTENT_ROOT}/vgrid_files_writable
	mkdir -p ${PERSISTENT_ROOT}/vgrid_home
	mkdir -p ${PERSISTENT_ROOT}/vgrid_private_base
	mkdir -p ${PERSISTENT_ROOT}/vgrid_public_base
	mkdir -p ${PERSISTENT_ROOT}/wwwpublic-archives
	mkdir -p ${PERSISTENT_ROOT}/wwwpublic-vgrid
	mkdir -p ${PERSISTENT_ROOT}/wwwpublic-download
	mkdir -p ${PERSISTENT_ROOT}/secrets
	mkdir -p ${LOG_ROOT}/miglog
	mkdir -p ${LOG_ROOT}/migrid
	mkdir -p ${LOG_ROOT}/migrid-io
	mkdir -p ${LOG_ROOT}/migrid-openid
	mkdir -p ${LOG_ROOT}/migrid-sftp
	mkdir -p ${LOG_ROOT}/migrid-webdavs
	mkdir -p ${LOG_ROOT}/migrid-ftps

initcomposevars:
	@echo "creating env variable map in docker-compose_shared.yml"
	@[ -r .env ] || echo "ERROR: no .env file found. Run 'make init' first."
	@echo "$$DOCKER_COMPOSE_SHARED_HEADER" > docker-compose_shared.yml
	@grep -v '\(^#.*\|^$$\)' .env >> docker-compose_shared.yml
	@sed -E -i 's!^([^=]*)=.*!        - \1=\$$\{\1\}!' docker-compose_shared.yml

initservices:
	@ENABLED_SERVICES="migrid"
	@for service in $$(${DOCKER_COMPOSE} config --services 2>/dev/null); do
		# NOTE: Enable all non-migrid services found in docker-compose file
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
	@echo $$ENABLED_SERVICES > ./.migrid_enabled_services

up:	initcomposevars initservices
	${DOCKER_COMPOSE} up ${RUN_ARGS} $(shell head -n1 .migrid_enabled_services)

down:	initcomposevars
	# NOTE: To suppress podman warnings about missing containers use:
	# ${DOCKER_COMPOSE} down $(file < ./.migrid_enabled_services)
	# NOTE: 'docker-compose down' doesn't support a list of services
	${DOCKER_COMPOSE} down

dockerbuild: init
	${DOCKER_COMPOSE} ${DOCKER_COMPOSE_BUILD_ARGS} build ${BUILD_ARGS}

dockerclean: initcomposevars
	${DOCKER_COMPOSE} down || true
	# remove latest image and dangling cache entries
	${DOCKER} rmi -f ${CONTAINER_REGISTRY}/$(OWNER)/$(IMAGE)${CONTAINER_TAG}
	# remove dangling images and build cache
	${DOCKER} image prune -f
	${DOCKER} builder prune -f || true

logs:	initcomposevars
	${DOCKER_COMPOSE} logs


dockerpushwarning:
	@if [ "${CONTAINER_REGISTRY}" == "docker.io" ]; then \
		echo
		echo "*** WARNING ***"
		echo "*** Pushing to docker.io ***"
		echo "*** This will make the $(OWNER)/$(IMAGE)${CONTAINER_TAG} image publicly available ***"
		echo "*** Any secrets in the $(OWNER)/$(IMAGE)${CONTAINER_TAG} image, such as passwords/salts set via environment variables/file(s), will be exposed ***"
		echo "*** Make sure that the $(OWNER)/$(IMAGE)${CONTAINER_TAG} image does not contain any such secrets before proceeding ***"
		echo
		echo "Are you sure you want to push $(OWNER)/$(IMAGE)${CONTAINER_TAG} to ${CONTAINER_REGISTRY}? [y/N]" && read ans && [ $${ans:-N} = y ]; \
	fi

dockerpush: dockerpushwarning
	${DOCKER} push ${CONTAINER_REGISTRY}/$(OWNER)/$(IMAGE)${CONTAINER_TAG}

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

sitestateclean: wipesitestatewarning
	rm -rf --one-file-system ./state
	# NOTE: never follow VOLATILE_ROOT values outside root dir!
	@echo "Force unmounting ${VOLATILE_ROOT} to prevent deleting outside ${DOCKER_MIGRID_ROOT}"
	umount ./${VOLATILE_ROOT} > /dev/null 2>&1 || true
	rm -rf --one-file-system ./${VOLATILE_ROOT}

sitedataclean: wipesitedatawarning
	# NOTE: never follow PERSISTENT_ROOT or LOG_ROOT values outside root dir!
	@echo "Force unmounting ${PERSISTENT_ROOT} to prevent deleting outside ${DOCKER_MIGRID_ROOT}"
	umount ./${PERSISTENT_ROOT} > /dev/null 2>&1 || true
	rm -rf --one-file-system ./${PERSISTENT_ROOT}
	@echo "Force unmounting ${LOG_ROOT} to prevent deleting outside ${DOCKER_MIGRID_ROOT}"
	umount ./${LOG_ROOT} > /dev/null 2>&1 || true
	rm -rf --one-file-system ./${LOG_ROOT}

# IMPORTANT: this target is meant to reset the dir to a pristine checkout
#            and thus runs full clean up of even the state dirs with user data
#            Be careful NOT to use it on production systems!
distclean: clean sitestateclean sitedataclean dockerclean dockervolumeclean
	rm -fr ./external-certificates
	# NOTE: certs remove in clean is conditional - always remove it here
	rm -fr ./certs
	rm -f .env docker-compose.yml Dockerfile

wipesitestatewarning:
	@echo
	@echo "*** Warning ***"
	@echo "This will permanently delete ALL data in state and ${VOLATILE_ROOT}"
	@echo
	@echo "Are you sure? [y/N]" && read ans && [ $${ans:-N} = y ]

wipesitedatawarning:
	@echo
	@echo "*** WARNING ***"
	@echo ""
	@echo "This will permanently delete ALL data in ${LOG_ROOT} and ${PERSISTENT_ROOT} !"
	@echo
	@echo "Are you really sure? [y/N]" && read ans && [ $${ans:-N} = y ]

# Test that all defined env variables are properly documented
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

# Internal helper to check if any of the Dockerfile ARGs should perhaps be
# added in env and then documented as per the test-doc target.
test-doc-full:
	@shopt -s extglob; \
	for i in $$( grep -E '^ARG [^=]+=' Dockerfile.* | sed -E 's!^Dockerfile\..+:ARG ([^=]+)=.*$$!\1!g'| grep -E -v "^(ARCH|TINI_VERSION)$$"  | sort | uniq ) ; do \
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
