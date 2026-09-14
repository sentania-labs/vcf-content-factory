"""vcfcf_extractor — reverse-engineering toolkit for VCF Operations content.

Walks a live dashboard and its dependency graph (views, super metrics)
and emits factory-shape YAML under ``bundles/third_party/<slug>/`` plus
a bundle manifest at ``bundles/third_party/<slug>.yaml`` that
``vcfcf_packaging build`` can turn into a distributable zip.

Reverse parsers live in their sibling packages:
  vcfcf_dashboards.reverse  -- dashboard JSON + view XML -> dataclasses
  vcfcf_supermetrics.reverse -- SM JSON + formula UUID->name rewrite

This package owns the orchestration, dependency walker, YAML writer,
and the top-level argparse CLI.
"""
