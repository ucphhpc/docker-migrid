
## DNS not working

migrid          | [Fri May 12 15:46:19.235230 2023] [core:crit] [pid 22] (EAI 2)Name or service not known: AH00077: alloc_listener: failed to set up sockaddr for www.dstor.it.ku.dk
```

This error message is likely due to DNS name not resolveable

## SFTP Subsystem doesn't start

This can happen due to different reasons.
Ensure that:

* Hosts keys are available and that they all have a corresponding pubkey file. Eg. `server.key` and `server.key.pub`
* If the ListenAddress is a hostname, it must be resolvable inside the container to one of its own IPs.

## DevDNS cannt get IPs of containers

`devdns          | E Could not get IP for container 'migrid-webdavs.test'`

This error occures when DevDNS get a notification of a container in another network.
You can set the network in which DevDNS works with the enviroment variable `NETWORK=docker-migrid_default` for example.
