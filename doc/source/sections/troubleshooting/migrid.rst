Login not possible
------------------

::

    A critical internal error occurred in the reqoid backend. It has been logged internally with error ID XXXXXXXXXXX.YY

A message like this in the webinterface can have multiple reasons.
One is that the ``crypto_salt`` and/or the ``digest_salt`` are missing.
Check the ``$DIGEST_SALT`` and ``$CRYPTO_SALT`` environment variables and see ``mig/server/MiGserver.conf`` for configuration examples.
