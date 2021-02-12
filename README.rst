==========================
eea.restapi.dataconnector
==========================
.. image:: https://ci.eionet.europa.eu/buildStatus/icon?job=eea/eea.restapi.dataconnector/develop
  :target: https://ci.eionet.europa.eu/job/eea/job/eea.restapi.dataconnector/job/develop/display/redirect
  :alt: Develop
.. image:: https://ci.eionet.europa.eu/buildStatus/icon?job=eea/eea.restapi.dataconnector/master
  :target: https://ci.eionet.europa.eu/job/eea/job/eea.restapi.dataconnector/job/master/display/redirect
  :alt: Master

The eea.restapi.dataconnector is a Plone add-on

.. contents::


Main features
=============

1. Easy to install/uninstall via Site Setup > Add-ons
2.
3.

Install
=======

* Add eea.restapi.dataconnector to your eggs section in your buildout and
  re-run buildout::

    [buildout]
    eggs +=
      eea.restapi.dataconnector

* You can download a sample buildout from:

  - https://github.com/eea/eea.restapi.dataconnector/tree/master/buildouts/plone4
  - https://github.com/eea/eea.restapi.dataconnector/tree/master/buildouts/plone5

* Or via docker::

    $ docker run --rm -p 8080:8080 -e ADDONS="eea.restapi.dataconnector" plone

* Install *eea.restapi.dataconnector* within Site Setup > Add-ons


Buildout installation
=====================

- `Plone 4+ <https://github.com/eea/eea.restapi.dataconnector/tree/master/buildouts/plone4>`_
- `Plone 5+ <https://github.com/eea/eea.restapi.dataconnector/tree/master/buildouts/plone5>`_


Source code
===========

- `Plone 4+ on github <https://github.com/eea/eea.restapi.dataconnector>`_
- `Plone 5+ on github <https://github.com/eea/eea.restapi.dataconnector>`_


Eggs repository
===============

- https://pypi.python.org/pypi/eea.restapi.dataconnector
- http://eggrepo.eea.europa.eu/simple


Plone versions
==============
It has been developed and tested for Plone 4 and 5. See buildouts section above.


How to contribute
=================
See the `contribution guidelines (CONTRIBUTING.md) <https://github.com/eea/eea.restapi.dataconnector/blob/master/CONTRIBUTING.md>`_.

Copyright and license
=====================

eea.restapi.dataconnector (the Original Code) is free software; you can
redistribute it and/or modify it under the terms of the
GNU General Public License as published by the Free Software Foundation;
either version 2 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
for more details.

You should have received a copy of the GNU General Public License along
with this program; if not, write to the Free Software Foundation, Inc., 59
Temple Place, Suite 330, Boston, MA 02111-1307 USA.

The Initial Owner of the Original Code is European Environment Agency (EEA).
Portions created by Eau de Web are Copyright (C) 2009 by
European Environment Agency. All Rights Reserved.


Funding
=======

EEA_ - European Environment Agency (EU)

.. _EEA: https://www.eea.europa.eu/
.. _`EEA Web Systems Training`: http://www.youtube.com/user/eeacms/videos?view=1
