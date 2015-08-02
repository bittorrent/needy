import os
import shutil

import Project
import Download
import GitRepository

from Project import ProjectDefinition
from ChangeDir import cd

from AndroidMk import AndroidMkProject
from Autotools import AutotoolsProject
from Make import MakeProject
from Source import SourceProject
from Xcode import XcodeProject


class Library:
    def __init__(self, configuration, directory, global_configuration):

        self.configuration = configuration
        self.directory = directory
        self.source_directory = os.path.join(directory, 'source')

        if 'download' in self.configuration:
            self.source = Download.Download(self.configuration['download'], self.configuration['checksum'], self.source_directory, os.path.join(directory, 'download'))
        elif 'repository' in self.configuration:
            self.source = GitRepository.GitRepository(self.configuration['repository'], self.configuration['commit'], self.source_directory)
        else:
            raise ValueError('no source specified in configuration')

        self.global_configuration = global_configuration

    def build(self, target):
        configuration = Project.evaluate_conditionals(self.configuration['project'] if 'project' in self.configuration else dict(), target)

        if 'build' in configuration and not configuration['build']:
            print 'Skipping for %s' % target.platform
            return False

        self.source.clean()

        project = self.project(target, configuration)

        print 'Building for %s' % target.platform

        if target.architecture:
            print 'Architecture: %s' % target.architecture

        if not project:
            raise RuntimeError('unknown project type')

        build_directory = self.build_directory(target)

        if not os.path.exists(build_directory):
            os.makedirs(build_directory)

        with cd(project.directory()):
            try:
                project.configure(build_directory)
                project.pre_build(build_directory)
                project.build(build_directory)
                project.post_build(build_directory)
            except:
                shutil.rmtree(build_directory)
                raise

        return True

    def build_universal_binary(self, name, configuration):
        import shutil, subprocess, Target

        for platform, architectures in configuration.iteritems():
            for architecture in architectures:
                target = Target.Target(platform, architecture)
                if not self.has_up_to_date_build(target):
                    if not self.build(target):
                        print 'Skipping universal binary %s' % name
                        return

        print 'Building universal binary %s' % name

        files = dict()
        target_count = 0

        for platform, architectures in configuration.iteritems():
            for architecture in architectures:
                target_count = target_count + 1
                target = Target.Target(platform, architecture)
                lib_directory = os.path.join(self.build_directory(target), 'lib')
                for file in os.listdir(lib_directory):
                    if not os.path.isfile(os.path.join(lib_directory, file)):
                        continue
                    if not file in files:
                        files[file] = []
                    files[file].append(os.path.join(lib_directory, file))

        universal_binary_directory = self.universal_binary_directory(name)

        if os.path.exists(universal_binary_directory):
            shutil.rmtree(universal_binary_directory)

        universal_lib_directory = os.path.join(self.universal_binary_directory(name), 'lib')
        os.makedirs(universal_lib_directory)

        try:
            for file, builds in files.iteritems():
                if len(builds) != target_count:
                    continue

                file_name, extension = os.path.splitext(file)

                if extension in ['.a', '.dylib', '.so']:
                    print 'Creating universal library %s' % file
                    subprocess.check_call(['lipo', '-create'] + builds + ['-output', os.path.join(universal_lib_directory, file)])
        except:
            shutil.rmtree(universal_binary_directory)
            raise

    def has_up_to_date_build(self, target):
        # TODO: return out-of-date if our configuration changes
        return os.path.exists(self.build_directory(target))

    def has_up_to_date_universal_binary(self, name, configuration):
        # TODO: return out-of-date if our configuration changes
        return os.path.exists(self.universal_binary_directory(name))

    def build_directory(self, target):
        return os.path.join(self.directory, 'build', target.platform, target.architecture if target.architecture else 'default')

    def universal_binary_directory(self, name):
        return os.path.join(self.directory, 'build', 'universal', name)

    def project(self, target, configuration):
        candidates = [AndroidMkProject, AutotoolsProject, MakeProject, XcodeProject]

        if 'configure-args' in configuration:
            candidates.insert(0, AutotoolsProject)

        if 'xcode-project' in configuration:
            candidates.insert(0, XcodeProject)

        if 'source-directory' in configuration:
            candidates.insert(0, SourceProject)

        if configuration:
            configuration = Project.evaluate_conditionals(configuration, target)

        definition = ProjectDefinition(target, self.source_directory, configuration)

        for candidate in candidates:
            if candidate.is_valid_project(definition):
                return candidate(definition, self.global_configuration)

        raise RuntimeError('unknown project type')
