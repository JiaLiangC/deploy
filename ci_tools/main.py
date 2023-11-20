import json

from python.common.basic_logger import logger
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
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, shell=shell,
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
        cmd_install = 'pip3 install distro jinja2 pyyaml requests'
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
        nexus_installer = NexusInstaller(self.conf["nexus"]["local_tar"],
                                         self.conf["nexus"]["install_dir"])
        jdk_installer = JDKInstaller(self.conf["nexus"]["jdk_local_tar"], self.conf["nexus"]["jdk_install_dir"])

        jdk_installer.install()
        nexus_installer.install()

    def upload2nexus_task(self, comps):
        if self.conf["nexus"]["use_existed"]:
            logger.info("use_existed_nexus")
            nexus_url = self.conf["nexus"]["url"]
        else:
            # 安装nexus 和jdk
            self.install_nexus_and_jdk()
            nexus_url = "localhost:8081"

        nexus_client = NexusClient(nexus_url, self.conf["nexus"]["user_name"], self.conf["nexus"]["user_pwd"])

        for comp in comps:
            pkg_dir = os.path.join(self.conf["bigtop"]["prj_dir"], f"output/{comp}")
            logger.info(f"uploading {pkg_dir} {comp}")
            nexus_client.batch_upload(pkg_dir, comp)

    def repo_sync(self,os_type):
        ## ['centos7', 'centos8', 'openeuler22', 'kylinv10']
        #os_type = 'centos7'
        synchronizer = NexusSynchronizer(os_type, self.conf["nexus"]["repo_data_dir"])
        synchronizer.generate_pkg_meta()
        synchronizer.sync_repository()

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


class InitializeTask(BaseTask):
    def __init__(self):
        super().__init__()

    def set_env(self):
        site_packages = site.getsitepackages()[0]
        portable_ansible_path = self.conf["ansible_install_dir"]
        ci_tools_path = CI_TOOLS_MODULE_PATH
        # 定义要添加的路径
        additional_paths = f"""
        {ci_tools_path}
        {portable_ansible_path}
        """

        # 创建 .pth 文件
        pth_file = Path(site_packages) / 'bigdata_modules_paths.pth'
        with pth_file.open('w') as f:
            f.write(additional_paths)

        # 将路径添加到 sys.path
        for path in additional_paths.strip().splitlines():
            if path not in sys.path:
                sys.path.insert(0, path)

    def create_link_for_ansible(self):
        # 获取配置中的 ansible 安装目录
        ansible_install_dir = self.conf["ansible_install_dir"]

        # 列表包含要创建符号链接的名字
        links = ["config", "console", "doc", "galaxy", "inventory", "playbook", "pull", "vault"]

        # 在 ansible 安装目录下为每个名字创建符号链接
        for link in links:
            src = os.path.join(ansible_install_dir, 'ansible')
            dst = os.path.join(ansible_install_dir, f'ansible-{link}')
            os.symlink(src, dst)

    def run(self):
        if not os.path.exists(OUTPUT_DIR):
            os.mkdir(OUTPUT_DIR)
        #ansible_installer = AnsibleInstaller(PORTABLE_ANSIBLE_PATH, self.conf["ansible_install_dir"])
        #ansible_installer.install()
        #self.create_link_for_ansible()


class TaskRunner:
    def __init__(self):
        self.tasks = queue.Queue(maxsize=30)
        self.worker = threading.Thread(target=self._worker)
        self.worker.start()


def generate_udh_release_task():
    # 0. 是否从头编译，上传，部署，打包
    # 1.stop nexus
    # 2.package nexus
    # 3.package bigtop deploy
    use_existed_nexus = False
    logger.info("generate_udh_release")
    if use_existed_nexus:
        logger.info("")
        # STOP NEXUS
        # tar zcvf nexus
        # tar both bigdata deploy and nexus
    else:
        logger.info("")
        # 编译所有，部署一个集群，部署好后停止nexus,tar zcvf nexus,tar both bigdata deploy and nexus


def setup_options():
    parser = argparse.ArgumentParser(description='CI Tools.')

    # Add the arguments
    parser.add_argument('-components',
                        metavar='components',
                        type=str,
                        help='The components to be build, donat split')

    parser.add_argument('-upload-nexus',
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
    os_type = args.repo_sync

    all_components = ["hadoop", "spark", "hive", "hbase", "zookeeper", "kafka", "flink", "ranger", "tez", "ambari",
                      "ambari-infra", "ambari-metrics", "bigtop-select", "bigtop-jsvc", "bigtop-groovy", "bigtop-utils"]
    init_task = InitializeTask()
    init_task.run()

    if build_all:
        components_str = ",".join(all_components)

    if components_str and len(components_str) > 0:
        # create container for building
        container_task = ContainerTask()
        container = container_task.run()
        build_args = {"clean_all": clean_all, "clean_components": clean_components, "components": components_str,
                      "stack": stack, "max_workers": parallel}
        build_components_task = BuildComponentsTask(container, build_args)
        build_components_task.run()

    if upload_nexus:
        components_arr = components_str.split(",")
        if len(components_arr) > 0:
            nexus_task = NexusTask()
            nexus_task.install_nexus_and_jdk()
            nexus_task.upload2nexus_task(components_arr)

    if repo_sync and len(os_type)>0:
        nexus_task = NexusTask()
        nexus_task.repo_sync(os_type)

    if deploy:
        deploy_cluster_task = DeployClusterTask()
        deploy_cluster_task.run()

    if release:
        logger.info("do release")

    # todo 增加多操作系统支持
    # todo 测试 nexus sync
    # portable ansible add requests
    # todo 使用设计模式重构


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
# python3 -m pip install virtualenv
# python3 -m virtualenv ansible  # Create a virtualenv if one does not already exist
# source ansible/bin/activate   # Activate the virtual environment
# python3 -m pip install ansible
# deactivate
