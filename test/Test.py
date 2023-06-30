# -*- coding: UTF-8 -*-
import unittest
import re
class InvalidConfigurationException(Exception):
    pass
def parse_config(configurations):
    parsed_configs = []


    for config in configurations:
        if len(config.split())!=3:
            raise InvalidConfigurationException

        if '[' in config:
            hostname_part, ip_part, password = config.split()
            hosts = []
            ips = []
            if '[' in hostname_part:
                match = re.search(r'\[(\d+)-(\d+)]', hostname_part)
                if match:
                    hostname_prefix = hostname_part[:match.start()]
                    hostname_range_start = int(match.group(1))
                    hostname_range_end = int(match.group(2))
                    hostname_suffix = hostname_part[match.end():]

                    for i in range(hostname_range_start, hostname_range_end + 1):
                        host = '{}{}{}'.format(hostname_prefix, i, hostname_suffix)
                        hosts.append(host)
                else:
                    raise InvalidConfigurationException
            if '[' in ip_part:
                match = re.search(r'\[(\d+)-(\d+)]', ip_part)
                if match:
                    ip_prefix = ip_part[:match.start()]
                    ip_range_start = int(match.group(1))
                    ip_range_end = int(match.group(2))
                    ip_suffix = ip_part[match.end():]

                    for i in range(ip_range_start, ip_range_end + 1):
                        ip = '{}{}{}'.format(ip_prefix, i, ip_suffix)
                        ips.append(ip)
            else:
                raise InvalidConfigurationException

            if len(hosts) != len(ips):
                raise InvalidConfigurationException("Configuration is invalid")
            for index,ip in enumerate(ips):
                parsed_configs.append((hosts[index],ip,password))
        else:

            parsed_configs.append(tuple(config.split()))

    return parsed_configs

# Usage
# configs = [
#     "10.1.1.12 hostname password",
#     "10.1.1.13 hostname2 password2",
#     "hostname10[1-2] 10.1.1.1[1-2] password",
#     "hostname[1-2]2 10.1.1.1[1-2] password",
#     "[1-2]hostname3 10.1[1-2].1.1 password"
# ]
#
# parsed = parse_config(configs)
# for config in parsed:
#     print(config)  # 将解析的配置打印出来
#
class TestConfigParser(unittest.TestCase):

    def test_parse_config(self):
        # 测试常规case
        configs = [
            "10.1.1.12 hostname password",
            "10.1.1.13 hostname2 password2",
            "hostname10[1-2] 10.1.1.1[1-2] password",
            "hostname[1-2]2 10.1.1.1[1-2] password",
            "[1-2]hostname3 10.1[1-2].1.1 password"
        ]
        expected_output = [
            ('10.1.1.12', 'hostname', 'password'),
            ('10.1.1.13', 'hostname2', 'password2'),
            ('hostname101', '10.1.1.11', 'password'),
            ('hostname102', '10.1.1.12', 'password'),
            ('hostname12', '10.1.1.11', 'password'),
            ('hostname22', '10.1.1.12', 'password'),
            ('1hostname3', '10.11.1.1', 'password'),
            ('2hostname3', '10.12.1.1', 'password'),
        ]
        self.assertItemsEqual(parse_config(configs), expected_output)

        # 测试当主机名和IP都没有范围的情况
        no_range_config = ["10.1.1.1 hostname password"]
        self.assertItemsEqual(parse_config(no_range_config), [('10.1.1.1', 'hostname', 'password')])

        # 测试当范围只在主机名的情况,报错
        hostname_range_config = ["hostname[1-3] 10.1.1.1 password"]
        with self.assertRaises(Exception):
            parse_config(hostname_range_config)

        # 配置字符串格式不正确的异常情报
        with self.assertRaises(Exception):
            parse_config(["10.1.1.1 hostname"])

        # 测试范围格式不正确的异常情况
        with self.assertRaises(Exception):
            parse_config(["hostname[1;2] 10.1.1.1 password"])


if __name__ == '__main__':
    unittest.main()
