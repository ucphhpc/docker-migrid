Overview
========
Considering the overview in the diagram below

.. image:: ../../res/images/arch-overview.png

the docker-migrid container basically provides the parts and services covered in
Frontend on

.. image:: ../../res/images/arch-frontend.png

where the docker setup relies on simpel local storage whereas
production systems typically rely on a separate network backend
storage to cluster a number of storage bricks as outlined below.

.. image:: ../../res/images/arch-backend.png

Further optional components like Jupyter, Cloud and Seafile run on
stand-alone systems but are more or less integrated and exposed
through the Web server at the Frontend.
