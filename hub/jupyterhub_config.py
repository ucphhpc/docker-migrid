# DAG config)
import os
from jhub.mount import SSHFSMounter
from jhubauthenticators import RegexUsernameParser, JSONParser

c = get_config()

c.JupyterHub.spawner_class = "jhub.SwarmSpawner"
c.JupyterHub.ip = "0.0.0.0"
c.JupyterHub.hub_ip = "0.0.0.0"
c.JupyterHub.base_url = "/DAG"

# Config required to seperate the proxy from JupyterHub
c.JupyterHub.cleanup_proxy = False
c.JupyterHub.cleanup_servers = False

# number of allowed servers, 0 means unlimited
c.JupyterHub.active_server_limit = 0

# First pulls can be really slow, so let's give it a big timeout
c.SwarmSpawner.start_timeout = 60 * 10

# Docker services typically can take up to ~15 seconds to spawn while the default `slow_spawn_timeout` is 10
# https://github.com/jupyterhub/jupyterhub/blob/9990100f896afbd80526e020905bec0a746f0a24/jupyterhub/handlers/base.py#L723
c.JupyterHub.tornado_settings = {"slow_spawn_timeout": 20}

c.SwarmSpawner.jupyterhub_service_name = "jupyter-service_jupyterhub"
c.SwarmSpawner.networks = ["jupyter-service_default"]

# Paths
home_path = os.path.join(os.sep, "home", "jovyan")
mount_dirs = ["work", "erda_mount"]
root_dir = {}

for dir in mount_dirs:
    path = os.path.join(home_path, dir)
    dag_config_path = os.path.join(path, "__dag_config__")
    r_libs_path = os.path.join(dag_config_path, "R", "libs")
    python2_path = os.path.join(dag_config_path, "python2")
    python3_path = os.path.join(dag_config_path, "python3")

    root_dir[dir] = {
        "path": path,
        "__dag_config__": dag_config_path,
        "r_libs": r_libs_path,
        "python2": python2_path,
        "python3": python3_path,
    }

conda_path = os.path.join(os.sep, "opt", "conda")
before_notebook_path = os.path.join(os.sep, "usr", "local", "bin", "before-notebook.d")
start_notebook_path = os.path.join(os.sep, "usr", "local", "bin", "start-notebook.d")
r_env_path = os.path.join(conda_path, "envs", "r")
r_environ_path = os.path.join(r_env_path, "lib", "R", "etc", "Renviron")
r_conf_path = os.path.join(os.sep, "etc", "rstudio", "rserver.conf")
jupyter_share_path = os.path.join(conda_path, "share", "jupyter")

user_uid = "1000"
user_gid = "100"

configs = [
    {
        "config_name": "jupyter-service_extensions_config",
        "filename": os.path.join(
            jupyter_share_path, "lab", "settings", "page_config.json"
        ),
        "uid": user_uid,
        "gid": user_gid,
        "mode": 0o440,
    },
    {
        "config_name": "jupyter-service_create_ipython_start_configs",
        "filename": os.path.join(
            before_notebook_path, "create_ipython_profile_start.py"
        ),
        "uid": user_uid,
        "gid": user_gid,
        "mode": 0o555,
    },
    {
        "config_name": "jupyter-service_create_r_libs_path_config",
        "filename": os.path.join(before_notebook_path, "create_r_libs_path_config.py"),
        "uid": user_uid,
        "gid": user_gid,
        "mode": 0o555,
    },
    {
        "config_name": "jupyter-service_set_jupyter_kernels_config",
        "filename": os.path.join(before_notebook_path, "set_jupyter_kernels.py"),
        "uid": user_uid,
        "gid": user_gid,
        "mode": 0o555,
    },
    {
        "config_name": "jupyter-service_set_python_pip_aliases_config",
        "filename": os.path.join(before_notebook_path, "set_pip_aliases.py"),
        "uid": user_uid,
        "gid": user_gid,
        "mode": 0o555,
    },
    {
        "config_name": "jupyter-service_r_environ_config",
        "filename": r_environ_path,
        "uid": user_uid,
        "gid": user_gid,
        "mode": 0o440,
    },
    {
        "config_name": "jupyter-service_r_server_config",
        "filename": r_conf_path,
        "uid": user_uid,
        "gid": user_gid,
        "mode": 0o440,
    },
    {
        "config_name": "jupyter-service_update_path_env_config",
        "filename": os.path.join(os.sep, "jupyter_startup_files", "update_path_env.py"),
        "uid": user_uid,
        "gid": user_gid,
        "mode": 0o555,
    },
]

