
{ pkgs }: {
  deps = [
    pkgs.python3
    pkgs.python3Packages.gunicorn
    pkgs.postgresql
    pkgs.openssl
  ];
}
