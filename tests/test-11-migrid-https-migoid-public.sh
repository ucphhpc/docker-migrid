#!/bin/bash

source default

${DOCKER:?} run --rm --network host --dns 127.0.0.1 curlimages/curl:8.7.1 \
  --connect-timeout 1 \
  --retry 1 \
  https://${MIGOID_DOMAIN}:${PUBLIC_HTTPS_PORT}/public/index.html \
  -k \
  -s \
  -v \
  --fail \
  -o /dev/null \
  -sw 'HTTP status code: %{http_code}\n' \
  > $(basename "$0").log \
  2>&1

[[ "$?" == 0 ]] && echo -e "${GREEN}passed${ENDCOLOR}" && exit 0
echo -e "${RED}failed${ENDCOLOR}" && exit 1
