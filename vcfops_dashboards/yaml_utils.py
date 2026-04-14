"""YAML loading utilities shared within vcfops_dashboards.

Provides ``strict_load``, a drop-in replacement for ``yaml.safe_load``
that raises ``yaml.constructor.ConstructorError`` on duplicate mapping
keys.  Duplicate keys are silently accepted by PyYAML's default loader
(last-value-wins), which hid the stacked-``id:`` pathology described in
the production incident of 2026-04-14.
"""
from __future__ import annotations

import yaml
import yaml.constructor
import yaml.resolver


class _StrictKeyLoader(yaml.SafeLoader):
    """SafeLoader extended to reject duplicate mapping keys."""


def _no_duplicates_constructor(
    loader: _StrictKeyLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict:
    """Mapping constructor that raises on duplicate keys."""
    mapping: dict = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                None,
                None,
                f"duplicate key '{key}' found at {key_node.start_mark}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_StrictKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _no_duplicates_constructor,
)


def strict_load(stream) -> object:
    """Parse *stream* as YAML, raising on duplicate mapping keys.

    *stream* may be a string or a file-like object, same as
    ``yaml.safe_load``.  Returns the parsed Python object (typically
    ``dict`` or ``None`` for an empty document).

    Raises:
        yaml.constructor.ConstructorError: if the YAML document contains
            duplicate keys at any mapping level.
    """
    return yaml.load(stream, Loader=_StrictKeyLoader)
