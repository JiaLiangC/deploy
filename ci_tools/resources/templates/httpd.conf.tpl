
ServerRoot "/etc/httpd"

#Listen 12.34.56.78:80
Listen 8881
Include conf.modules.d/*.conf

User apache
Group apache

ServerAdmin root@localhost

<Directory />
    AllowOverride none
    Require all granted
</Directory>

DocumentRoot "{{udh_local_repo_path}}"

<IfModule alias_module>
    Alias /repository/yum/udh3 "{{udh_local_repo_path}}"
</IfModule>

<Directory "{{udh_local_repo_path}}">
    Options Indexes FollowSymLinks
    AllowOverride None
    # Allow open access:
    Require all granted
    allow from all
    IndexOptions FancyIndexing FoldersFirst NameWidth=* DescriptionWidth=* SuppressHTMLPreamble HTMLTable
    IndexOptions Charset=utf-8 IconHeight=16 IconWidth=16 SuppressRules
    IndexIgnore web header.html footer.html actions defects
    HeaderName /web/header.html
    ReadmeName /web/footer.html
    IndexOrderDefault Ascending Date
    ServerSignature Off
</Directory>


<IfModule dir_module>
    DirectoryIndex index.html
</IfModule>

ErrorLog "logs/error_log"
LogLevel warn

<IfModule log_config_module>
    LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
    LogFormat "%h %l %u %t \"%r\" %>s %b" common

    <IfModule logio_module>
      # You need to enable mod_logio.c to use %I and %O
      LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\" %I %O" combinedio
    </IfModule>
    #CustomLog "logs/access_log" common
    CustomLog "logs/access_log" combined
</IfModule>



<IfModule mime_module>
    TypesConfig /etc/mime.types
    AddType application/x-compress .Z
    AddType application/x-gzip .gz .tgz
    AddType text/html .shtml
    AddOutputFilter INCLUDES .shtml
</IfModule>


AddDefaultCharset UTF-8

<IfModule mime_magic_module>
    MIMEMagicFile conf/magic
</IfModule>

#EnableMMAP off
EnableSendfile on

IncludeOptional conf.d/*.conf