from functools import wraps

from .cd import cd
from .needy import ConfiguredNeedy
from .platforms import available_platforms
from .utility import DummyContextManager

try:
    from exceptions import NotImplementedError
except ImportError:
    pass


class Command:
    def name(self):
        raise NotImplementedError('name')

    def add_parser(self, group):
        pass

    def execute(self, arguments):
        raise NotImplementedError('execute')


def completer(f):
    @wraps(f)
    def wrapper(parsed_args, **kwds):
        import argcomplete
        try:
            with cd(parsed_args.C) if parsed_args.C else DummyContextManager() as _:
                return f(parsed_args=parsed_args, **kwds)
        except Exception as e:
            argcomplete.warn('An error occurred during argument completion: {}'.format(e))
    return wrapper


@completer
def library_completer(prefix, parsed_args, **kwargs):
    with ConfiguredNeedy('.', parsed_args) as needy:
        target_or_universal_binary = parsed_args.universal_binary if getattr(parsed_args, 'universal_binary', None) else needy.target(getattr(parsed_args, 'target', 'host'))
        return [name for name in needy.libraries(target_or_universal_binary).keys() if name.startswith(prefix)]


@completer
def target_completer(prefix, parsed_args, **kwargs):
    if ':' in prefix:
        # architectures don't have any formal constraints, but we can provide some common ones
        architectures = ['x86_64', 'i386', 'armv7', 'arm64', 'amd64']
        platform = prefix[:prefix.find(':')]
        return [result for result in [platform + ':' + architecture for architecture in architectures] if result.startswith(prefix)]
    platform_identifiers = available_platforms().keys()
    ret = [identifier for identifier in platform_identifiers if identifier.startswith(prefix)]
    if prefix in platform_identifiers:
        ret.append(prefix + ':')
    return ret


@completer
def universal_binary_completer(prefix, parsed_args, **kwargs):
    with ConfiguredNeedy('.', parsed_args) as needy:
        return [name for name in needy.universal_binary_names() if name.startswith(prefix)]
