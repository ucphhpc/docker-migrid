#!/bin/bash
# Script used to deploy the JupyterHub service

docker stack deploy --compose-file docker-compose_dag.yml jupyter-service