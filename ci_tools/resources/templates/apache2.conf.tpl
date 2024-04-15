
Listen 8881

<Directory />
    AllowOverride none
    Require all granted
</Directory>

DocumentRoot {{udh_local_repo_path}}

<IfModule alias_module>
    Alias /repository/apt/udh3 {{udh_local_repo_path}}
</IfModule>

<Directory {{udh_local_repo_path}}>
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

#EnableMMAP off
EnableSendfile on