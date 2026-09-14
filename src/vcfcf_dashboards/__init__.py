"""Authoring + install of VCF Operations dashboards and view definitions
via the Content Management import API.

Authoring source of truth is YAML under views/ and dashboards/. The
loader builds in-memory models, the renderer produces the internal
formats VCF Ops uses (XML for views, JSON for dashboards), the packager
wraps them in the nested ZIP-in-ZIP layout the import endpoint expects,
and the client POSTs the result to /api/content/operations/import.
"""
