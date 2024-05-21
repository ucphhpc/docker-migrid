Rocky 8 Setup
===============

Goal
----
We needed a full-blown setup for running some SSHFS performance benchmarks on an
internet host and decided to do so on Rocky 8.5, which comes with a number of
throughput and crypto performance optimizations compared to our usual CentOS 7
platforms.

Overview
--------
In the particular setup we rely on Rocky 8 running virtualized in KVM
on a physical Rocky 8 host.
The underlying storage is provided by a remote Lustre 2.12 setup but
local storage or another network file system should also do the job.
Communication takes place on a private local network e.g. using a
172.x.y.z address on the first physical network interface.

System Setup
------------
First we set up the basic system to fit our needs with hardening and
dependency installations.

First upgrade all system packages and prevent SELinux interference::

    sudo dnf upgrade
    sed -i 's/SELINUX=enforcing/SELINUX=disabled/g' /etc/selinux/config
    sudo reboot

Then install additional helpers::
  
    sudo dnf install util-linux-user zsh screen nano emacs-nox vim-enhanced \
        net-tools rsyslog stow htop lsof rsync fail2ban ipset wget git make

Make sure the VM has the four or more IPs needed for the most common
virtual migrid hosts (www, sid, io, ext, oid, oidc and cert). The latter two
may be left out if you don't have access to external OpenID 2.0 OpenID
Connect or X509 certificate authentication infrastructure. You can
still use the system with manual user sign up and semi-automatic
operator user account acceptance.

Prepare PodMan version of Docker and Docker Compose::
  
    sudo dnf erase docker docker-compose
    sudo dnf install podman podman-docker podman-compose 
    sudo dnf install fuse-overlayfs

Harden sshd to use strong crypto in line with Mozilla recommendations
and limit remote log in to keys. If possible it's also recommended to
only allow log in through a DMZ jump host.
Please note that Rocky 8 uses a central systemd conf in
/etc/crypto-policies/back-ends/opensshserver.config for configuring
Ciphers, KexAlgorithms and MACs rather than the usual
/etc/sshd/sshd_config. You can remove those and check that the sshd
process does not run with them hard-coded on the command line based
on the output of::
  
    ps ax|grep sshd

TODO: Install logcheck or similar and postfix with authenticity adjustments

Prepare LetsEncrypt certificates with the getssl tool::
  
    VERSION=git-$(date +'%Y%m%d-%H%M%S')
    sudo mkdir -p /usr/local/packages/getssl-$VERSION/sbin
    sudo chown -R $(id -nu) /usr/local/packages/getssl-$VERSION
    cd /usr/local/packages/getssl-$VERSION/sbin
    sudo wget https://raw.githubusercontent.com/srvrco/getssl/master/getssl
    sudo chmod 700 getssl
    sudo chown 0:0 /usr/local/packages/getssl-$VERSION
    cd /usr/local/packages
    sudo stow -v --override='sbin/getssl' getssl-$VERSION

Setup root account for LetsEncrypt use::
  
    wget https://raw.githubusercontent.com/ucphhpc/migrid-sync/edge/mig/install/mig-user/.vimrc
    getssl -c bench.erda.dk
    mkdir -p /etc/httpd/MiG-certificates/letsencrypt
    chmod -R 755 /etc/httpd/MiG-certificates
    {
    echo 'CSR_SUBJECT="/C=DK/O=University of Copenhagen/OU=Benchmark Electronic Research Data Archive/CN=bench.erda.dk"'
    echo "ACL=('/home/mig/state/wwwpublic/letsencrypt/.well-known/acme-challenge')"
    echo 'USE_SINGLE_ACL="true"'
    echo 'SERVER_TYPE="https"'
    echo 'DOMAIN_CERT_LOCATION="/etc/httpd/MiG-certificates/letsencrypt/bench.erda.dk/server.crt"'
    echo 'DOMAIN_KEY_LOCATION="/etc/httpd/MiG-certificates/letsencrypt/bench.erda.dk/server.key"'
    echo 'CA_CERT_LOCATION="/etc/httpd/MiG-certificates/letsencrypt/bench.erda.dk/server.ca.pem"'
    echo 'DOMAIN_CHAIN_LOCATION="/etc/httpd/MiG-certificates/letsencrypt/bench.erda.dk/server.cert.ca.pem"'
    echo 'DOMAIN_PEM_LOCATION="/etc/httpd/MiG-certificates/letsencrypt/bench.erda.dk/server.key.crt.ca.pem"'
    } >> /root/.getssl/bench.erda.dk/getssl.cfg
    sed -i 's/=www.bench.erda.dk/=bench-www.erda.dk,bench-sid.erda.dk,bench-io.erda.dk,bench-ext.erda.dk,bench-oid.erda.dk,bench-oidc.erda.dk,bench-cert.erda.dk/g' /root/.getssl/bench.erda.dk/getssl.cfg

