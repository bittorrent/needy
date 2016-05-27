import os
import distutils

from .. import project


class BoostBuildProject(project.Project):

    @staticmethod
    def identifier():
        return 'boostbuild'

    @staticmethod
    def is_valid_project(definition, needy):
        if not os.path.isfile('Jamroot'):
            return False

        return os.path.isfile('b2') or distutils.spawn.find_executable('b2') is not None

    @staticmethod
    def configuration_keys():
        return project.Project.configuration_keys() | {'b2-args', 'linkage'}

    def get_build_concurrency_args(self):
        concurrency = self.build_concurrency()

        if concurrency > 1:
            return ['-j', str(concurrency)]
        elif concurrency == 0:
            return ['-j']
        return []

    def build(self, output_directory):
        b2 = './b2' if os.path.isfile('b2') else 'b2'
        b2_args = self.evaluate(self.configuration('b2-args'))
        b2_args.extend(self.get_build_concurrency_args())

        b2_args.append('architecture={}'.format('arm' if 'arm' in architecture else 'x86'))
        b2_args.append('address-model={}'.format('64' if '64' in architecture else '32'))

        if self.configuration('linkage') in ['static']:
            b2_args.append('link=static')
        elif self.configuration('linkage') in ['dynamic', 'shared']:
            b2_args.append('link=shared')

        toolset = 'darwin' if sys.platform == 'darwin' else 'gcc'
        b2_args.append('toolset={}-needy'.format(toolset))

        project_config = "import os ;\nusing {} : needy : [ os.environ CC ] ;\n".format(toolset)
        if os.path.exists('project-config.jam'):
            with open('project-config.jam', 'r') as f:
                project_config += f.read()
        with open('project-config.jam', 'w') as f:
            f.write(project_config)

        self.command([b2, 'install', '--prefix={}'.format(output_directory)] + b2_args)
