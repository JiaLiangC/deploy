bigdata-deply
-----------
- en [English](README.md)
- zh_CN [简体中文](README.zh_CN.md)

These Ansible playbooks will build a bigtop cluster using Ambari Blueprints. For a full list of supported features check [below](#features).

- Tested with: BIGTOP 3.2.0  Ambari 2.8.0 (the versions must be matched as per the [support matrix](https://supportmatrix.hortonworks.com)).



- The aim is prepare them (OS settings, database, KDC, etc) and then install Ambari and create the cluster using Ambari Blueprints.



## [Installation Instructions](id:instructions)
- Static inventory: See [INSTALL.md](INSTALL_static.md) for cluster installation on pre-built environments.


## [Requirements](id:requirements)

- Ansible 2.8+

- Expects CentOS/RHEL


## [Concepts](id:concepts)

The core concept of these playbooks is the `host_groups` field in the [Ambari Blueprint](https://cwiki.apache.org/confluence/display/AMBARI/Blueprints#Blueprints-BlueprintFieldDescriptions).
This is an essential piece of Ambari Blueprints that maps the topology components to the actual servers.


## [Parts](id:parts)

Currently, these playbooks are divided into the following parts:
 
1. **(Optional) Build the Cloud nodes**

   Run the `install_cluster.py` script to build the Cloud nodes. Refer to the Cloud specific INSTALL guides for more information.

2. **Install the cluster**

   Run the `install_cluster.sh` script that will install the HDP and / or HDF cluster using Blueprints while taking care of the necessary prerequisites.


...or, alternatively, run each step separately (also useful for replaying a specific part in case of failure):


1. **Prepare the Cloud nodes**

   Run the `prepare_nodes.sh` script to prepare the nodes.
  
   This installs the required OS packages, applies the recommended OS settings and prepares the database and / or the local MIT-KDC.

2. **Install Ambari**

   Run the `install_ambari.sh` script to install Ambari on the nodes.

   This adds the Ambari repo, installs the Ambari Agent and Server packages and configures the Ambari Server with the required Java and database options.

3. **Configure Ambari**

   Run the `configure_ambari.sh` script to configure Ambari.
  
   This further configures Ambari with some settings, changes admin password and adds the repository information needed by the cluster build.

4. **Apply Blueprint**

   Run the `apply_blueprint.sh` script to install HDP and / or HDF based on an Ambari Blueprint.
  
   This uploads the blueprint to Ambari and applies it. Ambari would then create and install the cluster.

5. **Post Install**

   Run the `post_install.sh` script to execute any actions after the cluster is built.


## [Features](id:features)

### Infrastructure support
- [x] Pre-built infrastructure (using a static inventory file)



### OS support
- [x] CentOS/RHEL 7 support

### Prerequisites done
- [x] clean all deployed hosts need install
- [x] Install and start NTP
- [x] Create /etc/hosts mappings
- [x] Set nofile and nproc limits
- [x] Set swappiness
- [x] Disable SELinux
- [x] Disable THP
- [x] Set Ambari repositories
- [x] Install OpenJDK 
- [x] Install and prepare MySQL
- [x] Install and prepare PostgreSQL
- [x] Install and configure local MIT KDC


### Cluster build supported features
- [x] Install Ambari Agents and Server
- [x] Configure Ambari Server with OpenJDK
- [x] Configure Ambari Server with external database options
- [ ] Configure Ambari Server with SSL
- [x] Configure custom Repositories 
- [x] Configure custom Paths (data / logs / metrics / tmp)
- [x] Build BIGTOP clusters
- [x] Build clusters with a dynamically generated JSON blueprint (dynamic blueprint based on Jinja2 template and variables)
- [x] Wait for the cluster to be built

### Dynamic blueprint supported features
> The components that will be installed are only those defined in the `blueprint_dynamic` [variable](ansible-scripts/playbooks/group_vars/all#L161).
> - Supported in this case means all prerequites (databases, passwords, required configs) are taken care of and the component is deployed successfully on the chosen `host_group`.
- [x] BIGTOP Services: `HDFS`, `YARN + MapReduce2`, `Hive`, `HBase`, `Accumulo`, `Oozie`, `ZooKeeper`, `Storm`, `Atlas`, `Kafka`, `Knox`, `Log Search`, `Ranger`, `Ranger KMS`, `SmartSense`, `Spark2`, `Zeppelin`, `Druid`, `Superset`
- [x] HA Configuration: NameNode, ResourceManager, Hive, HBase, Ranger KMS, Druid
- [x] Secure clusters with MIT KDC (Ambari managed)
- [x] Secure clusters with Microsoft AD (Ambari managed)
- [x] Install Ranger and enable all plugins
- [x] Ranger KMS
- [ ] Ranger AD integration
- [ ] Hadoop SSL
- [ ] Hadoop AD integration
- [ ] NiFi SSL
- [ ] NiFi AD integration
- [ ] Basic memory settings tuning
- [ ] Make use of additional storage for HDP workers
- [ ] Make use of additional storage for master services
- [ ] Configure additional storage for NiFi
