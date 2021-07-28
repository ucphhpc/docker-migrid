FROM centos:7

# Centos image default yum configs prevent docs installation
# https://superuser.com/questions/784451/centos-on-docker-how-to-install-doc-files
RUN sed -i '/nodocs/d' /etc/yum.conf

RUN yum update -y \
    && yum install -y epel-release \
    && yum clean all \
    && rm -fr /var/cache/yum

RUN yum update -y \
    && yum install -y \
    gcc \
    pam-devel \
    httpd \
    htop \
    openssh \
    crontabs \
    nano \
    mod_ssl \
    mod_wsgi \
    mod_proxy \
    mod_auth_openid \
    tzdata \
    initscripts \
    svn \
    vim \
    net-tools \
    telnet \
    ca-certificates \
    mercurial \
    openssh-server \
    openssh-clients \
    rsyslog \
    lsof \
    python-pip \
    python-devel \
    python-paramiko \
    python-enchant \
    python-jsonrpclib \
    python-requests \
    python2-psutil \
    python-future \
    python2-cffi \
    pysendfile \
    PyYAML \
    pyOpenSSL \
    cracklib-python \
    cracklib-devel \
    lftp \
    rsync \
    fail2ban \
    ipset


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
# Dhparam - generate yourself for production or use pregenerated one for test
#RUN openssl dhparam 4096 -out $CERT_DIR/dhparams.pem
RUN curl https://ssl-config.mozilla.org/ffdhe4096.txt -o $CERT_DIR/dhparams.pem

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
    && cat server.crt > server.ca.pem \
    && cat ca.pem >> server.ca.pem \
    && chown $USER:$USER combined.pem \
    && chown $USER:$USER server.ca.pem \
    && ssh-keygen -y -f combined.pem > combined.pub \
    && chown 0:0 *.key server.crt ca.pem \
    && chmod 400 *.key server.crt ca.pem combined.pem server.ca.pem

