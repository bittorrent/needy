from __future__ import print_function

import argparse
import os
import sys

from .needy import Needy
from .platform import available_platforms


def satisfy(args=[]):
    parser = argparse.ArgumentParser(
        prog='%s satisfy' % os.path.basename(sys.argv[0]),
        description='Satisfies library and universal binary needs.',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        'library',
        default=None,
        nargs='?',
        help='the library to satisfy. shell-style wildcards are allowed')
    parser.add_argument(
        '-t', '--target',
        default='host',
        help='builds needs for this target (example: iphone:armv7)')
    parser.add_argument(
        '-u', '--universal-binary',
        help='builds the universal binary with the given name')
    parser.add_argument(
        '-j', '--concurrency',
        default=1,
        const=0,
        nargs='?',
        type=int,
        help='number of jobs to process concurrently')
    for platform in available_platforms():
        platform.add_arguments(parser)
    parameters = parser.parse_args(args)

    needy = Needy('needs.json', parameters)

    if parameters.universal_binary:
        needy.satisfy_universal_binary(parameters.universal_binary, parameters.library)
    else:
        needy.satisfy_target(needy.target(parameters.target), parameters.library)

    return 0


def cflags(args=[]):
    parser = argparse.ArgumentParser(
        prog='%s cflags' % os.path.basename(sys.argv[0]),
        description='Gets compiler flags required for using the needs.',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('-t', '--target', default='host', help='gets flags for this target (example: iphone:armv7)')
    parameters = parser.parse_args(args)

    needy = Needy('needs.json', parameters)
    target = needy.target(parameters.target)

    print(' '.join([('-I%s' % path) for path in needy.include_paths(target)]), end='')
    return 0


def ldflags(args=[]):
    parser = argparse.ArgumentParser(
        prog='%s ldflags' % os.path.basename(sys.argv[0]),
        description='Gets linker flags required for using the needs.',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('-t', '--target', default='host', help='gets flags for this target (example: iphone:armv7)')
    parser.add_argument('-u', '--universal-binary', help='gets flags for this universal binary')
    parameters = parser.parse_args(args)

    needy = Needy('needs.json', parameters)

    print(' '.join([('-L%s' % path) for path in needy.library_paths(parameters.universal_binary if parameters.universal_binary else needy.target(parameters.target))]), end='')
    return 0

def builddir(args=[]):
    parser = argparse.ArgumentParser(
        prog='%s builddir' % os.path.basename(sys.argv[0]),
        description='Gets the build directory for a need.',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('library', help='the library to get the directory for')
    parser.add_argument('-t', '--target', default='host', help='gets the directory for this target (example: iphone:armv7)')
    parser.add_argument('-u', '--universal-binary', help='gets the directory for this universal binary')
    parameters = parser.parse_args(args)

    needy = Needy('needs.json', parameters)

    print(needy.build_directory(parameters.library, parameters.universal_binary if parameters.universal_binary else needy.target(parameters.target)), end='')
    return 0

def main(args=sys.argv):
    try:
        import colorama
        colorama.init()
    except ImportError:
        pass

    parser = argparse.ArgumentParser(
        description='Helps with dependencies.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=
"""available commands:
  satisfy     satisfies libraries / universal binary needs
  cflags      emits the compiler flags required to use the satisfied needs
  ldflags     emits the linker flags required to use the satisfied needs
  builddir    emits the build directory for a need

Use '%s <command> --help' to get help for a specific command.
""" % os.path.basename(sys.argv[0])
    )
    parser.add_argument('command', help='see below')
    parser.add_argument('args', nargs=argparse.REMAINDER)
    parameters = parser.parse_args(args[1:])

    if parameters.command == 'satisfy':
        return satisfy(parameters.args)
    if parameters.command == 'cflags':
        return cflags(parameters.args)
    if parameters.command == 'ldflags':
        return ldflags(parameters.args)
    if parameters.command == 'builddir':
        return builddir(parameters.args)

    print('\'%s\' is not a valid command. See \'%s --help\'.' % (parameters.command, os.path.basename(sys.argv[0])))
    return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv))
