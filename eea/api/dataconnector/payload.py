"""Canonical connector request payload helpers."""


def canonical_form(query_form=None, body_form=None):
    """Return the effective connector form used for execution and caching.

    Body values override URL values. REST expansion controls belong to the
    content request and must not become connector parameters. An omitted
    database version has the same semantics as ``latest``.
    """
    form = dict(query_form or {})
    form.update(body_form or {})
    canonical = {
        key: value
        for key, value in form.items()
        if key != "expand" and not key.startswith("expand.")
    }
    canonical["db_version"] = canonical.get("db_version") or "latest"
    return canonical
