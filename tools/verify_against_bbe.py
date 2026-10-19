"""Compare the pure snapshot with a BBE checkout without changing that checkout."""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nemc_block_states import block_registry as registry
from nemc_block_states import block_traits as traits
from nemc_block_states import block_groups as groups
from nemc_block_states import provenance
from nemc_block_states import state_transform as transform


def typed(properties):
    if properties is None:
        return None
    return tuple(sorted((key, type(value).__name__, value) for key, value in properties.items()))


def outcome(function, *args):
    try:
        return ('result', function(*args))
    except ValueError as error:
        return (type(error).__name__, str(error))


def equal(actual, expected, context):
    if actual != expected:
        raise ValueError('Snapshot parity mismatch: %r' % (context,))


def verify(host):
    started = time.monotonic()
    manifest = provenance.snapshot_manifest()
    for row in manifest['modules']:
        if hashlib.sha256((host / row['path']).read_bytes()).hexdigest() != row['source_sha256']:
            raise ValueError('Host source changed; regenerate snapshot first: ' + row['path'])
    sys.path.insert(0, str(host / 'behavior_pack/modern_projection'))
    old_registry = importlib.import_module('projection.block_registry')
    old_traits = importlib.import_module('projection.block_traits')
    old_transform = importlib.import_module('projection.state_transform')
    old_groups = importlib.import_module('projection.block_groups')
    equal(registry.BLOCKS, old_registry.BLOCKS, 'packed blocks')
    equal(registry.ALIASES, old_registry.ALIASES, 'packed aliases')
    equal(registry.DEFAULT_AUX, old_registry.DEFAULT_AUX, 'default aux')
    equal(registry.catalogue_values(), old_registry.catalogue_values(), 'catalogue')
    equal(transform.OPERATIONS, old_transform.OPERATIONS, 'operations')
    counters = {'records': 0, 'transforms': 0, 'trait_queries': 0, 'aliases': 0,
                'group_queries': 0, 'paired_records': 0}
    for name in registry.BLOCKS:
        for aux in registry.aux_values(name):
            value = (name, aux)
            equal(typed(registry.states(value)), typed(old_registry.states(value)), value)
            equal(registry.from_states(name, registry.states(value)), old_registry.from_states(
                name, old_registry.states(value)), value)
            for operation in transform.OPERATIONS:
                equal(outcome(transform.transform, value, operation), outcome(
                    old_transform.transform, value, operation), (value, operation))
                counters['transforms'] += 1
            for method in ('is_solid', 'is_snow_coverable', 'snow_capability', 'is_waterloggable'):
                equal(outcome(getattr(traits, method), value), outcome(
                    getattr(old_traits, method), value), (method, value))
                counters['trait_queries'] += 1
            for method in ('group_partner', 'group_is_upper'):
                equal(outcome(getattr(groups, method), value), outcome(
                    getattr(old_groups, method), value), (method, value))
                counters['group_queries'] += 1
            requested = (name, registry.DEFAULT_AUX[name])
            equal(groups.preserve_group_part(requested, value), old_groups.preserve_group_part(
                requested, value), ('preserve_group_part', requested, value))
            counters['group_queries'] += 1
            if groups.group_partner(value) is not None:
                counters['paired_records'] += 1
            counters['records'] += 1
    for name in registry.ALIASES:
        for aux in registry._decode(name, registry.ALIASES, {}):
            equal(registry.try_canonical((name, aux)), old_registry.try_canonical((name, aux)), (name, aux))
            counters['aliases'] += 1
    return {
        'schema_version': 1,
        'passed': True,
        'source_commit': manifest['source_commit'],
        'source_game_version': registry.source_version(),
        'block_palette_sha256': registry.fingerprint(),
        'coverage': counters,
        'seconds': round(time.monotonic() - started, 3),
        'limits': ['offline parity only', 'no editor/projection/world integration',
                   '3.9 source traits are not new 3.10 runtime qualification'],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, help='Optional compact verification report')
    args = parser.parse_args()
    report = verify(args.source.resolve())
    encoded = json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + '\n'
    if args.output:
        if args.output.resolve().is_relative_to(args.source.resolve()):
            raise ValueError('Verification output must not write into the host checkout')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding='ascii')
    print(encoded, end='')
