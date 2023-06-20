TLS cert error
--------------

This message apprears if nginx is configured as reverse proxy and forwards via HTTPS to a host that speaks plain HTTP::

    nginx-proxy | nginx.1 | 2023/05/25 14:05:37 [error] 27#27: 
          *7 cannot load certificate "data:": PEM_read_bio_X509_AUX() failed 
          (SSL: error:0909006C:PEM routines:get_name:no start line:Expecting: TRUSTED CERTIFICATE)
          while SSL handshaking, client: 192.168.208.1, server: 0.0.0.0:443

This might happen due to some port configuration issue. Might also be possible that multiple VirtualHosts with/without are listinging on the same port.

DNS not working
---------------

This error message is likely due to DNS name not resolveable::

    migrid | [Fri May 12 15:46:19.235230 2023] [core:crit] [pid 22] 
          (EAI 2)Name or service not known: AH00077: alloc_listener:
          failed to set up sockaddr for www.example.com


SFTP Subsystem doesn't start
----------------------------

This can happen due to different reasons.
Ensure that:

* Hosts keys are available and that they all have a corresponding pubkey file. Eg. `server.key` and `server.key.pub`
* If the ListenAddress is a hostname, it must be resolvable inside the container to one of its own IPs.

DevDNS cannt get IPs of containers
----------------------------------

::

    devdns          | E Could not get IP for container 'migrid-webdavs.test'

This error occures when DevDNS get a notification of a container in another network.
You can set the network in which DevDNS works with the enviroment variable `NETWORK=docker-migrid_default` for example.
