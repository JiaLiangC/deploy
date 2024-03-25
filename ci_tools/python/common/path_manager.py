# -*- coding:utf8 -*-
# !/usr/bin/python3
import json
import shutil

from python.common.basic_logger import get_logger
from python.common.constants import *
import os
from pathlib import Path

logger = get_logger()

class PathManager:
    def __init__(self, ci_config):
        # 各种目录的基目录，所有其他目录都基于此目录
        self.ci_config = ci_config
        # 初始化所有需要的路径
        self.release_output_dir = self.ci_config["udh_release_output_dir"]
        self.incremental_release_dir = os.path.join(self.release_output_dir, "release_tmp")

        self.release_project_dir = os.path.join(self.release_output_dir, os.path.basename(PRJDIR))
        self.incremental_project_dir = os.path.join(self.incremental_release_dir, os.path.basename(PRJDIR))

        self.pkg_relative_path = os.path.join(self.release_project_dir, "pkg")
        self.incremental_rpm_tar = os.path.join(self.incremental_project_dir, UDH_RPMS_RELATIVE_PATH)
        self.release_project_rpm_tar = os.path.join(self.release_project_dir, UDH_RPMS_RELATIVE_PATH)
        self.incremental_rpm_parent_dir = self.get_parent_dir(self.incremental_rpm_tar)

        self.release_project_rpm_dir = self.get_rpm_dir(self.release_project_dir)
        self.incremental_rpm_dir = self.get_rpm_dir(self.incremental_project_dir)

        self.pigz_path = os.path.join(PRJ_BIN_DIR, "pigz")
        self.centos7_pg_10_source_dir = self.ci_config["centos7_pg_10_dir"]
        self.compiled_pkg_out_dir = os.path.join(self.ci_config["bigtop"]["prj_dir"], "output")

        self.bigtop_project_dir = self.ci_config["bigtop"]["prj_dir"]
        self.bigtop_local_maven_repo_dir = self.ci_config["bigtop"]["local_maven_repo_dir"]
        self.bigtop_dl_dir = self.ci_config["bigtop"]["dl_dir"]
        self.bigtop_docker_volume_dir = self.ci_config["docker"]["volumes"]["bigtop"]
        self.bigtop_dl_docker_volume_dir = f'{self.ci_config["docker"]["volumes"]["bigtop"]}/dl'
        self.prj_docker_volume_dir = self.ci_config["docker"]["volumes"]["prj"]

        self.current_prj_dir = self.get_current_prj_dir()
        # 根据需要可以继续添加其他路径

    def get_current_prj_dir(self):
        if self.ci_config["bigtop"]["use_docker"]:
            return self.ci_config["docker"]["volumes"]["prj"]
        else:
            return PRJDIR

    def get_trino_jdk_source_path(self, os_arch):
        if os_arch == "x86_64":
            jdk_source = self.ci_config["jdk17_x86_location"]
        else:
            jdk_source = self.ci_config["jdk17_arm_location"]
        return jdk_source

    def get_rpm_dir(self, prj_dir):
        bigdata_rpm_dir = os.path.join(prj_dir, PKG_RELATIVE_PATH, os.path.basename(UDH_RPMS_PATH).split(".")[0])
        return bigdata_rpm_dir

    def get_parent_dir(self, p_dir):
        dir_path = Path(p_dir)
        parent_dir = dir_path.parent
        return parent_dir

    def get_pigz_path(self):
        return self.pigz_path
