import json

from python.common.basic_logger import get_logger
from python.common.constants import *
from python.nexus.nexus_client import NexusClient
from python.nexus.nexus_repo_sync import NexusSynchronizer
from python.install_utils.install_utils import *
import docker
import queue
import threading
import subprocess
import yaml
import os
import glob
import sys
import site
from pathlib import Path
import argparse
import json
import shlex
from datetime import datetime

logger = get_logger()

ALL_COMPONENTS = ["hadoop", "spark", "hive", "hbase", "zookeeper", "kafka", "flink", "ranger", "tez", "ambari",
                  "ambari-infra", "ambari-metrics", "bigtop-select", "bigtop-jsvc", "bigtop-groovy", "bigtop-utils"]


class BaseTask:
    def __init__(self):
        self.conf = self.load_conf()

    def load_conf(self):
        import yaml
        # "ci_conf.yml.template"
        conf_file_template_path = CI_CONF_FILE_TEMPLATE
        if not os.path.exists(CI_CONF_FILE):
            shutil.copy(CI_CONF_FILE_TEMPLATE, CI_CONF_FILE)
        with open(CI_CONF_FILE, 'r') as f:
            data = yaml.load(f, yaml.SafeLoader)
        return data

    def get_bigtop_working_dir(self):
        if self.conf["bigtop"]["use_docker"]:
            return self.conf["docker"]["volumes"]["bigtop"]
        else:
            return self.conf["bigtop"]["prj_dir"]

    # bigdata 项目会挂载到容器执行
    def get_prj_dir(self):
        if self.conf["bigtop"]["use_docker"]:
            return self.conf["docker"]["volumes"]["prj"]
        else:
            return PRJDIR

    def logged_exec_run(self, container, *args, **kwargs):
        if container and self.conf["bigtop"]["use_docker"]:
            logger.info(f"Executing command: {args} {kwargs}")
            response = container.exec_run(*args, **kwargs)
            logger.info(f'command in docker: {response}')
        else:
            cmd = kwargs.get('cmd', None)
            if cmd is not None:
                logger.info(f"Command to be executed: {cmd}")
            else:
                logger.error("No command provided.")
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
                                       universal_newlines=True)
            output, error = process.communicate()
            exit_code = process.returncode
            logger.info(f"logged_exec_run output:{output} error:{error}")
            response = (exit_code, output)

        return response


