Environment Variables
=====================

The MiGrid application is configured via environment variables which are passed into the containers.
By default the ``.env`` should be a link to the enviroment file of the used deployment.
If a variable is not set, the default value, which is set in the Dockerfile, applies.
Below you can find a list of the available variable names.

For further information you can have a look at the underlying `generateconfs.py <https://github.com/ucphhpc/migrid-sync/blob/master/mig/install/generateconfs.py>`



Variables
---------

.. list-table:: Variable Explainations
   :widths: 25 25 50
   :header-rows: 1

   * - Variable
     - Default
     - Notes
   * - DOCKER_MIGRID_ROOT
     - .
     - Optionally use DOCKER_MIGRID_ROOT to point to another root location than PWD, which might be useful e.g. when automating deployment with ansible.
   * - UID
     - 1000
     - User ID of the migrid user inside the container
   * - GID
     - 1000
     - Group ID of the migrid group inside the container
   * - BUILD_TYPE
     - basic
     - tba
   * - BUILD_TARGET
     - development
     - tba
   * - DOMAIN
     - migrid.test
     - The main domain under which the mirgid service is hosted. Used for landing page.
   * - WILDCARD_DOMAIN
     - \*.migrid.test
     - tba
   * - PUBLIC_DOMAIN
     - www.migrid.test
     - tba
   * - MIGCERT_DOMAIN
     - cert.migrid.test
     - The domain under which migrid own service for cert based authentication will be reachable.
   * - EXTCERT_DOMAIN
     - 
     - The domain under which a external service for cert based authentication will be reachable.
   * - MIGOID_DOMAIN
     - ext.migrid.test
     - The domain under which migrid own OpenID service will be reachable. This is usually used for external user from other universities.
   * - EXTOID_DOMAIN
     - 
     - The domain under which a externally hosted OpenID service will be reachable. This is usually used for users of the local university.
   * - EXTOIDC_DOMAIN
     - 
     - The domain under which migrid own OpenID service will be reachable. This is usually used for users of the local university.
   * - SID_DOMAIN
     - sid.migrid.test
     - The session ID domain under which migrid own authentication service will be reachable. This is usually used for signup of new users.
   * - IO_DOMAIN
     - io.migrid.test
     - The generic domain for the storage protocols like SFTP, Webdavs, etc.
   * - OPENID_DOMAIN
     - openid.migrid.test
     - tba
   * - FTPS_DOMAIN
     - ftps.migrid.test
     - Specific domain for the ftps service (if it's a dedicated IP)
   * - SFTP_DOMAIN
     - sftp.migrid.test
     - Specific domain for the sftp service (if it's a dedicated IP)
   * - WEBDAVS_DOMAIN
     - webdavs.migrid.test
     - Specific domain for the webdavs service (if it's a dedicated IP)
   * - MIG_OID_PROVIDER
     - https://ext.migrid.test/openid/
     - Full URI to migrids own Openid service
   * - EXT_OID_PROVIDER
     - unset
     - Full URI to a external Openid service
   * - EXT_OIDC_PROVIDER_META_URL
     - unset
     - Full URI to a external Openid Connect service
   * - EXT_OIDC_CLIENT_NAME
     - unset
     - tba
   * - EXT_OIDC_CLIENT_ID
     - unset
     - tba
   * - EXT_OIDC_SCOPE
     - unset
     - tba
   * - EXT_OIDC_REMOTE_USER_CLAIM
     - unset
     - tba
   * - EXT_OIDC_PASS_CLAIM_AS
     - unset
     - tba
   * - PUBLIC_HTTP_PORT
     - 80
     - TCP port for incoming HTTP connections. Will be redirected to HTTPS
   * - PUBLIC_HTTPS_PORT
     - 444
     - Public HTTPS port for the mirgid webinterface
   * - MIGCERT_HTTPS_PORT
     - 446
     - Public HTTPS port for migrids own cert based authentication service
   * - EXTCERT_HTTPS_PORT
     - 447
     - Public HTTPS port of the external cert based authentication service
   * - MIGOID_HTTPS_PORT
     - 443
     - Public HTTPS port for migrids own OpenID service
   * - EXTOID_HTTPS_PORT
     - 445
     - Public HTTPS port of the external OpenID service
   * - EXTOIDC_HTTPS_PORT
     - 449
     - Public HTTPS port of the external OpenID Connect service
   * - SID_HTTPS_PORT
     - 448
     - Public HTTPS port for migrids own OpenID service
   * - SFTP_SUBSYS_PORT
     - 22222
     - tba
   * - SFTP_PORT
     - 2222
     - TCP port for the SFTP service
   * - SFTP_SHOW_PORT
     - 22
     - tba
   * - DAVS_PORT
     - 4443
     - tba
   * - DAVS_SHOW_PORT
     - 443
     - tba
   * - FTPS_CTRL_PORT
     - 8021
     - tba
   * - FTPS_CTRL_SHOW_PORT
     - 21
     - tba
   * - OPENID_PORT
     - 8443
     - tba
   * - OPENID_SHOW_PORT
     - 443
     - tba
   * - MIG_SVN_REPO
     - https://svn.code.sf.net/p/migrid/code/trunk
     - tba
   * - MIG_SVN_REV
     - 5683
     - tba
   * - MIG_GIT_REPO
     - https://github.com/ucphhpc/migrid-sync.git
     - The Git repository from which the migrid code will be pulled, if Subversion isn't used
   * - MIG_GIT_BRANCH
     - edge
     - The Git branch which should be used when migrid source code is pulled.
   * - MIG_GIT_REV
     - b6c6a42c3952f8753f60a2f2571b99e3d48f5b11
     - The Git branch which should be used when migrid source code is pulled.
   * - ADMIN_EMAIL
     - mig
     - tba
   * - ADMIN_LIST
     - 
     - List of user accounts that have administrative rights (meaning they can access the Admin panel in the webinterface)
   * - SMTP_SENDER
     - 
     - tba
   * - LOG_LEVEL
     - info
     - tba
   * - TITLE
     - "Minimum intrusion Grid"
     - tba
   * - SHORT_TITLE
     - MiG
     - tba
   * - MIG_OID_TITLE
     - MiG
     - tba
   * - EXT_OID_TITLE
     - External
     - tba
   * - PEERS_PERMIT
     - "distinguished_name:.*"
     - tba
   * - VGRID_CREATORS
     - "distinguished_name:.*"
     - tba
   * - VGRID_MANAGERS
     - "distinguished_name:.*"
     - tba
   * - EMULATE_FLAVOR
     - migrid
     - tba
   * - EMULATE_FQDN
     - migrid.org
     - tba
   * - SKIN_SUFFIX
     - basic
     - tba
   * - ENABLE_OPENID
     - True
     - tba
   * - ENABLE_SFTP
     - True
     - tba
   * - ENABLE_SFTP_SUBSYS
     - True
     - tba
   * - ENABLE_DAVS
     - True
     - tba
   * - ENABLE_FTPS
     - True
     - tba
   * - ENABLE_SHARELINKS
     - True
     - tba
   * - ENABLE_TRANSFERS
     - True
     - tba
   * - ENABLE_DUPLICATI
     - True
     - tba
   * - ENABLE_SEAFILE
     - False
     - tba
   * - ENABLE_SANDBOXES
     - False
     - tba
   * - ENABLE_VMACHINES
     - False
     - tba
   * - ENABLE_CRONTAB
     - True
     - tba
   * - ENABLE_JOBS
     - True
     - tba
   * - ENABLE_RESOURCES
     - True
     - tba
   * - ENABLE_EVENTS
     - True
     - tba
   * - ENABLE_FREEZE
     - False
     - tba
   * - ENABLE_CRACKLIB
     - True
     - tba
   * - ENABLE_IMNOTIFY
     - False
     - tba
   * - ENABLE_NOTIFY
     - True
     - tba
   * - ENABLE_PREVIEW
     - False
     - tba
   * - ENABLE_WORKFLOWS
     - False
     - tba
   * - ENABLE_VERIFY_CERTS
     - True
     - tba
   * - ENABLE_JUPYTER
     - True
     - tba
   * - ENABLE_MIGADMIN
     - False
     - tba
   * - ENABLE_GDP
     - False
     - tba
   * - ENABLE_TWOFACTOR
     - True
     - tba
   * - ENABLE_TWOFACTOR_STRICT_ADDRESS
     - False
     - tba
   * - ENABLE_PEERS
     - True
     - tba
   * - PEERS_MANDATORY
     - False
     - tba
   * - PEERS_EXPLICIT_FIELDS
     - ""
     - tba
   * - PEERS_CONTACT_HINT
     - "authorized to invite you as peer"
     - tba
   * - ENABLE_SELF_SIGNED_CERTS
     - False
     - tba
   * - BUILD_MOD_AUTH_OPENID
     - False
     - tba
   * - UPGRADE_MOD_AUTH_OPENIDC
     - False
     - tba
   * - UPGRADE_PARAMIKO
     - False
     - tba
   * - PUBKEY_FROM_DNS
     - False
     - tba
   * - PREFER_PYTHON3
     - False
     - Whether PYTHON3 should be used. If not Python 2 is used. Depends on `$WITH_PY3`
   * - SIGNUP_METHODS
     - migoid
     - Which signup methods should be available in the webinterface
   * - LOGIN_METHODS
     - migoid
     - Which login methods should be available in the webinterface
   * - USER_INTERFACES
     - V3
     - Which versions of the webinterface should be available. New setups should only support V3
   * - AUTO_ADD_CERT_USER
     - False
     - Whether new cert based registrations should be automatically be activated or wait for admin approval first.
   * - AUTO_ADD_OID_USER
     - False
     - Whether new registrations via OpenID should be automatically be activated or wait for admin approval first.
   * - AUTO_ADD_OIDC_USER
     - False
     - Whether new registrations via OpenID Connect should be automatically be activated or wait for admin approval first.
   * - CERT_VALID_DAYS
     - 365
     - How long cert based user accounts should kept as active without login.
   * - OID_VALID_DAYS
     - 365
     - How long OpenID user accounts should kept as active without login.
   * - GENERIC_VALID_DAYS
     - 365
     - How long user accounts should kept as active without login.
   * - DEFAULT_MENU
     - 
     - The menu entries in the webinterface that are always active
   * - USER_MENU
     - jupyter
     - The menu entries in the webinterface that can be activated by the users
   * - WITH_PY3
     - False
     - Build container with python3 support and libraries
   * - MODERN_WSGIDAV
     - False
     - For Centos we stick with tried and tested wsgidav 1.3
   * - WITH_GIT
     - False
     - Use git instead of subversion, see `$MIG_GIT_REPO`
   * - OPENSSH_VERSION
     - 7.4
     - tba
   * - VGRID_LABEL
     - VGrid
     - tba
   * - DIGEST_SALT
     - "AUTO"
     - tba
   * - CRYPTO_SALT
     - "AUTO"
     - tba
   * - EXTRA_USERPAGE_SCRIPTS
     - ""
     - tba
   * - EXTRA_USERPAGE_STYLES
     - ""
     - tba
   * - GDP_EMAIL_NOTIFY
     - True
     - tba
   * - JUPYTER_SERVICES
     - ""
     - tba
   * - JUPYTER_SERVICES_DESC
     - "{}"
     - tba
