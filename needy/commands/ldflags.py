from __future__ import print_function

from .. import command
from ..needy import ConfiguredNeedy


class LDFlagsCommand(command.Command):
    def name(self):
        return 'ldflags'

    def add_parser(self, group):
        short_description = 'gets linker flags required for using the needs'
        parser = group.add_parser(self.name(), description=short_description.capitalize()+'.', help=short_description)
        parser.add_argument('library', default=None, nargs='*', help='the library to get flags for. shell-style wildcards are allowed').completer = command.library_completer
        command.add_target_specification_args(parser, 'gets the flags')

    def execute(self, arguments):
        with ConfiguredNeedy('.', arguments) as needy:
            print(' '.join([('-L%s' % path) for path in needy.library_paths(
                arguments.universal_binary if arguments.universal_binary else needy.target(arguments.target), arguments.library)]), end='')
        return 0
