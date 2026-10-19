# -*- coding: utf-8 -*-
"""Package metadata; the runtime package itself has no third-party dependency."""
from setuptools import setup

setup(
    name='nemc-block-states',
    version='0.1.0',
    description='Versioned NEMC block states and semantic transforms',
    author='Happy2018new',
    url='https://github.com/Happy2018new/nemc-block-states',
    packages=['nemc_block_states'],
    python_requires='>=2.7,!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*',
    license='Proprietary; see LICENSE',
)