Set up DNS for the 4 or more IPs needed for the virtual hosts
(130.225.104.110-117 used here) and configure the VM network to listen
on those IPs e.g. on the second physical network interface (e.g. eth1
as here)::
  
    {
    echo 'TYPE="Ethernet"'
    echo 'GATEWAY="130.225.104.1"'
    echo 'BOOTPROTO="none"'
    echo 'DEFROUTE="yes"'
    echo 'IPV4_FAILURE_FATAL="no"'
    echo 'IPV6_FAILURE_FATAL="no"'
    echo 'NAME="eth1"'
    echo 'DEVICE="eth1"'
    echo 'ONBOOT="yes"'
    echo 'MTU=1500'
    echo 'NM_CONTROLLED=yes'
    echo 'USERCTL=no'
    echo 'IPV6_AUTOCONF="no"'
    echo 'IPV6INIT="no"'
    echo 'IPADDR="130.225.104.110"'
    echo 'NETMASK="255.255.255.0"'
    echo 'IPADDR2="130.225.104.111"'
    echo 'NETMASK2="255.255.255.0"'
    echo 'IPADDR3="130.225.104.112"'
    echo 'NETMASK3="255.255.255.0"'
    echo 'IPADDR4="130.225.104.113"'
    echo 'NETMASK4="255.255.255.0"'
    echo 'IPADDR5="130.225.104.114"'
    echo 'NETMASK5="255.255.255.0"'
    echo 'IPADDR6="130.225.104.115"'
    echo 'NETMASK6="255.255.255.0"'
    echo 'IPADDR7="130.225.104.116"'
    echo 'NETMASK7="255.255.255.0"'
    echo 'IPADDR8="130.225.104.117"'
    echo 'NETMASK8="255.255.255.0"'
    } > /etc/sysconfig/network-scripts/ifcfg-eth1
    ifup eth1

Make sure the local firewall allows http and https access::

    pgrep firewalld > /dev/null && {
        sudo firewall-cmd --permanent --zone=public --add-service=ssh
        sudo firewall-cmd --permanent --zone=public --add-service=http
        sudo firewall-cmd --permanent --zone=public --add-service=https
        sudo firewall-cmd --reload
    }

Generate initial server certificates with a simple python web server::
  
    mkdir -p /home/mig/state/wwwpublic/letsencrypt/.well-known/acme-challenge
    screen -S simple-httpd -xRD
    cd /home/mig/state/wwwpublic/letsencrypt/
    python3 -m http.server 80 &
    [ctrl-a d]
    getssl --force bench.erda.dk
    screen -S simple-httpd -xRD
    [ctrl-c]
    [ctrl-d]
    cd /etc/httpd/MiG-certificates/
    curl https://ssl-config.mozilla.org/ffdhe4096.txt -o dhparams.pem
    chmod 755 letsencrypt/bench.erda.dk
    ln -s letsencrypt/bench.erda.dk .
    for dom in www sid io ext oid oidc cert; do
        ln -s letsencrypt/bench.erda.dk bench-${dom}.erda.dk;
    done
    ln -s bench.erda.dk/server.crt .
    ln -s bench.erda.dk/server.key .
    openssl rsa -in bench.erda.dk/server.key -text > bench.erda.dk/server.pem
    chmod 400 bench.erda.dk/server.pem
    chown mig:mig bench.erda.dk/combined.pem
    cat bench.erda.dk/server.pem bench.erda.dk/server.cert.ca.pem > bench.erda.dk/combined.pem
    chmod 400 bench.erda.dk/combined.pem
    ssh-keygen -y -f bench.erda.dk/combined.pem > bench.erda.dk/combined.pub
    ln -s bench-io.erda.dk/combined.pem .
    ln -s bench-io.erda.dk/combined.pub .

