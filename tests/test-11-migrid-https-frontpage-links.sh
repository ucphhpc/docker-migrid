#!/bin/bash

source default

function check_web() {
  URL="$1"
  ${DOCKER:?} run --rm --network host --dns 127.0.0.1 curlimages/curl:8.7.1 \
    --connect-timeout 1 \
    --retry-connrefused \
    --retry 3 \
    -k \
    -s \
    -v \
    --fail \
    -o /dev/null \
    -sw 'HTTP status code: %{http_code}\n' \
    ${URL} \
    > $(basename "$0").log 2>&1
  return $?
}

status=0
for PAGE in terms.html cookie-policy.pdf site-privacy-policy.pdf .well-known/security.txt .well-known/security-disclosure-policy.txt ; do
  check_web "https://${DOMAIN}:${PUBLIC_HTTPS_PORT}/${PAGE}"
  status=$(($status+$?))
done

[[ "$status" == 0 ]] && echo -e "${GREEN}passed${ENDCOLOR}" && exit 0
echo -e "${RED}failed${ENDCOLOR}" && exit 1