class ContainerTask(BaseTask):
    def __init__(self):
        super().__init__()

    # 编译脚本会挂载到容器运行

    def create_container(self):
        # Implementation of create_container method
        container_name = self.conf["docker"]["build_container_name"]
        client = docker.from_env()

        try:
            container = client.containers.get(container_name)

            if container.status == "running":
                container.stop()
                logger.info("Container is in running state, stopped it.")

            container.remove()
            logger.info("Container stopped and removed successfully.")

        except docker.errors.NotFound:
            logger.info("Container does not exist.")

        volumes = {
            self.conf["bigtop"]["prj_dir"]: {'bind': self.conf["docker"]["volumes"]["bigtop"], 'mode': 'rw'},
            self.conf["bigtop"]["local_maven_repo_dir"]: {'bind': self.conf["bigtop"]["local_maven_repo_dir"],
                                                          'mode': 'rw'},
            self.conf["bigtop"]["dl_dir"]: {'bind': f'{self.conf["docker"]["volumes"]["bigtop"]}/dl', 'mode': 'rw'},
            "/root/.ssh": {'bind': '/root/.ssh', 'mode': 'rw'},
            PRJDIR: {'bind': self.conf["docker"]["volumes"]["prj"], 'mode': 'rw'},
            PIP_CONF_FILE: {'bind': f'{os.path.expanduser("~/.config/pip/pip.conf")}', 'mode': 'rw'}
        }

        container = client.containers.run(image='bigtop/slaves:3.2.0-centos-7',
                                          detach=True,
                                          network_mode='host',
                                          volumes=volumes,
                                          working_dir=self.conf["docker"]["volumes"]["bigtop"],
                                          tty=True,
                                          name=container_name)

        logger.info(f"Container started, ID: {container.id}")
        logger.info(f"Container status: {container.status}")

        return container

    def install_dependencies(self, container):
        cmd_install = 'pip3 install jinja2 pyyaml requests'
        self.logged_exec_run(container, cmd=['/bin/bash', '-c', cmd_install])

    def setup_environment(self, container):
        conf_args = {"prepare_env": True, "local_repo": self.conf["bigtop"]["local_maven_repo_dir"],
                     "proxy": self.conf["bigtop"]["net_proxy"]}
        conf_str = json.dumps(conf_args)
        conf_str_quoted = shlex.quote(conf_str)

        prj_dir = self.get_prj_dir()
        ci_scripts_module_path = os.path.join(prj_dir, self.conf['bigtop']['ci_scripts_module_path'])

        logger.info(f"conf_str is {conf_str_quoted}")
        cmd_pyenv = ['/bin/bash', '-c',
                     f"echo 'export PYTHONPATH={ci_scripts_module_path}:$PYTHONPATH' >> /etc/profile && source /etc/profile"]
        self.logged_exec_run(container, cmd=cmd_pyenv, workdir='/')
        cmd = ['/bin/bash', '-c',
               f"source /etc/profile && python3 {prj_dir}/ci_tools/python/bigtop_compile/bigtop_utils.py --config={conf_str_quoted}"]
        self.logged_exec_run(container, cmd=cmd, workdir=f'{prj_dir}/ci_tools')

        # todo
        # cmd_install = 'yum clean all && yum install -y python3-devel'
        # self.logged_exec_run(container, cmd=['/bin/bash', '-c', cmd_install])

    def run(self):
        if self.conf["bigtop"]["use_docker"]:
            container = self.create_container()
        else:
            logger.info("not use docker to compile, build in local")
            container = None
        # todo
        # self.install_dependencies(container)
        self.setup_environment(container)
        return container


class BuildComponentsTask(BaseTask):
    def __init__(self, container, build_args):
        super().__init__()
        self.container = container
        self.build_args = build_args

    def build_components(self):
        prj_dir = self.get_prj_dir()
        # container, components_arr, rebuild_all_packages
        self.build_args["proxy"] = self.conf["bigtop"]["net_proxy"]
        conf_str = json.dumps(self.build_args)
        conf_str_quoted = shlex.quote(conf_str)
        pycmd = f'source /etc/profile && python3 {prj_dir}/ci_tools/python/bigtop_compile/bigtop_utils.py --config={conf_str_quoted}'
        cmd = ['/bin/bash', '-c', pycmd]
        exit_code, output = self.logged_exec_run(self.container, cmd=cmd, workdir=f'{prj_dir}/ci_tools')
        return exit_code

    def run(self):
        exit_code = self.build_components()
        if exit_code == 0:
            logger.info("build components  successfully")
        else:
            logger.error("build components  failed check the log")
            raise Exception("build components  failed check the log")


