#!/bin/bash

# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -e 

usage() {
    echo "usage: $PROG [-C file] [-F file] args"
    echo "       -C file                                   - Use alternate file for config.yaml"
    echo "       -F file, --docker-compose-yml file        - Use alternate file for docker-compose.yml"
    echo "  commands:"
    echo "       -c NUM_INSTANCES, --create NUM_INSTANCES  - Create a Docker based Bigtop Hadoop cluster"
    echo "       -d, --destroy                             - Destroy the cluster"
    echo "       -dcp, --docker-compose-plugin             - Execute docker compose plugin command 'docker compose'"
    echo "       -e, --exec INSTANCE_NO|INSTANCE_NAME      - Execute command on a specific instance. Instance can be specified by name or number"
    echo "                                                   For example: $PROG --exec 1 bash"
    echo "                                                                $PROG --exec docker_bigtop_1 bash"
    echo "       -l, --list                                - List out container status for the cluster"
    echo "       -L, --enable-local-repo                   - Whether to use repo created at local file system. You can get one by $ ./gradlew repo"
    echo "       -m, --memory MEMORY_LIMIT                 - Overwrite the memory_limit defined in config file"
    echo "       -r, --repo REPO_URL                       - Overwrite the yum/apt repo defined in config file"
    echo "       -h, --help"
    exit 1
}

create() {
    if [ -e .provision_id ]; then
        log "Cluster already exist! Run ./$PROG -d to destroy the cluster or delete .provision_id file and containers manually."
        exit 1;
    fi
    echo "`date +'%Y%m%d_%H%M%S'`_r$RANDOM" > .provision_id
    PROVISION_ID=`cat .provision_id`


	echo > ./config/hosts

    # set correct image name based on running architecture
    if [ -z ${image_name+x} ]; then
        image_name=$(get-yaml-config docker image)
    fi
    running_arch=$(uname -m)
    if [ "x86_64" == ${running_arch} ]; then
        image_name=${image_name}
    else
        image_name=${image_name}-${running_arch}
    fi
    export DOCKER_IMAGE=${image_name}

    if [ -z ${memory_limit+x} ]; then
        memory_limit=$(get-yaml-config docker memory_limit)
    fi
    export MEM_LIMIT=${memory_limit}

    export HOST_PORT=8082
    export HOST_PORT HOST_PORT_END=8089
    # Startup instances
    $DOCKER_COMPOSE_CMD -p $PROVISION_ID up -d --scale bigtop=$1 --no-recreate
    if [ $? -ne 0 ]; then
        log "Docker container(s) startup failed!";
        exit 1;
    fi

    # Get the headnode FQDN
    # shellcheck disable=SC2207
    NODES=(`$DOCKER_COMPOSE_CMD -p $PROVISION_ID ps -q`)
    # shellcheck disable=SC1083
    hadoop_head_node=`docker inspect --format {{.Config.Hostname}}.{{.Config.Domainname}} ${NODES[0]}`

    # Fetch configurations form specificed yaml config file
    if [ -z ${repo+x} ]; then
        repo=$(get-yaml-config repo)
    fi
    if [ -z ${components+x} ]; then
        components="[`echo $(get-yaml-config components) | sed 's/ /, /g'`]"
    fi
    if [ -z ${distro+x} ]; then
        distro=$(get-yaml-config distro)
    fi
    if [ -z ${enable_local_repo+x} ]; then
        enable_local_repo=$(get-yaml-config enable_local_repo)
    fi
    if [ -z ${gpg_check+x} ]; then
        disable_gpg_check=$(get-yaml-config disable_gpg_check)
        if [ -z "${disable_gpg_check}" ]; then
            if [ "${enable_local_repo}" = true ]; then
                # When enabling local repo, set gpg check to false
                gpg_check=false
            else
                gpg_check=true
            fi
        elif [ "${disable_gpg_check}" = true ]; then
            gpg_check=false
        else
            gpg_check=true
        fi
    fi
#    generate-config "$hadoop_head_node" "$repo" "$components"


	"ci_tools/resources/pkgs/udh-packages"
    # Start provisioning
    generate-hosts

    bootstrap $distro $enable_local_repo

    DEST_DIR="/deploy-home/bigdata-deploy"
    CONF_DIR="/deploy-home/bigdata-deploy/conf"
    FILENAME="base_conf.yml"

	output=""
	for node in ${NODES[*]}; do
		ip_hostname=$(docker inspect --format "{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}} {{.Config.Hostname}}.{{.Config.Domainname}}" $node)
		output+="  - $ip_hostname B767610qa4Z\n"
	done



	echo "Configuration file has been generated at $CONF_DIR/$FILENAME"

    get_nodes
    for node in ${NODES[*]}; do
    	docker exec $node bash -c "echo -e \"default_password: 'B767610qa4Z'
stack_version: '3.3.0'
data_dirs: ['/data/sdv1']
repos:

user: root
hosts:
$output
components_to_install: ['zookeeper','ambari','hbase','hdfs','yarn','hive','spark','flink','ambari_metrics','infra_solr']

backup_old_repo: no
should_deploy_ambari_mpack: false
deploy_ambari_only: false
prepare_nodes_only: false

cluster_name: 'cluster'
hdfs_ha_name: 'c1'
ansible_ssh_port: 22\" > $CONF_DIR/$FILENAME" &
        docker exec $node bash -c "/deploy-home/provisioner/utils/install_cluster.sh $DEST_DIR" &
        break  # 只在第一台机器上执行
    done
    wait
#    provision
}

