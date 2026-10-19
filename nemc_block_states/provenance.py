# -*- coding: utf-8 -*-
"""Source identity checks without filesystem access or engine initialization."""
from copy import deepcopy

from ._snapshot import MANIFEST


def snapshot_manifest():
    """Return detached metadata; consumers cannot mutate the stored identity."""
    return deepcopy(MANIFEST)


def require_source(game_version, block_palette_sha256):
    """Reject a different version or whole-palette identity.

The user-supplied 3.10 comparison is limited vanilla-state evidence. It does not
authorize relabelling the 3.9 palette, traits or host render proxies as 3.10.
"""
    if game_version != MANIFEST['game_version']:
        raise ValueError('Block state snapshot game version mismatch: %s != %s' %
                         (game_version, MANIFEST['game_version']))
    if block_palette_sha256.lower() != MANIFEST['block_palette_sha256']:
        raise ValueError('Block state snapshot palette SHA-256 mismatch')