class NexusTask(BaseTask):
    def __init__(self):
        super().__init__()

    def install_nexus_and_jdk(self):
        logger.info("install_nexus_and_jdk")
        nexus_installer = NexusInstaller(self.conf["nexus"]["local_tar"],
                                         self.conf["nexus"]["install_dir"], self.conf["nexus"]["user_pwd"])
        jdk_installer = JDKInstaller(self.conf["nexus"]["jdk_local_tar"], self.conf["nexus"]["jdk_install_dir"])

        jdk_installer.install()
        nexus_installer.install()

    def upload_bigdata_copms2nexus(self, comps):
        logger.info("upload bigdata copmponents to nexus")
        if self.conf["nexus"]["use_existed"]:
            nexus_host = self.conf["nexus"]["host"]
        else:
            nexus_host = "localhost"
        nexus_client = NexusClient(nexus_host, self.conf["nexus"]["user_name"], self.conf["nexus"]["user_pwd"])
        for comp in comps:
            pkg_dir = os.path.join(self.conf["bigtop"]["prj_dir"], f"output/{comp}")
            logger.info(f"uploading {pkg_dir} {comp}")
            nexus_client.repo_create("yum",remove_old=False)
            nexus_client.batch_upload_bigdata_pkgs(pkg_dir, comp)


    def repo_sync(self, os_type, upload_ospkgs):
        ## ['centos7', 'centos8', 'openeuler22', 'kylinv10']
        # os_type = 'centos7'
        logger.info(f"repo_sync sync {os_type} upload_ospkgs:{upload_ospkgs}")
        synchronizer = NexusSynchronizer(os_type, self.conf["nexus"]["repo_data_dir"])
        synchronizer.generate_pkg_meta()
        synchronizer.sync_repository()
        nexus_host = "localhost"
        if upload_ospkgs:
            pkgs_dir = synchronizer.get_local_pkgs_dir()
            logger.info(f"will upload os pkgs under  {pkgs_dir} to {nexus_host}")
            nexus_client = NexusClient(nexus_host, self.conf["nexus"]["user_name"], self.conf["nexus"]["user_pwd"])
            nexus_client.repo_create(nexus_client.get_os_type(), remove_old=True)
            nexus_client.batch_upload_os_pkgs(pkgs_dir)

    def kill_nexus_process(self):
        logger.info("kill nexus process")
        find_process_command = ["pgrep", "-f", "org.sonatype.nexus.karaf.NexusMain"]
        try:
            process_ids = subprocess.check_output(find_process_command).decode().split()
            for pid in process_ids:
                logger.info(f"Killing process {pid}")
                kill_command = ["kill", "-9", pid]
                subprocess.run(kill_command)
        except subprocess.CalledProcessError:
            logger.info("No such process found")
    def run(self):
        logger.info()


class DeployClusterTask(BaseTask):
    def __init__(self):
        super().__init__()

    def deploy(self):
        playbook_path = os.path.join(ANSIBLE_PRJ_DIR, 'playbooks/install_cluster.yml')
        inventory_path = os.path.join(ANSIBLE_PRJ_DIR, 'inventory/hosts')
        log_file = os.path.join(LOGS_DIR, "ansible_playbook.log")
        ansible_install_dir = self.conf["ansible_install_dir"]
        # todo move to prepare environment

        from python.install_utils.conf_utils import ConfUtils
        from python.install_utils.blueprint_utils import BlueprintUtils

        cf_util = ConfUtils()
        conf = cf_util.get_conf()

        hosts_info = cf_util.get_hosts_info()
        ambari_server_host = cf_util.get_ambari_server_host()

        b = BlueprintUtils(conf)
        b.build()
        b.generate_ansible_hosts(conf, hosts_info, ambari_server_host)

        command = ["ansible-playbook", playbook_path, f"--inventory={inventory_path}"]
        with open(log_file, "w") as log:
            logger.info(f"run playbook {command}")
            process = subprocess.Popen(command, shell=False, stdout=log, stderr=log,
                                       universal_newlines=True)
        # 等待子进程完成
        exit_status = process.wait()
        logger.info(f"run_playbook {command} exit_status: {exit_status}")

    def run(self):
        logger.info("deploy ")
        self.deploy()


