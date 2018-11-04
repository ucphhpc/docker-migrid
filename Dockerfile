FROM centos:latest

RUN yum update -y \
    && yum upgrade -y \
    && yum install -y \
    httpd \
    crontabs \
    nano \
    mod_ssl \
    mod_wsgi \
    mod_proxy \
    mod_auth_openid \
    tzdata \
    initscripts \
    svn \
    vimdiff

# Setup user
ENV USER=mig
RUN useradd -ms /bin/bash $USER

# MIG environment
ENV MIG_ROOT=/home/$USER
ENV VERSION=4010

# Clone into $USER home
WORKDIR $MIG_ROOT
USER $USER

RUN svn checkout -r $VERSION https://svn.code.sf.net/p/migrid/code/trunk .

# Install
ENV WEB_DIR=/etc/httpd

WORKDIR $MIG_ROOT/mig/install

# Dependency
RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py \
    && python get-pip.py --user

ENV PATH=$PATH:/home/$USER/.local/bin

RUN pip install --user python-openid

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
    --enable_events=False \
    --base_fqdn=localhost \
    --public_fqdn=www.localhost \
    --mig_cert_fqdn= \
    --ext_cert_fqdn= \
    --mig_oid_fqdn=ext.localhost \
    --ext_oid_fqdn= \
    --mig_oid_fqdn= \
    --mig_oid_port= \
    --ext_oid_fqdn= \
    --ext_oid_port= \
    --sid_fqdn= \
    --io_fqdn= \
    --user=mig \
    --group=mig \
    --hg_path=/usr/bin/hg \
    --hgweb_scripts=/usr/share/doc/mercurial-2.6.2 \
    --trac_admin_path= \
    --trac_ini_path= \
    --public_port=80 \
    --ext_cert_port= \
    --mig_oid_port=443 \
    --ext_oid_port= \
    --sid_port= \
    --enable_openid=True \
    --enable_wsgi=True \
    --serveralias_clause=#ServerAlias \
    --mig_oid_provider=https://ext.localhost/openid/ \
    --landing_page=/wsgi-bin/fileman.py \
    --skin=idmc-basic

#
#GENERATECONFS_COMMAND :
#./generateconfs.py --source=. --destination=generated-confs
#--destination_suffix=_svn3965:4005M --base_fqdn=test.idmc.dk
#--public_fqdn=test-www.idmc.dk --mig_cert_fqdn= --ext_cert_fqdn=test-cert.idmc.dk
#--mig_oid_fqdn=test-ext.idmc.dk --ext_oid_fqdn=test-oid.idmc.dk
#--sid_fqdn=test-sid.idmc.dk --io_fqdn=test-io.idmc.dk --user=mig
#--group=mig --apache_version=2.4 --apache_etc=/etc/httpd
#--apache_run=/var/run/httpd --apache_lock=/var/lock/subsys/httpd
#--apache_log=/var/log/httpd --openssh_version=7.4 --mig_code=/home/mig/mig
#--mig_state=/home/mig/state --mig_certs=/etc/httpd/MiG-certificates
#--hg_path=/usr/bin/hg --hgweb_scripts=/usr/share/doc/mercurial-2.6.2 --trac_admin_path=
#--trac_ini_path= --public_port=80 --ext_cert_port=443 --mig_oid_port=443
#--ext_oid_port=443 --sid_port=443 --mig_oid_provider=https://test-ext.idmc.dk/openid/
#--ext_oid_provider=https://openid.ku.dk/ --enable_openid=True --enable_wsgi=True
#--enable_sftp=True --enable_sftp_subsys=True --enable_davs=True --enable_ftps=True
#--enable_jupyter=True --enable_sharelinks=True --enable_transfers=True
#--enable_imnotify=False --enable_seafile=False --enable_duplicati=False
#--enable_preview=True --enable_sandboxes=False --enable_vmachines=False
#--enable_crontab=True --enable_jobs=True --enable_events=True --enable_freeze=False
#--enable_twofactor=True --enable_cracklib=True --enable_vhost_certs=True
#--enable_verify_certs=True --enable_hsts=True --jupyter_hosts=http://dag000.science
#--jupyter_base_url=/dag --user_clause=User --group_clause=Group --listen_clause=#Listen
# --serveralias_clause=#ServerAlias --alias_field=email
# --dhparams_path=~/certs/dhparams.pem --daemon_keycert=~/certs/combined.pem
# --daemon_pubkey=~/certs/combined.pub
# --daemon_show_address=test-io.idmc.dk "--signup_methods=extoid migoid extcert"
#  "--login_methods=extoid migoid extcert" --distro=centos
#  --landing_page=/wsgi-bin/fileman.py --skin=idmc-basic --wsgi_procs=25


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

# Root confs
RUN cp generated-confs/apache2.conf $WEB_DIR/ \
    && cp generated-confs/ports.conf $WEB_DIR/ \
    && cp generated-confs/MiG-jupyter.conf $WEB_DIR/ \
    && cp generated-confs/MiG-jupyter-def.conf $WEB_DIR/ \
    && cp generated-confs/envvars $WEB_DIR/

# Front page
RUN ln -s /home/mig/state/wwwpublic/index-idmc.dk.html /home/mig/state/wwwpublic/index.html

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
