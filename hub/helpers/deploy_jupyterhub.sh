#!/bin/bash
# Script used to deploy the JupyterHub service
source hub/setup_jup_crypt_secrets.sh
docker stack deploy --compose-file docker-compose_dag.yml jupyter-service
