* 常用的一些工具打成RPM 配置到 tools目录即可 [jdk.zip" -arthas.tar.gz  perf-tools.tar.gz]
* 测试本机 nexus 安装
* 测试远程数据库是否可用, 存在同名数据库时报错
* 多次执行幂等
* path 等通用变量优化
* 完善增加各种异常检测，增强建壮性
* 支持用户自定义蓝图并且动态生成 cluster_template
* 检测防火墙杀不死, 导致服务无法通信的case
* mpack install for all services
* docker 一键测试安装集群
* 用户可以轻易的添加支持新的部署的组件
* conf key 检测(防止用户误删除或修改了配置的key)
* 遍历蓝图，清理conf中设置的自定义的数据目录比较靠谱
* 按照 hortonworks 原项目增加repo 多操作系统支持
* backup 整个yumrepo 风险较高，把ambari repo 丢到蓝图里试试
* 配置里开启 ranger 后必须在组件里选择ranger 组件
* docker 一键部署
* 配置简化，方便用户使用
* 使用手册编写,生成配置模版示例
* 安全除了支持kerberos 和 none 也支持其他方式
* 插件式开发，尽量提供良好的扩展性
* tools_pre_install:
* 暂时不支持hdfs数据目录以外的目录配置多个目录
#数据目录（dfs.data.dir）：这是存储 HDFS 数据块的目录。通过将多个数据目录配置在不同的物理磁盘上，可以实现数据的分布和并行读写，从而提高性能和容量。
#名称目录（dfs.name.dir）：这是存储 HDFS 的命名空间和元数据的目录。配置多个名称目录可以提供冗余和容错能力，以防止元数据损坏或丢失。
#日志目录（dfs.namenode.edits.dir）：这是存储 HDFS 名称节点编辑日志的目录。配置多个日志目录可以增加编辑日志的冗余和容错性，并提高故障恢复的能力。