# -*- coding:utf8 -*-
# !/usr/bin/python3

from python.common.basic_logger import get_logger
from python.common.constants import *
from python.utils.filesystem_util import *
from python.utils.os_utils import *
from python.common.path_manager import *
from python.executor.command_executor import *
import os
from datetime import datetime
import shutil

logger = get_logger()

DOCKER_IMAGE_MAP = {"centos7": "bigtop/slaves:trunk-centos-7", "centos8": "bigtop/slaves:trunk-rockylinux-8"}
class Release:
    def __init__(self, os_info, ci_config, comps=None, incremental_release_src_tar=""):
        if comps is None:
            comps = []
        self.os_type = os_info[0]
        self.os_version = os_info[1]
        self.os_arch = os_info[2]
        self.comps = comps
        self.incremental_release_src_tar = incremental_release_src_tar
        self.path_manager = PathManager(ci_config)
        self.release_prj_dir = self.path_manager.release_project_dir
        self.pigz_path = self.path_manager.pigz_path
        self.executor = CommandExecutor()

    def get_release_name(self):
        time_dir_name = datetime.now().isoformat().replace(':', '-').replace('.', '-')
        release_name = f"UDH_RELEASE_{self.os_type}{self.os_version}_{self.os_arch}-{time_dir_name}.tar.gz"
        return release_name

    def incremental_package(self):
        self.setup_temp_dir()
        self.extract_existing_release()
        self.update_components()
        if len(self.comps)>0:
            self.compress_and_cleanup_dir(self.path_manager.incremental_rpm_dir,
                                          self.path_manager.release_project_rpm_tar)
        else:
            print(f"incremental packaging: no component specified ,will just move {self.path_manager.incremental_rpm_tar} to {self.path_manager.release_project_rpm_tar}")
            shutil.move(self.path_manager.incremental_rpm_tar, self.path_manager.release_project_rpm_tar)
        FilesystemUtil.delete(self.path_manager.incremental_release_dir)

    def setup_temp_dir(self):
        udh_release_output_dir = self.path_manager.incremental_release_dir
        FilesystemUtil.create_dir(udh_release_output_dir, empty_if_exists=True)

    def extract_existing_release(self):
        command = f"tar -I {self.pigz_path} -xf {self.incremental_release_src_tar} -C {self.path_manager.incremental_release_dir}"
        self.executor.execute_command(command, shell=True)

        if bool(self.comps):
            print("extract existing release to tmp ")
            rpms_tar = self.path_manager.incremental_rpm_tar
            rpms_tar_parent_dir = self.path_manager.incremental_rpm_parent_dir
            pigz_path = self.path_manager.pigz_path
            command = f"tar -I  {pigz_path} -xf  {rpms_tar} -C {rpms_tar_parent_dir}"
            self.executor.execute_command(command, shell=True)

    def update_components(self):
        print(f"update components {self.comps}")
        for comp in self.comps:
            self.package_component(self.path_manager.incremental_rpm_dir, comp)

    def package_component(self, rpms_dir, comp):
        comp_dir = os.path.join(rpms_dir, comp)
        FilesystemUtil.create_dir(comp_dir, empty_if_exists=True)

        non_src_filepaths = self.get_compiled_packages(comp)
        for filepath in non_src_filepaths:
            dest_path = os.path.join(comp_dir, os.path.basename(filepath))
            print(f"copy {filepath}  to  {dest_path}")
            shutil.copy(filepath, dest_path)

    def compress_and_cleanup_dir(self, source_dir, dest_tar):
        print(f"compress_and_cleanup_dir source:{source_dir} dest:{dest_tar}")

        parent_dir = self.path_manager.get_parent_dir(source_dir)
        print(f"compress_and_cleanup_dir parent_dir: {parent_dir} ")
        os.chdir(parent_dir)

        source_last_dir = os.path.basename(os.path.normpath(source_dir))
        dest_last_dir = os.path.basename(os.path.normpath(dest_tar))

        command = f"tar cf - {source_last_dir} | {self.pigz_path} -k -5 -p 16 > {dest_last_dir}"
        self.executor.execute_command(command, shell=True)
        FilesystemUtil.delete(source_dir)

    def compress_release_directory(self):
        release_name = self.get_release_name()
        self.compress_and_cleanup_dir(self.path_manager.release_project_dir, release_name)
        logger.info(f"Release packaged successfully, removing {os.path.basename(self.release_prj_dir)}")

    def package_bigdata_rpms(self):
        FilesystemUtil.create_dir(self.path_manager.release_project_rpm_dir, empty_if_exists=True)
        self.package_all_components()
        self.handle_special_conditions()
        self.create_yum_repository()
        self.compress_and_cleanup_dir(self.path_manager.release_project_rpm_dir,
                                      self.path_manager.release_project_rpm_tar)

    def package_trino_jdk(self):
        # 根据架构 cp jdk 到resource 目录下，在generate的时候，动态生成jdk 文件的位置填充到ansible里
        jdk_source = self.path_manager.get_trino_jdk_source_path(self.os_arch)
        dest_path = os.path.join(self.release_prj_dir, PKG_RELATIVE_PATH, os.path.basename(jdk_source))
        logger.info(f"trino jdk will copy from  {jdk_source} to {dest_path} ")
        shutil.copy(jdk_source, dest_path)

    def package_all_components(self):
        rpms_dir = self.path_manager.release_project_rpm_dir
        for comp in ALL_COMPONENTS:
            self.package_component(rpms_dir, comp)

    def get_compiled_packages(self, comp):
        # 搜索bigtop项目的编译的输出目录，获取编译好的某个组件的rpm包的路径,排除"src.rpm"文件
        pkg_dir = os.path.join(self.path_manager.compiled_pkg_out_dir, comp)
        non_src_filepaths = FilesystemUtil.recursive_glob(pkg_dir, suffix='.rpm',
                                                          filter_func=lambda fp: not fp.endswith("src.rpm"))
        return non_src_filepaths

    def handle_special_conditions(self):
        if self.os_type.lower().strip() == "centos" and self.os_version.strip() == "7":
            self.handle_centos7_special()
        self.package_trino_jdk()

    def handle_centos7_special(self):
        pg_dir = os.path.join(self.path_manager.release_project_rpm_dir, "pg10")
        FilesystemUtil.create_dir(pg_dir)
        pg_rpm_source = self.path_manager.centos7_pg_10_source_dir
        pg_filepaths = FilesystemUtil.recursive_glob(pg_rpm_source, suffix=".rpm")
        for filepath in pg_filepaths:
            dest_path = os.path.join(pg_dir, os.path.basename(filepath))
            FilesystemUtil.copy(filepath, dest_path)

    def create_yum_repository(self):
        # 需要调用特定命令创建YUM仓库 # 确保系统拥有此类操作的工具
        res = create_yum_repository(self.path_manager.release_project_rpm_dir)
        if not res:
            raise Exception("Create YUM repository failed, check the log.")

    def package(self):
        self.prepare_release_directory()
        self.copy_project_to_release_directory()
        self.cleanup_unnecessary_files()

        if self.should_perform_incremental_packaging():
            print("will perform incremental packaging")
            self.incremental_package()
        else:
            print("will perform all packaging")
            self.package_bigdata_rpms()
        self.compress_release_directory()

    def prepare_release_directory(self):
        # 根据需要，准备发布目录，如创建或清理
        release_output_dir = self.path_manager.release_output_dir
        FilesystemUtil.create_dir(release_output_dir, empty_if_exists=True)

    def copy_project_to_release_directory(self):
        # 这里的实现需要根据实际业务逻辑具体处理，以下仅为示例
        shutil.copytree(PRJDIR, self.path_manager.release_project_dir, symlinks=True, ignore=None)

    def cleanup_unnecessary_files(self):
        base_dir = self.path_manager.release_project_dir
        # 清理项目目录中不需要的文件和目录，如.git目录、未使用的配置文件等
        unnecessary_paths = [os.path.join(base_dir, ".git"),
                             os.path.join(base_dir, "bin/portable-ansible"),
                             os.path.join(base_dir, "bin/ansible-playbook")]
        for path in unnecessary_paths:
            FilesystemUtil.delete(path)

    def should_perform_incremental_packaging(self):
        # 决定是否执行增量打包
        return bool(self.incremental_release_src_tar)