MiGrid
======
Issues related to the core MiGrid stack are covered here.

Login not possible
------------------

::

    A critical internal error occurred in the reqoid backend. It has been logged internally with error ID XXXXXXXXXXX.YY

A message like this in the webinterface can have multiple reasons and they are usually explained in more detail in the mig.log available under state/log/.
One is that the ``crypto_salt`` and/or the ``digest_salt`` values are missing or inaccessible.
Check the ``$DIGEST_SALT`` and ``$CRYPTO_SALT`` environment variables and see ``mig/server/MiGserver.conf`` for configuration examples.
