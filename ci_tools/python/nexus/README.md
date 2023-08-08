脚本
1.自动安装启动一个nexus bin

2.1自动下载并且上传对应的包到nexus
2.2自动开启bigtop 容器打包
3.容器打包结束上传，可以增加是否跑冒烟测试的步骤

4.判断前两部结果，都过了就打包一份大包
5.自动部署一个ambari 集群进行测试


1.bigtop 拉容器自动打包，打包目录是映射的
2.增加各个组件的repo 设置patch,py3 patch
2.脚本设置容器内前端，rpm, wget 等代理
2.判断打包成功后，调用脚本，自动安装启动一个nexus bin, 上传包到对应的repo，记录组件打包结果

1.打包环境设置
1.使用maven jinja2配置模版，替换容器系统默认的maven setting.xml
2.gradle 仓库设置 
3.组件仓库 patch
4.前端代理设置



1.系统配置好 maven 代理
jinja2 模版

2.gradel 配置好代理 git 配置好代理

所有组件设置 respository 的patch

2.所有组件编译成功判断

3.输入参数编译某几个组件上传到指定，nexus 参数，并重新部署集群

增加运行指定打好的包的冒烟测试的流程

不同阶段 可以设置依赖，可以并发和串行调度

1.去docker 镜像
2.改镜像的repo



1.镜像修改后丢到 nexus
记录修改文档

2.手动下载好所有的编译要下载的文件，源码包，gradle包，做好软链接丢到bigtop

3.bigtop 修改maven
3.docker run -d -it --network host -v ${PWD}:/ws -v /data/sdv1/bigtop_reporoot:/root --workdir /ws --name BIGTOP bigtop/slaves:3.2.0-centos-7
docker run -d -it --network host -v ${PWD}:/ws -v /data/sdv1/bigtop_reporoot:/root --workdir /ws --name BIGTOP bigtop/slaves:3.2.0-centos-7