class UDHReleaseTask(BaseTask):
    def __init__(self):
        super().__init__()

    # ansible 依赖都是要分操作系统的
    # nexus 安装，组件上传，停止，打包
    # 打包 pigz pyenv 和 bigdata deploy 代码
    # 解压后根据配置安装nexus pigz pyenv
    def package(self):
        # todo 删除 pg9 相关的包
        udh_release_output_dir = self.conf["udh_release_output_dir"]

        if os.path.exists(udh_release_output_dir):
            shutil.rmtree(udh_release_output_dir,ignore_errors=True)
        os.makedirs(udh_release_output_dir)

        # 1. Copy project directory into udh_release_output_dir
        shutil.copytree(PRJDIR, udh_release_output_dir)
        # 2. Change into the copied directory and remove .git
        os.chdir(os.path.join(udh_release_output_dir, os.path.basename(PRJDIR)))
        if os.path.exists(".git"):
            shutil.rmtree(".git")

        tar_files_dir = os.path.join(udh_release_output_dir,"bigdata_deploy/ci_tools/resources/pkgs/")
        prj_bin_files_dir = os.path.join(udh_release_output_dir,"bigdata_deploy/bin")

        #install pigz
        prj_bin_dir = os.path.join(udh_release_output_dir, "venv.tar.gz")
        pigz_installer = PigzInstaller(PIGZ_SOURC_CODE_PATH, prj_bin_files_dir)
        pigz_installer.install()
        #pyenv
        install_dir = self.conf["python_venv_install_dir"]
        venv_file = os.path.join(install_dir, "venv.tar.gz")
        shutil.move(venv_file, tar_files_dir)
        #nexus
        self.package_nexus(tar_files_dir)

        time_dir_name = datetime.now().isoformat().replace(':', '-').replace('.', '-')
        udh_release_name = f"UDH_RELEASE_{time_dir_name}.tar.gz"
        # 3. Start a subprocess to compress
        subprocess.run(["tar", "-zcvf", udh_release_name, udh_release_output_dir], check=True,cwd=udh_release_output_dir)

    def package_nexus(self,tar_files_dir):
        nexus_task = NexusTask()
        #install nexus and jdk
        nexus_task.install_nexus_and_jdk()
        #create repo if not exist and upload bigdata pkgs to nexus
        nexus_task.upload_bigdata_copms2nexus(ALL_COMPONENTS)
        #create repo and sync and upload os pkgs to nexus
        nexus_task.repo_sync(os_type, True)
        nexus_task.kill_nexus_process()
        nexus_dir = self.conf["nexus"]["install_dir"]
        parent_dir_path = os.path.dirname(nexus_dir)
        subprocess.run(["tar", "-zcvf", "nexus.tar.gz", nexus_dir], check=True, cwd=parent_dir_path)
        shutil.move(f"{parent_dir_path}/nexus.tar.gz", tar_files_dir)



class InitializeTask(BaseTask):
    def __init__(self):
        super().__init__()

    def run(self):
        if not os.path.exists(OUTPUT_DIR):
            os.mkdir(OUTPUT_DIR)
        # ansible_installer = AnsibleInstaller(PORTABLE_ANSIBLE_PATH, self.conf["ansible_install_dir"])
        # ansible_installer.install()
        # self.create_link_for_ansible()



def setup_options():
    parser = argparse.ArgumentParser(description='CI Tools.')

    # Add the arguments
    parser.add_argument('-components',
                        metavar='components',
                        type=str,
                        help='The components to be build, donat split')
    parser.add_argument('-install-nexus',
                        action='store_true',
                        help='install nexus ')

    parser.add_argument('-upload-nexus',
                        action='store_true',
                        help='upload components to nexus build')

    parser.add_argument('-upload-ospkgs',
                        action='store_true',
                        help='upload components to nexus build')

    parser.add_argument('-deploy',
                        action='store_true',
                        help='deploy a cluster')

    parser.add_argument('-clean-components',
                        metavar='clean_components',
                        type=str,
                        default=False,
                        help='Rebuild Some Packages')

    parser.add_argument('-clean-all',
                        action='store_true',
                        help='Rebuild all packages')

    parser.add_argument('-build-all',
                        action='store_true',
                        help='Rebuild all packages')

    parser.add_argument('-repo-sync',
                        metavar='repo_sync',
                        type=str,
                        default="",
                        help='The parallel build parallel threads used in build')

    parser.add_argument('-stack',
                        metavar='stack',
                        type=str,
                        default="ambari",
                        help='The stack to be build')

    parser.add_argument('-parallel',
                        metavar='parallel',
                        type=int,
                        default=1,
                        help='The parallel build parallel threads used in build')

    parser.add_argument('-release',
                        action='store_true',
                        help='Rebuild all packages make udh release')

    # Parse the arguments
    args = parser.parse_args()
    logger.info(f"main program params is : {args}")
    return args


