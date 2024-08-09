#  Docker provisioner

## Overview

The Docker Compose definition and wrapper script that creates Ambari  Hadoop cluster on top of Docker containers for you, by pulling from existing publishing bigtop repositories.
This cluster can be used:
test

This has been verified on Docker Engine 1.9.1, with api version 1.15, and Docker Compose 1.5.2 on Amazon Linux 2015.09 release.

## Prerequisites

### OS X and Windows

* Install [Docker Toolbox](https://www.docker.com/docker-toolbox)

### Linux

* Install [Docker](https://docs.docker.com/installation/)

* Install [Docker Compose](https://docs.docker.com/compose/install/)

* Start the Docker daemon

```
service docker start
```

## USAGE

Remember to place all your compiled RPMs in the following directory before executing the script: ci_tools/resources/pkgs/udh-packages/
if you are in windows plz use .\setup_ansible.ps1 instead of source venv.sh 

1) Set up the environment
```
cd bigdata_deploy
source venv.sh
```
2) Modify the configuration file `conf/docker_deploy_config.yaml`
By default, it uses the `bigtop/puppet:trunk-rockylinux-8` image and deploys ['zookeeper', 'ambari', 'hdfs', 'ambari_metrics']. 
If you don't have RPMs for some components, please only list the components for which you have RPMs.

3) 
Create a Bigtop Hadoop cluster with a specified number of nodes
```
python3 provisioner/docker/hadoop_docker.py -d -dcp --create 3 --docker-compose-plugin --memory 8g
```

This process takes about 10-20 minutes. 
The fewer components you deploy, the faster it will be. Once this step is complete, your cluster is deployed. Congratulations! 
For additional functionality, refer to the documentation below:




4) Destroy the cluster.
```
python3 provisioner/docker/hadoop_docker.py -d -dcp
```

5) Get into the first container (the master)

```
python3 provisioner/docker/hadoop_docker.py --exec 1 /bin/bash
```

6) Execute a command on the second container

```
python3 provisioner/docker/hadoop_docker.py --exec 2 hadoop fs -ls /
```

7) Update your cluster after doing configuration changes on ./config

```
python3 provisioner/docker/hadoop_docker.py --provision
```

Commands will be executed by following order:

```
create 5 node cluster => insatll ambari  cluster
```

8) See helper message:

```
python3 provisioner/docker/hadoop_docker.py -h
usage: hadoop_docker.py [-h] [-C CONF] [-F DOCKER_COMPOSE_YML]
                        [-c NUM_INSTANCES] [-d] [-dcp] [-e EXEC [EXEC ...]]
                        [-l] [-L] [-m MEMORY] [-r REPO]

Manage Docker based Bigtop Hadoop cluster

optional arguments:
  -h, --help            show this help message and exit
  -C CONF, --conf CONF  Use alternate file for config.yaml
  -F DOCKER_COMPOSE_YML, --docker-compose-yml DOCKER_COMPOSE_YML
                        Use alternate file for docker-compose.yml
  -c NUM_INSTANCES, --create NUM_INSTANCES
                        Create a Docker based Bigtop Hadoop cluster
  -d, --destroy         Destroy the cluster
  -dcp, --docker-compose-plugin
                        Execute docker compose plugin command 'docker compose'
  -e EXEC [EXEC ...], --exec EXEC [EXEC ...]
                        Execute command on a specific instance
  -l, --list            List out container status for the cluster
  -L, --enable-local-repo
                        Whether to use repo created at local file system
  -m MEMORY, --memory MEMORY
                        Overwrite the memory_limit defined in config file
  -r REPO, --repo REPO  Overwrite the yum/apt repo defined in config file
```

## Configurations

* There are several parameters can be configured in config.yaml:

1) Modify memory limit for Docker containers

```
docker:
        memory_limit: "8g"

```

2) Enable local repository

If you've built packages using local cloned bigtop and produced the apt/yum repo, set the following to true to deploy those packages:

```
enable_local_repo = true
```

## Configure Apache Hadoop ecosystem components
* Choose the ecosystem you want to be deployed by modifying components in config.yaml

```
components: "hadoop, hbase, yarn,..."
```

By default, Apache Hadoop and YARN will be installed.