FROM centos:latest

# Centos image default yum configs prevent docs installation
# https://superuser.com/questions/784451/centos-on-docker-how-to-install-doc-files
RUN sed -i '/nodocs/d' /etc/yum.conf

RUN yum update -y \
    && yum install -y \
    httpd \
    htop \
    openssh \
    crontabs \
    epel-release \
    nano \
    mod_ssl \
    mod_wsgi \
    mod_proxy \
    mod_auth_openid \
    tzdata \
    initscripts \
    svn \
    vimdiff \
    net-tools \
    telnet \
    ca-certificates \
    openssh-server \
    mercurial \
    python-dev

# Apache OpenID (provided by epel)
RUN yum install -y mod_auth_openid

# Setup user
ENV USER=mig
ENV UID=1000
ENV GID=1000

RUN groupadd -g $GID $USER
RUN useradd -u $UID -g $GID -ms /bin/bash $USER

ARG DOMAIN=migrid.test
# MiG environment
ENV MIG_ROOT=/home/$USER
ENV WEB_DIR=/etc/httpd
ENV CERT_DIR=$WEB_DIR/MiG-certificates

USER root

RUN mkdir -p $CERT_DIR/MiG/*.$DOMAIN \
    && chown $USER:$USER $CERT_DIR \
    && chmod 775 $CERT_DIR

# Setup certs and keys
# Dhparam
RUN openssl dhparam 2048 -out $CERT_DIR/dhparams.pem

# CA
# https://gist.github.com/Soarez/9688998
RUN openssl genrsa -des3 -passout pass:qwerty -out ca.key 2048 \
    && openssl rsa -passin pass:qwerty -in ca.key -out ca.key \
    && openssl req -x509 -new -key ca.key \
    -subj "/C=XX/L=Default City/O=Default Company Ltd/CN=oid.${DOMAIN}" -out ca.crt \
    && openssl req -x509 -new -nodes -key ca.key -sha256 -days 1024 \
    -subj "/C=XX/L=Default City/O=Default Company Ltd/CN=oid.${DOMAIN}" -out ca.pem

# Server key/ca
# https://gist.github.com/Soarez/9688998
RUN openssl genrsa -out server.key 2048 \
    && openssl req -new -key server.key -out server.csr \
    -subj "/C=XX/L=Default City/O=Default Company Ltd/CN=oid.${DOMAIN}" \
    && openssl x509 -req -days 365 -in server.csr -signkey server.key -out server.crt

# CRL
RUN touch /etc/pki/CA/index.txt \
    && echo '00' > /etc/pki/CA/crlnumber \
    && openssl ca -gencrl -keyfile ca.key -cert ca.pem -out crl.pem

# Daemon keys
RUN cat server.{key,crt} > combined.pem \
    && chown $USER:$USER combined.pem \
    && ssh-keygen -y -f combined.pem > combined.pub \
    && chown 0:0 *.key server.crt ca.pem \
    && chmod 400 *.key server.crt ca.pem combined.pem

# Prepare keys for mig
RUN mv server.crt $CERT_DIR/MiG/*.$DOMAIN/ \
    && mv server.key $CERT_DIR/MiG/*.$DOMAIN/ \
    && mv crl.pem $CERT_DIR/MiG/*.$DOMAIN/ \
    && mv ca.pem $CERT_DIR/MiG/*.$DOMAIN/cacert.pem \
    && mv combined.pem $CERT_DIR/MiG/*.$DOMAIN/ \
    && mv combined.pub $CERT_DIR/MiG/*.$DOMAIN/

WORKDIR $CERT_DIR

RUN ln -s MiG/*.$DOMAIN/server.crt server.crt \
    && ln -s MiG/*.$DOMAIN/server.key server.key \
    && ln -s MiG/*.$DOMAIN/crl.pem crl.pem \
    && ln -s MiG/*.$DOMAIN/cacert.pem cacert.pem \
    && ln -s MiG/*.$DOMAIN/combined.pem combined.pem \
    && ln -s MiG/*.$DOMAIN/combined.pub combined.pub \
    && ln -s MiG/*.$DOMAIN io.migrid.test

WORKDIR $MIG_ROOT
USER $USER

RUN mkdir -p MiG-certificates \
    && cd MiG-certificates \
    && ln -s $CERT_DIR/MiG/*.$DOMAIN/cacert.pem cacert.pem \
    && ln -s $CERT_DIR/MiG MiG \
    && ln -s $CERT_DIR/combined.pem combined.pem \
    && ln -s $CERT_DIR/combined.pub combined.pub \
    && ln -s $CERT_DIR/dhparams.pem dhparams.pem

# Prepare OpenID
RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py \
    && python get-pip.py --user

ENV PATH=$PATH:/home/$USER/.local/bin
RUN pip install --user https://github.com/openid/python-openid/archive/master.zip

# Modules required by grid_events.py
RUN pip install --user \
    watchdog \
    scandir

# Modules required by grid_sftp.py
RUN pip install --user \
    paramiko

# Modules required by grid_webdavs
RUN pip install --user \
    wsgidav \
    CherryPy

# Modules required by grid_ftps
RUN pip install --user \
    pyftpdlib

# Modules required by jupyter
RUN pip install --user \
    requests

# Install and configure MiG
ARG MIG_CHECKOUT=4199
RUN svn checkout -r $MIG_CHECKOUT https://svn.code.sf.net/p/migrid/code/trunk .

ADD mig $MIG_ROOT/mig

USER root
RUN chown -R $USER:$USER $MIG_ROOT/mig

USER $USER

WORKDIR $MIG_ROOT/mig/install

RUN ./generateconfs.py \
    --source=. \
    --destination=generated-confs \
    --destination_suffix="_svn$(svnversion -n ~/)" \
    --apache_etc=/etc/httpd \
    --apache_run=/var/run/httpd \
    --apache_lock=/var/lock/subsys/httpd \
    --apache_log=/var/log/httpd \
    --distro=centos \
    --mig_state=/home/mig/state \
    --listen_clause=#Listen \
    --enable_events=True \
    --enable_crontab=True \
    --enable_imnotify=True \
    --enable_hsts=True \
    --enable_jupyter=True \
    --enable_sftp_subsys=True \
    --jupyter_services="modi.http://modi" \
    --jupyter_services_desc="{'modi': 'Hello from modi'}" \
    --base_fqdn=$DOMAIN \
    --public_fqdn=www.$DOMAIN \
    --public_port=80 \
    --mig_cert_fqdn= \
    --mig_cert_port= \
    --ext_cert_fqdn= \
    --ext_cert_port= \
    --mig_oid_fqdn=oid.$DOMAIN \
    --mig_oid_port=443 \
    --ext_oid_fqdn= \
    --ext_oid_port= \
    --sid_fqdn=sid.$DOMAIN \
    --sid_port=444 \
    --io_fqdn=io.$DOMAIN \
    --user=mig \
    --group=mig \
    --hg_path=/usr/bin/hg \
    --hgweb_scripts=/usr/share/doc/mercurial-2.6.2 \
    --trac_admin_path= \
    --trac_ini_path= \
    --enable_openid=True \
    --enable_wsgi=True \
    --serveralias_clause=#ServerAlias \
    --mig_oid_provider=https://oid.$DOMAIN/openid/ \
    --signup_methods="migoid" \
    --login_methods="migoid" \
    --alias_field='email' \
    --daemon_show_address=io.$DOMAIN \
    --mig_certs=/etc/httpd/MiG-certificates \
    --dhparams_path=~/certs/dhparams.pem \
    --daemon_keycert=~/certs/combined.pem \
    --landing_page=/wsgi-bin/fileman.py \
    --skin=idmc-basic

RUN cp generated-confs/MiGserver.conf $MIG_ROOT/mig/server/ \
    && cp generated-confs/static-skin.css $MIG_ROOT/mig/images/ \
    && cp generated-confs/index.html $MIG_ROOT/state/user_home/

# Enable jupyter menu
RUN sed -i -e 's/#user_menu =/user_menu = jupyter/g' $MIG_ROOT/mig/server/MiGserver.conf \
    && sed -i -e 's/loglevel = info/loglevel = debug/g' $MIG_ROOT/mig/server/MiGserver.conf

# Prepare oiddiscover for httpd
RUN cd $MIG_ROOT/mig \
    && python shared/httpsclient.py | grep -A 80 "xml version" \
    > $MIG_ROOT/state/wwwpublic/oiddiscover.xml

USER root

# Sftp subsys config
RUN cp generated-confs/sshd_config-MiG-sftp-subsys /etc/ssh/ \
    && chown 0:0 /etc/ssh/sshd_config-MiG-sftp-subsys

RUN chmod 755 generated-confs/envvars \
    && chmod 755 generated-confs/httpd.conf

# Automatic inclusion confs
RUN cp generated-confs/MiG.conf $WEB_DIR/conf.d/ \
    && cp generated-confs/httpd.conf $WEB_DIR/ \
    && cp generated-confs/mimic-deb.conf $WEB_DIR/conf/httpd.conf \
    && cp generated-confs/envvars /etc/sysconfig/httpd \
    && cp generated-confs/apache2.service /lib/systemd/system/httpd.service

# Root confs
RUN cp generated-confs/apache2.conf $WEB_DIR/ \
    && cp generated-confs/ports.conf $WEB_DIR/ \
    && cp generated-confs/envvars $WEB_DIR/

# Jupyter apache confs
RUN mkdir -p $WEB_DIR/conf.extras.d \
    && cp generated-confs/MiG-jupyter-def.conf $WEB_DIR/conf.extras.d \
    && cp generated-confs/MiG-jupyter-openid.conf $WEB_DIR/conf.extras.d \
    && cp generated-confs/MiG-jupyter-proxy.conf $WEB_DIR/conf.extras.d/ \
    && cp generated-confs/MiG-jupyter-rewrite.conf $WEB_DIR/conf.extras.d/

# Disable certificate check for OID
RUN sed -i '/\/server.ca.pem/ a SSLProxyCheckPeerName off' $WEB_DIR/conf.d/MiG.conf \
    && sed -i '/SSLProxyCheckPeerName off/ a SSLProxyCheckPeerCN off' \
    $WEB_DIR/conf.d/MiG.conf

# Front page
RUN ln -s $MIG_ROOT/state/wwwpublic/index-idmc.dk.html $MIG_ROOT/state/wwwpublic/index.html \
    && chown -R $USER:$USER $MIG_ROOT/state/wwwpublic/index.html

# Replace index.html redirects to development domain RUN
# Default non KU login to oid.$DOMAIN instead of ext.$DOMAIN
RUN sed -i -e "s/idmc.dk/$DOMAIN/g" $MIG_ROOT/state/wwwpublic/index.html \
    && sed -i -e "s/ext.$DOMAIN/oid.$DOMAIN/g" $MIG_ROOT/state/wwwpublic/index.html

# State clean services
RUN chmod 755 generated-confs/{migstateclean,migerrors} \
    && cp generated-confs/{migstateclean,migerrors} /etc/cron.daily/

# Init scripts
RUN cp generated-confs/migrid-init.d-rh /etc/init.d/migrid

WORKDIR $MIG_ROOT

# Prepare default conf.d
RUN mv $WEB_DIR/conf.d/autoindex.conf $WEB_DIR/conf.d/autoindex.conf.centos \
    && mv $WEB_DIR/conf.d/ssl.conf $WEB_DIR/conf.d/ssl.conf.centos \
    && mv $WEB_DIR/conf.d/userdir.conf $WEB_DIR/conf.d/userdir.conf.centos \
    && mv $WEB_DIR/conf.d/welcome.conf $WEB_DIR/conf.d/welcome.conf.centos

# Add generated certificate to trust store
RUN update-ca-trust force-enable \
    && cp $CERT_DIR/combined.pem /etc/pki/ca-trust/source/anchors/ \
    && update-ca-trust extract

# Reap defuncted/orphaned processes
ARG TINI_VERSION=v0.18.0
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini /tini
RUN chmod +x /tini
ENTRYPOINT ["/tini", "--"]

ADD docker-entry.sh /app/docker-entry.sh
ADD migrid-httpd.env /app/migrid-httpd.env
RUN chown $USER:$USER /app/docker-entry.sh \
    && chmod +x /app/docker-entry.sh

USER root
WORKDIR /app

EXPOSE 80 443

CMD ["bash", "/app/docker-entry.sh"]
