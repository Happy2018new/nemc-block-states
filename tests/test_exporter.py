"""Guard against silently exporting a partial rule after upstream dependencies change."""
import sys
import unittest
if sys.version_info[0] >= 3:
    from pathlib import Path
    from tools.extract_symbols import extract_groups
    ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(sys.version_info[0] < 3, 'Export tooling requires Python 3; runtime tests are separate')
class SymbolExtractionTests(unittest.TestCase):
    def source(self):
        return (ROOT / 'nemc_block_states/block_groups.py').read_bytes()

    def test_dependency_change_is_rejected(self):
        modified = self.source().replace(b'def group_partner(value):',
                                        b'def group_partner(value):\n    unaudited_world_query(value)')
        with self.assertRaisesRegex(ValueError, 'unaudited_world_query'):
            extract_groups(modified)

    def test_new_local_import_is_rejected(self):
        modified = self.source().replace(b'def group_partner(value):',
                                        b'def group_partner(value):\n    import mod.client.extraClientApi')
        with self.assertRaisesRegex(ValueError, 'gained an import'):
            extract_groups(modified)

    def test_missing_symbol_is_rejected(self):
        modified = self.source().replace(b'def group_is_upper(value):', b'def renamed_group_is_upper(value):')
        with self.assertRaisesRegex(ValueError, 'Missing or changed group symbol'):
            extract_groups(modified)

    def test_shadowed_builtin_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'shadows an exported builtin'):
            extract_groups(self.source() + b'\nlen = external_count\n')

    def test_selected_definitions_regenerate_without_host_imports(self):
        source = self.source()
        generated = extract_groups(source)
        self.assertEqual(source, generated)
        self.assertNotIn(b'from .cell', generated)
        self.assertNotIn(b'from .visible_actor', generated)


if __name__ == '__main__':
    unittest.main()
