"""
Simple helper to convert a C header file to rohitab's API Monitor
"""
import os
import os.path as osp
import argparse
import xml.etree.ElementTree as ET
from pycparser import c_parser, c_ast


class ApiMonitorTypes:
    def __init__(self):
        self.definitions = set()
        self.apimonitor_base_dir = None

    def is_defined(self, typename):
        return typename in self.definitions

    def _basename_to_path(self, basename):
        if self.apimonitor_base_dir:
            base_dir = self.apimonitor_base_dir
        else:
            base_dir = osp.join(os.getenv('ChocolateyInstall'), 'lib/apimonitor/tools/API Monitor (rohitab.com)')
        print('include', basename)
        path = osp.join(base_dir, 'API/Headers', basename + ('.xml' if not basename.endswith('.xml') else ''))
        assert osp.exists(path)
        return path

    def parse(self, et):
        for el in et.iter('Variable'):
            self.definitions.add(el.attrib['Name'])
        for el in et.findall('Include'):
            path = el.attrib['Filename']
            if path.startswith('Headers'):
                self.parse_system_header(path[len('Headers') + 1:])

    def parse_system_header(self, basename):
        path = self._basename_to_path(basename)
        self.parse(ET.parse(path))

    @classmethod
    def read_known_types(cls, includes=None, apimonitor_base_dir=None):
        obj = cls()
        obj.apimonitor_base_dir = apimonitor_base_dir
        if includes:
            for inc in includes:
                obj.parse_system_header(inc)
        else:
            obj.parse_system_header('common.h')
        return obj


class ApiPrinter(c_ast.NodeVisitor):
    def __init__(self, fout):
        super().__init__()
        self.fout = fout
        self.success_is = 0
        self.return_value_is_not_error = set()
        self.known_types = ApiMonitorTypes()
        self.unknown_types = set()

    def _write_parameters(self, params):
        for param in params:
            if isinstance(param.type, c_ast.TypeDecl):
                typestr = ' '.join(param.type.quals + param.type.type.names)
            elif isinstance(param.type, c_ast.PtrDecl):
                if isinstance(param.type.type, c_ast.TypeDecl):
                    typestr = (' '.join(param.type.type.quals + param.type.type.type.names)) + '*'
                elif isinstance(param.type.type, c_ast.PtrDecl):
                    if isinstance(param.type.type.type, c_ast.TypeDecl):
                        typestr = (' '.join(param.type.type.type.quals + param.type.type.type.type.names)) + '**'
                    else:
                        raise RuntimeError
                else:
                    raise RuntimeError
            elif isinstance(param.type, c_ast.ArrayDecl):
                if isinstance(param.type.type, c_ast.TypeDecl):
                    typestr = (' '.join(param.type.type.quals + param.type.type.type.names)) + '*'
                else:
                    raise RuntimeError
            else:
                raise RuntimeError
            if not self.known_types.is_defined(typestr):
                self.unknown_types.add(typestr)
            print('\t\t\t<Param Type="%s" Name="%s" />' % (typestr, param.name), file=self.fout)

    def _write_return_type(self, node):
        if node.type.declname in self.return_value_is_not_error and node.type.type.names[0] == 'BOOL':
            print('\t\t\t<Return Type="%s" />' % 'int', file=self.fout)
        else:
            print('\t\t\t<Return Type="%s" />' % (''.join(node.type.type.names)), file=self.fout)

    def _write_success_hint(self, node):
        if node.type.type.names[0] != 'void' and node.type.declname not in self.return_value_is_not_error:
            if self.success_is == 0:
                print('\t\t\t<Success Return="Equal" Value="0" />', file=self.fout)
            else:
                print('\t\t\t<Success Return="NotEqual" Value="0" />', file=self.fout)

    def visit_FuncDecl(self, node: c_ast.FuncDecl):
        print('\t\t<Api Name="%s">' % node.type.declname, file=self.fout)
        print(node.type.declname)
        self._write_parameters(node.args.params)
        self._write_return_type(node)
        self._write_success_hint(node)
        print('\t\t</Api>', file=self.fout)


class CHeader:
    def __init__(self, string, filename='<stdin>'):
        self.filename = filename
        self.module = osp.splitext(osp.basename(filename))[0] + '.dll'
        self.ast = c_parser.CParser().parse(string, filename=filename)
        self.calling_convention = None
        self.return_value_is_not_error = set()
        self.include = []
        self.success_is = 0
        self.known_types = ApiMonitorTypes()
        self._custom_definitions = []

    def _write_include_section(self, fout):
        for header in self.include:
            print('\t<Include Filename="Headers\\%s.xml" />' % header, file=fout)

    def _write_module_open_tag(self, fout):
        print('\t<Module Name="%s"' % self.module, file=fout, end='')
        if self.calling_convention:
            print(' CallingConvention="%s"' % self.calling_convention, file=fout, end='')
        print('>', file=fout)

    def _write_custom_definitions(self, fout):
        for definition in self._custom_definitions:
            fout.write('\t\t')
            definition.tail = '\n'
            ET.ElementTree(definition).write(fout, encoding='unicode')

    def write_apimonitor_xml(self, path):
        with open(path, 'w') as fout:
            print('<ApiMonitor>', file=fout)
            self._write_include_section(fout)
            self._write_module_open_tag(fout)
            print('\t\t<Category Name="Custom" />', file=fout)
            self._write_custom_definitions(fout)
            printer = ApiPrinter(fout)
            printer.return_value_is_not_error = self.return_value_is_not_error
            printer.success_is = self.success_is
            printer.known_types = self.known_types
            printer.visit(self.ast)
            print('\t</Module>', file=fout)
            print('</ApiMonitor>', file=fout)
            if len(printer.unknown_types):
                print('unknown types:', ', '.join(printer.unknown_types))

    def add_custom_type_definition(self, path):
        et = ET.parse(path)
        self.known_types.parse(et)
        self._custom_definitions = list(et.iter('Variable'))

    @classmethod
    def from_file(cls, path):
        with open(path, 'r') as fin:
            obj = cls(fin.read(), path)
        return obj


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('header_file')
    p.add_argument('--error-return-type', default='int')
    p.add_argument('--apimonitor-installation-base')
    p.add_argument('--custom-types')
    p.add_argument('-b', '--returns-true-boolean', action='append')
    p.add_argument('-i', '--returns-true-int', action='append')
    p.add_argument('-o', '--output', default='api.xml')
    p.add_argument('-c', '--calling-convention', default='STDCALL')
    p.add_argument('-E', '--success-is', type=int)
    p.add_argument('-I', '--include', action='append')
    p.add_argument('-M', '--module')
    return p.parse_args()


def main():
    args = parse_args()
    cheader = CHeader.from_file(args.header_file)
    cheader.calling_convention = args.calling_convention
    if args.returns_true_boolean:
        cheader.return_value_is_not_error |= set(args.returns_true_boolean)
    if args.returns_true_int:
        cheader.return_value_is_not_error |= set(args.returns_true_int)
    cheader.include = args.include if args.include else []
    if args.module:
        cheader.module = args.module
    if args.success_is:
        cheader.success_is = args.success_is
    cheader.known_types = ApiMonitorTypes.read_known_types(args.include, args.apimonitor_installation_base)
    if args.custom_types:
        cheader.add_custom_type_definition(args.custom_types)
    cheader.write_apimonitor_xml(args.output)


if __name__ == '__main__':
    main()
