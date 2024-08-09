#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
import yaml
from datetime import datetime
import random

PROG = os.path.basename(sys.argv[0])
PROVISION_ID_FILE = '.provision_id'
YAML_CONF = 'config.yaml'
DOCKER_COMPOSE_CMD = 'docker-compose'
ERROR_PREFIX = '.error_msg_'

def run_command(command, shell=False):
  """Execute a shell command and return its output."""
  try:
    result = subprocess.run(command, shell=shell, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.stdout.strip()
  except subprocess.CalledProcessError as e:
    print(f"Command failed: {e}")
    print(f"Error output: {e.stderr}")
    sys.exit(1)

def log(message):
  print(f"\n[LOG] {message}\n")

def get_yaml_config(key, subkey=None):
  with open(YAML_CONF, 'r') as file:
    data = yaml.safe_load(file)
  if subkey:
    return data[key][subkey]
  return data[key]

def get_nodes():
  global NODES
  if PROVISION_ID:
    NODES = run_command(f"{DOCKER_COMPOSE_CMD} -p {PROVISION_ID} ps -q", shell=True).split()

def create(num_instances):
  global PROVISION_ID
  if os.path.exists(PROVISION_ID_FILE):
    log(f"Cluster already exists! Run ./{PROG} -d to destroy the cluster or delete {PROVISION_ID_FILE} file and containers manually.")
    sys.exit(1)

  PROVISION_ID = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_r{random.randint(1000, 9999)}"
  with open(PROVISION_ID_FILE, 'w') as f:
    f.write(PROVISION_ID)

  open('./config/hosts', 'w').close()

  image_name = get_yaml_config('docker', 'image')
  running_arch = run_command('uname -m')
  if running_arch != 'x86_64':
    image_name = f"{image_name}-{running_arch}"
  os.environ['DOCKER_IMAGE'] = image_name

  memory_limit = get_yaml_config('docker', 'memory_limit')
  os.environ['MEM_LIMIT'] = memory_limit

  os.environ['HOST_PORT'] = '8082'
  os.environ['HOST_PORT_END'] = '8089'

  run_command(f"{DOCKER_COMPOSE_CMD} -p {PROVISION_ID} up -d --scale bigtop={num_instances} --no-recreate", shell=True)

  get_nodes()
  hadoop_head_node = run_command(f"docker inspect --format {{{{.Config.Hostname}}}}.{{{{.Config.Domainname}}}} {NODES[0]}", shell=True)

  repo = get_yaml_config('repo')
  components = f"[{', '.join(get_yaml_config('components'))}]"
  distro = get_yaml_config('distro')
  enable_local_repo = get_yaml_config('enable_local_repo')

  disable_gpg_check = get_yaml_config('disable_gpg_check')
  gpg_check = 'false' if enable_local_repo or disable_gpg_check else 'true'

  generate_hosts()
  bootstrap(distro, enable_local_repo)

  DEST_DIR = "/deploy-home/bigdata-deploy"
  CONF_DIR = "/deploy-home/bigdata-deploy/conf"
  FILENAME = "base_conf.yml"

  output = ""
  for node in NODES:
    ip_hostname = run_command(f"docker inspect --format '{{{{range.NetworkSettings.Networks}}}}{{{{.IPAddress}}}}{{{{end}}}} {{{{.Config.Hostname}}}}.{{{{.Config.Domainname}}}}' {node}", shell=True)
    output += f"  - {ip_hostname} B767610qa4Z\n"

  print(f"Configuration file has been generated at {CONF_DIR}/{FILENAME}")

  get_nodes()
  for node in NODES:
    config_content = f"""default_password: 'B767610qa4Z'
stack_version: '3.3.0'
data_dirs: ['/data/sdv1']
repos:

user: root
hosts:
{output}
components_to_install: ['zookeeper','ambari','hbase','hdfs','yarn','hive','spark','flink','ambari_metrics','infra_solr']

backup_old_repo: no
should_deploy_ambari_mpack: false
deploy_ambari_only: false
prepare_nodes_only: false

cluster_name: 'cluster'
hdfs_ha_name: 'c1'
ansible_ssh_port: 22"""
    run_command(f"docker exec {node} bash -c \"echo '{config_content}' > {CONF_DIR}/{FILENAME}\"", shell=True)
    run_command(f"docker exec {node} bash -c '/deploy-home/provisioner/utils/install_cluster.sh {DEST_DIR}'", shell=True)
    break  # 只在第一台机器上执行

def generate_hosts():
  get_nodes()
  for node in NODES:
    entry = run_command(f"docker inspect --format '{{{{range.NetworkSettings.Networks}}}}{{{{.IPAddress}}}}{{{{end}}}} {{{{.Config.Hostname}}}}.{{{{.Config.Domainname}}}} {{{{.Config.Hostname}}}}' {node}", shell=True)
    run_command(f"docker exec {NODES[0]} bash -c \"echo {entry} >> /etc/hosts\"", shell=True)
  run_command(f"docker exec {NODES[0]} bash -c \"echo '127.0.0.1 localhost' >> /etc/hosts\"", shell=True)

def copy_to_instances(src, dest):
  get_nodes()
  for node in NODES:
    run_command(f"docker cp {src} {node}:{dest}", shell=True)

def bootstrap(distro, enable_local_repo):
  get_nodes()
  for node in NODES:
    run_command(f"docker exec {node} bash -c '/deploy-home/provisioner/utils/setup-env-{distro}.sh {enable_local_repo}'", shell=True)

def provision():
  for file in os.listdir('.'):
    if file.startswith(ERROR_PREFIX):
      os.remove(file)
  get_nodes()
  for node in NODES:
    result = run_command(f"bigtop-puppet {node}", shell=True)
    if result not in ['0', '2']:
      with open(f"{ERROR_PREFIX}{node}", 'w') as f:
        f.write(f"Failed to provision container {node} with exit code {result}")

  error_files = [f for f in os.listdir('.') if f.startswith(ERROR_PREFIX)]
  if error_files:
    for file in error_files:
      with open(file, 'r') as f:
        print(f.read())
    sys.exit(1)

def destroy():
  global PROVISION_ID
  if not PROVISION_ID:
    print("No cluster exists!")
  else:
    get_nodes()
    run_command(f"docker exec {NODES[0]} bash -c 'umount /etc/hosts; rm -f /etc/hosts'", shell=True)
    NETWORK_ID = run_command(f"docker network ls --quiet --filter name={PROVISION_ID}_default", shell=True)

    if PROVISION_ID:
      run_command(f"{DOCKER_COMPOSE_CMD} -p {PROVISION_ID} stop", shell=True)
      run_command(f"{DOCKER_COMPOSE_CMD} -p {PROVISION_ID} rm -f", shell=True)

    if NETWORK_ID:
      run_command(f"docker network rm {PROVISION_ID}_default", shell=True)

    for file in ['./config', PROVISION_ID_FILE] + [f for f in os.listdir('.') if f.startswith(ERROR_PREFIX)]:
      if os.path.isdir(file):
        os.rmdir(file)
      else:
        os.remove(file)

def execute(target, *args):
  if target.isdigit():
    get_nodes()
    node = NODES[int(target) - 1]
  else:
    node = target
  run_command(f"docker exec -ti {node} {' '.join(args)}", shell=True)

def env_check():
  print("Environment check...")
  print("Check docker:")
  run_command("docker -v", shell=True)
  print("Check docker-compose:")
  run_command(f"{DOCKER_COMPOSE_CMD} -v", shell=True)
  print("Check ruby:")
  run_command("ruby -v", shell=True)

def list_cluster():
  try:
    msg = run_command(f"{DOCKER_COMPOSE_CMD} -p {PROVISION_ID} ps", shell=True)
  except subprocess.CalledProcessError:
    msg = "Cluster hasn't been created yet."
  print(msg)

def main():
  global DOCKER_COMPOSE_CMD, PROVISION_ID

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

  if args.docker_compose_plugin:
    DOCKER_COMPOSE_CMD = "docker compose"

  if os.path.exists(PROVISION_ID_FILE):
    with open(PROVISION_ID_FILE, 'r') as f:
      PROVISION_ID = f.read().strip()

  if args.conf:
    global YAML_CONF
    YAML_CONF = args.conf

  if args.docker_compose_yml:
    DOCKER_COMPOSE_CMD += f" -f {args.docker_compose_yml}"

  if args.create:
    env_check()
    create(args.create)
  elif args.destroy:
    destroy()
  elif args.exec:
    execute(*args.exec)
  elif args.list:
    list_cluster()
  else:
    parser.print_help()

if __name__ == "__main__":
  main()
