{pkgs}: {
  deps = [
    pkgs.python312Packages.deep-translator
    pkgs.freetype
    pkgs.glibcLocales
    pkgs.postgresql
    pkgs.openssl
  ];
}