Prepare an unprivileged `mig` account for running docker-migrid using
the podman docker wrappers. In that relation we need to disable
Jupyter to avoid a problem with support for the complex
JUPYTER_SERVICE_DESC env argument::
  
    sudo adduser mig
    chsh mig -s /usr/bin/zsh
    su - mig
    mv .zshrc{,.orig}
    wget https://raw.githubusercontent.com/ucphhpc/migrid-sync/edge/mig/install/mig-user/.zshrc
    wget https://raw.githubusercontent.com/ucphhpc/migrid-sync/edge/mig/install/mig-user/.vimrc
    . ~/.zshrc
    mkdir -p ~/bin
    cd ~/bin/ && ln -s /usr/bin/podman-compose docker-compose
    git clone https://github.com/ucphhpc/docker-migrid.git docker-migrid
    cd docker-migrid
    ln -s /etc/httpd/MiG-certificates .
    ln -s MiG-certificates certs
    sed 's/dev\([a-z*-]*\)\.erda\.dk/bench\1.erda.dk/g' \
        docker-compose_dev.erda.dk_full.yml > \
        docker-compose_bench.erda.dk_full.yml
    ln -s docker-compose_bench.erda.dk_full.yml docker-compose.yml
    sed 's/dev\([a-z*-]*\)\.erda\.dk/bench\1.erda.dk/g' \
        advanced_dev.erda.dk_full.env | \
        sed 's/^ENABLE_JUPYTER=True/ENABLE_JUPYTER=False/g' > \
        advanced_bench.erda.dk_full.env
    ln -s advanced_bench.erda.dk_full.env .env
    make
    podman-compose -t hostnet up


Lustre
------

Install the Lustre client build dependencies::

  sudo dnf config-manager --set-enabled powertools
  sudo dnf -y groupinstall "Development Tools"
  sudo dnf -y install net-snmp-devel libyaml-devel libselinux-devel libtool
  sudo dnf -y install kernel-devel-$(uname -r) kernel-rpm-macros kernel-abi-whitelists

Build and install the Lustre client::

  VERSION=2.12.8
  git clone git://git.whamcloud.com/fs/lustre-release.git
  cd lustre-release
  git checkout ${VERSION}
  sh ./autogen.sh
  ./configure --disable-server --enable-quota --enable-utils --enable-gss
  make rpms

  sudo yum remove lustre-client.x86_64 kmod-lustre-client.x86_64
  sudo yum localinstall -y ./kmod-lustre-client-${VERSION}-1.el8.x86_64.rpm
  sudo yum localinstall -y ./lustre-client-${VERSION}-1.el8.x86_64.rpm
  sudo mv /etc/lnet.conf.rpmsave /etc/lnet.conf
  sudo service lnet stop
  sudo lustre_rmmod
  sudo service lnet start
  sudo systemctl enable lnet