generate-hosts() {
    get_nodes
    for node in ${NODES[*]}; do
        entry=`docker inspect --format "{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}} {{.Config.Hostname}}.{{.Config.Domainname}} {{.Config.Hostname}}" $node`
        docker exec ${NODES[0]} bash -c "echo $entry >> /etc/hosts"
    done
    wait
    # This must be the last entry in the /etc/hosts
    docker exec ${NODES[0]} bash -c "echo '127.0.0.1 localhost' >> ./etc/hosts"
}


copy-to-instances() {
    get_nodes
    for node in ${NODES[*]}; do
        docker cp  $1 $node:$2 &
    done
    wait
}

bootstrap() {
    get_nodes
    for node in ${NODES[*]}; do
        docker exec $node bash -c "/deploy-home/provisioner/utils/setup-env-$1.sh $2" &
    done
    wait
}

provision() {
    rm -f .error_msg_*
    get_nodes
    for node in ${NODES[*]}; do
        (
        bigtop-puppet $node
        result=$?
        # 0: The run succeeded with no changes or failures; the system was already in the desired state.
        # 1: The run failed, or wasn't attempted due to another run already in progress.
        # 2: The run succeeded, and some resources were changed.
        # 4: The run succeeded, and some resources failed.
        # 6: The run succeeded, and included both changes and failures.
        if [ $result != 0 ] && [ $result != 2 ]; then
            log "Failed to provision container $node with exit code $result" > .error_msg_$node
        fi
        ) &
    done
    wait
    if [ `find . -maxdepth 1 -type f -name ".error_msg_*" | wc -l` -gt 0 ]; then
      cat .error_msg_* 2>/dev/null && exit 1
    fi
}

destroy() {
    if [ -z ${PROVISION_ID+x} ]; then
        echo "No cluster exists!"
    else
        get_nodes
        docker exec ${NODES[0]} bash -c "umount /etc/hosts; rm -f /etc/hosts"
        NETWORK_ID=`docker network ls --quiet --filter name=${PROVISION_ID}_default`

        if [ -n "$PROVISION_ID" ]; then
            $DOCKER_COMPOSE_CMD -p $PROVISION_ID stop
            $DOCKER_COMPOSE_CMD -p $PROVISION_ID rm -f
            
        fi

        if [ -n "$NETWORK_ID" ]; then
            docker network rm ${PROVISION_ID}_default
        fi 
        rm -rvf ./config .provision_id .error_msg*
    fi
}


