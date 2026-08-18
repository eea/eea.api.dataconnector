==========================
eea.api.dataconnector
==========================
.. image:: https://ci.eionet.europa.eu/buildStatus/icon?job=eea/eea.api.dataconnector/develop
  :target: https://ci.eionet.europa.eu/job/eea/job/eea.api.dataconnector/job/develop/display/redirect
  :alt: Develop
.. image:: https://ci.eionet.europa.eu/buildStatus/icon?job=eea/eea.api.dataconnector/master
  :target: https://ci.eionet.europa.eu/job/eea/job/eea.api.dataconnector/job/master/display/redirect
  :alt: Master

The eea.api.dataconnector is a Plone add-on.

.. contents::

Upgrade
=======
**12.0 (Breaking)**
- Logic for plotly visualization was moved to eea.plotly
- Install eea.plotly >= 1.x
- Use volto-plotlycharts >= 12.x
- Enable eea.plotly add-on
- Activate EEA-Viz_Plotly behavior
- Run any pending upgrades on eea.api.dataconnector

**8.0**
- Endpoints for @tableau-visualization and @map-visualization are removed. Use volto-eea-map@^3.0.0 and volto-tableau@^7.0.0

Main features
=============

1. Easy to install/uninstall via Site Setup > Add-ons
2.
3.

Connector-data response contract
================================

Successful ``@connector-data`` responses expose provider data as an object with
``results`` and ``metadata`` fields. ``results`` is an empty array when no rows
exist; ``metadata`` remains an object and may contain provider information such
as ``readme``. The minimal empty shape is::

    {
      "results": [],
      "metadata": {}
    }

The response ``payload`` is public request-identity metadata, not diagnostic
output. ``volto-datablocks`` uses its canonical ``data_query`` and ``form`` to
reuse data preloaded during server-side rendering. Authentication credentials
must be carried in request headers or cookies and must never be passed as
connector form or data-query values.

Virtual pages may attach a transient ``connector_data`` preload produced by
this package. It is accepted only from the virtual object itself and must match
the complete ``@connector-data`` envelope: ``@id``, ``path``, ``data`` and
``payload``. The envelope is returned unchanged so its payload continues to
describe the exact request that produced its data.

Expanded connector data is memoized by provider path, request identity, and
provider content revision. Editing a provider configuration or replacing its
file therefore changes the cache identity immediately. Changes in external SQL
data are bounded by the global ``CACHE_TTL`` configured by ``eea.volto.policy``.

Install
=======

* Add eea.api.dataconnector to your eggs section in your buildout and
  re-run buildout::

    [buildout]
    eggs +=
      eea.api.dataconnector

* You can download a sample buildout from:

  - https://github.com/eea/eea.api.dataconnector/tree/master/buildouts/plone4
  - https://github.com/eea/eea.api.dataconnector/tree/master/buildouts/plone5

* Or via docker::

    $ docker run --rm -p 8080:8080 -e ADDONS="eea.api.dataconnector" plone

* Install *eea.api.dataconnector* within Site Setup > Add-ons


Buildout installation
=====================

- `Plone 4+ <https://github.com/eea/eea.api.dataconnector/tree/master/buildouts/plone4>`_
- `Plone 5+ <https://github.com/eea/eea.api.dataconnector/tree/master/buildouts/plone5>`_


Source code
===========

- `Plone 4+ on github <https://github.com/eea/eea.api.dataconnector>`_
- `Plone 5+ on github <https://github.com/eea/eea.api.dataconnector>`_


Eggs repository
===============

- https://pypi.python.org/pypi/eea.api.dataconnector
- http://eggrepo.eea.europa.eu/simple


Plone versions
==============
It has been developed and tested for Plone 4 and 5. See buildouts section above.


How to contribute
=================
See the `contribution guidelines (CONTRIBUTING.md) <https://github.com/eea/eea.api.dataconnector/blob/master/CONTRIBUTING.md>`_.

Copyright and license
=====================

eea.api.dataconnector (the Original Code) is free software; you can
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

Secret Scanning
===============

This repository uses the Betterleaks GitHub Action to scan the current
repository content on every push and pull request. The scan uses the rules in
``.gitleaks.toml`` and uploads a ``betterleaks-report`` artifact when a finding
is detected.

If the optional SMTP secrets are configured, failed scans also send an email to
the last commit committer. The workflow expects these repository or
organization secrets:

- ``SMTP_URL``
- ``SMTP_PORT`` (optional, defaults to ``25``)
- ``SMTP_EMAIL``
- ``SMTP_PASSWORD`` (optional if the SMTP server does not require authentication)

Port ``465`` is sent with direct TLS; other ports use the default SMTP
handshake. The email includes a short finding summary from the redacted
Betterleaks report, including the redacted matched line from each finding.

There are three common outcomes:

1. Everything is OK. The ``Betterleaks / Scan for secrets`` check is green and
   no action is needed. Regular references to runtime values are OK, for example::

     token_from_cookie = request.cookies.get("auth_token")

2. A real secret was found. The check is red and the workflow log asks you to
   download the ``betterleaks-report`` artifact. Open the artifact from the
   GitHub Actions run and check the reported file, line and rule. Remove the
   committed value, move it to the proper secret store, and rotate it if it was
   exposed. A report entry looks like this::

     {
       "RuleID": "secret-literal-assignment",
       "File": "src/config.py",
       "StartLine": 12,
       "Secret": "[REDACTED]"
     }

3. The finding is a false positive. Keep the value only if it is clearly not
   sensitive, such as a test fixture, placeholder, or public example. Add
   ``betterleaks:allow`` on the same line and include a short explanation in the
   pull request::

     test_password = "admin"  #betterleaks:allow

Do not add ``betterleaks:allow`` to real credentials.
