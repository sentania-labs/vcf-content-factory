"""Offline importer: existing VCF Operations content files -> factory YAML.

Location-agnostic half of ``python3 -m vcfcf_extractor import-local``
(the factory wrapper ``vcfcf_extractor.importer`` writes the plan, runs the
stock-id guard and verifies through the real loaders). Nothing here reads
``.env``, touches a live instance, assumes a repo layout or writes a file.

- ``inputs.scan_inputs``: walk files, directories and archives into source
  objects (views, dashboards, report templates, alerts, symptoms,
  recommendations, super metrics), with the stock-id guard's archive limits.
- ``flat``: the exact flat form (``{path: value}``) of every type, shared by
  the comparator, duplicate merging, recorded losses and deviations, and the
  accounting.
- per-type mappers (``views``, ``dashboards``, ``reports``, ``alerts``,
  ``supermetrics``): one source object -> one YAML tree; then
  ``accounting.account`` classifies every source key (converted, renumbered,
  renderer constant, documented loss) or stops the object (TOOLSET GAP).
- ``convert.plan_conversion``: duplicates, drops, names, ids, references and
  target-version gates -> a ``Plan`` of YAML documents.
- ``compare``: exact comparison of a source object with its render.

How-to: ``knowledge/context/authoring/importer_offline_conversion.md``.
"""
from .convert import ConvertOptions, Plan, plan_conversion  # noqa: F401
from .inputs import InputScan, SourceObject, scan_inputs  # noqa: F401