append_to_notebook_configs = [
    {
        "config_name": "migrid-service_append_to_notebook_config",
        "filename": os.path.join(before_notebook_path, "append_to_notebook_config.py"),
        "uid": user_uid,
        "gid": user_gid,
        "mode": 0o555,
    }
]

c.SwarmSpawner.configs = configs

mounts = [
    SSHFSMounter(
        {
            "type": "volume",
            "driver_config": "ucphhpc/sshfs:latest",
            "driver_options": {
                "sshcmd": "{sshcmd}",
                "id_rsa": "{id_rsa}",
                "port": "{port}",
                "one_time": "True",
                "allow_other": "",
                "reconnect": "",
                "ServerAliveInterval": "120",
            },
            "source": "",
            "target": root_dir["work"]["path"],
        }
    )
]

# NOTE: Used for eg. updating packages
jupyter_hooks_mounts = [
    {
        "type": "bind",
        "source": "/etc/jupyter/hooks/start-notebook.d",
        "target": start_notebook_path,
    }
]

# Add bind masks to prevent access to specific binaries
# NOTE: This is only ment to block binaries temporarily until
# next image re-build where these binaries should be updated or removed
security_mask_mounts = [
    {"type": "bind", "source": "/dev/null", "target": "/usr/bin/sudo"},
    {"type": "bind", "source": "/dev/null", "target": "/usr/bin/sudoreplay"},
    {"type": "bind", "source": "/dev/null", "target": "/usr/bin/sudoedit"},
]
mounts += security_mask_mounts

# 'args' is the command to run inside the service
# IPYTHON_STARTUP_DIR is required by the `jupyter-service-create_ipython
# start_configs` for the destination directory
c.SwarmSpawner.container_spec = {
    "env": {
        "JUPYTER_ENABLE_LAB": "1",
        "IPYTHON_STARTUP_DIR": "/jupyter_startup_files",
        "NOTEBOOK_DIR": root_dir["work"]["path"],
        "R_LIBS_USER": root_dir["work"]["r_libs"],
        "R_ENVIRON_USER": r_environ_path,
        "JUPYTER_KERNEL_PYTHON2_ENV_PYTHONUSERBASE": root_dir["work"]["python2"],
        "JUPYTER_KERNEL_PYTHON3_ENV_PYTHONUSERBASE": root_dir["work"]["python3"],
    },
    "command": "start-notebook.sh",
    "args": ["--NotebookApp.default_url=/lab"],
}

# Before the user can select which image to spawn,
# user_options has to be enabled
c.SwarmSpawner.use_user_options = True

# Available docker images the user can spawn
c.SwarmSpawner.images = [
    {
        "image": "nielsbohr/datascience-notebook:latest",
        "name": "Datascience Notebook with Python",
        "mounts": mounts,
    },
    {
        "image": "nielsbohr/r-notebook:latest",
        "name": "R Notebook with R-Studio",
        "mounts": mounts,
    },
    {
        "image": "nielsbohr/gpu-notebook:latest",
        "name": "AI Notebook",
        "mounts": mounts,
    }
]

# Authenticator setup
c.JupyterHub.authenticator_class = "jhubauthenticators.HeaderAuthenticator"
c.HeaderAuthenticator.enable_auth_state = True
c.HeaderAuthenticator.allowed_headers = {"auth": "Remote-User"}
c.HeaderAuthenticator.header_parser_classes = {"auth": RegexUsernameParser}
c.HeaderAuthenticator.user_external_allow_attributes = ["data"]

# Email regex
RegexUsernameParser.username_extract_regex = (
    "([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)"
)
RegexUsernameParser.replace_extract_chars = {"@": "_", ".": "_"}

# Service that checks for inactive notebooks
# Defaults to kill services that hasn't been used for 2 hour
c.JupyterHub.services = [
    {
        "name": "cull-idle",
        "admin": True,
        "command": "python3 cull_idle_servers.py --timeout=7200 --protected_users={},{}".format(
            dgx_db_access_path, gpu_ai_db_access_path
        ).split(),
    }
]