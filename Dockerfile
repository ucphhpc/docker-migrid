FROM centos:latest

RUN yum update -y \
    && yum upgrade -y \
    && yum install -y \
    httpd \
    crontabs \
    nano \
    mod_ssl \
    mod_wsgi \
    tzdata \
    initscripts \
    svn \
    vimdiff

# Setup user
ENV USER=mig
RUN useradd -ms /bin/bash $USER

# MIG environment
ENV MIG_ROOT=/home/$USER
ENV VERSION=3986

# Clone into $USER home
WORKDIR $MIG_ROOT
USER $USER

RUN svn checkout -r $VERSION https://svn.code.sf.net/p/migrid/code/trunk .

# Install
ENV WEB_DIR=/etc/httpd

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
    --enable_events=False

RUN cp generated-confs/MiGserver.conf $MIG_ROOT/mig/server/ \
    && cp generated-confs/static-skin.css $MIG_ROOT/mig/images/ \
    && cp generated-confs/index.html $MIG_ROOT/state/user_home/

USER root

RUN chmod 755 generated-confs/envvars \
    && chmod 755 generated-confs/httpd.conf

# Automatic inclusion confs
RUN cp generated-confs/MiG.conf $WEB_DIR/conf.d/ \
    && cp generated-confs/httpd.conf $WEB_DIR/ \
    && cp generated-confs/mimic-deb.conf $WEB_DIR/conf/httpd.conf \
    && cp generated-confs/envvars /etc/sysconfig/httpd \
    && cp generated-confs/apache2.service /lib/systemd/system/httpd.service

## Root confs
RUN cp generated-confs/apache2.conf $WEB_DIR/ \
    && cp generated-confs/ports.conf $WEB_DIR/ \
    && cp generated-confs/MiG-jupyter.conf $WEB_DIR/ \
    && cp generated-confs/MiG-jupyter-def.conf $WEB_DIR/ \
    && cp generated-confs/envvars $WEB_DIR/

# State clean services
RUN chmod 755 generated-confs/{migstateclean,migerrors} \
    && cp generated-confs/{migstateclean,migerrors} /etc/cron.daily/

WORKDIR $MIG_ROOT

# Create CA
# https://gist.github.com/Soarez/9688998
RUN openssl genrsa -des3 -passout pass:qwerty -out ca.key 2048 \
    && openssl rsa -passin pass:qwerty -in ca.key -out ca.key \
    && openssl req -x509 -new -key ca.key \
    -subj "/C=XX/L=Default City/O=Default Company Ltd/CN=localhost" -out ca.crt \
    && openssl req -x509 -new -nodes -key ca.key -sha256 -days 1024 \
    -subj "/C=XX/L=Default City/O=Default Company Ltd/CN=localhost" -out ca.pem

# Server key/ca
# https://gist.github.com/Soarez/9688998
RUN openssl genrsa -out server.key 2048 \
    && openssl req -new -key server.key -out server.csr \
    -subj "/C=XX/L=Default City/O=Default Company Ltd/CN=localhost" \
    && openssl x509 -req -days 365 -in server.csr -signkey server.key -out server.crt

# Setup CRL
RUN touch /etc/pki/CA/index.txt \
    && echo '00' > /etc/pki/CA/crlnumber \
    && openssl ca -gencrl -keyfile ca.key -cert ca.pem -out crl.pem

# Prepare fo rmig
RUN mv server.crt $MIG_ROOT/certs/ \
    && mv server.key $MIG_ROOT/certs/ \
    && mv crl.pem $MIG_ROOT/certs/ \
    && mv ca.pem $MIG_ROOT/certs/cacert.pem

# Prepare default conf.d
RUN mv $WEB_DIR/conf.d/autoindex.conf $WEB_DIR/conf.d/autoindex.conf.centos \
    && mv $WEB_DIR/conf.d/ssl.conf $WEB_DIR/conf.d/ssl.conf.centos \
    && mv $WEB_DIR/conf.d/userdir.conf $WEB_DIR/conf.d/userdir.conf.centos \
    && mv $WEB_DIR/conf.d/welcome.conf $WEB_DIR/conf.d/welcome.conf.centos

# Reap defuncted/orphaned processes
ENV TINI_VERSION v0.18.0
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini /tini
RUN chmod +x /tini
ENTRYPOINT ["/tini", "--"]

ADD run_migrid.sh $MIG_ROOT/
RUN chown $USER:$USER $MIG_ROOT/run_migrid.sh \
    && chmod +x $MIG_ROOT/run_migrid.sh

RUN chmod 700 $MIG_ROOT

USER root

EXPOSE 80
WORKDIR $MIG_ROOT

CMD ["/home/mig/run_migrid.sh"]