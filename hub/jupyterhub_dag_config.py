# Example config
from jhubauthenticators import RegexUsernameParser, JSONParser

c = get_config()

c.JupyterHub.ip = '0.0.0.0'
c.JupyterHub.hub_ip = '0.0.0.0'
c.JupyterHub.port = 80
c.JupyterHub.base_url = '/dag'

# Spawner setup
c.JupyterHub.spawner_class = 'dockerspawner.DockerSpawner'
c.DockerSpawner.image = 'nielsbohr/base-notebook:latest'
c.DockerSpawner.remove_containers = True
c.DockerSpawner.network_name = 'docker-migrid_default'
c.DockerSpawner.environment = {'JUPYTER_ENABLE_LAB': '1'}

# Authenticator setup
c.JupyterHub.authenticator_class = 'jhubauthenticators.HeaderAuthenticator'
c.HeaderAuthenticator.enable_auth_state = True
c.HeaderAuthenticator.allowed_headers = {'auth': 'Remote-User'}
c.HeaderAuthenticator.header_parser_classes = {'auth': RegexUsernameParser}
c.HeaderAuthenticator.user_external_allow_attributes = ['data']

# Email regex
RegexUsernameParser.username_extract_regex = '([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)'