# Prepare keys for mig
RUN mv server.crt $CERT_DIR/MiG/*.$DOMAIN/ \
    && mv server.key $CERT_DIR/MiG/*.$DOMAIN/ \
    && mv crl.pem $CERT_DIR/MiG/*.$DOMAIN/ \
    && mv ca.pem $CERT_DIR/MiG/*.$DOMAIN/cacert.pem \
    && mv combined.pem $CERT_DIR/MiG/*.$DOMAIN/ \
    && mv combined.pub $CERT_DIR/MiG/*.$DOMAIN/ \
    && mv server.ca.pem $CERT_DIR/MiG/*.$DOMAIN/

WORKDIR $CERT_DIR

RUN ln -s MiG/*.$DOMAIN/server.crt server.crt \
    && ln -s MiG/*.$DOMAIN/server.key server.key \
    && ln -s MiG/*.$DOMAIN/crl.pem crl.pem \
    && ln -s MiG/*.$DOMAIN/cacert.pem cacert.pem \
    && ln -s MiG/*.$DOMAIN/combined.pem combined.pem \
    && ln -s MiG/*.$DOMAIN/server.ca.pem server.ca.pem \
    && ln -s MiG/*.$DOMAIN/combined.pub combined.pub \
    && ln -s MiG/*.$DOMAIN www.$DOMAIN \
    && ln -s MiG/*.$DOMAIN cert.$DOMAIN \
    && ln -s MiG/*.$DOMAIN ext.$DOMAIN \
    && ln -s MiG/*.$DOMAIN oid.$DOMAIN \
    && ln -s MiG/*.$DOMAIN io.$DOMAIN \
    && ln -s MiG/*.$DOMAIN sid.$DOMAIN

# Upgrade pip, required by cryptography
RUN python -m pip install -U pip==20.3.4

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
ENV PATH=$PATH:/home/$USER/.local/bin
RUN pip install --user python-openid

# Modules required by grid_events.py
RUN pip install --user \
    watchdog \
    scandir

# Modules required by grid_sftp.py
# NOTE: we use yum version for now
#RUN pip install --user \
#    paramiko

# Modules required by grid_webdavs
# TODO: upgrade wsgidav to latest once we run Python 3
#RUN pip install --user \
#    wsgidav \
#    CherryPy
# NOTE: we require <=1.3.0 for now
RUN pip install --user \
    wsgidav==1.3.0

# Modules required by grid_ftps
# NOTE: relies on pyOpenSSL and Cryptography from yum for now
RUN pip install --user \
    pyftpdlib

# Modules required by jupyter
RUN pip install --user \
    requests

# Module required to run pytests
# 4.6 is the latest with python2 support
RUN pip install --user \
    pytest

# NOTE: we use yum version for now
#RUN pip install --user \
#    future

# Modules required by 2FA
RUN pip install --user \
    pyotp==2.3.0

# Support sftp cracklib check
# NOTE: we use yum version for now
#RUN pip install --user \
#    cracklib

# Install and configure MiG
ARG CHECKOUT=5205
RUN svn checkout -r $CHECKOUT https://svn.code.sf.net/p/migrid/code/trunk .

ADD mig $MIG_ROOT/mig

USER root
RUN chown -R $USER:$USER $MIG_ROOT/mig

USER $USER

ENV PYTHONPATH=${MIG_ROOT}
# Ensure that the $USER sets it during session start
RUN echo "PYTHONPATH=${MIG_ROOT}" >> ~/.bash_profile \
    && echo "export PYTHONPATH" >> ~/.bash_profile

WORKDIR $MIG_ROOT/mig/install

RUN ./generateconfs.py --source=. \
    --destination=generated-confs \
    --destination_suffix="_svn$(svnversion -n ~/)" \
    --base_fqdn=$DOMAIN \
    --public_fqdn=www.$DOMAIN \
    --mig_cert_fqdn=cert.$DOMAIN \
    --ext_cert_fqdn= \
    --mig_oid_fqdn=ext.$DOMAIN \
    --ext_oid_fqdn= \
    --sid_fqdn=sid.$DOMAIN \
    --io_fqdn=io.$DOMAIN \
    --user=mig --group=mig \
    --apache_version=2.4 \
    --apache_etc=/etc/httpd \
    --apache_run=/var/run/httpd \
    --apache_lock=/var/lock/subsys/httpd \
    --apache_log=/var/log/httpd \
    --openssh_version=7.2 \
    --mig_code=/home/mig/mig \
    --mig_state=/home/mig/state \
    --mig_certs=/etc/httpd/MiG-certificates \
    --hg_path=/usr/bin/hg \
    --hgweb_scripts=/usr/share/doc/mercurial-common/examples \
    --trac_admin_path=/usr/bin/trac-admin \
    --trac_ini_path=/home/mig/mig/server/trac.ini \
    --public_http_port=80 --public_https_port=443 \
    --mig_oid_port=444 --ext_oid_port=445 \
    --mig_cert_port=446 --ext_cert_port=447 \
    --sid_port=448 \
    --sftp_port=2222 --sftp_subsys_port=22222 \
    --mig_oid_provider=https://ext.$DOMAIN/openid/ \
    --ext_oid_provider= \
    --enable_openid=True --enable_wsgi=True \
    --enable_sftp=True --enable_sftp_subsys=True \
    --enable_davs=True --enable_ftps=True \
    --enable_sharelinks=True --enable_transfers=True \
    --enable_duplicati=True --enable_seafile=False \
    --enable_sandboxes=False --enable_vmachines=False \
    --enable_crontab=True --enable_jobs=True \
    --enable_resources=True --enable_events=True \
    --enable_freeze=False --enable_imnotify=False \
    --enable_twofactor=True --enable_cracklib=True \
    --enable_notify=True --enable_preview=False \
    --enable_workflows=False --enable_hsts=True \
    --enable_vhost_certs=True --enable_verify_certs=True \
    --enable_jupyter=False \
    --user_clause=User --group_clause=Group \
    --listen_clause='#Listen' \
    --serveralias_clause='ServerAlias' --alias_field=email \
    --dhparams_path=~/certs/dhparams.pem \
    --daemon_keycert=~/certs/combined.pem \
    --daemon_pubkey=~/certs/combined.pub \
    --daemon_pubkey_from_dns=False \
    --daemon_show_address=io.$DOMAIN \
    --signup_methods="extoid migoid migcert" \
    --login_methods="extoid migoid migcert" \
    --distro=centos \
    --skin=idmc-basic --short_title="MiGrid-Test" \
    --apache_worker_procs=128 --wsgi_procs=25

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

# Disable certificate check for OID
RUN sed -i '/\/server.ca.pem/ a SSLProxyCheckPeerName off' $WEB_DIR/conf.d/MiG.conf \
    && sed -i '/SSLProxyCheckPeerName off/ a SSLProxyCheckPeerCN off' \
    $WEB_DIR/conf.d/MiG.conf

# Front page
RUN ln -s index-idmc.dk.html $MIG_ROOT/state/wwwpublic/index.html && \
    ln -s about-idmc.dk.html $MIG_ROOT/state/wwwpublic/about-snippet.html && \
    ln -s support-idmc.dk.html $MIG_ROOT/state/wwwpublic/support-snippet.html && \
    ln -s tips-idmc.dk.html $MIG_ROOT/state/wwwpublic/tips-snippet.html && \
    ln -s terms-idmc.dk.html $MIG_ROOT/state/wwwpublic/terms-snippet.html && \
    chown -R $USER:$USER $MIG_ROOT/state/wwwpublic/*.html

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
