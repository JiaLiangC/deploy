import requests
import json
import hashlib
import os
from urllib.parse import urljoin
from time import sleep
import argparse
import yaml

# 1.考虑到请求不能过快，防止被当作爬虫
# 2.考虑到请求失败的情况，记录失败的包到一个json文件里，成功的也记录到一个另一个json 文件。
# 3.下载好后对比md5 hash 进行文件校验，如果不一致，就删除该包，然后记录到失败包json 文件。
# 4.如果请求失败，就重试三次
# 5.每次启动时，检测下载失败文件json记录,然后重新下载失败的包，下载成功后，从失败的文件中移除记录，添加到成功的json 文件里
# 6.每次启动时访问远端代理仓库获取全量包信息后，对比本地下载成功的JSON 数据，只下载未下载的包,下载成功后添加到成功json 文件里。
# 7.可以接受参数，包下载目录，远程代理仓库地址

class NexusSynchronizer:
    def __init__(self, remote_repo_url, local_dir):
        self.remote_repo_url = remote_repo_url
        self.local_dir = local_dir
        self.success_file = os.path.join(local_dir, 'success.json')
        self.failure_file = os.path.join(local_dir, 'failure.json')
        self.retry_limit = 3

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

    def validate_md5(self, downloaded_file, md5_hash):
        hash_md5_local = hashlib.md5()
        with open(downloaded_file, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5_local.update(chunk)
        return hash_md5_local.hexdigest() == md5_hash

    def download_package(self, package_url, local_filepath, md5_hash):
        retries = 0
        while retries < self.retry_limit:
            try:
                response = requests.get(package_url, stream=True)
                if response.status_code == 200:
                    with open(local_filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    if self.validate_md5(local_filepath, md5_hash):
                        return True, None
                    else:
                        os.remove(local_filepath)
                sleep(0.1)  # delay to prevent being seen as a bot
                retries += 1
            except Exception as e:
                return False, str(e)
        return False, 'Retry limit exceeded.'

    def sync_repository(self):
        success_packages = self.load_json_data(self.success_file)
        failure_packages = self.load_json_data(self.failure_file)
        # get package list from remote repo
        repo_packages = get_packages()
        for package_info in repo_packages['packages']:
            pkg_name = package_info['name']
            pkg_md5 = package_info['md5']
            pkg_url = urljoin(self.remote_repo_url, pkg_name)
            local_filename = os.path.join(self.local_dir, pkg_name)
            if pkg_name not in success_packages:
                success, error = self.download_package(pkg_url, local_filename, pkg_md5)
                if success:
                    success_packages[pkg_name] = {'md5': pkg_md5}
                    if pkg_name in failure_packages:
                        del failure_packages[pkg_name]
                else:
                    failure_packages[pkg_name] = {'error': error, 'md5': pkg_md5}
        self.write_json_data(self.success_file, success_packages)
        self.write_json_data(self.failure_file, failure_packages)

def get_packages():
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(SCRIPT_DIR, 'packages.yml')
    with open(file_path, 'r') as f:
        data = yaml.load(f)
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('remote_repo_url', help='Remote Nexus Repository URL',
                        default="http://mirrors.aliyun.com/centos/7/os/x86_64/Packages/")
    parser.add_argument('local_dir', help='Launch command', default="/data/sdv1/nexus_data")
    args = parser.parse_args()

    synchronizer = NexusSynchronizer(args.remote_repo_url, args.local_dir)
    synchronizer.sync_repository()
