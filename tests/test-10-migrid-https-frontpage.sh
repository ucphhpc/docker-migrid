#!/bin/bash

source default

${DOCKER:?} run --rm --network host curlimages/curl:8.2.1 \
  --connect-timeout 1 \
  --retry 1 \
  https://${DOMAIN}:${PUBLIC_HTTPS_PORT} \
  -k \
  -s \
  -v \
  -o /dev/null \
  -sw 'HTTP status code: %{http_code}\n' \
  > $(basename "$0").log \
  2>&1

[[ "$?" == 0 ]] && echo -e "${GREEN}passed${ENDCOLOR}" && exit 0
echo -e "${RED}failed${ENDCOLOR}" && exit 1
