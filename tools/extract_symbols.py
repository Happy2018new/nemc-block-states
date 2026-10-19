"""Extract audited pure symbols and reject new global dependencies."""
import ast
import symtable


GROUP_SYMBOLS = (
    '_BED_DIRECTIONS', '_NON_PAIRED_UPPER_BLOCKS', '_MIN_GROUP_GROWTH',
    'from_states', '_part_key', 'group_partner', 'preserve_group_part', 'group_is_upper',
)
GROUP_BUILTINS = frozenset(('frozenset', 'getattr', 'tuple', 'dict', 'len',
                            'int', 'type', 'ValueError'))


def _global_references(table):
    result = {symbol.get_name() for symbol in table.get_symbols()
              if symbol.is_global() and symbol.is_referenced()}
    for child in table.get_children():
        result.update(_global_references(child))
    return result


def extract_groups(raw):
    source = raw.decode('utf8')
    tree = ast.parse(source)
    tables = {child.get_name(): child for child in symtable.symtable(
        source, 'block_groups.py', 'exec').get_children()}
    definitions = {}
    bound_names = set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            bound_names.update(alias.asname or alias.name.split('.')[0] for alias in node.names)
        if isinstance(node, ast.FunctionDef):
            bound_names.add(node.name)
            if node.name in GROUP_SYMBOLS:
                definitions[node.name] = node
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bound_names.add(target.id)
                    if target.id in GROUP_SYMBOLS:
                        definitions[target.id] = node
    if set(definitions) != set(GROUP_SYMBOLS):
        raise ValueError('Missing or changed group symbol: ' + ', '.join(
            sorted(set(GROUP_SYMBOLS) - set(definitions))))
    shadowed = GROUP_BUILTINS & bound_names
    if shadowed:
        raise ValueError('Source shadows an exported builtin: ' + ', '.join(sorted(shadowed)))
    allowed = set(GROUP_SYMBOLS) | GROUP_BUILTINS | {'registry'}
    lines = source.splitlines(keepends=True)
    fragments = []
    for name in GROUP_SYMBOLS:
        node = definitions[name]
        if isinstance(node, ast.FunctionDef):
            if node.decorator_list or node.args.defaults or node.args.kw_defaults or node.returns:
                raise ValueError('Group function definition changed; audit required: ' + name)
            references = _global_references(tables[name])
        else:
            references = {item.id for item in ast.walk(node.value) if isinstance(item, ast.Name)}
        if any(isinstance(item, (ast.Import, ast.ImportFrom)) for item in ast.walk(node)):
            raise ValueError('Group symbol gained an import: ' + name)
        unknown = references - allowed
        if unknown:
            raise ValueError('Group symbol %s gained unaudited dependencies: %s' %
                             (name, ', '.join(sorted(unknown))))
        fragments.append(''.join(lines[node.lineno - 1:node.end_lineno]).rstrip())
    header = ('# -*- coding: utf-8 -*-\n'
              '# Generated selected symbols from BBE block_groups.py; do not edit.\n'
              'from __future__ import unicode_literals\n'
              'from . import block_registry as registry\n\n\n')
    return (header + '\n\n\n'.join(fragments) + '\n').encode('utf8')
