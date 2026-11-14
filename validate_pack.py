"""Validate this handoff's fixture consistency, not medical correctness.

Run: python validate_pack.py
Optional full JSON Schema validation: pip install jsonschema
No network or provider credentials required by this script.
"""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parent

def load(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))

def walk(value):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from walk(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from walk(nested)

def validate_shape(value, spec, root):
    """Validate the subset used by the supplied schema, without dependencies.

    Full standards-level schema validation remains available with jsonschema.
    """
    if '$ref' in spec:
        name = spec['$ref'].removeprefix('#/$defs/')
        return validate_shape(value, root['$defs'][name], root)
    for keyword, exactly_one in [('anyOf', False), ('oneOf', True)]:
        if keyword in spec:
            successes = 0
            for alternative in spec[keyword]:
                try:
                    validate_shape(value, alternative, root)
                    successes += 1
                except (AssertionError, KeyError):
                    pass
            assert successes == 1 if exactly_one else successes >= 1
            return
    kind = spec.get('type')
    types = {'string': str, 'object': dict, 'array': list, 'boolean': bool,
             'integer': int, 'null': type(None)}
    if kind:
        assert type(value) is types[kind], (kind, type(value).__name__)
    if 'enum' in spec:
        assert value in spec['enum']
    if isinstance(value, str):
        assert len(value) >= spec.get('minLength', 0)
        if 'pattern' in spec:
            assert re.search(spec['pattern'], value)
    if type(value) is int and 'minimum' in spec:
        assert value >= spec['minimum']
    if isinstance(value, list):
        for item in value:
            validate_shape(item, spec['items'], root)
    if isinstance(value, dict):
        properties = spec.get('properties', {})
        assert set(spec.get('required', [])).issubset(value)
        for key, item in value.items():
            if key in properties:
                validate_shape(item, properties[key], root)
            else:
                additional = spec.get('additionalProperties', True)
                assert additional is not False, key
                if isinstance(additional, dict):
                    validate_shape(item, additional, root)

def main():
    schema = load('contracts/domain.schema.json')
    cases = load('data/synthetic/cases.json')
    collection = load('data/synthetic/collection.json')
    passages = {}
    case_ids = set()
    for case in cases:
        assert case['case_id'] not in case_ids
        case_ids.add(case['case_id'])
        assert case['source_kind'] == 'synthetic'
        assert case['article_url'] is None and case['article_identifiers'] == {}
        assert case['clinical_reviewed'] is False
        own = {}
        for passage in case['passages']:
            pid = passage['passage_id']
            assert pid not in passages
            assert passage['case_id'] == case['case_id']
            assert hashlib.sha256(passage['text'].encode()).hexdigest() == passage['sha256']
            own[pid] = passage['text']
            passages[pid] = passage['text']
        for node in walk(case):
            for evidence in node.get('evidence', []):
                assert evidence['source_type'] == 'case_passage'
                assert evidence['source_id'] in own
                assert evidence['quote'] in own[evidence['source_id']]
    expected_hash = hashlib.sha256(json.dumps(cases, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    assert collection['version'] == expected_hash
    assert collection['case_count'] == len(cases)
    assert collection['source_review_count'] == len(cases)

    examples = []
    for path in sorted((ROOT / 'contracts/examples').glob('*.json')):
        value = json.loads(path.read_text(encoding='utf-8'))
        examples.append(value)
        snapshot = value.get('snapshot', value)
        if 'turns' not in snapshot:
            continue
        turns = {turn['turn_id']: turn['text'] for turn in snapshot['turns']}
        for node in walk(snapshot):
            if set(('source_type', 'source_id', 'quote')).issubset(node):
                source_map = turns if node['source_type'] == 'patient_turn' else passages
                assert node['source_id'] in source_map, (path.name, node)
                assert node['quote'] in source_map[node['source_id']], (path.name, node)
        for search in snapshot['search_history']:
            assert search['collection_version'] == collection['version']
            assert search['ranked_case_ids'] == [card['case_id'] for card in search['cards']]
            for score in search['score_components']:
                assert score['total'] == sum(score[key] for key in ('shared_site','shared_symptom','shared_duration','shared_exposure'))
            for card in search['cards']:
                owned_passages = {p['passage_id'] for p in card['passages']}
                for node in walk(card):
                    if node.get('source_type') == 'case_passage':
                        assert node['source_id'] in owned_passages
        if snapshot['state'] == 'confirmed':
            assert snapshot['confirmed_revision'] == snapshot['revision']
        if snapshot['search_history']:
            assert snapshot['brief']['patient_revision'] == snapshot['revision']

    for case in cases:
        validate_shape(case, schema, schema)
    for example in examples:
        validate_shape(example, schema, schema)

    try:
        import jsonschema
    except ImportError:
        print('PASS: supplied schema shapes, fixture quotes, ownership, hashes, ranking metadata and revisions.')
        print('SKIPPED: optional full JSON Schema standards validation; install jsonschema to run it.')
    else:
        jsonschema.Draft202012Validator.check_schema(schema)
        validator = jsonschema.Draft202012Validator(schema)
        for case in cases:
            validator.validate(case)
        for example in examples:
            validator.validate(example)
        print('PASS: JSON Schema and fixture quotes, ownership, hashes, ranking metadata and revisions.')
    print('This validates planning assets only; no application or live integration has been tested.')

if __name__ == '__main__':
    main()
