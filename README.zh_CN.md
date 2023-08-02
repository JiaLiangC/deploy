bigdata-deply
-----------
- en [English](README.md)
- zh_CN [简体中文](README.zh_CN.md)

这个项目主要使用 Ambari Blueprints 来一件部署大数据集群. 完整的功能特性列表如下 [below](#features).

- 已测试的版本: BIGTOP 3.2.0  Ambari 2.8.0 .


- 项目目标是配置机器环境 (OS settings, database, KDC, etc) 然后安装 Ambari 使用 Ambari Blueprints去创建一个集群.


## [Installation Instructions](id:instructions)
- Static inventory: See [INSTALL.md](INSTALL_static.md) for cluster installation on pre-built environments.


## [Requirements](id:requirements)

- Ansible 2.8+

- Expects CentOS/RHEL


## [Concepts](id:concepts)

The core concept of these playbooks is the `host_groups` field in the [Ambari Blueprint](https://cwiki.apache.org/confluence/display/AMBARI/Blueprints#Blueprints-BlueprintFieldDescriptions).
This is an essential piece of Ambari Blueprints that maps the topology components to the actual servers.


## [Parts](id:parts)

目前，项目中安装所做的操作被分成以下几个部分：:
 
1. **(Optional) Build the Cloud nodes**

   运行  `install_cluster.py` .


1. **Prepare the cluster nodes**
  
    安装所需的操作系统包，应用推荐的操作系统设置，并准备数据库和/或本地MIT-KDC（麻省理工学院的Key Distribution Center，密钥分发中心）。

2. **Install Ambari**

   在这些节点上安装Ambari。

   这将添加Ambari仓库，安装Ambari Agent和Server包，并配置Ambari Server所需的Java和数据库选项。

3. **Configure Ambari**

    配置 Ambari.
    将进一步配置Ambari的一些设置，更改管理员密码，并添加集群构建所需的仓库信息。


4. **Apply Blueprint**  
   将蓝图上传到Ambari并开启。然后，Ambari会创建并安装集群。



## [Features](id:features)

### Infrastructure support
- [x] Pre-built infrastructure (using a static inventory file)



### OS support
- [x] CentOS/RHEL 7 support

### Prerequisites done
- [x] 清理所有被部署机器中已经安装过的文件，防止再次安装失败
- [x] 安装 且启动 NTP
- [x] 创建 /etc/hosts 映射
- [x] 设置 nofile and nproc limits
- [x] 设置 swappiness
- [x] 关闭 SELinux
- [x] 关闭 THP
- [x] 设置 Ambari yum 仓库
- [x] 安装 OpenJDK 
- [x] 安装 配置 MySQL
- [x] 安装 配置 PostgreSQL
- [x] 安装 配置 本地的 MIT KDC


### Cluster build supported features
- [x] 安装 Ambari Agents and Server
- [x] 配置 Ambari Server with OpenJDK
- [x] 配置 Ambari Server with external database options
- [ ] 配置 Ambari Server with SSL
- [x] 配置 custom Repositories 
- [x] 配置 custom Paths (data / logs / metrics / tmp)
- [x] 构建 BIGTOP clusters
- [x] Build clusters with a dynamically generated JSON blueprint (dynamic blueprint based on Jinja2 template and variables)
- [x] Wait for the cluster to be built

### Dynamic blueprint supported features
> The components that will be installed are only those defined in the `blueprint_dynamic` [variable](ansible-scripts/playbooks/group_vars/all#L161).
> - Supported in this case means all prerequites (databases, passwords, required configs) are taken care of and the component is deployed successfully on the chosen `host_group`.
- [x] BIGTOP Services: `HDFS`, `YARN + MapReduce2`, `Hive`, `HBase`, `Accumulo`, `Oozie`, `ZooKeeper`, `Storm`, `Atlas`, `Kafka`, `Knox`, `Log Search`, `Ranger`, `Ranger KMS`, `SmartSense`, `Spark2`, `Zeppelin`, `Druid`, `Superset`
- [x] HA 配置: NameNode, ResourceManager, Hive, HBase, Ranger KMS, Druid
- [x] 集群安全 MIT KDC (Ambari managed)
- [x] 安装 Ranger 和 开启所有的 ranger  plugins
- [x] Ranger KMS
- [ ] Hadoop SSL
- [ ] Basic memory settings tuning
- [ ] Make use of additional storage for master services

