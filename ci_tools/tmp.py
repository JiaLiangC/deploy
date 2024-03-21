class UDHReleaseTask(BaseTask):
    def __init__(self, os_type, os_version, os_arch, comps=[], incremental_release_src_tar=""):
        super().__init__()
        self.os_type = os_type
        self.os_version = os_version
        self.os_arch = os_arch
        self.release_prj_dir = ""
        self.pigz_path = os.path.join(PRJ_BIN_DIR, "pigz")
        self.comps = comps
        self.incremental_release_src_tar = incremental_release_src_tar
        self.executor = CommandExecutor
        self.initialize()


    def get_release_name(self):
        time_dir_name = datetime.now().isoformat().replace(':', '-').replace('.', '-')
        udh_release_name = f"UDH_RELEASE_{self.os_type}{self.os_version}_{self.os_arch}-{time_dir_name}.tar.gz"
        return udh_release_name


    def initialize(self):
        udh_release_output_dir = self.conf["udh_release_output_dir"]
        self.release_prj_dir = os.path.join(udh_release_output_dir, os.path.basename(PRJDIR))
        #初始化发布目录，安装pigz
        if os.path.exists(udh_release_output_dir):
            logger.info(f"rmtree udh_release_output_dir {udh_release_output_dir}")
            shutil.rmtree(udh_release_output_dir, ignore_errors=True)
        os.makedirs(udh_release_output_dir)
        pigz_installer = PigzInstaller(PIGZ_SOURC_CODE_PATH, PRJ_BIN_DIR)
        pigz_installer.install()

    def get_compiled_packages(self, comp):
        #搜索bigtop项目的编译的输出目录，获取编译好的某个组件的rpm 包的路径
        pkg_dir = os.path.join(self.conf["bigtop"]["prj_dir"], f"output/{comp}")
        logger.info(f"package bigdata rpms pkg_dir:{pkg_dir} comp:{comp}")
        filepaths = glob.glob(os.path.join(pkg_dir, "**", "*.rpm"), recursive=True)
        non_src_filepaths = [fp for fp in filepaths if not fp.endswith("src.rpm")]
        return non_src_filepaths

    def package_bigdata_rpms(self):
        #1.初始化存放所有rpms 的目录udh_rpms
        rpm_dir_name = os.path.basename(UDH_RPMS_PATH).split(".")[0]
        bigdata_rpm_dir = os.path.join(self.release_prj_dir, PKG_RELATIVE_PATH, rpm_dir_name)
        if os.path.exists(bigdata_rpm_dir):
            logger.info(f"rmtree bigdata_rpm_dir {bigdata_rpm_dir}")
            shutil.rmtree(bigdata_rpm_dir, ignore_errors=True)
        os.makedirs(bigdata_rpm_dir)

        #2.对于所有组件创建对应的组件目录，并且把编译好的rpm 复制到对应目录
        for comp in ALL_COMPONENTS:
            comp_dir = os.path.join(bigdata_rpm_dir, comp)
            if not os.path.exists(comp_dir):
                os.makedirs(comp_dir)

            non_src_filepaths = self.get_compiled_packages(comp)

            for filepath in non_src_filepaths:
                dest_path = os.path.join(comp_dir, os.path.basename(filepath))
                shutil.copy(filepath, dest_path)
                logger.info(f"copy from {filepath} to {dest_path}")


        #3.对于centos7 需要特殊处理，需要初始化pg10目录，额外拷贝pg10的包过去
        if self.os_type.lower().strip() == "centos" and self.os_version.strip() == "7":
            pg_dir = os.path.join(bigdata_rpm_dir, "pg10")
            pg_rpm_source = self.conf["centos7_pg_10_dir"]
            if not os.path.exists(pg_dir):
                os.makedirs(pg_dir)
            pg_filepaths = glob.glob(os.path.join(pg_rpm_source, "**", "*.rpm"), recursive=True)
            for filepath in pg_filepaths:
                dest_path = os.path.join(pg_dir, os.path.basename(filepath))
                shutil.copy(filepath, dest_path)
                logger.info(f"copy from {filepath} to {dest_path}")

        #4.创建yum 仓库
        res = create_yum_repository(bigdata_rpm_dir)
        if not res:
            raise Exception("create repo failed, check the log")

        #5.把前面所有的安放好的udh_rpms 目录打成一个压缩包
        dest_tar = f"{bigdata_rpm_dir}.tar.gz"
        os.chdir(os.path.join(self.release_prj_dir, PKG_RELATIVE_PATH))
        command = f"tar cf - {os.path.basename(bigdata_rpm_dir)} | {self.pigz_path} -k -5 -p 16 > {dest_tar}"
        returncode = run_shell_command(command, shell=True)
        if returncode == 0:
            shutil.rmtree(bigdata_rpm_dir)
        else:
            logger.error("package rpm failed, check the log")

    def incremental_package(self):
        #增量打包，只重新编译部分组件，其他的包还是用的已经存在的包

        #1.初始化临时目录用来解压存量的包
        udh_release_output_dir = self.conf["udh_release_output_dir"]
        pigz_path = self.pigz_path
        # 创建临时目录并自动清理
        temp_dir = os.path.join(udh_release_output_dir,"release_tmp")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        # with tempfile.TemporaryDirectory(dir=udh_release_output_dir) as temp_dir:
        os.makedirs(temp_dir)
        print(f"临时目录已创建在: {temp_dir}")

        #2.解压存量发布包到临时目录
        command = f" tar -I  {pigz_path} -xf  {self.incremental_release_src_tar} -C {temp_dir}"
        returncode = run_shell_command(command, shell=True)

        #3.获取rpms 压缩包位置，把存量发布包中的udh-rpms.tar.gz 这个存放所有rpm安装包的压缩包解压了
        temp_release_prj_dir = os.path.join(temp_dir, "bigdata-deploy")
        udh_rpms_tar = os.path.join(temp_release_prj_dir, UDH_RPMS_RELATIVE_PATH)
        rpm_dir_name = os.path.basename(UDH_RPMS_PATH).split(".")[0]
        bigdata_rpm_dir = os.path.join(temp_release_prj_dir, PKG_RELATIVE_PATH, rpm_dir_name)
        dir_path = Path(bigdata_rpm_dir)
        udh_rpms_parent_dir = dir_path.parent
        print(f"父目录路径是: {udh_rpms_parent_dir}")
        command = f" tar -I  {pigz_path} -xf  {udh_rpms_tar} -C {udh_rpms_parent_dir}"
        returncode = run_shell_command(command, shell=True)

        # 4.在解压后的 udh-rpms 中删除comp，这些comps 是需要重新编译被增量的部分
        for comp in self.comps:
            comp_dir = os.path.join(bigdata_rpm_dir, comp)
            if os.path.exists(comp_dir):
                shutil.rmtree(comp_dir)
            os.makedirs(comp_dir)

            # 4.1 从 output 中复制对应的增量rpm 到 udh-rpms 中
            non_src_filepaths= self.get_compiled_packages(comp)
            for filepath in non_src_filepaths:
                dest_path = os.path.join(comp_dir, os.path.basename(filepath))
                shutil.copy(filepath, dest_path)
                logger.info(f"copy from {filepath} to {dest_path}")

        # 5.压缩 udh-rpms
        dest_tar = f"{bigdata_rpm_dir}.tar.gz"
        os.chdir(os.path.join(temp_release_prj_dir, PKG_RELATIVE_PATH))
        command = f"tar cf - {os.path.basename(bigdata_rpm_dir)} | {self.pigz_path} -k -5 -p 16 > {dest_tar}"
        returncode = run_shell_command(command, shell=True)
        if returncode == 0:
            # 6.删除 udh-rpms文件夹
            shutil.rmtree(bigdata_rpm_dir)
        else:
            logger.error("package rpm failed, check the log")

    def package(self):


        #0.获取发布目录
        udh_release_output_dir = self.conf["udh_release_output_dir"]
        release_prj_dir = self.release_prj_dir

        #1.删除软连接，拷贝本项目到发布目录
        logger.info(f"packaging: copy {PRJDIR} to {release_prj_dir}")

        playbook_link = os.path.join(PRJDIR,"bin","ansible-playbook")
        if os.path.islink(playbook_link):
            os.remove(playbook_link)
        shutil.copytree(PRJDIR, release_prj_dir)

        # 2. 改变目录到发布目录，并且删除不必要的内容
        os.chdir(release_prj_dir)
        git_dir = os.path.join(release_prj_dir, ".git")
        if os.path.exists(git_dir):
            logger.info(f"remove git dir {git_dir}")
            shutil.rmtree(git_dir)

        conf_dir = os.path.join(release_prj_dir, "conf")
        for filename in os.listdir(conf_dir):
            if not filename.endswith(".template"):
                conf_file = os.path.join(conf_dir, filename)
                if os.path.isfile(conf_file):
                    os.remove(conf_file)
                    logger.info(f"Removed file: {conf_file}")

        portable_ansible_dir = os.path.join(release_prj_dir, "bin/portable-ansible")
        if os.path.exists(portable_ansible_dir):
            logger.info(f"remove portable_ansible dir {portable_ansible_dir}")
            shutil.rmtree(portable_ansible_dir)
        ansible_playbook_link = os.path.join(release_prj_dir, "bin/ansible-playbook")

        if os.path.islink(ansible_playbook_link):
            try:
                # 删除软链接
                os.unlink(ansible_playbook_link)
                logger.info(f"Successfully removed the symlink at {ansible_playbook_link}")
            except OSError as e:
                logger.error(f"Error: {e.filename} - {e.strerror}.")

        if not os.path.exists(os.path.join(udh_release_output_dir, "pigz")):
            shutil.copy(self.pigz_path, os.path.join(udh_release_output_dir, "pigz"))

        #3.如果是增量安装就增量，否则全量
        if len(self.comps) > 0 and len(self.incremental_release_src_tar) > 0:
            self.incremental_package()
        else:
            self.package_bigdata_rpms()

        #4.改变工作目录到发布目录,然后压缩打包发布包
        udh_release_name = self.get_release_name()
        command = f"tar cf - {os.path.basename(PRJDIR)} | {self.pigz_path} -k -5 -p 16 > {udh_release_name}"
        self.executor.execute_command(command, shell=True)
        logger.info(f"UDH Release packaged success, remove {os.path.basename(release_prj_dir)}")
        shutil.rmtree(os.path.basename(release_prj_dir))