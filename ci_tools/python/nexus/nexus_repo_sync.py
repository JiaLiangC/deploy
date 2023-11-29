#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import json
import hashlib
import os
from urllib.parse import urljoin
import urllib
from time import sleep
import requests
import argparse
import xmltodict
import logging
from python.common.constants import *
from concurrent.futures import ProcessPoolExecutor
import concurrent.futures
from python.common.basic_logger import get_logger

logger = get_logger(name="nexus_sync",log_file="bigdata_nexus_sync.log")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# centos7.9
# kylinv10_sp3
# openeuler22
OS_INFO = {
    "centos7_x86_64": {"repo_url": "http://mirrors.aliyun.com/centos/7/os/x86_64/Packages/",
                       "meta_file": "centos7_x86_64-primary.xml"},
    "centos8_x86_64": {"repo_url": "http://mirrors.aliyun.com/centos/8/BaseOS/x86_64/os/Packages",
                       "meta_file": "centos8_x86_64-primary.xml"},
    "openeuler22_x86_64": {"repo_url": "https://repo.openeuler.org/openEuler-22.03-LTS/OS/x86_64/Packages/",
                           "meta_file": "openeuler22_x86_64-primary.xml"},
    "kylinv10_aarch64": {"repo_url": "https://update.cs2c.com.cn/NS/V10/V10SP3/os/adv/lic/base/aarch64/Packages/",
                         "meta_file": "kylinv10_aarch64-primary.xml"},
    "kylinv10_x86_64": {"repo_url": "https://update.cs2c.com.cn/NS/V10/V10SP3/os/adv/lic/base/x86_64/Packages/",
                        "meta_file": "kylinv10_x86_64-primary.xml"}
}