WAYF OpenID Connect Sign Up and Log In
--------------------------------------
By default the site will use only the locally managed user database
with OpenID 2.0 login through the built-in grid_openid service. One
can configure additional authentication methods like X509 user
certificates or OpenID 2.0 or OpenID Connect from external ID
providers. One such international ID provider with OpenID Connect
access is WAYF (https://www.wayf.dk/). In order to access it for
authentication purposes it is necessary to get in touch with the
WAYF admins and exchange public keys / certificates for the host
authentication involved. This includes a bit of configuration on their
PHPH self-service interface (https://phph.wayf.dk/).

One preparation step is to create a private key and a self-signed
certificate e.g. with `openssl`::

    [root@bench /]# mkdir -p /etc/httpd/MiG-certificates/wayf.dk/4k
    [root@bench /]# cd /etc/httpd/MiG-certificates/wayf.dk/4k
    [root@bench 4k]# openssl req -x509 -newkey rsa:4096 -keyout key.pem \
                                 -out cert.pem -sha256 -days 3650
    Generating a 4096 bit RSA private key
    ....................................................................++
    ........................++
    writing new private key to 'key.pem'
    Enter PEM pass phrase:
    Verifying - Enter PEM pass phrase:
    -----
    You are about to be asked to enter information that will be incorporated
    into your certificate request.
    What you are about to enter is what is called a Distinguished Name or a DN.
    There are quite a few fields but you can leave some blank
    For some fields there will be a default value,
    If you enter '.', the field will be left blank.
    -----
    Country Name (2 letter code) [XX]:DK
    State or Province Name (full name) []:
    Locality Name (eg, city) [Default City]:Copenhagen
    Organization Name (eg, company) [Default Company Ltd]:KU
    Organizational Unit Name (eg, section) []:Science HPC Center
    Common Name (eg, your name or your server's hostname) []:bench-wayf.erda.dk
    Email Address []:
    [root@bench 4k]#


For Apache we may not want to enter passphrase to launch the service.
A key without passphrase can be extracted with::

    openssl rsa -in /etc/httpd/MiG-certificates/wayf.dk/4k/key.pem \
                -out /etc/httpd/MiG-certificates/wayf.dk/4k/key-nopw.pem


Such keys should of course not be generally readable.
So we properly protect them with::

    [root@bench 4k]# chmod 400 key*.pem


We downloaded WAYF's certificate and saved it in
`/etc/httpd/MiG-certificates/wayf.dk/wayf-idp.pem`

After handling the key and auth service setup we configured our site
to allow the WAYF OpenID Connect service as a valid ID provider for
users wanting to access our site as explained
below. Some of the docker-migrid variables needed for the purpose were
added in May 2024. It is tested to work with docker-migrid from late
May and a recent `migrid-sync` version.


In our `.env` file we use these WAYF related variables::

  EXTOIDC_DOMAIN=bench-wayf.erda.dk
  EXT_OIDC_PROVIDER_META_URL="https://${PUBLIC_DOMAIN}/.well-known/wayf-openid-configuration"
  EXT_OIDC_TITLE="WAYF"
  EXT_OIDC_CLIENT_NAME=""
  EXT_OIDC_CLIENT_ID="http://erda.dk"
  EXT_OIDC_SCOPE=""
  EXT_OIDC_REMOTE_USER_CLAIM=sub
  EXT_OIDC_PASS_CLAIM_AS="both"
  EXT_OIDC_PKCE_METHOD=S256
  EXT_OIDC_PROVIDER_ISSUER="https://wayf.wayf.dk"
  EXT_OIDC_PROVIDER_AUTHORIZATION_ENDPOINT="https://wayf.wayf.dk/saml2/idp/SSOService2.php"
  EXT_OIDC_PROVIDER_TOKEN_ENDPOINT="https://wayf.wayf.dk/token"
  EXT_OIDC_PROVIDER_USER_INFO_ENDPOINT="https://wayf.wayf.dk/token"
  EXT_OIDC_PROVIDER_TOKEN_ENDPOINT_AUTH=none
  EXT_OIDC_USER_INFO_TOKEN_METHOD=post_param
  EXT_OIDC_USER_INFO_SIGNED_RESPONSE_ALG=RS256
  EXT_OIDC_COOKIE_SAME_SITE="Off"
  EXT_OIDC_PASS_COOKIES="wayfid"
  EXT_OIDC_RESPONSE_MODE=form_post
  EXT_OIDC_PROVIDER_VERIFY_CERT_FILES="/etc/httpd/MiG-certificates/wayf.dk/wayf-idp.pem"
  EXT_OIDC_PRIVATE_KEY_FILES="wayf#/etc/httpd/MiG-certificates/wayf.dk/4k/key-nopw.pem"
  EXT_OIDC_PUBLIC_KEY_FILES="wayf#/etc/httpd/MiG-certificates/wayf.dk/4k/cert.pem"
  EXT_OIDC_ID_TOKEN_ENCRYPTED_RESPONSE_ALG=RSA-OAEP
  EXT_OIDC_ID_TOKEN_ENCRYPTED_RESPONSE_ENC=A256GCM
  EXT_OIDC_REWRITE_COOKIE="wayfid:wayf-qa:.erda.dk:0:/:true:true"
  EXTOIDC_HTTPS_PORT=443
  SIGNUP_METHODS="migoid extcert extoid extoidc"
  LOGIN_METHODS="migoid extcert extoid extoidc"
  AUTO_ADD_OIDC_USER=True

Please note that there are a few remarks to add about the variable values.

First of all the `EXT_OIDC_CLIENT_ID` is a value negotiated with
WAYF. You'll need your own one to map your site(s) to your WAYF
(self-service) setup. The same applies for the site suffix part of the
`EXT_OIDC_REWRITE_COOKIE` value, where you should replace `.erda.dk`
with your configured domain.

Regarding the key/cert negotiation we have the three CERT and KEY
variables to point to the WAYF certificate plus our own private key
and certificate. The former is `EXT_OIDC_PROVIDER_VERIFY_CERT_FILES` and
the latter is `EXT_OIDC_PRIVATE_KEY_FILES` and
`EXT_OIDC_PUBLIC_KEY_FILES`.

The `EXT_OIDC_PROVIDER_META_URL` value is used to point out a OpenID
Connect specific discovery URL where the service optionally presents
all available settings and parameters. At the time of writing we did
not have such a service from WAYF, so in order to get a more
straight-forward integration we added a mock one in the form of a
simple json file served from our own site.
You should either make your own copy based on data from WAYF or use
any future discovery service they add.

Finally you should decide on a site basis if you want automatic
creation of authenticated users or not with the `AUTO_ADD_OIDC_USER`
variable.
