"""Regenerate a small pure snapshot from the authoritative BBE checkout.

This tool is Python 3 tooling. Generated/runtime modules remain Python 2.7 and
Python 3 compatible. The host checkout is only read, never modified.
"""
import argparse
import ast
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

from extract_symbols import GROUP_SYMBOLS, extract_groups


ROOT = Path(__file__).resolve().parents[1]
PROJECTION = 'behavior_pack/modern_projection/projection/'
MODULES = ('block_registry.py', 'block_registry_data.py', 'state_transform.py',
           'block_traits.py', 'block_traits_data.py')
GENERATOR_VERSION = 2
EVIDENCE = (
    'tools/generate_block_registry.py',
    'tools/generate_block_traits.py',
    'tools/data/block_registry_manifest.json',
    'tools/data/legacy_block_aliases.json',
    'tools/data/native_block_metadata_nemc_3.9.0.401155.json',
    'tools/data/native_snow_overlays_nemc_3.9.0.401155.json',
    'tools/data/native_snow_states_nemc_3.9.0.401155.json',
    'tools/data/native_paired_snow_nemc_3.9.0.401155.json',
    'tools/data/native_water_overlays_nemc_3.9.0.401155.json',
    'docs/reference/block_palettes/audit_nemc_3.9_to_3.10_20261017.json',
    'docs/reference/block_palettes/diff_nemc_3.9_to_3.10_20261017.json',
    'docs/reference/block_palettes/nemc_3.10_user_dump_20261017.json.gz',
)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def constants(raw, names):
    """Read only literal assignments, without executing upstream modules."""
    selected = {}
    for node in ast.parse(raw).body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in names:
                selected[target.id] = ast.literal_eval(node.value)
    missing = set(names) - set(selected)
    if missing:
        raise ValueError('Missing source constants: ' + ', '.join(sorted(missing)))
    return selected


def source_record(host, path):
    raw = (host / path).read_bytes()
    return {'path': path, 'sha256': digest(raw), 'bytes': len(raw)}


def _comparison(host, audit, palette):
    rows = audit['namespace_comparison']['minecraft']
    if (rows['added_records'] or rows['removed_records'] or
            rows['typed_state_changes_at_shared_aux'] or rows['default_aux_changes'] or
            rows['normalized_all_fields_old_sha256'] != rows['normalized_all_fields_new_sha256']):
        raise ValueError('Recorded 3.10 vanilla comparison no longer proves equality')
    archive = (host / audit['sources']['new']['archive']).read_bytes()
    if (palette['sha256'] != audit['sources']['old']['sha256'].lower() or
            digest(archive) != audit['sources']['new']['gzip_sha256'].lower()):
        raise ValueError('Palette comparison source identities differ')
    new_raw = gzip.decompress(archive)
    if digest(new_raw) != audit['sources']['new']['sha256'].lower():
        raise ValueError('Archived user dump differs from its recorded original bytes')
    old_rows = json.loads((host / palette['path']).read_bytes())['blocks']
    new_rows = json.loads(new_raw)['blocks']
    for records in (old_rows, new_rows):
        vanilla = sorted((row for row in records if row['name'].startswith('minecraft:')),
                         key=lambda row: (row['name'], row['data']))
        normalized = json.dumps(vanilla, ensure_ascii=True, sort_keys=True,
                                separators=(',', ':')).encode('utf8')
        if (len(vanilla) != rows['old_records'] or
                len({row['name'] for row in vanilla}) != rows['old_names'] or
                digest(normalized) != rows['normalized_all_fields_old_sha256']):
            raise ValueError('Archived vanilla records do not reproduce the comparison audit')
    return {
        'scope': 'minecraft: records in the two archived dumps only',
        'version_label': audit['new_version_label'],
        'exact_runtime_version': None,
        'version_origin': 'user statement; no version embedded in dump',
        'source_sha256': audit['sources']['new']['sha256'].lower(),
        'archive_sha256': audit['sources']['new']['gzip_sha256'].lower(),
        'normalized_all_fields_sha256': rows['normalized_all_fields_old_sha256'],
        'vanilla_names': rows['old_names'],
        'vanilla_records': rows['old_records'],
        'extends_traits_or_render_qualification': False,
        'authorizes_whole_palette_version_match': False,
    }


