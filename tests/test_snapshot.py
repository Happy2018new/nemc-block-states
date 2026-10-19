# -*- coding: utf-8 -*-
"""Independent runtime and transform contracts, runnable on Python 2.7 and 3."""
from __future__ import unicode_literals
import hashlib
import io
import json
import os
import sys
import unittest

from nemc_block_states import block_groups as groups
from nemc_block_states import block_registry as registry
from nemc_block_states import block_traits as traits
from nemc_block_states import provenance
from nemc_block_states import state_transform as transform


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys.version_info[0] == 2:
    ROOT = ROOT.decode(sys.getfilesystemencoding())
INVERSE = {'rotate_y90': 'rotate_y270', 'rotate_y180': 'rotate_y180',
           'rotate_y270': 'rotate_y90', 'mirror_x': 'mirror_x',
           'mirror_y': 'mirror_y', 'mirror_z': 'mirror_z'}


def typed(properties):
    return dict((key, (type(value).__name__, value)) for key, value in properties.items())


class SnapshotTests(unittest.TestCase):
    def test_source_identity_rejects_unrelated_versions_and_palettes(self):
        provenance.require_source(registry.source_version(), registry.fingerprint().upper())
        with self.assertRaises(ValueError):
            provenance.require_source('NEMC 3.10.0.420447', registry.fingerprint())
        with self.assertRaises(ValueError):
            provenance.require_source(registry.source_version(), '0' * 64)

    def test_manifest_is_detached_and_distinguishes_comparison_from_qualification(self):
        first = provenance.snapshot_manifest()
        first['game_version'] = 'mutated'
        first['vanilla_palette_equivalence']['vanilla_names'] = 0
        current = provenance.snapshot_manifest()
        self.assertEqual(registry.source_version(), current['game_version'])
        self.assertEqual(1321, current['vanilla_palette_equivalence']['vanilla_names'])
        self.assertFalse(current['vanilla_palette_equivalence']['extends_traits_or_render_qualification'])
        self.assertIsNone(current['vanilla_palette_equivalence']['exact_runtime_version'])

    def test_snapshot_files_match_manifest_and_no_sdk_is_imported(self):
        with io.open(os.path.join(ROOT, 'snapshot_manifest.json'), encoding='ascii') as stream:
            source = json.load(stream)
        self.assertEqual(source, provenance.snapshot_manifest())
        for row in source['modules']:
            with open(os.path.join(ROOT, row['destination']), 'rb') as stream:
                self.assertEqual(row['sha256'], hashlib.sha256(stream.read()).hexdigest())
        self.assertFalse(any(name == 'mod' or name.startswith('mod.') for name in sys.modules))
        self.assertFalse(any(name == 'projection' or name.startswith('projection.') for name in sys.modules))

    def test_every_record_round_trips_with_distinct_scalar_types(self):
        count = 0
        for name in registry.BLOCKS:
            for aux in registry.aux_values(name):
                material = (name, aux)
                self.assertEqual(material, registry.canonical(material))
                properties = registry.states(material)
                resolved = registry.from_states(name, properties)
                self.assertIsNotNone(resolved)
                self.assertEqual(typed(properties), typed(registry.states(resolved)))
                count += 1
        self.assertEqual(registry.RECORD_COUNT, count)

    def test_all_six_operations_preserve_native_legality_and_inverse(self):
        count = 0
        for name in registry.BLOCKS:
            for aux in registry.aux_values(name):
                material = (name, aux)
                expected = typed(registry.states(material))
                for operation in transform.OPERATIONS:
                    target = transform.transform(material, operation)
                    self.assertEqual(name, target[0])
                    self.assertIn(target[1], registry.aux_values(name))
                    actual = transform.transform(target, INVERSE[operation])
                    self.assertEqual(expected, typed(registry.states(actual)))
                    count += 1
        self.assertEqual(6 * registry.RECORD_COUNT, count)

    def test_known_geometric_results_and_input_immutability(self):
        source = {'weirdo_direction': 0, 'upside_down_bit': False}
        self.assertEqual({'weirdo_direction': 2, 'upside_down_bit': False},
                         transform.transform_states(source, 'rotate_y90'))
        self.assertEqual({'weirdo_direction': 0, 'upside_down_bit': True},
                         transform.transform_states(source, 'mirror_y'))
        self.assertEqual({'weirdo_direction': 0, 'upside_down_bit': False}, source)
        self.assertEqual({'rail_direction': 7},
                         transform.transform_states({'rail_direction': 6}, 'rotate_y90'))
        self.assertEqual({'pillar_axis': 'z'},
                         transform.transform_states({'pillar_axis': 'x'}, 'rotate_y90'))

    def test_unknown_states_and_wrong_bool_types_fail_closed(self):
        for source in ({'future_direction': 'north'}, {'upside_down_bit': 1},
                       {'weirdo_direction': True}, {'facing_direction': 6}):
            with self.assertRaises(ValueError):
                transform.transform_states(source, 'rotate_y90')
        properties = registry.states(('minecraft:oak_stairs', 0))
        properties['upside_down_bit'] = 0
        self.assertIsNone(registry.from_states('minecraft:oak_stairs', properties))

    def test_aliases_and_unknown_mod_blocks_keep_existing_boundaries(self):
        self.assertEqual(('minecraft:cyan_stained_glass', 0),
                         registry.canonical(('minecraft:stained_glass', 9)))
        self.assertEqual(('minecraft:granite', 0), registry.canonical(('minecraft:stone', 1)))
        self.assertIsNone(registry.try_canonical(('minecraft:cyan_stained_glass', 32767)))
        custom = ('custom:unregistered', 7)
        self.assertEqual(custom, registry.canonical(custom))
        self.assertIsNone(registry.states(custom))
        with self.assertRaises(ValueError):
            transform.transform(custom, 'rotate_y90')

    def test_traits_keep_observed_state_and_unknown_boundaries(self):
        self.assertTrue(traits.is_solid(('minecraft:stone', 0)))
        self.assertFalse(traits.is_solid(('minecraft:glass', 0)))
        self.assertEqual('supported', traits.snow_capability(('minecraft:poppy', 0)))
        self.assertEqual('unsupported', traits.snow_capability(('minecraft:tall_grass', 0)))
        self.assertEqual('unknown', traits.snow_capability(('minecraft:poppy', 999)))
        self.assertEqual('unknown', traits.snow_capability(('minecraft:poppy', False)))
        self.assertEqual('complete', traits.water_capabilities_status())
        self.assertTrue(traits.is_waterloggable(('minecraft:oak_fence', 0)))
        self.assertFalse(traits.is_waterloggable(('minecraft:stone', 0)))

    def test_all_derived_partners_are_reciprocal_and_transform_with_offsets(self):
        paired = 0
        for name in registry.BLOCKS:
            for aux in registry.aux_values(name):
                material = (name, aux)
                partner = groups.group_partner(material)
                if partner is None:
                    continue
                offset, other = partner
                inverse_offset, restored = groups.group_partner(other)
                self.assertEqual(tuple(-value for value in offset), inverse_offset)
                self.assertEqual(typed(registry.states(material)), typed(registry.states(restored)))
                for operation in transform.OPERATIONS:
                    moved_offset, moved_other = groups.group_partner(transform.transform(material, operation))
                    x, y, z = offset
                    if operation.startswith('rotate_y'):
                        for unused in range(int(operation[8:]) // 90):
                            x, z = -z, x
                    elif operation == 'mirror_x':
                        x = -x
                    elif operation == 'mirror_y':
                        y = -y
                    elif operation == 'mirror_z':
                        z = -z
                    self.assertEqual((x, y, z), moved_offset)
                    self.assertEqual(typed(registry.states(transform.transform(other, operation))),
                                     typed(registry.states(moved_other)))
                paired += 1
        self.assertEqual(722, paired)

    def test_partners_exclude_unpaired_carpet_and_young_pitcher_crop(self):
        self.assertIsNone(groups.group_partner(('minecraft:pale_moss_carpet', 0)))
        self.assertIsNone(groups.group_partner(('minecraft:pitcher_crop', 0)))
        self.assertIsNone(groups.group_partner(('custom:unregistered', 0)))
        upper = registry.from_states('minecraft:acacia_door',
                                     dict(registry.states(('minecraft:acacia_door', 0)), upper_block_bit=True))
        replacement = groups.preserve_group_part(('minecraft:birch_door', 0), upper)
        self.assertTrue(groups.group_is_upper(replacement))
        self.assertEqual('minecraft:birch_door', replacement[0])


if __name__ == '__main__':
    unittest.main()
