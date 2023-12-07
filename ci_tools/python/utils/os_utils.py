import platform
import subprocess
import sys
from contextlib import contextmanager
import shutil
import os
from jinja2 import Template
import time


from python.common.basic_logger import get_logger

logger = get_logger()


def get_os_arch():
    return platform.machine()


def get_os_type():
    operatingSystem = platform.system().lower()
    if operatingSystem == 'linux':
        operatingSystem = platform.linux_distribution()[0].lower()

    # special cases
    if operatingSystem.startswith('ubuntu'):
        operatingSystem = 'ubuntu'
    elif operatingSystem.startswith('red hat enterprise linux'):
        operatingSystem = 'redhat'
    elif operatingSystem.startswith('kylin linux'):
        operatingSystem = 'kylin'
    elif operatingSystem.startswith('centos linux'):
        operatingSystem = 'redhat'
    elif operatingSystem.startswith('rocky linux'):
        operatingSystem = 'redhat'
    elif operatingSystem.startswith('uos'):
        operatingSystem = 'uos'
    elif operatingSystem.startswith('anolis'):
        operatingSystem = 'anolis'
    elif operatingSystem.startswith('asianux server'):
        operatingSystem = 'asianux'
    elif operatingSystem.startswith('bclinux'):
        operatingSystem = 'bclinux'
    elif operatingSystem.startswith('openeuler'):
        operatingSystem = 'openeuler'

    if operatingSystem == '':
        raise Exception("Cannot detect os type. Exiting...")

    return operatingSystem


def get_os_version():
    os_type = get_os_type()
    version = platform.linux_distribution()[1]

    if version:
        if os_type == "kylin":
            # kylin v10
            if version == 'V10':
                version = 'v10'
        elif os_type == 'anolis':
            if version == '20':
                version = '20'
        elif os_type == 'uos':
            # uos 20
            if version == '20':
                version = '20'
        elif os_type == 'openeuler':
            # openeuler 22
            version = '22'
        elif os_type == 'bclinux':
            version = '8'
        elif os_type == '4.0.':
            # support nfs (zhong ke fang de)
            version = '4'
        elif len(version.split(".")) > 2:
            # support 8.4.0
            version = version.split(".")[0]
        else:
            version = version
        return version
    else:
        raise Exception("Cannot detect os version. Exiting...")


def get_full_os_major_version():
    os_type = get_os_type()
    os_version = get_os_version()
    os_arch = get_os_arch()
    full_os_major_version = f"{os_type}{os_version}_{os_arch}"
    logger.info(f"full_os_and_major_version is {full_os_major_version}")
    return full_os_major_version


def kill_nexus_process():
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


def kill_user_processes(username):
    p = subprocess.Popen(['pgrep', '-u', username], stdout=subprocess.PIPE)
    out, err = p.communicate()

    for pid in out.splitlines():
        subprocess.run(['kill', '-9', pid])


def copy_file(src, dst):
    with open(src, 'rb') as fsrc:
        with open(dst, 'wb') as fdst:
            fdst.write(fsrc.read())


@contextmanager
def smart_open(file: str, mode: str, *args, **kwargs):
    if file == "-":
        if "w" in mode:
            yield sys.stdout.buffer
        else:
            yield sys.stdin.buffer
        return
    with open(file, mode, *args, **kwargs) as fh:
        yield fh


def run_shell_command(command, shell=False):
    try:
        result = subprocess.run(command, check=True, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True)

        if result.returncode != 0:
            logger.error(f"run command: {command} shell:{shell} Output: {result.stdout} Error: {result.stderr}")
        else:
            logger.info(f"run command: {command} shell:{shell} Output: {result.stdout}")
        return result.returncode
    except subprocess.CalledProcessError as e:
        logger.error(f"Command '{e.cmd}' failed with return code {e.returncode} Output: {e.output} Error: {e.stderr}")
        return e.returncode


def create_yum_repository(repo_data_dir):
    try:
        repodata_path = os.path.join(repo_data_dir, "repodata")
        if os.path.exists(repodata_path):
            shutil.rmtree(repodata_path)

        command = f"createrepo -o {repo_data_dir} {repo_data_dir}"
        returncode = run_shell_command(command.split())
        if returncode != 0:
            logger.error(f"Error executing createrepo")
            return False
        logger.info(f"Successfully created YUM repository")
        return True
    except Exception as e:
        logger.error(f"An error occurred: {e}", file=sys.stderr)
        return False

def is_httpd_installed():
    try:
        subprocess.run(["httpd", "-v"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False
    except FileNotFoundError:
        return False

def install_httpd():
    install_command = ["yum", "install", "httpd", "-y"]
    run_shell_command(install_command)

def render_template(template_path, context, output_path):
    """
    从指定的模板文件渲染内容，并将其写入到输出文件中。
    :param template_path: 模板文件的路径。
    :param context: 一个字典，包含渲染模板时要使用的变量。
    :param output_path: 渲染后内容写入的文件路径。
    """
    with open(template_path, 'r') as template_file:
        template_content = template_file.read()

    template = Template(template_content)
    rendered_content = template.render(context)

    with open(output_path, 'w') as output_file:
        output_file.write(rendered_content)

def get_ip_address():
    try:
        # 获取主机的 IP 地址
        ip = subprocess.check_output("hostname -I | cut -d' ' -f1", shell=True).decode().strip()
        return ip
    except subprocess.CalledProcessError as e:
        return "无法获取 IP 地址: " + str(e)

def sleep_with_logging(total_sleep_time, log_interval, log_message):
    """
    使程序睡眠一段时间，每隔一定时间记录一条日志。

    :param total_sleep_time: 总睡眠时间（秒）
    :param log_interval: 日志打印间隔（秒）
    :param log_message: 要打印的日志消息
    """
    start_time = time.time()  # 开始时间
    end_time = start_time + total_sleep_time  # 结束时间

    while time.time() < end_time:
        logger.info(f"{log_message} - {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
        time.sleep(log_interval)  # 睡眠指定的间隔时间

    logger.info("完成睡眠。")
