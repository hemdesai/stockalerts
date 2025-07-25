{ pkgs }: {
    deps = [
        pkgs.python311
        pkgs.python311Packages.pip
        pkgs.postgresql_15
        pkgs.glibcLocales
    ];
    
    env = {
        PYTHONBIN = "${pkgs.python311}/bin/python3.11";
        LANG = "en_US.UTF-8";
        PIP_DEFAULT_TIMEOUT = "100";
    };
}