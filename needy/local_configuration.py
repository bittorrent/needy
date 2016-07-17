import fcntl
import json
import os
import sys

from .filesystem import lock_file

from .caches.directory import Directory


class LocalConfiguration:
    """ This is a context manager that obtains exclusive read and write access to the given file."""

    def __init__(self, path, blocking=True):
        self.__path = path
        self.__configuration = {}
        self.__blocking = blocking

    def __enter__(self):
        directory = os.path.dirname(self.__path)
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
            except os.error as e:
                if not os.path.exists(directory):
                    raise e

        self.__fd = lock_file(self.__path, timeout=0)
        if self.__fd is None:
            if not self.__blocking:
                return None
            print('Waiting for other needy instances to terminate...')
            self.__fd = lock_file(self.__path)


        with open(self.__path, 'rt') as f:
            contents = f.read()
            if contents:
                self.__configuration = json.loads(contents)

        return self

    def __exit__(self, etype, value, traceback):
        with open(self.__path, 'wt') as f:
            json.dump(self.__configuration, f)
        if self.__fd:
            os.close(self.__fd)

    def development_mode(self, library_name):
        return self.__library_configuration(library_name, 'development_mode', False)

    def set_development_mode(self, library_name, enable=True):
        self.__set_library_configuration(library_name, 'development_mode', enable)

    def cache(self):
        if 'cache' in self.__configuration:
            cache_type = self.__configuration['cache']['type']
            for candidate in [Directory]:
                if cache_type == candidate.type():
                    return candidate.from_dict(self.__configuration['cache']['configuration'])
            raise RuntimeError('Invalid cache type: {}'.format(cache_type))

    def set_cache(self, path):
        if path:
            self.__configuration['cache'] = {
                'type': Directory.type(),
                'configuration': Directory(path=path).to_dict(),
            }
        else:
            del self.__configuration['cache']

    def __library_configuration(self, library_name, key, default=None):
        if 'libraries' not in self.__configuration or library_name not in self.__configuration['libraries']:
            return default
        return self.__configuration['libraries'][library_name][key]

    def __set_library_configuration(self, library_name, key, value):
        if 'libraries' not in self.__configuration:
            self.__configuration['libraries'] = {}
        if library_name not in self.__configuration['libraries']:
            self.__configuration['libraries'][library_name] = {}
        self.__configuration['libraries'][library_name][key] = value
