TLS cert error
--------------

This message appears if nginx is configured as reverse proxy and forwards via HTTPS to a host that speaks plain HTTP::

    nginx-proxy | nginx.1 | 2023/05/25 14:05:37 [error] 27#27: 
          *7 cannot load certificate "data:": PEM_read_bio_X509_AUX() failed 
          (SSL: error:0909006C:PEM routines:get_name:no start line:Expecting: TRUSTED CERTIFICATE)
          while SSL handshaking, client: 192.168.208.1, server: 0.0.0.0:443

This might happen due to some port configuration issue. Might also be possible that multiple VirtualHosts with/without are listening on the same port.

DNS not working
---------------

This error message is likely due to DNS name not resolvable::

    migrid | [Fri May 12 15:46:19.235230 2023] [core:crit] [pid 22] 
          (EAI 2)Name or service not known: AH00077: alloc_listener:
          failed to set up sockaddr for www.example.com


SFTP Subsystem doesn't start
----------------------------

This can happen due to different reasons.
Ensure that:

* Hosts keys are available and that they all have a corresponding pubkey file. Eg. `server.key` and `server.key.pub`
* If the ListenAddress is a hostname, it must be resolvable inside the container to one of its own IPs.
* No other ssh service already uses the same address e.g. because it is configured to bind on all available interfaces (`ListenAddress 0.0.0.0` or `ListenAddress ::`)

DevDNS can't get IPs of containers
----------------------------------

::

    devdns          | E Could not get IP for container 'migrid-webdavs.test'

This error occurs when DevDNS gets a notification of a container in another network.
You can set the network in which DevDNS works with the environment variable `NETWORK=docker-migrid_default` for example.


Docker Compose complains about volume paths
-------------------------------------------

::

    Error response from daemon: invalid mount config for type "bind": invalid mount path: 'docker-migrid_httpd' mount path must be absolute

This error message happens when Docker Compose V2 is used and a target path in one of the volumes contains a **trailing slash**
