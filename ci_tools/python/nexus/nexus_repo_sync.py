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
import threading


logger = get_logger(name="nexus_sync", log_file="nexus_sync.log")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# centos7.9
# kylinv10_sp3
# openeuler22
OS_INFO = {
    "centos7_x86_64": {"base": {"repo_url": "http://mirrors.aliyun.com/centos/7/os/x86_64/Packages/",
                                "meta_file": "centos7_x86_64_base-primary.xml"},
                       "updates": {"repo_url": "http://mirrors.aliyun.com/centos/7/updates/x86_64/Packages/",
                                "meta_file": "centos7_x86_64_updates-primary.xml"}
                       },
    "centos8_x86_64": {"base": {"repo_url": "http://mirrors.aliyun.com/centos/8/BaseOS/x86_64/os/Packages",
                                "meta_file": "centos8_x86_64_base-primary.xml"}},
    "openeuler22_x86_64": {"base": {"repo_url": "https://repo.openeuler.org/openEuler-22.03-LTS/OS/x86_64/Packages/",
                                    "meta_file": "openeuler22_x86_64-primary.xml"}},
    "kylinv10_aarch64": {
        "base": {"repo_url": "https://update.cs2c.com.cn/NS/V10/V10SP3/os/adv/lic/base/aarch64/Packages/",
                 "meta_file": "kylinv10_aarch64_base-primary.xml"},
        "updates": {"repo_url": "https://update.cs2c.com.cn/NS/V10/V10SP3/os/adv/lic/updates/aarch64/Packages/",
                    "meta_file": "kylinv10_aarch64_updates-primary.xml"}
    },
    "kylinv10_x86_64": {
        "base": {"repo_url": "https://update.cs2c.com.cn/NS/V10/V10SP3/os/adv/lic/base/x86_64/Packages/",
                 "meta_file": "kylinv10_x86_64_base-primary.xml"},
        "updates": {"repo_url": "https://update.cs2c.com.cn/NS/V10/V10SP3/os/adv/lic/updates/x86_64/Packages/",
                    "meta_file": "kylinv10_x86_64_updates-primary.xml"}
    }
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
        #self.lock = threading.Lock()

    def get_os_info(self, repo_key, key):
        return OS_INFO.get(f"{self.os_type}{self.os_version}_{self.os_arch}").get(repo_key).get(key)

    def get_repo_meta_infos(self):
        return OS_INFO.get(f"{self.os_type}{self.os_version}_{self.os_arch}")

    def get_local_pkgs_dir(self, repo_key="base"):
        #with self.lock:
        pkgs_path = os.path.join(self.local_dir, f"{self.os_type}{self.os_version}_{self.os_arch}_{repo_key}_pkgs")
        if not os.path.exists(pkgs_path):
            os.makedirs(pkgs_path)
        return pkgs_path

    def get_local_pkgs_dirs(self):
        repo_meta_infos = self.get_repo_meta_infos()
        pkgs_paths = [self.get_local_pkgs_dir(repo_key=repo_key) for repo_key, repo_meta in repo_meta_infos.items()]
        return pkgs_paths

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

    def get_meta_files_path(self, fn):
        repo_meta_infos = self.get_repo_meta_infos()
        meta_files = {repo_key: os.path.join(REPO_FILES_DIR, fn(repo_meta.get("meta_file"))) for repo_key, repo_meta in
                      repo_meta_infos.items()}
        return meta_files

    def get_meta_json_files_path(self):
        return self.get_meta_files_path(lambda x: f"{x}.json")

    def get_packages(self):
        repo_json_files_dict = self.get_meta_json_files_path()
        logger.info(f"get packages meta data from {repo_json_files_dict}")
        json_data = {repo_key: self.load_json_data(repo_json) for repo_key, repo_json in repo_json_files_dict.items()}
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

    def scan_package(self, pkg_name, pkg_md5,repo_key):
        local_filename = os.path.join(self.get_local_pkgs_dir(repo_key=repo_key), pkg_name)
        if os.path.exists(local_filename):
            if self.validate_md5(local_filename, pkg_md5):
                logger.info(f"The {pkg_name} rpm is already downloaded and hash is consistent")
                return None
            else:
                logger.info(
                    f"The {pkg_name} rpm is already downloaded and hash is  inconsistent, will be re-downloading")
                return pkg_name
        else:
            logger.info(f"The {pkg_name} rpm is not exist,will be downloading")
            return pkg_name

    def concurrent_scan_packages(self):
        packages_need_download = {}
        repo_packages_dict = self.get_packages()

        with ProcessPoolExecutor(max_workers=15) as executor:  # 设置并发进程数为10
            for repo_key, repo_packages in repo_packages_dict.items():
                future_to_pkg = {executor.submit(self.scan_package, pkg_name, pkg_md5, repo_key): pkg_name for pkg_name, pkg_md5 in repo_packages.items()}
                for future in concurrent.futures.as_completed(future_to_pkg):
                    pkg_name = future.result()
                    if pkg_name is not None:
                        pkg_hash = repo_packages[pkg_name]
                        packages_need_download.setdefault(repo_key, {})[pkg_name] = pkg_hash

            logger.info(
                f"repo: {repo_key} scan finished, packages need download {packages_need_download}")
        return packages_need_download

    def download(self, pkg_name, pkg_md5, repo_key):
        remote_repo_url = self.get_os_info(repo_key,"repo_url")
        pkg_url = urljoin(remote_repo_url, pkg_name)
        logger.info(f"downloading  {pkg_name} from {pkg_url}")
        local_filename = os.path.join(self.get_local_pkgs_dir(repo_key=repo_key), pkg_name)

        success, msg = self.download_package(pkg_url, local_filename, pkg_md5, by_stream=True)
        return (pkg_name, success, msg)

    def sync_repository(self):
        packages_need_download = self.concurrent_scan_packages()
        if len(packages_need_download) <= 0:
            logger.info(f"all {self.os_type} repo files synchronized successfully")
            return

        logger.info("synchronizing repository")
        success_packages = {}
        failure_packages = {}

        # packages_need_download={repo_key: {pkg_name1:pkg_md5,pkg_name2:pkg_md5}}
        for repo_key, repo_pkgs in packages_need_download.items():
            with ProcessPoolExecutor(max_workers=10) as executor:
                future_to_pkg = {executor.submit(self.download, pkg_name, pkg_md5, repo_key): pkg_name for
                                 pkg_name, pkg_md5 in
                                 repo_pkgs.items()}
                for future in concurrent.futures.as_completed(future_to_pkg):
                    pkg_name, success, msg = future.result()
                    if success:
                        success_packages.setdefault(repo_key, {})[pkg_name] = True
                        if pkg_name in failure_packages:
                            del failure_packages[pkg_name]
                    else:
                        failure_packages.setdefault(repo_key, {})[pkg_name] = msg

                self.write_json_data(self.success_file, success_packages)
                self.write_json_data(self.failure_file, failure_packages)

    def generate_pkg_meta(self):
        repo_metadata_files_dict = self.get_meta_files_path(lambda x: x)
        for repo_key, repo_metadata_file in repo_metadata_files_dict.items():
            logger.info(f"parseing {repo_key} {self.os_type} repo  {repo_metadata_file} file")
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

            logger.info(f"generating {self.os_type} repo json file")
            json_path = os.path.join(REPO_FILES_DIR, f'{repo_metadata_file}.json')
            self.write_json_data(json_path, rpms)


if __name__ == '__main__':

    synchronizer = NexusSynchronizer("centos", "7", "x86_64", "./")
    synchronizer.generate_pkg_meta()

    synchronizer = NexusSynchronizer("centos", "8", "x86_64", "./")
    synchronizer.generate_pkg_meta()


    synchronizer = NexusSynchronizer("openeuler", "22", "x86_64", "./")
    synchronizer.generate_pkg_meta()

    synchronizer = NexusSynchronizer("kylin", "v10", "aarch64", "./")
    synchronizer.generate_pkg_meta()

    synchronizer = NexusSynchronizer("kylin", "v10", "x86_64", "./")
    synchronizer.generate_pkg_meta()
