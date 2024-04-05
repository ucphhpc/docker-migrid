Data Analysis Gateway
=====================

Enable DAG
----------

DAG or Data Analysis Gateway is enabled by building a version of the Docker MiGrid image that includes the DAG service. This page contains information on how the DAG service itself is configured if so required.

Configuring DAG
---------------

DAG or Data Analysis Gateway is primarily configured via the supplied `hub/jupyterhub_config.py`.
This can be configured as per the official `JupyterHub <https://jupyterhub.readthedocs.io/en/stable/>` configuration.

This however should not be necessary as a first step, since the supplied pre-configured `hub/jupyterhub_config.py` should cover a basic setup.