class NexusSynchronizer:
    def __init__(self, os_type, os_version, os_arch, local_dir):
        assert os_arch in SUPPORTED_ARCHS
        self.os_type = os_type
        self.os_version = os_version
        self.os_arch = os_arch
        self.local_dir = local_dir
        self.success_file = os.path.join(SCRIPT_DIR, 'success.json')
        self.failure_file = os.path.join(SCRIPT_DIR, 'failure.json')
        self.retry_limit = 3


    def get_os_info(self,key):
        return OS_INFO.get(f"{self.os_type}{self.os_version}_{self.os_arch}").get(key)

    def get_local_pkgs_dir(self):
        pkgs_path = os.path.join(self.local_dir, f"{self.os_type}{self.os_version}_{self.os_arch}_pkgs")
        if not os.path.exists(pkgs_path):
            os.makedirs(pkgs_path)
        return pkgs_path


    def load_json_data(self, filepath):
        if os.path.exists(filepath):
            with open(filepath, 'r') as jsonfile:
                json_data = json.load(jsonfile)
        else:
            json_data = {}
        return json_data

    def write_json_data(self, filepath, json_data):
        with open(filepath, 'w') as jsonfile:
            json.dump(json_data, jsonfile, indent=4)



    def get_meta_json_file_path(self):
        repo_metadata_file = self.get_os_info("meta_file")

        return os.path.join(REPO_FILES_DIR, f'{repo_metadata_file}.json')

    def get_packages(self):
        logger.info(f"get packages meta data from {self.get_meta_json_file_path()}")
        json_data = self.load_json_data(self.get_meta_json_file_path())
        return json_data

    def sha256sum(self, filename):
        h = hashlib.sha256()
        b = bytearray(128 * 1024)
        mv = memoryview(b)
        with open(filename, 'rb', buffering=0) as f:
            for n in iter(lambda: f.readinto(mv), 0):
                h.update(mv[:n])
        return h.hexdigest()


    def validate_md5(self, downloaded_file, md5_hash):
        dh = self.sha256sum(downloaded_file)
        return dh == md5_hash

    def download_file(self, url, local_path):
        try:
            urllib.urlretrieve(url, local_path)
            return True
        except urllib.ContentTooShortError as e:
            logger.info(f"The download data is less than expected:{e}")
        except Exception as e:
            logger.info(f'Error: {e} {url}')
        return False

    def download_package(self, package_url, local_filepath, md5_hash, by_stream=True):
        logger.info(f"downloading package from {package_url}")
        retries = 0
        while retries < self.retry_limit:
            try:
                if by_stream:
                    success, msg = self.download_package_by_stream(package_url, local_filepath, md5_hash)
                else:
                    success, msg = self.download_package_by_urlretrieve(package_url, local_filepath, md5_hash)

                return success, msg
            except Exception as e:
                return False, str(e)
        logger.warning("Retry limit exceeded.")
        return False, 'Retry limit exceeded.'

    def download_package_by_stream(self, package_url, local_filepath, md5_hash):
        try:
            response = requests.get(package_url, timeout=10, stream=True)
            if response.status_code == 200:
                with open(local_filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                if self.validate_md5(local_filepath, md5_hash):
                    return True, None
                else:
                    os.remove(local_filepath)
        except Exception as e:
            return False, str(e)
        return False, 'Retry limit exceeded.'

    def download_package_by_urlretrieve(self, package_url, local_filepath, md5_hash):
        try:
            res = self.download_file(package_url, local_filepath)
            if res and self.validate_md5(local_filepath, md5_hash):
                return True, None
            else:
                os.remove(local_filepath)
            sleep(0.5)  # delay to prevent being seen as a bot
        except Exception as e:
            return False, str(e)
        return False, None

    def scan_package(self, pkg_name, pkg_md5):
        local_filename = os.path.join(self.get_local_pkgs_dir(), pkg_name)
        if os.path.exists(local_filename):
            if self.validate_md5(local_filename, pkg_md5):
                logger.info(f"The {pkg_name} rpm is already downloaded and hash is consistent")
                return None
            else:
                logger.info(
                    f"The {pkg_name} rpm is already downloaded and hash is not consistent, will be re-downloading")
                return pkg_name
        else:
            logger.info(f"The {pkg_name} rpm is not exist,will be downloading")
            return pkg_name

    def concurrent_scan_packages(self):
        packages_need_download = {}
        repo_packages = self.get_packages()

        with ProcessPoolExecutor(max_workers=15) as executor:  # 设置并发进程数为10
            future_to_pkg = {executor.submit(self.scan_package, pkg_name, pkg_md5): pkg_name for pkg_name, pkg_md5 in
                             repo_packages.items()}
            for future in concurrent.futures.as_completed(future_to_pkg):
                pkg_name = future_to_pkg[future]
                result = future.result()
                if result is not None:
                    packages_need_download[result] = repo_packages[result]

        logger.info(f"scan finished, packages need download {packages_need_download.keys()}")
        return packages_need_download

    def scan_packages(self):
        packages_need_download = {}
        repo_packages = self.get_packages()
        for pkg_name, pkg_md5 in repo_packages.items():
            logger.info(f"scanning  {pkg_name}")
            local_filename = os.path.join(self.get_local_pkgs_dir(), pkg_name)
            if os.path.exists(local_filename):
                if self.validate_md5(local_filename, pkg_md5):
                    logger.info(f"The {pkg_name} rpm is already downloaded and hash is consistent")
                    continue
                else:
                    packages_need_download[pkg_name] = pkg_md5
                    logger.info(
                        f"The {pkg_name} rpm is already downloaded and hash is not consistent, will be re-downloading")
            else:
                packages_need_download[pkg_name] = pkg_md5
                logger.info(f"The {pkg_name} rpm is not exist,will be downloading")

        logger.info(f"scan finished, packages need download {packages_need_download.keys()}")
        return packages_need_download


    def download(self, pkg_name, pkg_md5):
        remote_repo_url = self.get_os_info("repo_url")
        pkg_url = urljoin(remote_repo_url, pkg_name)
        logger.info(f"downloading  {pkg_name} from {pkg_url}")
        local_filename = os.path.join(self.get_local_pkgs_dir(), pkg_name)

        success, msg = self.download_package(pkg_url, local_filename, pkg_md5, by_stream=True)
        return (pkg_name, success, msg)

    def sync_repository(self):
        # packages_need_download = self.scan_packages()
        packages_need_download = self.concurrent_scan_packages()
        if len(packages_need_download) <= 0:
            logger.info(f"all {self.os_type} repo files synchronized successfully")
            return

        logger.info("synchronizing repository")
        success_packages = {}
        failure_packages = {}

        with ProcessPoolExecutor(max_workers=10) as executor:
            future_to_pkg = {executor.submit(self.download, pkg_name, pkg_md5): pkg_name for pkg_name, pkg_md5 in packages_need_download.items()}
            for future in concurrent.futures.as_completed(future_to_pkg):
                pkg_name, success, msg = future.result()
                if success:
                    success_packages[pkg_name] = True
                    if pkg_name in failure_packages:
                        del failure_packages[pkg_name]
                else:
                    failure_packages[pkg_name] = msg

                self.write_json_data(self.success_file, success_packages)
                self.write_json_data(self.failure_file, failure_packages)


    def generate_pkg_meta(self):
        repo_metadata_file = self.get_os_info("meta_file")
        logger.info(f"parseing {self.os_type} repo  {repo_metadata_file} file")
        with open(os.path.join(REPO_FILES_DIR, repo_metadata_file)) as fd:
            doc = xmltodict.parse(fd.read())
        rpms = {}
        for pinfo in doc["metadata"]["package"]:
            type = pinfo["@type"]  # rpm
            name = pinfo["name"]
            arch = pinfo["arch"]
            ver = pinfo["version"]["@ver"]
            rel = pinfo["version"]["@rel"]
            ctype = pinfo["checksum"]["@type"]
            hash = pinfo["checksum"]["#text"]
            if type == "rpm" and (arch == self.os_arch.strip() or arch == "noarch"):
                rpm_name = f"{name}-{ver}-{rel}.{arch}.rpm"
                rpms[rpm_name] = hash

        logger.info(f"generating {self.os_type} repo  {self.get_meta_json_file_path()} file")
        self.write_json_data(self.get_meta_json_file_path(), rpms)


if __name__ == '__main__':
    # Create the parser
    parser = argparse.ArgumentParser(description='Sync packages from a source to a local directory.')

    # Add the arguments
    parser.add_argument('--os_type',
                        metavar='os_type',
                        type=str,
                        required=True,
                        choices=['centos7', 'centos8', 'openeuler22', 'kylinv10'],
                        help='The type of OS for which to sync packages. Options are: "centos7", "centos8", "openeuler22", "kylinv10"')

    parser.add_argument('--data_dir',
                        metavar='data_dir',
                        type=str,
                        default=os.getcwd(),
                        help='The directory to which to sync packages. Default is the current working directory.')

    # Parse the arguments
    args = parser.parse_args()
    # Use the arguments
    os_type = args.os_type
    DATA_DIR = args.data_dir

    logger.info(f"params os_type: {os_type}, data_dir: {DATA_DIR}")

    synchronizer = NexusSynchronizer(os_type, DATA_DIR)

    synchronizer.generate_pkg_meta()
    synchronizer.sync_repository()
