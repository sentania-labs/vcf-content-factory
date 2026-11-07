# docs-gen baseline fixtures

Two adapter projects with no `stitch_targets` stanza, and the docset
`generate_docset` produced for each before `stitch_targets` existed
(factory #310), under `<pak>/expected/`. The regression test
`tests/managementpacks/test_docs_gen_stitch_targets.py` regenerates each
docset and requires it to match byte for byte, so a pak that does not
declare the stanza keeps exactly the docs it had.

- `tree_pak`: an own-kind tree (foreign parent, `/recursive` level,
  multi-parent kind) plus a `cross_mp_edges` stanza.
- `stitch_only_pak`: the vsanperf shape, an adapter instance and one
  collector kind, no TraversalSpecKind.

Do not regenerate `expected/` to make the test pass: a diff there is a
docs change for every pak without the stanza.
