Fork of the amazing [Ulauncher](https://github.com/Ulauncher) to show desktop files or executables paths in Ulauncher results.

![](https://i.imgur.com/Mq37K6H.png)

It's based on Ulauncher V5.

## Installation

Debian package is available in [Releases](https://github.com/brunetton/Ulauncher/releases)

## Make

To make a Debian package from sources, use the `ul` script, that calls `build-deb` script (a modified version to suppress signatures)

```bash
git fetch add_executables_paths   # better be on the good branch
apt install dh-python python3-all gobject-introspection python3-distutils-extra
sudo ./ul build-deb "5-with-paths" --deb
```
