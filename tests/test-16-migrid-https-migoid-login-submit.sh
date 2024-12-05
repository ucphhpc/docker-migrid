#!/bin/bash

source default

${DOCKER:?} run --rm --network host --dns 127.0.0.1 curlimages/curl:8.7.1 \
  --connect-timeout 1 \
  --retry-connrefused \
  --retry 3 \
  --data-urlencode user=${MIG_TEST_USER} \
  --data-urlencode password=${MIG_TEST_USER_PASSWORD} \
  --data-urlencode success_to=/openid/id/ \
  --data-urlencode submit=yes \
  https://${OPENID_DOMAIN}:${OPENID_PORT}/openid/loginsubmit \
  -k \
  -L \
  -v \
  -b cookies -c cookies \
  -sw 'HTTP status code: %{http_code}\n' \
  > $(basename "$0").log \
  2>&1

[[ "$?" == 0 ]] && echo -e "${GREEN}passed${ENDCOLOR}" && exit 0
echo -e "${RED}failed${ENDCOLOR}" && exit 1
