# Example config
import os
from jhub.mount import SSHFSMounter
from jhubauthenticators import RegexUsernameParser, JSONParser

c = get_config()

c.JupyterHub.ip = '0.0.0.0'
c.JupyterHub.hub_ip = '0.0.0.0'
c.JupyterHub.port = 80
c.JupyterHub.base_url = '/dag'

# Spawner setup
c.JupyterHub.spawner_class = 'jhub.SwarmSpawner'
c.SwarmSpawner.jupyterhub_service_name = 'migrid-service_dag'
c.SwarmSpawner.start_timeout = 60 * 10
c.SwarmSpawner.image = 'nielsbohr/base-notebook:latest'
c.SwarmSpawner.networks = ['migrid-service_default']
c.SwarmSpawner.use_user_options = True

home_path = '/home/jovyan'
work_path = os.path.join(home_path, 'work')

mounts = [SSHFSMounter({
    'type': 'volume',
    'driver_config': 'rasmunk/sshfs:latest',
    'driver_options': {'sshcmd': '{sshcmd}', 'id_rsa': '{id_rsa}',
                       'one_time': 'True',
                       'allow_other': '', 'reconnect': '', 'port': '{port}'},
    'source': '',
    'target': work_path})]

c.SwarmSpawner.container_spec = {
    'env': {'JUPYTER_ENABLE_LAB': '1',
            'NOTEBOOK_DIR': work_path},
    'mounts': mounts
}

# Authenticator setup
c.JupyterHub.authenticator_class = 'jhubauthenticators.HeaderAuthenticator'
c.HeaderAuthenticator.enable_auth_state = True
c.HeaderAuthenticator.allowed_headers = {'auth': 'Remote-User'}
c.HeaderAuthenticator.header_parser_classes = {'auth': RegexUsernameParser}
c.HeaderAuthenticator.user_external_allow_attributes = ['data']

# Email regex
RegexUsernameParser.username_extract_regex = '([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)'
RegexUsernameParser.replace_extract_chars = {'@': '_', '.': '_'}
