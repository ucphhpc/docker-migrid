OWNER=nielsbohr
IMAGE=migrid
TAG=edge

build:
	docker build -t ${OWNER}/${IMAGE}:${TAG} .
push:
	docker push ${OWNER}/${IMAGE}:${TAG}
