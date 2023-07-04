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
* 卸载脚本及其他地方会连带卸载系统依赖，$ rpm -e --nodeps packageA 
* krb5-libs 不能随便卸载，否则系统很多模块无法使用 
