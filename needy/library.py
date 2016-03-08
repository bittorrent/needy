import binascii
import hashlib
import json
import os
import shutil
import logging

from operator import itemgetter

try:
    from colorama import Fore
except ImportError:
    class EmptyStringAttributes:
        def __getattr__(self, name):
            return ''
    Fore = EmptyStringAttributes()

from .project import evaluate_conditionals
from .project import ProjectDefinition

from .sources.download import Download
from .sources.directory import Directory
from .sources.git import GitRepository

from .cd import cd
from .override_environment import OverrideEnvironment
from .target import Target

from .process import command

from .projects.androidmk import AndroidMkProject
from .projects.autotools import AutotoolsProject
from .projects.boostbuild import BoostBuildProject
from .projects.cmake import CMakeProject
from .projects.custom import CustomProject
from .projects.make import MakeProject
from .projects.source import SourceProject
from .projects.xcode import XcodeProject


class Library:
    def __init__(self, configuration, directory, needy):
        self.__configuration = configuration
        self.__directory = directory

        if 'download' in self.__configuration:
            self.source = Download(self.__configuration['download'], self.__configuration['checksum'], self.source_directory(), os.path.join(directory, 'download'))
        elif 'repository' in self.__configuration:
            self.source = GitRepository(self.__configuration['repository'], self.__configuration['commit'], self.source_directory())
        elif 'directory' in self.__configuration:
            self.source = Directory(self.__configuration['directory'] if os.path.isabs(self.__configuration['directory']) else os.path.join(needy.path(), self.__configuration['directory']), self.source_directory())
        else:
            raise ValueError('no source specified in configuration')

        self.needy = needy

    def configuration(self):
        return self.__configuration

    def project_configuration(self, target):
        return evaluate_conditionals(self.__configuration['project'] if 'project' in self.__configuration else dict(), target)

    def should_build(self, target):
        configuration = self.project_configuration(target)
        return 'build' not in configuration or configuration['build']

    def configuration_variables(self, target):
        return {
            'build_directory': self.build_directory(target),
            'platform': target.platform.identifier(),
            'architecture': target.architecture,
            'self_directory': self.needy.path()
        }

    def evaluate(self, str_or_list, target, **kwargs):
        l = [] if not str_or_list else (str_or_list if isinstance(str_or_list, list) else [str_or_list])
        variables = self.configuration_variables(target)
        variables.update(kwargs)
        return [str.format(**variables) for str in l]

    def build(self, target):
        if not self.should_build(target):
            return False

        print('Building for %s %s' % (target.platform.identifier(), target.architecture))

        if ' ' in self.__directory:
            print(Fore.YELLOW + '[WARNING]' + Fore.RESET + ' The build path contains spaces. Some build systems don\'t '
                  'handle spaces well, so if you have problems, consider moving the project or using a symlink.')

        self.source.clean()

        configuration = self.project_configuration(target)
        env_overrides = self.__parse_env_overrides(configuration['environment'] if 'environment' in configuration else None, target)

        with OverrideEnvironment(env_overrides):
            post_clean_commands = configuration['post-clean'] if 'post-clean' in configuration else []
            with cd(self.source_directory()):
                if isinstance(post_clean_commands, list):
                    for cmd in post_clean_commands:
                        command(cmd)
                else:
                    command(post_clean_commands)

            definition = ProjectDefinition(target, self.source_directory(), configuration)
            project = self.project(definition)
            project.set_configuration_variables(**self.configuration_variables(target))

            if not project:
                raise RuntimeError('unknown project type')

            build_directory = self.build_directory(target)

            if os.path.exists(build_directory):
                shutil.rmtree(build_directory)

            os.makedirs(build_directory)

            with cd(self.source_directory()):
                try:
                    project.configure(build_directory)
                    project.pre_build(build_directory)
                    project.build(build_directory)
                    project.post_build(build_directory)
                except:
                    shutil.rmtree(build_directory)
                    raise

            with open(self.build_status_path(target), 'w') as status_file:
                status = {
                    'configuration': binascii.hexlify(self.__configuration_hash(target))
                }
                json.dump(status, status_file)

        return True

    def __parse_env_overrides(self, overrides, target):
        if overrides is None:
            return dict()
        ret = overrides.copy()
        for k, v in ret.iteritems():
            ret[k] = self.evaluate(v, target, current=os.environ[k] if k in os.environ else '')[0]
        return ret

    def build_universal_binary(self, name, configuration):
        for platform, architectures in configuration.iteritems():
            for architecture in architectures:
                target = Target(self.needy.platform(platform), architecture)
                if not self.has_up_to_date_build(target):
                    if not self.build(target):
                        print('Skipping universal binary %s' % name)
                        return

        print('Building universal binary %s' % name)

        universal_paths = dict()
        target_count = 0

        for platform, architectures in configuration.iteritems():
            for architecture in architectures:
                target_count = target_count + 1
                target = Target(self.needy.platform(platform), architecture)
                for root, dirs, files in os.walk(self.build_directory(target)):
                    for path in files + dirs:
                        key = os.path.join(os.path.relpath(root, self.build_directory(target)), path)
                        if key not in universal_paths:
                            universal_paths[key] = []
                        universal_paths[key].append((target, os.path.join(root, path)))

        universal_binary_directory = self.universal_binary_directory(name)

        if os.path.exists(universal_binary_directory):
            shutil.rmtree(universal_binary_directory)

        os.makedirs(universal_binary_directory)

        try:
            for path, builds in universal_paths.iteritems():
                if len(builds) != target_count:
                    continue

                file_name, extension = os.path.splitext(path)
                output_path = os.path.join(universal_binary_directory, path)

                self.__make_output_dirs_for_builds(output_path, builds)

                if any([os.path.isdir(source_path) for _, source_path in builds]):
                    continue

                if target_count == 1:
                    print('Copying %s' % path)
                    source_path = builds[0][1]
                    if os.path.islink(source_path):
                        os.symlink(os.readlink(source_path), output_path)
                    else:
                        shutil.copy(source_path, output_path)
                elif extension in ['.a', '.dylib', '.so']:
                    print('Creating universal library %s' % path)
                    command(['lipo', '-create'] + [lib for target, lib in builds] + ['-output', output_path])
                elif extension in ['.h', '.hpp']:
                    header_contents = '#if __APPLE__\n#include "TargetConditionals.h"\n#endif\n'
                    for target, header in builds:
                        macro = target.platform.detection_macro(target.architecture)
                        if not macro:
                            header_contents = ''
                            break
                        header_path = os.path.relpath(header, os.path.dirname(output_path))
                        header_contents += '#if {}\n#include "{}"\n#endif\n'.format(macro, header_path)
                    if header_contents:
                        print('Creating universal header %s' % path)
                        with open(output_path, 'w') as f:
                            f.write(header_contents)
        except:
            shutil.rmtree(universal_binary_directory)
            raise

    def __make_output_dirs_for_builds(self, output_path, builds):
        for _, source_dir in builds:
            dir = output_path if os.path.isdir(source_dir) else os.path.dirname(output_path)
            if not os.path.exists(dir):
                os.makedirs(dir)

    def has_up_to_date_build(self, target):
        if self.needy.parameters().force_build:
            return False

        if not self.should_build(target):
            return True

        if not os.path.isfile(self.build_status_path(target)):
            return False

        configuration = self.project_configuration(target)

        with open(self.build_status_path(target), 'r') as status_file:
            status_text = status_file.read()
            if not status_text.strip():
                return False
            status = json.loads(status_text)
            if 'configuration' not in status or binascii.unhexlify(status['configuration']) != self.__configuration_hash(target):
                return False

        return True

    def has_up_to_date_universal_binary(self, name, configuration):
        if self.needy.parameters().force_build:
            return False

        for platform, architectures in configuration.iteritems():
            for architecture in architectures:
                target = Target(self.needy.platform(platform), architecture)
                if self.should_build(target) and not self.has_up_to_date_build(target):
                    return False
        return os.path.exists(self.universal_binary_directory(name))

    def build_directory(self, target_or_universal_binary):
        if isinstance(target_or_universal_binary, Target):
            return os.path.join(self.__directory, 'build', target_or_universal_binary.platform.identifier(), target_or_universal_binary.architecture)
        return self.universal_binary_directory(target_or_universal_binary)

    def build_status_path(self, target):
        return os.path.join(self.build_directory(target), 'needy.status')

    def source_directory(self):
        return os.path.join(self.__directory, 'source')

    def universal_binary_directory(self, name):
        return os.path.join(self.__directory, 'build', 'universal', name)

    def include_path(self, target):
        return os.path.join(self.build_directory(target), 'include')

    def library_path(self, target_or_universal_binary):
        return os.path.join(self.build_directory(target_or_universal_binary), 'lib')

    def project(self, definition):
        candidates = [AndroidMkProject, AutotoolsProject, CMakeProject, BoostBuildProject, MakeProject, XcodeProject, SourceProject, CustomProject]

        if 'type' in definition.configuration:
            for candidate in candidates:
                if candidate.identifier() == definition.configuration['type']:
                    return candidate(definition, self.needy)
            raise RuntimeError('unknown project type')

        scores = [(len(definition.configuration.viewkeys() & c.configuration_keys()), c) for c in candidates]
        candidates = [candidate for score, candidate in sorted(scores, key=itemgetter(0), reverse=True)]

        with cd(definition.directory):
            for candidate in candidates:
                if candidate.is_valid_project(definition, self.needy):
                    return candidate(definition, self.needy)

        raise RuntimeError('unknown project type')

    def __configuration_hash(self, target):
        hash = hashlib.sha256()

        top = self.__configuration.copy()
        top.pop('project', None)
        hash.update(json.dumps(top, sort_keys=True))

        hash.update(json.dumps(self.project_configuration(target), sort_keys=True))

        platform_configuration_hash = target.platform.configuration_hash(target.architecture)
        if platform_configuration_hash:
            hash.update(platform_configuration_hash)

        return hash.digest()
