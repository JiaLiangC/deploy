#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
import yaml
from datetime import datetime
import random
import shutil
import logging
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, as_completed

class BigTopClusterManager:
  def __init__(self):
    self.prog = os.path.basename(sys.argv[0])
    self.provision_id_file = '.provision_id'
    self.config_file = 'config.yaml'
    self.docker_compose_cmd = 'docker-compose'
    self.error_prefix = '.error_msg_'
    self.setup_logging()
    self.load_config()
    self.docker_compose_env = {}
    self.head_node = None
    # can't mount prj in /
    self.prj_mount_dir = "/deploy/deploy-home"

  def setup_logging(self):
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

  def load_config(self):
    logging.info("Loading configuration...")
    self.provision_id = self._load_provision_id()
    self.image_name = self._get_yaml_config('docker', 'image')
    self.memory_limit = self._get_yaml_config('docker', 'memory_limit')
    self.port_start = self._get_yaml_config('port_start')
    self.repo = self._get_yaml_config('repo')
    self.distro = self._get_yaml_config('distro')
    self.port_end = self._get_yaml_config('port_end')
    self.nodes = []
    self.enable_local_repo = False
    logging.info("Configuration loaded successfully.")

  def _load_provision_id(self):
    if os.path.exists(self.provision_id_file):
      with open(self.provision_id_file, 'r') as f:
        return f.read().strip()
    return None

  def _get_yaml_config(self, key, subkey=None):
    with open(self.config_file, 'r') as file:
      data = yaml.safe_load(file)
    if subkey:
      return data[key][subkey]
    return data[key]

  def run_command(self, command, workdir=None, env_vars=None, shell=False, logfile=None, ignore_errors=False):
    logging.info(f"Executing command: {command}")
    out = logfile or subprocess.PIPE
    env_vars = dict(env_vars) if env_vars else os.environ.copy()
    try:
      process = subprocess.Popen(
        command,
        stdout=out,
        stderr=out,
        shell=shell,
        cwd=workdir,
        env=env_vars,
        universal_newlines=True
      )

      if logfile:
        exit_status = process.wait()
        return exit_status

      output, error = process.communicate()
      exit_code = process.returncode
      if exit_code == 0:
        logging.info(f"Command executed successfully: {command}")
      else:
        logging.error(f"Command failed with exit code {exit_code}: cmd: {command}, out: {output}, err:{error}")
        if not ignore_errors:
          raise Exception(f"Command failed with exit code {exit_code}: cmd: {command}, out: {output}, err:{error}")
      return exit_code, output, error
    except Exception as e:
      logging.error(f"Exception occurred while executing command: {e}")
      if not ignore_errors:
        raise
      return -1, "", str(e)

  def get_result(self, subprocess_res):
    return [node.strip() for node in subprocess_res.split("\n") if node.strip()]

  def get_nodes(self):
    logging.info("Retrieving node information...")
    if self.provision_id:
      exit_code, output, error = self.run_command(f"{self.docker_compose_cmd} -p {self.provision_id} ps -q", shell=True)
      self.nodes = self.get_result(output)
      self.head_node = self.nodes[0] if self.nodes else None
      logging.info(f"Nodes retrieved: {self.nodes}")

  def create_or_touch_file(self, file_path):
    logging.info(f"Creating or touching file: {file_path}")
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
      os.makedirs(directory)
    try:
      with open(file_path, 'a'):
        os.utime(file_path, None)
    except IOError as e:
      logging.error(f"Error creating or touching file: {e}")

  def create(self, num_instances):
    logging.info(f"Creating cluster with {num_instances} instances...")
    if os.path.exists(self.provision_id_file):
      logging.error(f"Cluster already exists! Run ./{self.prog} -d to destroy the cluster or delete {self.provision_id_file} file and containers manually.")
      sys.exit(1)
    self.provision_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_r{random.randint(1000, 9999)}"
    self.create_or_touch_file('./config/hosts')

    self.run_command(f"{self.docker_compose_cmd} -p {self.provision_id} up -d --scale bigtop={num_instances} --no-recreate", shell=True, env_vars=self.docker_compose_env)
    with open(self.provision_id_file, 'w') as f:
      f.write(self.provision_id)

    self.get_nodes()
    self.configure_cluster()
    logging.info("Cluster creation completed.")

  def configure_cluster(self):
    logging.info("Configuring cluster...")
    self.generate_hosts()
    self.bootstrap(self.distro, self.enable_local_repo)
    self.generate_config_file()
    logging.info("Cluster configuration completed.")

  def generate_hosts(self):
    logging.info("Generating hosts file...")
    for node in self.nodes:
      exit_code, output, error = self.run_command(f"docker inspect --format '{{{{range.NetworkSettings.Networks}}}}{{{{.IPAddress}}}}{{{{end}}}} {{{{.Config.Hostname}}}}.{{{{.Config.Domainname}}}} {{{{.Config.Hostname}}}}' {node}", shell=True)
      entry = self.get_result(output)[0]
      self.run_command(f"docker exec {self.head_node} bash -c \"echo {entry} >> /etc/hosts\"", shell=True)
    self.run_command(f"docker exec {self.head_node} bash -c \"echo '127.0.0.1 localhost' >> /etc/hosts\"", shell=True)
    logging.info("Hosts file generated successfully.")

  def bootstrap(self, distro, enable_local_repo):
    logging.info(f"Bootstrapping nodes with distro: {distro}, enable_local_repo: {enable_local_repo}")
    commands = [
      f"docker exec {node} bash -c '{self.prj_mount_dir}/provisioner/utils/setup-env-{distro}.sh {enable_local_repo}'"
      for node in self.nodes
    ]
    self.parallel_execute(self.run_command, commands, shell=True)
    logging.info("Bootstrap completed.")

  def parallel_execute(self, task, params, **kwargs):
    logging.info(f"Executing {len(params)} tasks in parallel...")
    with ThreadPoolExecutor(max_workers=20) as executor:
      futures = {executor.submit(task, param, **kwargs): param for param in params}

      for future in as_completed(futures):
        param = futures[future]
        try:
          result = future.result()
          if result:
            logging.info(f"Task executed successfully: {param}")
          else:
            logging.warning(f"Task execution failed: {param}")
        except Exception as e:
          logging.error(f"Task execution resulted in an exception: {param}. Error: {e}")
    logging.info("Parallel execution completed.")

  def generate_config_file(self):
    logging.info("Generating configuration file...")
    dest_dir = self.prj_mount_dir
    conf_dir = f"{self.prj_mount_dir}/conf"
    filename = "base_conf.yml"

    hosts = self._get_hosts_config()
    config_content = self._generate_config_content(hosts)

    self.run_command(f"docker exec {self.head_node} bash -c \"echo '{config_content}' > {conf_dir}/{filename}\"", shell=True)
    self.run_command(f"docker exec {self.head_node} bash -c '{self.prj_mount_dir}/provisioner/utils/install_cluster.sh {dest_dir}'", shell=True)
    logging.info(f"Configuration file has been generated at {conf_dir}/{filename}")

  def _get_hosts_config(self):
    hosts = ""
    for node in self.nodes:
      exit_code, output, error = self.run_command(f"docker inspect --format '{{{{range.NetworkSettings.Networks}}}}{{{{.IPAddress}}}}{{{{end}}}} {{{{.Config.Hostname}}}}.{{{{.Config.Domainname}}}}' {node}", shell=True)
      ip_hostname = self.get_result(output)[0]
      hosts += f"  - {ip_hostname} B767610qa4Z\n"
    return hosts

  def _generate_config_content(self, hosts):
    return f"""default_password: 'B767610qa4Z'
stack_version: '3.3.0'
data_dirs: ['/data/sdv1']
repos:

user: root
hosts:
{hosts}
components_to_install: ['zookeeper','ambari','hbase','hdfs','yarn','hive','spark','flink','ambari_metrics','infra_solr']

backup_old_repo: no
should_deploy_ambari_mpack: false
deploy_ambari_only: false
prepare_nodes_only: false

cluster_name: 'cluster'
hdfs_ha_name: 'c1'
ansible_ssh_port: 22"""

  def destroy(self):
    logging.info("Destroying cluster...")
    if not self.provision_id:
      logging.info("No cluster exists!")
      return

    self.get_nodes()
    if not self.nodes:
      self._remove_provision_id_file()
      return

    self._cleanup_head_node()
    self._stop_and_remove_containers()
    self._remove_network()
    self._remove_files()
    logging.info("Cluster destroyed successfully.")

  def _cleanup_head_node(self):
    if self.nodes:
      self.run_command(f"docker exec {self.nodes[0]} bash -c 'umount /etc/hosts; rm -f /etc/hosts'", shell=True)

  def _stop_and_remove_containers(self):
    if self.provision_id:
      self.run_command(f"{self.docker_compose_cmd} -p {self.provision_id} stop", shell=True)
      self.run_command(f"{self.docker_compose_cmd} -p {self.provision_id} rm -f", shell=True)

  def _remove_network(self):
    network_id = self.run_command(f"docker network ls --quiet --filter name={self.provision_id}_default", shell=True)
    if network_id:
      self.run_command(f"docker network rm {self.provision_id}_default", shell=True)

  def _remove_files(self):
    for file in ['./config', self.provision_id_file] + [f for f in os.listdir('.') if f.startswith(self.error_prefix)]:
      if os.path.isdir(file):
        shutil.rmtree(file, ignore_errors=True)
      elif os.path.exists(file):
        os.remove(file)

  def _remove_provision_id_file(self):
    if os.path.exists(self.provision_id_file):
      os.remove(self.provision_id_file)

  def execute(self, target, *args):
    logging.info(f"Executing command on target: {target}")
    if target.isdigit():
      self.get_nodes()
      node = self.nodes[int(target) - 1]
    else:
      node = target
    self.run_command(f"docker exec -ti {node} {' '.join(args)}", shell=True)

  def env_check(self):
    logging.info("Performing environment check...")
    logging.info("Checking docker:")
    self.run_command("docker -v", shell=True)
    logging.info("Checking docker-compose:")
    self.run_command(f"{self.docker_compose_cmd} -v", shell=True)

  def list_cluster(self):
    logging.info("Listing cluster status...")
    try:
      msg = self.run_command(f"{self.docker_compose_cmd} -p {self.provision_id} ps", shell=True)
    except subprocess.CalledProcessError:
      msg = "Cluster hasn't been created yet."
    logging.info(msg)

  def initialize_config(self, args):
    logging.info("Initializing configuration...")
    repo = args.repo or self.repo
    memory_limit = args.memory or self.memory_limit

    self.docker_compose_env = {
      'DOCKER_IMAGE': self.image_name,
      'MEM_LIMIT': memory_limit,
      'HOST_PORT': str(self.port_start),
      'HOST_PORT_END': str(self.port_end),
      'PRJ_MOUNT_DIR': str(self.prj_mount_dir)
    }

    logging.info(f"Initialized configuration: {self.docker_compose_env}")

