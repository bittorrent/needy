import os
import re

from .. import project


class MakeProject(project.Project):

    @staticmethod
    def is_valid_project(definition):
        return MakeProject.get_makefile_path(definition.directory) is not None

    @staticmethod
    def get_makefile_path(directory='.'):
        valid_makefile_names = ['Makefile', 'GNUmakefile']

        for makefile in valid_makefile_names:
            path = os.path.join(directory, makefile)
            if os.path.isfile(path):
                return path
        return None

    def configure(self, output_directory):
        excluded_targets = []

        if self.target().platform.identifier() != 'host':
            excluded_targets.extend(['test', 'tests', 'check'])

        makefile_path = MakeProject.get_makefile_path()

        with open(makefile_path, 'r') as makefile:
            with open('MakefileNeedyGenerated', 'w') as needy_makefile:
                for line in makefile.readlines():
                    uname_assignment = re.match('(.+=).*shell .*uname', line, re.MULTILINE)
                    if uname_assignment and self.target().platform.identifier() == 'android':
                        needy_makefile.write('%sLinux\n' % uname_assignment.group(1))
                        continue

                    excluded_target = None
                    for target in excluded_targets:
                        if line.find('%s:' % target) == 0:
                            excluded_target = target
                            break

                    if excluded_target:
                        needy_makefile.write('%s:\nneedy-excluded-%s-for-non-host-platform:\n' % (excluded_target, excluded_target))
                        continue

                    needy_makefile.write(line)

    def build(self, output_directory):
        import re, subprocess

        make_args = ['-f', './MakefileNeedyGenerated']
        path_override = None

        target_os = None

        c_compiler = self.target().platform.c_compiler(self.target().architecture)
        if c_compiler:
            make_args.append('CC=%s' % c_compiler)

        cxx_compiler = self.target().platform.cxx_compiler(self.target().architecture)
        if cxx_compiler:
            make_args.append('CXX=%s' % cxx_compiler)

        libraries = self.target().platform.libraries(self.target().architecture)
        if len(libraries) > 0:
            make_args.append('LDFLAGS=%s' % ' '.join(libraries))

        binary_paths = self.target().platform.binary_paths(self.target().architecture)
        if len(binary_paths) > 0:
            path_override = '%s:%s' % (':'.join(binary_paths), os.environ['PATH'])

        if self.target().platform.identifier() == 'android':
            target_os = 'Linux'

        environment_overrides = dict()

        if target_os:
            make_args.extend([
                'OS=%s' % target_os,
                'TARGET_OS=%s' % target_os
            ])

        if path_override:
            make_args.append('PATH=%s' % path_override)
            environment_overrides['PATH'] = path_override

        self.needy.command(['make'] + make_args, environment_overrides = environment_overrides)

        make_install_args = [
            'PREFIX=%s' % output_directory,
            'INSTALLPREFIX=%s' % output_directory,
            'INSTALL_PREFIX=%s' % output_directory
        ]

        recon = subprocess.check_output(['make', 'install', '--recon'] + make_args + make_install_args)
        doing_things_inside_prefix = False
        doing_things_outside_prefix = False

        while True:
            match = re.search(' (/.+?[^\\\\])( |$)', recon, re.MULTILINE)
            if match == None:
                break

            path = match.group(1)
            if os.path.relpath(path, self.directory()).find('..') == 0:
                if os.path.relpath(path, output_directory).find('..') == 0:
                    doing_things_outside_prefix = True
                else:
                    doing_things_inside_prefix = True

            recon = recon[match.end() - 1:]

        if doing_things_outside_prefix or not doing_things_inside_prefix:
            raise RuntimeError('unable to figure out how to set installation prefix')

        self.needy.command(['make', 'install'] + make_args + make_install_args, environment_overrides = environment_overrides)
