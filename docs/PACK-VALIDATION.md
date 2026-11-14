# Planning-pack validation

The included `validate_pack.py` runs without accounts or network access. It checks the schema shapes used by the pack, synthetic quote references and case ownership, passage hashes, collection hash, serialized search/card ordering, score arithmetic and current brief/confirmation revisions. It also runs full JSON Schema validation when the optional `jsonschema` package is available.

During preparation, the built-in shape and fixture-consistency checks passed. Full JSON Schema standards validation was not run because the optional package was not installed. The pack's validator does not test the future application, live provider access or medical correctness.

After bootstrap, Kiro must replace this limited artifact check with the application's meaningful API/domain/browser checks and separately report actual live integration smoke results. Do not copy a planning-pack PASS into the hackathon README as if the product passed tests.