def clean_logs():
    # 使用 glob 模块找到目录下的所有 .log 文件
    log_files = glob.glob(os.path.join(LOGS_DIR, '*.log'))
    for log_file in log_files:
        try:
            os.remove(log_file)
            print(f"File {log_file} has been removed successfully")
        except Exception as e:
            print(f"Problem occurred: {str(e)}")


def main():
    clean_logs()
    args = setup_options()
    release = args.release
    deploy = args.deploy
    clean_all = args.clean_all
    build_all = args.build_all
    parallel = args.parallel
    clean_components = args.clean_components
    components_str = args.components
    stack = args.stack
    upload_nexus = args.upload_nexus
    upload_ospkgs = args.upload_ospkgs
    os_type = args.repo_sync
    install_nexus = args.install_nexus

    init_task = InitializeTask()
    init_task.run()

    if install_nexus:
        nexus_task = NexusTask()
        nexus_task.install_nexus_and_jdk()

    if build_all:
        components_str = ",".join(ALL_COMPONENTS)

    if components_str and len(components_str) > 0:
        # create container for building
        container_task = ContainerTask()
        container = container_task.run()
        build_args = {"clean_all": clean_all, "clean_components": clean_components, "components": components_str,
                      "stack": stack, "max_workers": parallel}
        build_components_task = BuildComponentsTask(container, build_args)
        build_components_task.run()

    if upload_nexus:
        #如果没通过buid参数指定传哪些包，默认传全部
        if not components_str or len(components_str)==0:
            components_str = ",".join(ALL_COMPONENTS)
        components_arr = components_str.split(",")
        if len(components_arr) > 0:
            nexus_task = NexusTask()
            nexus_task.upload_bigdata_copms2nexus(components_arr)

    if os_type and len(os_type) > 0:
        nexus_task = NexusTask()
        nexus_task.repo_sync(os_type, upload_ospkgs)

    if deploy:
        deploy_cluster_task = DeployClusterTask()
        deploy_cluster_task.run()

    if release:
        logger.info("do release")

    # todo 离线python依赖
    # todo 增加多操作系统支持
    # todo 测试 nexus sync
    # todo 使用设计模式重构
    # todo 制作大包，使用大发布包部署


if __name__ == '__main__':
    main()

# todo 容器默认安装python3-devel
# todo 1.增加发布一个操作系统的大包的功能 (检查nexus repo,编译组件打rpm,rpm 上传到nexus,打包nexus 和部署脚本)
# todo 梳理容器依赖和宿主机依赖
# todo 程序退出时杀死ansible 进程
# todo component name and params check
# only work with python 3.7 and higher

# docker run -d -it --network host -v ${PWD}:/ws -v /data/sdv1/bigtop_reporoot:/root --workdir /ws --name BIGTOP bigtop/slaves:3.2.0-centos-7
# {根据os 获取对应的镜像的名字}
# todo 把容器需要的都丢到一个目录，挂载到容器对应的目录下

# download all static files first
# todo nexus install, password set, repo create
# todo rpm available test
# todo 整理所有依赖 1.xml2dict
#virtualenv -p /usr/bin/python3 --no-site-packages venv
# python3 -m pip install virtualenv
# python3 -m virtualenv ansible  # Create a virtualenv if one does not already exist
# source ansible/bin/activate   # Activate the virtual environment
# python3 -m pip install ansible
# deactivate


#todo 依赖整理: requests  xml2dict ansible
#mkdir /opt/bigdata_tools_venv/
#cd /opt/bigdata_tools_venv/
#python3 -m virtualenv -p /usr/bin/python3  venv
#/opt/bigdata_tools_venv/bin/pip3 install requests  xml2dict ansible
#tar zcvf venv.tar.gz venv