get-yaml-config() {
    RUBY_EXE=ruby
    if [ $# -eq 1 ]; then
        RUBY_SCRIPT="data = YAML::load(STDIN.read); puts data['$1'];"
    elif [ $# -eq 2 ]; then
        RUBY_SCRIPT="data = YAML::load(STDIN.read); puts data['$1']['$2'];"
    else
        echo "The yaml config retrieval function can only take 1 or 2 parameters.";
        exit 1;
    fi
    cat ${yamlconf} | $RUBY_EXE -ryaml -e "$RUBY_SCRIPT" | tr -d '\r'
}

execute() {
    re='^[0-9]+$'
    if [[ $1 =~ $re ]] ; then
        no=$1
        shift
        get_nodes
        docker exec -ti ${NODES[$((no-1))]} "$@"
    else
        name=$1
        shift
        docker exec -ti $name "$@"
    fi
}

env-check() {
    echo "Environment check..."
    echo "Check docker:"
    docker -v || exit 1
    echo "Check docker-compose:"
    $DOCKER_COMPOSE_CMD -v || exit 1
    echo "Check ruby:"
    ruby -v || exit 1
}

list() {
    local msg
    msg=$($DOCKER_COMPOSE_CMD -p $PROVISION_ID ps 2>&1)
    if [ $? -ne 0 ]; then
        msg="Cluster hasn't been created yet."
    fi
    echo "$msg"
}

log() {
    echo -e "\n[LOG] $1\n"
}


get_nodes() {
    if [ -n "$PROVISION_ID" ]; then
        # shellcheck disable=SC2207
        NODES=(`$DOCKER_COMPOSE_CMD -p $PROVISION_ID ps -q`)
    fi
}

change_docker_compose_cmd() {
    DOCKER_COMPOSE_CMD="docker compose"
}

PROG=`basename $0`

if [ $# -eq 0 ]; then
    usage
fi

yamlconf="config.yaml"
DOCKER_COMPOSE_CMD="docker-compose"

for arg in $@
do
   if [ "$arg" == "-dcp" ] || [ "$arg" == "--docker-compose-plugin" ]; then 
       change_docker_compose_cmd
   fi
done

if [ -e .provision_id ]; then
    PROVISION_ID=`cat .provision_id`
fi

while [ $# -gt 0 ]; do
    case "$1" in
    -c|--create)
        if [ $# -lt 2 ]; then
          echo "Create requires a number" 1>&2
          usage
        fi
        env-check
        READY_TO_LAUNCH=true
        NUM_INSTANCES=$2
        shift 2;;
    -C|--conf)
        if [ $# -lt 2 ]; then
          echo "Alternative config file for config.yaml" 1>&2
          usage
        fi
	      yamlconf=$2
        shift 2;;
    -F|--docker-compose-yml)
        if [ $# -lt 2 ]; then
          echo "Alternative config file for docker-compose.yml" 1>&2
          usage
        fi
	      DOCKER_COMPOSE_CMD="${DOCKER_COMPOSE_CMD} -f ${2}"
        shift 2;;
    -d|--destroy)
        destroy
        shift;;
    -dcp|--docker-compose-plugin)
        shift;;
    -e|--exec)
        if [ $# -lt 3 ]; then
          echo "exec command takes 2 parameters: 1) instance no 2) command to be executed" 1>&2
          usage
        fi
        shift
        execute "$@"
        shift $#;;
    -i|--image)
        if [ $# -lt 2 ]; then
          log "No image specified"
          usage
        fi
        image_name=$2
        # Determine distro to bootstrap provisioning environment
        case "${image_name}" in
          *-centos-*|*-fedora-*|*-opensuse-*|*-rockylinux-*|*-openeuler-*)
            distro=centos
            ;;
          *-debian-*|*-ubuntu-*)
            distro=debian
            ;;
          *)
            echo "Unsupported distro [${image_name}]"
            exit 1
            ;;
        esac
        shift 2;;
    -l|--list)
        list
        shift;;
    -L|--enable-local-repo)
        enable_local_repo=true
        shift;;
    -m|--memory)
        if [ $# -lt 2 ]; then
          log "No memory specified. Try --memory 4g"
          usage
        fi
        memory_limit=$2
        shift 2;;
    -p|--provision)
        provision
        shift;;
    -r|--repo)
        if [ $# -lt 2 ]; then
          log "No yum/apt repo specified"
          usage
        fi
        repo=$2
        shift 2;;
    -h|--help)
        usage
        shift;;
    *)
        echo "Unknown argument: '$1'" 1>&2
        usage;;
    esac
done

if [ "$READY_TO_LAUNCH" = true ]; then
    create $NUM_INSTANCES
fi
if [ "$READY_TO_TEST" = true ]; then
    smoke-tests
fi
