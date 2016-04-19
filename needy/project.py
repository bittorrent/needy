import os
import sys
import logging

from .process import command
from .process import command_output


def evaluate_conditionals(configuration, target):
    should_continue = True
    while should_continue:
        if 'conditionals' not in configuration:
            return configuration

        copy = configuration.copy()
        copy.pop('conditionals')
        should_continue = False

        for key, cases in configuration['conditionals'].items():
            values = []
            if key == 'platform':
                values.append(target.platform.identifier())
                if target.platform.is_host():
                    values.append('host')
                    values.append(sys.platform)
            elif key == 'architecture':
                values.append(target.architecture)
            else:
                raise ValueError('unknown conditional key')

            for case, config in cases.items():
                if case in values or (case[0] == '!' and case[1:] not in values) or case == '*':
                    should_continue = True
                    copy.update(config)
                    break

        configuration = copy

    return configuration


class ProjectDefinition:
    def __init__(self, target, directory, configuration):
        self.target = target
        self.directory = directory
        self.configuration = configuration


class Project:
    def __init__(self, definition, needy):
        self.__definition = definition
        self.needy = needy

    @staticmethod
    def identifier():
        raise NotImplementedError('Subclasses of Project must override identifier')

    @staticmethod
    def is_valid_project(definition, needy):
        raise NotImplementedError('Subclasses of Project must override is_valid_project')

    @staticmethod
    def configuration_keys():
        """ should return a list of configuration keys that this project uses """
        return []

    def target(self):
        return self.__definition.target

    def directory(self):
        return self.__definition.directory

    def configuration(self, key=None):
        if key is None:
            return self.__definition.configuration
        if key in self.__definition.configuration:
            return self.__definition.configuration[key]
        return None

    def build_concurrency(self):
        concurrency = self.needy.build_concurrency()
        if self.configuration('max-concurrency') is not None:
            concurrency = min(concurrency, self.configuration('max-concurrency'))
        return concurrency

    def project_targets(self):
        return self.configuration('targets') or []

    def set_configuration_variables(self, **kwargs):
        self.__configuration_variables = kwargs

    def evaluate(self, str_or_list):
        l = [] if not str_or_list else (str_or_list if isinstance(str_or_list, list) else [str_or_list])
        return [str.format(**self.__configuration_variables) for str in l]

    def run_commands(self, commands):
        for command in self.evaluate(commands):
            self.command(command)

    def environment_overrides(self):
        ret = {}

        c_compiler = self.target().platform.c_compiler(self.target().architecture)
        if c_compiler:
            ret['CC'] = c_compiler

        cxx_compiler = self.target().platform.cxx_compiler(self.target().architecture)
        if cxx_compiler:
            ret['CXX'] = cxx_compiler

        libraries = self.target().platform.libraries(self.target().architecture)
        if len(libraries) > 0:
            ret['LDFLAGS'] = ' '.join(libraries)

        binary_paths = self.target().platform.binary_paths(self.target().architecture)
        if len(binary_paths) > 0:
            ret['PATH'] = ('%s:%s' % (':'.join(binary_paths), os.environ['PATH']))

        return ret

    def pre_build(self, output_directory):
        self.run_commands(self.configuration('pre-build'))

    def configure(self, build_directory):
        pass

    def post_build(self, output_directory):
        self.run_commands(self.configuration('post-build'))
        build_dirs = [os.path.join(output_directory, d) for d in ['include', 'lib']]
        self.__create_directories(build_dirs)

    def __create_directories(self, dirs):
        for d in dirs:
            if not os.path.exists(d):
                os.makedirs(d)

    def command(self, cmd, verbosity=logging.INFO, environment_overrides={}):
        env = environment_overrides.copy()
        env.update(self.environment_overrides())
        command(cmd, environment_overrides=env)

    def command_output(self, arguments, verbosity=logging.INFO, environment_overrides={}):
        return command_output(arguments, environment_overrides=environment_overrides)