def build(host):
    host = host.resolve()
    source = json.loads((host / 'tools/data/block_registry_manifest.json').read_text(encoding='utf8'))
    registry = constants((host / PROJECTION / 'block_registry_data.py').read_bytes(),
                         ('SOURCE_VERSION', 'SOURCE_SHA256', 'RECORD_COUNT'))
    traits = constants((host / PROJECTION / 'block_traits_data.py').read_bytes(),
                       ('SCHEMA_VERSION', 'SOURCE_VERSION', 'SOURCE_SHA256'))
    palette = source_record(host, source['source_file'])
    identity = registry['SOURCE_SHA256'].lower()
    if (palette['sha256'] != identity or source['source_sha256'].lower() != identity or
            traits['SOURCE_SHA256'].lower() != identity or
            traits['SOURCE_VERSION'] != registry['SOURCE_VERSION'] or
            source['game_version'] != registry['SOURCE_VERSION'] or
            source['record_count'] != registry['RECORD_COUNT']):
        raise ValueError('Registry, traits, manifest and source palette identities differ')
    audit = json.loads((host / EVIDENCE[-3]).read_text(encoding='utf8'))
    module_rows = [source_record(host, PROJECTION + name) for name in MODULES]
    outputs = {'nemc_block_states/' + name: (host / PROJECTION / name).read_bytes()
               for name in MODULES}
    group_source = source_record(host, PROJECTION + 'block_groups.py')
    group_raw = extract_groups((host / group_source['path']).read_bytes())
    outputs['nemc_block_states/block_groups.py'] = group_raw
    generated_rows = [dict(row, destination='nemc_block_states/' + Path(row['path']).name,
                           mode='byte-for-byte', source_sha256=row['sha256']) for row in module_rows]
    generated_rows.append(dict(group_source, destination='nemc_block_states/block_groups.py',
                               mode='selected-symbols', symbols=list(GROUP_SYMBOLS),
                               source_sha256=group_source['sha256'], sha256=digest(group_raw)))
    tracked = [row['path'] for row in generated_rows] + list(EVIDENCE) + [source['source_file']]
    dirty = subprocess.check_output(
        ['git', '-C', str(host), 'status', '--porcelain=v1', '--untracked-files=all', '--'] + tracked,
        text=True, encoding='utf8').splitlines()
    manifest = {
        'schema_version': 1,
        'snapshot_version': 2,
        'package_version': '0.1.0',
        'status': 'independently importable snapshot; host is not integrated',
        'authoritative_repository': 'https://github.com/Happy2018new/better-building-editor',
        'source_commit': subprocess.check_output(
            ['git', '-C', str(host), 'rev-parse', 'HEAD'], text=True).strip(),
        'source_worktree_changes': dirty,
        'game_version': registry['SOURCE_VERSION'],
        'block_palette_sha256': identity,
        'record_count': registry['RECORD_COUNT'],
        'name_count': source['name_count'],
        'state_key_count': source['state_key_count'],
        'palette': palette,
        'traits_schema_version': traits['SCHEMA_VERSION'],
        'generator': {'path': 'tools/sync_from_bbe.py', 'version': GENERATOR_VERSION,
                      'sha256': digest(Path(__file__).read_bytes()),
                      'symbol_extractor_sha256': digest((ROOT / 'tools/extract_symbols.py').read_bytes())},
        'modules': generated_rows,
        'upstream_generators_and_evidence': [source_record(host, path) for path in EVIDENCE],
        'vanilla_palette_equivalence': _comparison(host, audit, palette),
        'boundary': {
            'native_vanilla_names': 1321,
            'native_vanilla_records': 15839,
            'host_preview_names': 19,
            'host_preview_records': 19,
            'cell_document_transactions': 'remain in host',
            'paired_block_rules': 'pure part relations extracted; cell/chest transactions remain in host',
            'typed_nbt_and_renderer_fields': 'remain in host for this snapshot',
        },
    }
    encoded = json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + '\n'
    outputs['snapshot_manifest.json'] = encoded.encode('ascii')
    outputs['nemc_block_states/_snapshot.py'] = (
        '# Generated by tools/sync_from_bbe.py; do not edit.\n'
        'import json\n\nMANIFEST = json.loads(' + repr(encoded) + ')\n').encode('ascii')
    outputs['LICENSE'] = (host / 'LICENSE').read_bytes()
    return outputs


def sync(host, check=False):
    outputs = build(host)
    stale = [name for name, raw in outputs.items()
             if not (ROOT / name).exists() or (ROOT / name).read_bytes() != raw]
    if check and stale:
        raise ValueError('Snapshot differs from source: ' + ', '.join(sorted(stale)))
    if not check:
        for name, raw in outputs.items():
            path = ROOT / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    print(json.dumps({'check': check, 'outputs': len(outputs),
                      'bytes': sum(map(len, outputs.values())), 'stale': len(stale)}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='BBE checkout root (read-only)')
    parser.add_argument('--check', action='store_true', help='Verify without writing any files')
    args = parser.parse_args()
    sync(args.source, args.check)
