# -*- coding:utf8 -*-
# !/usr/bin/python3

from python.common.basic_logger import get_logger
from python.common.constants import *
from python.common.path_manager import *
import argparse
from python.config_management.configurations.ci_configuration import *
from python.nexus.nexus_manager import *
from python.deploy.deployment import *
from python.utils.filesystem_util import *
from python.build.build_manager import *
from python.container.container_manager import *
from python.release.release import *
from python.executor.command_executor import *


logger = get_logger()
class MainApplication:
    def __init__(self, ci_config):
        self.args = self.parse_arguments()
        self.os_info = self.get_os_info_tuple()
        self.ci_config = ci_config
        self.path_manager = PathManager(ci_config)
        self.nexus_manager = NexusManager(ci_config, self.os_info)
        self.build_manager = None
        self.deployment_manager =  Deployment(ci_config)
        self.release_manager = None
        self.executor = CommandExecutor

    def get_os_info_tuple(self):
        os_info_arr = self.args.os_info.split(",") if self.args.os_info else ["", "", ""]
        return tuple(os_info_arr)

    def initialize(self):
        pass
        # FilesystemUtil.create_dir(OUTPUT_DIR, empty_if_exists=True)

    def check_os_info(self):
        os_type, os_version, os_arch = self.os_info
        assert os_arch in SUPPORTED_ARCHS
        assert os_type in SUPPORTED_OS

    def parse_arguments(self):
        parser = argparse.ArgumentParser(description='Release Tool.')

        # Add the arguments
        parser.add_argument('-components', metavar='components', type=str,
                            help='The components to be build, donat split')
        parser.add_argument('-install-nexus', action='store_true', help='install nexus ')
        parser.add_argument('-upload-nexus', action='store_true', help='upload components rpms to nexus')
        parser.add_argument('-repo-sync', action='store_true', help='sync the os repo from remote mirror to local disk')
        parser.add_argument('-upload-os-pkgs', action='store_true', help='upload os pkgs to nexus')
        parser.add_argument('-pkg-nexus', action='store_true', help='create the nexus package with os repo')
        parser.add_argument('-deploy', action='store_true', help='deploy a cluster')
        parser.add_argument('-generate-conf', action='store_true', help='generate all configuration files')
        parser.add_argument('-clean-components', metavar='clean_components', type=str, default=False,
                            help='clean components that already build')
        parser.add_argument('-clean-all', action='store_true', help='rebuild all packages')
        parser.add_argument('-build-all', action='store_true', help='build all packages')
        parser.add_argument('-os-info', metavar='os_info', type=str, default="",
                            help='the release params: os_name,os_version,arch exp:centos,7,x86_64')
        parser.add_argument('-stack', metavar='stack', type=str, default="ambari", help='The stack to be build')
        parser.add_argument('-parallel', metavar='parallel', type=int, default=3,
                            help='The parallel build threads used in build')
        parser.add_argument('-release', action='store_true', help='make  bigdata platform release')
        parser.add_argument('-incremental-tar', metavar='incremental_tar', type=str,
                            help='Incrementally update a release.')
        # Add more arguments as needed
        args = parser.parse_args()
        return args

    def install_nexus_if_needed(self):
        if self.args.install_nexus:
            self.check_os_info()
            self.nexus_manager.install_and_configure_nexus()

    def build_components_if_needed(self):
        if self.args.release:
            print("do release will skip build")
            return
        if self.args.build_all or self.args.components:
            self.check_os_info()

            container_manager = ContainerManager(self.os_info, PathManager(self.ci_config))
            container_manager.create_container()
            components_str = self.args.components or ",".join(ALL_COMPONENTS)

            self.build_manager = BuildManager(self.ci_config, container_manager)
            self.build_manager.build_components(self.args.clean_all, self.args.clean_components, components_str,
                                                self.args.stack, self.args.parallel)

    def upload_to_nexus_if_needed(self):
        if self.args.upload_nexus:
            components_str = self.args.components or ",".join(ALL_COMPONENTS)
            components_arr = components_str.split(",")
            self.nexus_manager.upload_bigdata_components(components_arr)

    def sync_repo_if_needed(self):
        if self.args.repo_sync:
            self.check_os_info()
            self.nexus_manager.sync_os_repositories()

    def deploy_cluster_if_needed(self):
        if self.args.deploy:
            self.deployment_manager.deploy_cluster()

    def generate_conf_if_needed(self):
        if self.args.generate_conf:
            self.deployment_manager.generate_deploy_conf()

    def package_nexus_if_needed(self):
        if self.args.pkg_nexus:
            self.nexus_manager.package_nexus()

    def release_if_needed(self):
        if self.args.release:
            self.check_os_info()
            components_str = self.args.components
            components_arr = components_str.split(",") if components_str else []

            # components_str 不为空将进行增量打包，为空且带了增量打包的源包，则仅仅更新RPM包意外的内容，比如自动化部署项目.
            self.release_manager = Release(self.os_info, self.ci_config, components_arr,
                                           self.args.incremental_tar)
            self.release_manager.package()

    def upload_os_packages_if_needed(self):
        if self.args.upload_os_pkgs:
            self.nexus_manager.upload_os_packages()

    def run(self):
        self.initialize()
        self.install_nexus_if_needed()
        self.build_components_if_needed()
        self.upload_to_nexus_if_needed()
        self.sync_repo_if_needed()
        self.deploy_cluster_if_needed()
        self.generate_conf_if_needed()
        self.package_nexus_if_needed()
        self.release_if_needed()
        self.upload_os_packages_if_needed()

def check_config():
    pass

# Check configuration validity

if __name__ == '__main__':
    ci_config_manager = CIConfiguration()
    app = MainApplication(ci_config_manager.get_conf())
    app.run()

# sudo apt install apache2
# sudo systemctl start apache2
# sudo systemctl enable apache2
# todo reprepro
# todo user input check component name and params check
# pip3 install -t requests ansible/extras
# tar -I pigz -xf nexus.tar.gz -C /tmp
# docker run -d -it --network host -v ${PWD}:/ws -v /data/sdv1/bigtop_reporoot:/root --workdir /ws --name BIGTOP bigtop/slaves:3.2.0-centos-7
# yum install createrepo
# todo rpm db brokern 