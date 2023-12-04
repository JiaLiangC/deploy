import platform
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from shutil import copyfileobj
from traceback import format_exc

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
        logger.info(f"run command: {command} shell:{shell} Output: {result.stdout} Error: {result.stderr}")
        return result.returncode
    except subprocess.CalledProcessError as e:
        logger.error(f"Command '{e.cmd}' failed with return code {e.returncode} Output: {e.output} Error: {e.stderr}")
        return e.returncode
