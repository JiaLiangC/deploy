import time

import requests
from python.common.basic_logger import get_logger
import os
import glob
from python.common.constants import *
from python.utils.os_utils import *
import json
from functools import wraps

from concurrent.futures import ThreadPoolExecutor, as_completed

logger = get_logger(name="nexus_client", log_file="nexus_client.log")


class NexusClient:
    def __init__(self, server_host, username, password):
        self.server_host = server_host
        self.server_por = "8081"
        self.auth = (username, password)

    def get_nexus_url(self):
        return f"http://{self.server_host}:{self.server_por}"

    # repository/centos/7/os/x86_64/Packages/Cython-0.19-5.el7.x86_64.rpm
    def get_os_packages_url(self, os_info):
        import platform
        os_type = os_info[0]
        os_version = os_info[1]
        os_architecture = os_info[2]
        if os_architecture not in SUPPORTED_ARCHS:
            raise Exception(f"os architecture {os_architecture} not supported. only support: {SUPPORTED_ARCHS} ")
        base_url = f"{self.get_nexus_url()}/repository/{os_type}/{os_version}/os/{os_architecture}/Packages"
        logger.info(f"nexus client get_os_packages_url: {base_url}")
        return base_url

    def get_os_repo_name(self, os_info):
        os_type = os_info[0]
        return os_type

    def get_os_yum_dir(self, os_info):
        os_type = os_info[0]
        os_version = os_info[1]
        os_architecture = os_info[2]
        yum_dir = f"/{os_version}/os/{os_architecture}/Packages"
        return yum_dir

    def get_udh_yum_dir(self, component_dir_name):
        relative_dir = UDH_NEXUS_REPO_PACKAGES_PATH
        yum_dir = f"/{relative_dir}/{component_dir_name}"
        return yum_dir

    def get_bigdata_component_url(self, component_dir_name):
        repo_name = UDH_NEXUS_REPO_NAME
        relative_dir = UDH_NEXUS_REPO_PACKAGES_PATH
        base_url = f"{self.get_nexus_url()}/repository/{repo_name}/{relative_dir}/{component_dir_name}"
        return base_url

    def retry(max_retries):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                for i in range(max_retries):
                    result = func(*args, **kwargs)
                    if result:
                        return result
                    else:
                        logger.info(f"Retry {i + 1}/{max_retries}")
                return False

            return wrapper

        return decorator

    def upload_rpm_to_yum_repo(self, file_path, repo_name, yum_directory):
        url = f"{self.get_nexus_url()}/service/rest/v1/components?repository={repo_name}"
        files = {'yum.asset': (file_path.split('/')[-1], open(file_path, 'rb'))}
        data = {
            'yum.asset.filename': file_path.split('/')[-1],
            'yum.directory': yum_directory
        }
        response = requests.post(url, auth=self.auth, data=data, files=files)
        if response.status_code == 204:
            return True
        logger.error(
            f"Upload  failed for {file_path}, {url} Status code:{response.status_code} Headers:  {response.headers}")
        return True

    @retry(max_retries=3)
    def upload(self, file_path, base_url):
        with open(file_path, 'rb') as f:
            response = requests.put(base_url, data=f, auth=self.auth)
            if response.status_code == 200:
                logger.info(f"Upload completed for {file_path}, {base_url}")
                return True
            else:
                logger.info(
                    f"Upload failed for {file_path}, {base_url} Status code:{response.status_code} Headers:  {response.headers} Body: {response.text}")
                return False

    def upload_os_pkgs(self, file_path, os_info):
        is_success = self.upload_rpm_to_yum_repo(file_path, self.get_os_repo_name(os_info),
                                                 self.get_os_yum_dir(os_info))
        return is_success

    def upload_bigdata_pkgs(self, file_path, component_dir_name):
        is_success = self.upload_rpm_to_yum_repo(file_path, UDH_NEXUS_REPO_NAME,
                                                 self.get_udh_yum_dir(component_dir_name))
        return is_success

    def batch_upload_os_pkgs(self, source_dirs, os_info, num_threads=10):
        for source_dir in source_dirs:
            filepaths = glob.glob(os.path.join(source_dir, "**", "*.rpm"), recursive=True)
            non_src_filepaths = [fp for fp in filepaths if not fp.endswith("src.rpm")]

            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = {executor.submit(self.upload_os_pkgs, filepath, os_info): filepath for filepath in
                           non_src_filepaths}

                for future in as_completed(futures):
                    filepath = futures[future]
                    try:
                        success = future.result()
                        if success:
                            logger.info(f"Upload was successful for {filepath}")
                        else:
                            logger.info(f"Upload failed for {filepath}")
                    except Exception as e:
                        logger.error(f"Upload resulted in an exception for {filepath}: {e}")
        self.rebuild_index(self.get_os_repo_name(os_info))
        # Wait for Nexus to automatically refresh the repodata build.
        sleep_with_logging(15 * 60, 10, "waiting nexus rebuild repodata")

    def batch_upload_bigdata_pkgs(self, source_dir, component_dir_name, num_threads=10):
        filepaths = glob.glob(os.path.join(source_dir, "**", "*.rpm"), recursive=True)
        non_src_filepaths = [fp for fp in filepaths if not fp.endswith("src.rpm")]
        logger.debug(f"non_src_filepaths: {non_src_filepaths}")
        self.delete_folder(UDH_NEXUS_REPO_NAME, f"{UDH_NEXUS_REPO_PACKAGES_PATH}/{component_dir_name}")
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = {executor.submit(self.upload_bigdata_pkgs, filepath, component_dir_name): filepath for filepath in
                       non_src_filepaths}
            for future in as_completed(futures):
                filepath = futures[future]
                success = future.result()
                if success:
                    logger.info(f"Upload was successful for {filepath}")
                else:
                    logger.info(f"Upload failed for filepath: {filepath} source_dir:{source_dir}")
                    raise Exception("upload bigdata components failed,please check the log and update again")
        self.rebuild_index(UDH_NEXUS_REPO_NAME)
        # Wait for Nexus to automatically refresh build repodata.
        sleep_with_logging(15 * 60, 10, "waiting nexus rebuild repodata")

    def rebuild_index(self, repo_name):
        url = f"{self.get_nexus_url()}/service/rest/v1/repositories/{repo_name}/rebuild-index"
        headers = {
            'Content-Type': 'application/json',
        }
        response = requests.post(url, headers=headers, auth=self.auth)
        logger.info(
            f"nexus rebuild_index url:{url} params:{repo_name}  Status code:{response.status_code} Headers:  {response.headers} Body: {response.text}")

    def delete_folder(self, repo_name, relative_path):
        url = f"{self.get_nexus_url()}/service/extdirect"
        logger.info(f"component_delete {url}")
        headers = {
            'Content-Type': 'application/json',
        }

        data = {
            'action': 'coreui_Component',
            'method': 'deleteFolder',
            'data': [f'{relative_path}', repo_name],
            'type': 'rpc',
            'tid': 20
        }

        logger.info(f"------data is {data}")
        response = requests.post(url, headers=headers, json=data, auth=self.auth)
        logger.info(
            f"nexus delete_folder url:{url} params:{repo_name} {relative_path} Status code:{response.status_code} Headers:  {response.headers} Body: {response.text}")

    def do_repo_create(self, repo_name, redeploy=False):
        write_policy = "ALLOW" if redeploy else "ALLOW_ONCE"
        recipe = "yum-hosted"
        url = f"{self.get_nexus_url()}/service/extdirect"
        logger.info(f"component_delete {url}")
        headers = {
            'Content-Type': 'application/json',
        }
        data = {
            "action": "coreui_Repository",
            "method": "create",
            "data": [{"attributes": {f"yum": {"repodataDepth": 1, "deployPolicy": "STRICT"},
                                     "storage": {"blobStoreName": "default", "strictContentTypeValidation": True,
                                                 "writePolicy": write_policy},
                                     "component": {"proprietaryComponents": False}, "cleanup": {"policyName": []}},
                      "name": repo_name, "format": "", "type": "", "url": "", "online": True, "recipe": recipe}],
            "type": "rpc", "tid": 20
        }

        logger.info(f"------data is {data}")
        response = requests.post(url, headers=headers, json=data, auth=self.auth)
        logger.info(
            f"do_repo_create url:{url} repo_name:{repo_name} Status code:{response.status_code} Headers:  {response.headers} Body: {response.text}")

    def repo_create(self, repo_name, remove_old=False, redeploy=False):
        repo_list = self.get_repos()
        result = list(filter(lambda d: d['name'] == repo_name, repo_list))
        logger.info(f"repo_create check  {repo_name} whether exist, result: {result}")
        if len(result) > 0:
            if remove_old:
                self.repo_remove(repo_name)
        else:
            logger.info(f"do_repo_create {repo_name}")
            self.do_repo_create(repo_name, redeploy=redeploy)

    def repo_remove(self, repo_name):
        recipe = "yum-hosted"
        url = f"{self.get_nexus_url()}/service/extdirect"
        logger.info(f"component_delete {url}")
        headers = {
            'Content-Type': 'application/json',
        }
        data = {"action": "coreui_Repository", "method": "remove", "data": [repo_name], "type": "rpc", "tid": 60}
        response = requests.post(url, headers=headers, json=data, auth=self.auth)
        logger.info(
            f"repo_remove repo_name:{repo_name}  url:{url} Status code:{response.status_code} Headers:  {response.headers} Body: {response.text}")

    def get_repos(self):
        url = f"{self.get_nexus_url()}/service/extdirect"
        data = {"action": "coreui_Repository", "method": "readReferences",
                "data": [{"page": 1, "start": 0, "limit": 100}], "type": "rpc", "tid": 30}

        headers = {
            'Content-Type': 'application/json',
        }
        response = requests.get(url, headers=headers, json=data, auth=self.auth)

        if response.status_code == 200:
            response_data = response.json()  # 获取响应体的 JSON 格式内容
            repo_list = response_data["result"]["data"]
            return repo_list
        else:
            logger.error(
                f"request faild, Status code:{response.status_code} Headers:  {response.headers} Body: {response.text}")
            return []

    def change_password(self, new_pwd):
        url = f"{self.get_nexus_url()}/service/rest/v1/security/users/admin/change-password"
        headers = {
            'Content-Type': 'text/plain',
        }
        response = requests.put(
            url,
            auth=self.auth,
            headers=headers,
            data=new_pwd
        )
        logger.info(f"url: {url} Status code:{response.status_code} Headers:  {response.headers} Body: {response.text}")

    def upload_script(self, admin_password):
        url = f"{self.get_nexus_url()}/service/rest/v1/script"
        script_name = os.path.splitext(os.path.basename(GROOVY_FILE))[0]

        with open(f'{GROOVY_FILE}', 'r') as file:
            script_content = file.read()
        body = {
            "name": script_name,
            "type": "groovy",
            "content": script_content
        }

        response = requests.post(
            url,
            timeout=30,
            auth=('admin', admin_password),
            headers={'Content-Type': 'application/json'},
            verify=False,
            data=json.dumps(body)
        )
        logger.info(f"url: {url} Status code:{response.status_code} Headers:  {response.headers} Body: {response.text}")

        if response.status_code == 204:
            logger.info('Script declaration was successful.')
        else:
            logger.info(f'Unexpected status code: {response.status_code}')

    def run_script(self, admin_password, new_pwd):
        script_name = os.path.splitext(os.path.basename(GROOVY_FILE))[0]
        url = f"{self.get_nexus_url()}/service/rest/v1/script/{script_name}/run"
        args = {"new_password": new_pwd}
        response = requests.post(
            url,
            timeout=30,
            auth=('admin', admin_password),
            headers={'Content-Type': 'text/plain'},
            verify=False,
            data=json.dumps(args)
        )

        if response.status_code == 200:
            logger.info('Script run was successful.')
        else:
            logger.info(f'Unexpected status code: {response.status_code}')

        logger.info(f"url: {url} Status code:{response.status_code} Headers:  {response.headers} Body: {response.text}")

    def set_pwd_first_launch(self, initila_pwd, new_pwd):
        self.upload_script(initila_pwd)
        self.run_script(initila_pwd, new_pwd)


if __name__ == '__main__':
    repo = "http://172.27.8.25:8081/repository/yum/sdp_3.1/packages/test"
    nexus_client = NexusClient("172.27.8.25", "admin", "admin123")
    # nexus_client.component_upload("/home/jialiang/sdp/prjs/tmp/ambari-agent-3.0.0.0-SNAPSHOT.x86_64.rpm", "test")
    # nexus_client.component_delete("test")
    # nexus_client.repo_create("test1")
