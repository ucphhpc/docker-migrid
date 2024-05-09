Environment Variables
=====================

The MiGrid application stack is configured via environment variables, which are passed into the containers.
By default the ``.env`` should be a link to the environment file of the used deployment.
If a variable is not set, the default value, which is set in the Dockerfile, applies.
Below you can find a list of the available variable names.

For further information you can have a look at the underlying `generateconfs.py <https://github.com/ucphhpc/migrid-sync/blob/master/mig/install/generateconfs.py>`


Variables
---------

.. list-table:: Variable Explanations
   :widths: 25 25 50
   :header-rows: 1

   * - Variable
     - Default
     - Notes
   * - CONTAINER_TAG
     - ${MIG_GIT_BRANCH}
     - The Docker tag used for the MiGrid image that is created. This might either be a Git tag, a MiGrid version or a arbitrary name.
   * - FTPS_PASSIVE_PORTS
     - 8100-8399
     - The port range for FTPS passive ports used for data transmission.
   * - ENABLE_LOGROTATE
     - False
     - Whether or not the logrotate cron job should be started inside the containers. Be aware that the cron daemon itself might be started through the #RUN_SERVICES variable in the docker-entry.sh.
   * - LOGROTATE_MIGRID
     - False
     - Add explicit logrotate of migrid log files inside the container
   * - MIG_TEST_USER
     - test@external.domain
     - The username of the test user. Used by the development environments for tests.
   * - MIG_TEST_USER_PASSWORD
     - TestPw0rd
     - The password for the test user. Used by the development environments for tests.
   * - SMTP_SERVER
     - localhost
     - The MTA that is used to submit mails from migrid. Can be a hostname or an IP.
   * - SMTP_LISTEN_PORT
     - 25
     - Which local port for container SMTP process to listen on when using the devmail container as in the development env. Must be an integer below 65536 specifying a port which isn't already in use on the host.
   * - TZ
     - Europe/Copenhagen
     - The timezone that is used inside the containers.
   * - DOCKER_MIGRID_ROOT
     - .
     - Optionally use DOCKER_MIGRID_ROOT to point to another root location than PWD, which might be useful e.g. when automating deployment with ansible.
   * - UID
     - 1000
     - User ID of the migrid user inside the container, which might be useful to avoid various permission errors when juggling data inside and outside containers.
   * - GID
     - 1000
     - Group ID of the migrid group inside the container, which might be useful to avoid various permission errors when juggling data inside and outside containers.
   * - DOMAIN
     - migrid.test
     - The main domain under which the migrid service is hosted. Used for web landing page.
   * - WILDCARD_DOMAIN
     - \*.migrid.test
     - For self-signed certificate use
   * - PUBLIC_DOMAIN
     - www.migrid.test
     - The domain to serve public migrid web pages on
   * - MIGCERT_DOMAIN
     - cert.migrid.test
     - The optional domain under which migrid web for certificate-based authentication with a local CA will be reachable.
   * - EXTCERT_DOMAIN
     - 
     - The optional domain under which migrid web for certificate-based authentication with an external CA will be reachable.
   * - MIGOID_DOMAIN
     - ext.migrid.test
     - The optional domain under which migrid web for OpenID-based authentication with the built-in OpenID 2.0 service will be reachable. This is usually used for external users e.g. from other universities or companies.
   * - EXTOID_DOMAIN
     - 
     - The optional domain under which migrid web for OpenID-based authentication with an external OpenID 2.0 service will be reachable. This is usually used for centrally authenticating users at the local university or company when the central user database authentication is exposed in an OpenID 2.0 service.
   * - MIGOIDC_DOMAIN
     - 
     - The optional domain under which migrid web for OpenIDC-based authentication with a future built-in OpenID Connect service will be reachable. This is currently unused but should be used for external users e.g. from other universities or companies.
   * - EXTOIDC_DOMAIN
     - 
     - The optional domain under which migrid web for OpenID-based authentication with an external OpenID Connect service will be reachable. This is usually used for centrally authenticating users at the local university or company when the central user database authentication is exposed in an OpenID Connect service. This is known to work e.g. with MicroFocus ID Manager and Microsoft Azure AD.
   * - SID_DOMAIN
     - sid.migrid.test
     - The optional domain under which migrid web for SessionID-based authentication with various built-in services will be reachable. This is usually used e.g. for signup of new users and sharelink access.
   * - IO_DOMAIN
     - io.migrid.test
     - The generic domain for the various built-in storage protocols like SFTP, FTPS and WebDAVS.
   * - OPENID_DOMAIN
     - openid.migrid.test
     - The optional domain where the built-in OpenID 2.0 service runs.
   * - FTPS_DOMAIN
     - ftps.migrid.test
     - Specific domain for the FTPS service (if it's a dedicated IP)
   * - SFTP_DOMAIN
     - sftp.migrid.test
     - Specific domain for the SFTP service (if it's a dedicated IP)
   * - WEBDAVS_DOMAIN
     - webdavs.migrid.test
     - Specific domain for the WebDAVS service (if it's a dedicated IP)
   * - MIG_OID_PROVIDER
     - https://ext.migrid.test/openid/
     - Full URI to the built-in OpenID 2.0 service. Please note that you might want to keep this in sync with MIGOID_DOMAIN to get transparent proxying of the local OpenID service through Apache.
   * - EXT_OID_PROVIDER
     - unset
     - Full URI to a external OpenID 2.0 service used with the Apache virtual host on EXTOID_DOMAIN
   * - EXT_OIDC_PROVIDER_META_URL
     - unset
     - Full URI to a external OpenID Connect service used with the Apache virtual host on EXTOIDC_DOMAIN
   * - EXT_OIDC_CLIENT_NAME
     - unset
     - Used in authentication between external OpenID Connect IDP and the migrid web app. Should be negotiated with the IDP admins ahead of use.
   * - EXT_OIDC_CLIENT_ID
     - unset
     - Used in authentication between external OpenID Connect IDP and the migrid web app. Should be negotiated with the IDP admins ahead of use.
   * - EXT_OIDC_SCOPE
     - unset
     - Used in the user ID exchange between external OpenID Connect IDP and the migrid web app. Should be negotiated with the IDP admins ahead of use.
   * - EXT_OIDC_REMOTE_USER_CLAIM
     - unset
     - Used for the local user ID in migrid when a user authenticates through an external OpenID Connect IDP. Might be negotiated with the IDP admins ahead of use to assure that it's always available and unique.
   * - EXT_OIDC_PASS_CLAIM_AS
     - unset
     - Used in the user ID exchange between external OpenID Connect IDP and the migrid web app. Adjustments might be needed if user IDs may contain accented characters. Default is "both" but in some such cases "both latin1" may be needed instead.
   * - PUBLIC_HTTP_PORT
     - 80
     - TCP port for incoming plain HTTP connections. Will generally be redirected to HTTPS, except when used for LetsEncrypt HTTP-01 verification.
   * - PUBLIC_HTTPS_PORT
     - 444
     - Public HTTPS port for the migrid public web interface
   * - MIGCERT_HTTPS_PORT
     - 446
     - Public HTTPS port for cert-based authentication with a local CA
   * - EXTCERT_HTTPS_PORT
     - 447
     - Public HTTPS port for cert-based authentication with an external CA
   * - MIGOID_HTTPS_PORT
     - 443
     - Public HTTPS port for OpenID-based authentication with the built-in OpenID 2.0 service
   * - EXTOID_HTTPS_PORT
     - 445
     - Public HTTPS port for OpenID-based authentication with an external OpenID 2.0 service
   * - EXTOIDC_HTTPS_PORT
     - 449
     - Public HTTPS port for OpenID-based authentication with an external OpenID Connect service
   * - SID_HTTPS_PORT
     - 448
     - Public HTTPS port for SessionID-based authentication with built-in migrid services
   * - SFTP_SUBSYS_PORT
     - 22222
     - TCP port of the service offering SFTP access through the migrid sftp-subsystem for OpenSSH
   * - SFTP_PORT
     - 2222
     - TCP port of the service offering SFTP access through the native migrid sftp daemon
   * - SFTP_SHOW_PORT
     - 22
     - Where the SFTP service is advertized to run for the users. Mainly used when the standard sftp port 22 is transparently forwarded in the local firewall.
   * - DAVS_PORT
     - 4443
     - TCP port of the service offering WebDAVS access through the native migrid webdavs daemon
   * - DAVS_SHOW_PORT
     - 443
     - Where the WebDAVS service is advertized to run for the users. Mainly used when the standard webdavs port 443 is transparently forwarded in the local firewall.
   * - FTPS_CTRL_PORT
     - 8021
     - TCP port of the service offering FTPS access through the native migrid ftps daemon
   * - FTPS_CTRL_SHOW_PORT
     - 21
     - Where the FTPS service is advertized to run for the users. Mainly used when the standard ftps port 21 is transparently forwarded in the local firewall.
   * - OPENID_PORT
     - 8443
     - TCP port of the service offering OpenID 2.0 authentication through the native migrid openid daemon
   * - OPENID_SHOW_PORT
     - 443
     - Where the OpenID service is advertized to run for the users. Mainly used when the standard openid port 443 is transparently forwarded in the local firewall or Apache proxy.
   * - MIG_SVN_REPO
     - https://svn.code.sf.net/p/migrid/code/trunk
     - The Subversion repository from which the migrid code will be pulled, if Git isn't specifically requested (i.e. unless WITH_GIT=True) 
   * - MIG_SVN_REV
     - HEAD
     - Which SVN revision of the migrid codebase to deploy from the above repo when SVN is used
   * - MIG_GIT_REPO
     - https://github.com/ucphhpc/migrid-sync.git
     - The Git repository from which the migrid code will be pulled, if Git is requested (i.e. WITH_GIT=True)
   * - MIG_GIT_BRANCH
     - edge
     - The Git branch which should be used when migrid source code is pulled.
   * - MIG_GIT_REV
     - HEAD
     - The Git revision which should be used when migrid source code is pulled.
   * - ADMIN_EMAIL
     - mig
     - The email address to send various internal status and account request emails to from the migrid stack
   * - ADMIN_LIST
     - 
     - List of user accounts that have administrative rights (meaning they can access the Server Admin panel in the webinterface). Needs to be comma-separated list of full migrid user IDs on the usual x509-format.
   * - SMTP_SENDER
     - 
     - Mainly used to set a noreply@ sender address on various outgoing notification email from the instance, when there is no sane recipient for users to reply to. 
   * - LOG_LEVEL
     - info
     - Verbosity of the migrid service logs (debug, info, warn, error)
   * - TITLE
     - "Minimum intrusion Grid"
     - Site title used in various pages and emails
   * - SHORT_TITLE
     - MiG
     - A short or acronym form of the title used where the full title may be too clunky. 
   * - MIG_OID_TITLE
     - MiG
     - Title or label for the intended audience of the built-in OpenID 2.0 service
   * - EXT_OID_TITLE
     - External
     - Title or label for the intended audience of the external OpenID 2.0 service
   * - PEERS_PERMIT
     - "distinguished_name:.*"
     - A regex-filter to define which users can act as Peers in external user approval. Applied to user database entries.
   * - VGRID_CREATORS
     - "distinguished_name:.*"
     - A regex-filter to define which users can create VGrids / Workgroups / Projects. Applied to user database entries.
   * - VGRID_MANAGERS
     - "distinguished_name:.*"
     - A regex-filter to define which users can manage existing VGrids / Workgroups / Projects when assigned ownership. Applied to user database entries.
   * - EMULATE_FLAVOR
     - migrid
     - Which web design and site to use as a basis when generating the instance web pages
   * - EMULATE_FQDN
     - migrid.org
     - The FQDN of the site on the basis site to replace with the one of this instance
   * - SKIN_SUFFIX
     - basic
     - Which skin variant to use as a basis. If flavor is migrid and skin suffix is basic the skin in migrid-basic will effectively be used.
   * - ENABLE_OPENID
     - True
     - Enable the built-in OpenID 2.0 service for authenticating local users on web
   * - ENABLE_SFTP
     - True
     - Enable the built-in native SFTP service using Paramiko only
   * - ENABLE_SFTP_SUBSYS
     - True
     - Enable the built-in SFTP service provided as a sftp-subsystem to OpenSSH
   * - ENABLE_DAVS
     - True
     - Enable the built-in native WebDAVS service
   * - ENABLE_FTPS
     - True
     - Enable the built-in native FTPS service
   * - ENABLE_SHARELINKS
     - True
     - Enable the built-in sharelinks feature for easy data sharing without account requirement
   * - ENABLE_TRANSFERS
     - True
     - Enable the built-in datatransfers feature for data import and export
   * - ENABLE_DUPLICATI
     - True
     - Enable the built-in Duplicati integration for client backup
   * - ENABLE_SEAFILE
     - False
     - Enable the built-in Seafile integration for file synchronization. Requires a stand-alone Seafile instance.
   * - ENABLE_SANDBOXES
     - False
     - Enable the built-in sandbox resource feature for grid jobs
   * - ENABLE_VMACHINES
     - False
     - Enable the built-in vmachine resource feature for grid jobs
   * - ENABLE_CRONTAB
     - True
     - Enable the built-in Schedule Tasks feature for users
   * - ENABLE_JOBS
     - True
     - Enable the built-in grid job execution feature
   * - ENABLE_RESOURCES
     - True
     - Enable the built-in grid execution resource feature
   * - ENABLE_EVENTS
     - True
     - Enable the built-in file system event triggers feature with inotify
   * - ENABLE_FREEZE
     - False
     - Enable the built-in frozen archives feature for write-protecting and publishing user data.
   * - ENABLE_CRACKLIB
     - True
     - Enable the built-in cracklib password checking integration on user-supplied passwords
   * - ENABLE_IMNOTIFY
     - False
     - Enable the built-in instant messaging service integration. Requires a stand-alone messaging service.
   * - ENABLE_NOTIFY
     - True
     - Enable the built-in user notification daemon to inform users about failed logins, etc. on email.
   * - ENABLE_PREVIEW
     - False
     - Enable the built-in image preview feature - deprecated.
   * - ENABLE_WORKFLOWS
     - False
     - Enable the built-in workflows feature to act on file system events
   * - ENABLE_VERIFY_CERTS
     - True
     - Enable the built-in LetsEncrypt HTTP-01 support with a catch-all http vhost in the web server
   * - ENABLE_JUPYTER
     - True
     - Enable the built-in Jupyter integration - requires stand-alone Jupyter nodes
   * - ENABLE_MIGADMIN
     - False
     - Enable the built-in Server Admin feature for web based management of external user, log inspection, etc.
   * - ENABLE_GDP
     - False
     - Enable GDP mode for sensitive data with a lot of restrictions on access and logging
   * - ENABLE_TWOFACTOR
     - True
     - Enable the built-in twofactor authentication feature with TOTP tokens
   * - ENABLE_TWOFACTOR_STRICT_ADDRESS
     - False
     - Require client IO sessions to come from the same IP where user already has an active web login session with 2FA
   * - TWOFACTOR_AUTH_APPS
     - 
     - Which 2FA apps to suggest and link to on the 2-Factor Auth Setup wizard. Space-separated list of app names or empty string for all (bitwarden, freeotp, google, microfocus, microsoft, yubico).
   * - ENABLE_PEERS
     - True
     - Enable the built-in Peers system for privileged users to invite external collaboration partners
   * - PEERS_MANDATORY
     - False
     - Whether Peers validation by an existing user is mandatory before an external sign up request can be accepted.
   * - PEERS_EXPLICIT_FIELDS
     - ""
     - ID fields required for Peers when signing up as an external user on this site
   * - PEERS_CONTACT_HINT
     - "authorized to invite you as peer"
     - A brief hint about possible Peers when signing up as an external user on this site
   * - ENABLE_SELF_SIGNED_CERTS
     - False
     - Generate and use self-signed host certificates during build. Also disables certificate verification when connecting to OpenID with self signed cert
   * - MIG_PASSWORD_POLICY
     - MEDIUM
     - The password strength policy for user sign-up and all enabled I/O-services. Possible values are: NONE, WEAK, MEDIUM, HIGH, MODERN:L, CUSTOM:L:C where `:L` can be used to specify the minimum length and `:L:C` both the length and the required number of character classes (lowercase, uppercase, numeric and other). More details are available in the resulting MiGserver.conf but in short MEDIUM equals CUSTOM:8:3, HIGH equals CUSTOM:10:4 and MODERN:12 equals CUSTOM:12:1. NOTE: modern password guidelines now typically favor complexity requirements through longer passwords over the far less user-friendly character class demands.
   * - BUILD_MOD_AUTH_OPENID
     - False
     - Build and install the Apache mod auth OpenID from source during build 
   * - UPGRADE_MOD_AUTH_OPENIDC
     - False
     - Upgrade the default Apache mod auth OpenIDC to latest supported one during build 
   * - UPGRADE_PARAMIKO
     - False
     - Upgrade the default Paramiko version to latest supported one during build 
   * - PUBKEY_FROM_DNS
     - False
     - Advertize to SFTP users that they can find the host key in DNS(SEC).
   * - PREFER_PYTHON3
     - False
     - Whether PYTHON3 should be used as the default. If not Python 2 is used. Depends on `$WITH_PY3`
   * - SIGNUP_METHODS
     - migoid
     - Which signup methods should be advertized in the webinterface
   * - LOGIN_METHODS
     - migoid
     - Which login methods should be advertized in the webinterface
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
     - How long cert based user accounts should kept as active without login or renewal.
   * - OID_VALID_DAYS
     - 365
     - How long OpenID user accounts should kept as active without login or renewal.
   * - GENERIC_VALID_DAYS
     - 365
     - How long user accounts should by default be kept as active without login or renewal.
   * - DEFAULT_MENU
     - 
     - The menu entries in the webinterface that are always active. Leave empty for the default dynamic set based on enabled services.
   * - USER_MENU
     - jupyter
     - The menu entries in the webinterface that can be activated by the users from Home
   * - WITH_PY3
     - False
     - Build container with python3 support and libraries
   * - MODERN_WSGIDAV
     - False
     - Whether the WebDAVS service should use the tried and tested wsgidav 1.3 or upgrade to a more modern version.
   * - WITH_GIT
     - False
     - Use git instead of subversion, see `$MIG_GIT_REPO`
   * - OPENSSH_VERSION
     - 7.4
     - Minimum client OpenSSH version to support, mainly regarding security hardening
   * - VGRID_LABEL
     - VGrid
     - The label used to describe VGrids everywhere: e.g. VGrid, Workgroup or Project
   * - DIGEST_SALT
     - "AUTO"
     - A 32-byte hex salt value used for various string digest purposes. Can be a string or a reference to a file where the value is actually stored. The latter is better as the value should remain constant once set.
   * - CRYPTO_SALT
     - "AUTO"
     - A 32-byte hex salt value used for various string crypto purposes. Can be a string or a reference to a file where the value is actually stored. The latter is better as the value should remain constant once set.
   * - EXTRA_USERPAGE_SCRIPTS
     - ""
     - Optional extra web page scripts to embed on site user web pages (analytics, etc.) 
   * - EXTRA_USERPAGE_STYLES
     - ""
     - Optional extra web page styles to embed on site user web pages (branding, etc.) 
   * - MIG_SYSTEM_RUN
     - "state/mig_system_run"
     - A preferably fast (e.g. tmpfs-backed) scratch folder path for various internal cache and helper files. It must have read/write access by the same USER:GROUP running in the containers and will be shared among all containers for cache and state coherence.
   * - OPENID_STORE
     - "state/openid_store"
     - A preferably fast (e.g. tmpfs-backed) scratch folder path for the optional OpenID 2.0 authentication of users in the apache web server. It must have read/write access by the same USER:GROUP running in the containers and will only be exposed in the migrid container for mod auth openid cache and session state.
   * - VGRID_FILES_WRITABLE
     - "state/vgrid_files_writable"
     - The path where the vgrid_files_writable directory is available. It is used as a source for a read-only bind mount of the data there onto the vgrid_files_readonly directory in order to support users write-protecting VGrids/Workgroups shared folders on the site.
   * - GDP_EMAIL_NOTIFY
     - True
     - Whether to send project administration emails to address(es) configured in state/gdp_home/notifyemails.txt when in GDP mode
   * - GDP_ID_SCRAMBLE
     - safe_hash
     - Which method to use for scrambling user IDs in the gdp.log associated with GDP sites. Uses SHA256 hashing by default to allow logs to be forwarded to less restrictive remote log environments without disclosing actual user info and to allow 'forgetting' removed users. 
   * - GDP_PATH_SCRAMBLE
     - safe_encrypt
     - Which method to use for scrambling potentially sensitive path and filenames in the gdp.log associated with GDP sites. Uses Fernet encryption by default to allow logs to be forwarded to less restrictive remote log environments without disclosing actual metadata from the user data.
   * - JUPYTER_SERVICES
     - ""
     - Where the optional external Jupyter nodes can be reached
   * - JUPYTER_SERVICES_DESC
     - "{}"
     - A text to describe the optional external Jupyter nodes
   * - QUOTA_BACKEND
     - ""
     - Filesystem backend used to set quotas and fetch data usage. Supported backends: 'lustre' and 'lustre-gocryptfs'
   * - QUOTA_USER_LIMIT
     - 1099511627776
     - Data limit for MiG users in bytes.
   * - QUOTA_VGRID_LIMIT
     - 1099511627776
     - Data limit for MiG vgrids in bytes.
   * - QUOTA_LUSTRE_VERSION
     - 2.15.4
     - The MiG lustre quota helper depends on the lustre source code. The version number should be aligned with the lustre client version used when mounting lustre. First lustre version that supports quotas is 2.15.4
   * - QUOTA_LUSTRE_BASE
     - "/dev/null"
     - Path to MiG lustre base containing 'user_home', 'vgrid_home' and 'vgrid_files_writable'. If using lustre-gocryptfs then lustre base is the encrypted base path.
   * - QUOTA_GOCRYPYFS_XRAY
     - "/dev/null"
     - If data is encrypted with gocryptfs then
     quotas are set on the encrypted data paths. gocryptfs-xray is needed to resolve the encrypted data paths from the decrypted MiG data paths.
   * - QUOTA_GOCRYPYFS_SOCK
     - "/dev/null"
     - A gocryptfs socket is needed by gocryptfs-xray to resolve encoded data paths from MiG data paths.