def main():
  manager = BigTopClusterManager()

  parser = argparse.ArgumentParser(description="Manage Docker based Bigtop Hadoop cluster")
  parser.add_argument("-C", "--conf", help="Use alternate file for config.yaml")
  parser.add_argument("-F", "--docker-compose-yml", help="Use alternate file for docker-compose.yml")
  parser.add_argument("-c", "--create", type=int, metavar="NUM_INSTANCES", help="Create a Docker based Bigtop Hadoop cluster")
  parser.add_argument("-d", "--destroy", action="store_true", help="Destroy the cluster")
  parser.add_argument("-dcp", "--docker-compose-plugin", action="store_true", help="Execute docker compose plugin command 'docker compose'")
  parser.add_argument("-e", "--exec", nargs='+', help="Execute command on a specific instance")
  parser.add_argument("-l", "--list", action="store_true", help="List out container status for the cluster")
  parser.add_argument("-L", "--enable-local-repo", action="store_true", help="Whether to use repo created at local file system")
  parser.add_argument("-m", "--memory", help="Overwrite the memory_limit defined in config file")
  parser.add_argument("-r", "--repo", help="Overwrite the yum/apt repo defined in config file")

  args = parser.parse_args()

  logging.info(f"Parsed arguments: {args}")

  manager.initialize_config(args)

  if args.docker_compose_plugin:
    manager.docker_compose_cmd = "docker compose"

  if args.conf:
    manager.config_file = args.conf

  if args.docker_compose_yml:
    manager.docker_compose_cmd += f" -f {args.docker_compose_yml}"

  if args.destroy:
    manager.destroy()

  if args.create:
    manager.env_check()
    manager.create(args.create)
  elif args.exec:
    manager.execute(*args.exec)
  elif args.list:
    manager.list_cluster()
  else:
    parser.print_help()

if __name__ == "__main__":
  main()

