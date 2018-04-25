#!/usr/bin/env python3
import distutils.cmd
import distutils.log
from setuptools import setup, find_packages

class BuildDoc(distutils.cmd.Command):
    description = 'build documentation'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        import subprocess
        command = ['scripts/website', '-s', 'example/src', '-t',
                   'example/templates', '-c', 'example/config.yaml', '-o',
                   'doc/']
        self.announce('Buliding documentation', level=distutils.log.INFO)
        subprocess.check_call(command)

if __name__ == "__main__":
    setup(name='website',
          version='0.1',
          description='Templating for static websites',
          author="Michael S. Kelley",
          author_email="davenportman@gmail.com",
          url="https://github.com/mkelley/website",
          requires=['jinja2', 'pyyaml'],
          cmdclass={
              'build_doc': BuildDoc
          },
          packages=find_packages(),
          scripts=['scripts/website'],
          license='MIT',
      )
