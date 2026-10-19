# -*- coding: utf-8 -*-
# Generated selected symbols from BBE block_groups.py; do not edit.
from __future__ import unicode_literals
from . import block_registry as registry


_BED_DIRECTIONS = ((0, 0, 1), (-1, 0, 0), (0, 0, -1), (1, 0, 0))


_NON_PAIRED_UPPER_BLOCKS = frozenset(('minecraft:pale_moss_carpet',))


_MIN_GROUP_GROWTH = {'minecraft:pitcher_crop': 3}


def from_states(name, properties):
    resolver = getattr(registry, 'from_states', None)
    if resolver is not None:
        return resolver(name, properties)
    for aux in registry.aux_values(name):
        value = (name, aux)
        if registry.states(value) == properties:
            return value
    return None


def _part_key(name, properties):
    if properties.get('growth', 0) < _MIN_GROUP_GROWTH.get(name, 0):
        return None
    if 'upper_block_bit' in properties and name not in _NON_PAIRED_UPPER_BLOCKS:
        return 'upper_block_bit'
    if properties.get('sea_grass_type') in ('double_bot', 'double_top'):
        return 'sea_grass_type'
    if 'head_piece_bit' in properties:
        return 'head_piece_bit'
    return None


def group_partner(value):
    """Return ``(offset, value)`` for the reciprocal half, or None if ungrouped."""
    try:
        value = registry.canonical(value)
    except ValueError:
        return None
    properties = registry.states(value)
    if properties is None:
        return None
    key = _part_key(value[0], properties)
    if key == 'upper_block_bit':
        upper = properties['upper_block_bit']
        offset = (0, -1 if upper else 1, 0)
        paired_value = not upper
    elif key == 'sea_grass_type':
        lower = properties['sea_grass_type'] == 'double_bot'
        offset = (0, 1 if lower else -1, 0)
        paired_value = 'double_top' if lower else 'double_bot'
    elif key == 'head_piece_bit':
        head = properties['head_piece_bit']
        direction = properties.get('direction')
        if type(direction) is not int or not 0 <= direction < len(_BED_DIRECTIONS):
            raise ValueError('床方向状态无效，无法解析床头与床脚')
        sign = -1 if head else 1
        offset = tuple(sign * value for value in _BED_DIRECTIONS[direction])
        paired_value = not head
    else:
        return None
    paired = dict(properties)
    paired[key] = paired_value
    partner = from_states(value[0], paired)
    if partner is None:
        raise ValueError('原版方块表缺少多格方块的对应部件：%s' % value[0])
    return offset, partner


def preserve_group_part(value, original):
    """Keep the selected half when replacing one paired block with another."""
    requested = value
    try:
        original = registry.canonical(original)
        value = registry.canonical(value)
    except ValueError:
        return requested
    original_states = registry.states(original)
    value_states = registry.states(value)
    if original_states is None or value_states is None:
        return value
    original_key = _part_key(original[0], original_states)
    value_key = _part_key(value[0], value_states)
    if original_key is not None and original_key == value_key:
        value_states[value_key] = original_states[original_key]
        return from_states(value[0], value_states) or requested
    return requested


def group_is_upper(value):
    try:
        value = registry.canonical(value)
    except ValueError:
        return False
    properties = registry.states(value) or {}
    key = _part_key(value[0], properties)
    if key == 'upper_block_bit':
        return properties[key] is True
    if key == 'sea_grass_type':
        return properties[key] == 'double_top'
    if key == 'head_piece_bit':
        return properties[key] is True
    return False
