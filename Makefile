IMAGE=migrid
TAG=edge

build:
	docker build -t ${IMAGE}:${TAG} .
