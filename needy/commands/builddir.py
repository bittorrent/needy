from __future__ import print_function

from .. import command
from ..needy import ConfiguredNeedy


class BuildDirCommand(command.Command):
    def name(self):
        return 'builddir'

    def add_parser(self, group):
        short_description = 'gets the build directory for a need'
        parser = group.add_parser(self.name(), description=short_description.capitalize()+'.', help=short_description)
        parser.add_argument('library', help='the library to get the directory for').completer = command.library_completer
        parser.add_argument('-t', '--target', default='host', help='gets the directory for this target (example: ios:armv7)').completer = command.target_completer
        parser.add_argument('-u', '--universal-binary', help='gets the directory for this universal binary').completer = command.universal_binary_completer

    def execute(self, arguments):
        with ConfiguredNeedy('.', arguments) as needy:
            print(needy.build_directory(arguments.library,
                                        arguments.universal_binary if arguments.universal_binary else needy.target(arguments.target)), end='')
        return 0
