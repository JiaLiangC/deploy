* todo ansible 到所有节点的免密登录
* todo 多次执行幂等
* path 等通用变量优化
* 完善增加各种异常检测，增强建壮性
* 增加完善配置检测(检测每个组的机器不可以有重复）
* todo 需要建立一个 完整的centos7 nexus 仓库
* mpack install for all services
* 检查所有template 防止没有成功覆盖老文件
* 测试远程nexus, 数据库是否可用
* 重写项目中的检测逻辑, 包括set variable 中的
* psmisc 检测并安装
*  conf 两组group 数量和名字检测一致性
* 支持用户自定义蓝图并且动态生成cluster_template
* hdfs ha 必须存在 journal node, SECONDARY_NAMENODE 不能共存， 只能满足两种模式，hdfs ha 两 nn, 奇数个JN，两个ZKFC，其他HA 模式组件都进行检查
*  暂时不支持数据目录意外的目录配置多个目录
#数据目录（dfs.data.dir）：这是存储 HDFS 数据块的目录。通过将多个数据目录配置在不同的物理磁盘上，可以实现数据的分布和并行读写，从而提高性能和容量。
#名称目录（dfs.name.dir）：这是存储 HDFS 的命名空间和元数据的目录。配置多个名称目录可以提供冗余和容错能力，以防止元数据损坏或丢失。
#日志目录（dfs.namenode.edits.dir）：这是存储 HDFS 名称节点编辑日志的目录。配置多个日志目录可以增加编辑日志的冗余和容错性，并提高故障恢复的能力。