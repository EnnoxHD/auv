# Arch Userland Virtualization (AUV)
## Table of contents
- [Arch Userland Virtualization (AUV)](#arch-userland-virtualization-auv)
  - [Table of contents](#table-of-contents)
  - [What is this good for?](#what-is-this-good-for)
    - [Introduction](#introduction)
    - [Example use cases](#example-use-cases)
  - [Prerequisites](#prerequisites)
  - [How to use](#how-to-use)
    - [Preface](#preface)
    - [Overview](#overview)
    - [Connecting to containers](#connecting-to-containers)
    - [Using the desktop environment of the containers on headless hosts](#using-the-desktop-environment-of-the-containers-on-headless-hosts)
    - [Execution of a shell script at container start](#execution-of-a-shell-script-at-container-start)
    - [Additional arguments for `podman run` when starting a container](#additional-arguments-for-podman-run-when-starting-a-container)
## What is this good for?
### Introduction
This project allows creating highly customizable Arch Linux [Podman](https://github.com/containers/podman) images based on the [official Arch Linux Docker image](https://hub.docker.com/_/archlinux/).

Automatic installation of packages during building utilizes [pacman](https://wiki.archlinux.org/title/pacman) and [aurman](https://github.com/polygamma/aurman) with the supported "package sources" being:
- [Official Arch Linux packages](https://archlinux.org/packages/) (installed via pacman)
- [Chaotic-AUR](https://archlinux.pkgs.org/rolling/chaotic-aur-x86_64/) (installed via pacman)
- [Arch User Repository](https://aur.archlinux.org/packages) (installed via aurman)

Images will also contain:
- [Xfce4 desktop environment](https://www.xfce.org/)
- [LightDM display manager](https://github.com/canonical/lightdm) (in general not needed, but may be used to spawn Xfce4 on hosts without desktop environment)
- [X2Go server](https://wiki.x2go.org/doku.php) (allows connecting graphically to containers utilizing Xfce4)
- [OpenSSH server](https://github.com/openssh/openssh-portable) (allows connecting to containers)

Some more features are:
- A Python helper script, which allows intuitive and easy usage of this project
- The Python helper may be used from command-line only, see e.g. the [GitHub workflow](https://github.com/polygamma/auv/blob/main/.github/workflows/main.yml) of this project
- Images may be imported and exported as a single file via the Python helper
- [systemd services](https://www.freedesktop.org/software/systemd/man/systemd.service.html) for automatic starting of containers may be created via the Python helper
- [Xhost](https://wiki.archlinux.org/title/Xhost) may be executed via the Python helper to grant containers access to the X screen of the host
- Automatic fetching of fastest [pacman mirrors](https://wiki.archlinux.org/title/mirrors) during building
- Some [makepkg optimizations](https://wiki.archlinux.org/title/makepkg#Tips_and_tricks) for the aurman package installation
- Scripting capabilities for containers are available via a shell script that gets executed via a systemd service at container start
- Hot plugging works - this is achieved via [mdev](https://git.busybox.net/busybox/plain/docs/mdev.txt)
- Additional parameters for [podman run](https://docs.podman.io/en/latest/markdown/podman-run.1.html) may be included e.g. to mount stuff into containers
- Podman works inside the containers, so this project may be developed using this project
### Example use cases
#### Consistent environments across different devices
An image built with this project may be distributed to various devices, ensuring a consistent environment across them.
This applies to both development and deployment, allowing development in the exact environment where the software will eventually run.
Switching between images/environments is straightforward using the Python helper's import and export functions.
#### One environment for everything
Since you can include basically anything in an image, the limitation of using this project is your own creativity.
E.g. IDEs, compilers, libraries, browsers, drivers, and more can all be integrated into a single image.
When you switch X2Go to fullscreen or use LightDM, it's nearly imperceptible that you're even working inside a Podman container.
## Prerequisites
- Have [Podman installed](https://podman.io/docs/installation) on a Linux machine
- Have [Python](https://www.python.org/) (version >= 3.7) installed (for the Python helper, which you probably want to use)
## How to use
### Preface
A lot is happening here, even though it may seem otherwise when using the Python helper.
[Containerfile_x86_64](https://github.com/polygamma/auv/blob/main/Containerfile_x86_64) contains the whole build process.
You want to read (and maybe change) the file for a lot of reasons, some of them are:
- Default passwords
- User permissions
- Disabled signature checking
- Keyboard layout (see also [00-keyboard.conf](https://github.com/polygamma/auv/blob/main/containerfiles/00-keyboard.conf))
- Timezone
- mdev default for new devices
- Usage of environment variables given via the Python helper via `podman build --build-arg`
### Overview
- You may want to configure the folder, in which Podman saves stuff: graphroot in [storage.conf](https://github.com/containers/storage/blob/main/docs/containers-storage.conf.5.md)
- You want to edit the [pacman](https://github.com/polygamma/auv/blob/main/software/x86_64/pacman) and [aurman](https://github.com/polygamma/auv/blob/main/software/x86_64/aurman) files to configure the software to be included in the images
- If you need "things" not provided by packages, or if packages require not just installation but also configuration, you should include all of that in [Containerfile_x86_64](https://github.com/polygamma/auv/blob/main/Containerfile_x86_64)
- The Python helper may be executed from the base directory of this project with `python3 src/main.py` and usage should be self-explanatory
- To use the Python helper from the command-line only, look for `if __name__ == "__main__":` in [main.py](https://github.com/polygamma/auv/blob/main/src/main.py).
  The `execution_possibilities` list contains all possible arguments, e.g. `build_image` to build the image.
  E.g. `python3 src/main.py build_image save_image exit_python_helper` would build the image, export it to a file and exit
- To update all packages, just rebuild the image
### Connecting to containers
After having started a container, a x2go connection is available on port `5910` on `localhost`

This implies that an SSH connection is available on the same port, which means if you don't need a graphical interface, you may simply connect to containers via SSH instead of using x2go.

> You may use `ssh pod@127.0.0.1 -p 5910` to connect to a container on the same host

To use x2go, the x2goclient is needed on the client side (the container is the server).

Install instructions are found [here](https://wiki.x2go.org/doku.php/doc:installation:x2goclient).

In short:
*  Arch Linux: `sudo pacman -S x2goclient`
*  Ubuntu: `sudo apt-get install x2goclient`

When creating a session in the x2goclient, the following options in the Session tab need to be set:
*  Login: pod
*  SSH port: `5910`
*  Session type: Custom desktop with the command `/x2go_startup.sh`
*  Host: `localhost`, if you want to connect to containers on the same host, otherwise you need to enter the IP of the device on which a container is running

To circumvent a firewall you may use an [SSH tunnel](https://www.ssh.com/ssh/tunneling/example).
### Using the desktop environment of the containers on headless hosts
On a headless system (system without graphical interface) you may want to use the desktop environment of a container on the host itself, without having to use x2go from another non-headless system.

> On non-headless systems, x2go or ssh should be used to connect to containers, even if a container is running on the same host

A fully configured LightDM (display manager) is ready to be started from within the containers.

> It should be made sure, that the correct graphics drivers are installed and running on the host system.
> Otherwise, the feature may not work as intended or not at all.

When you start LightDM and the desktop environment with it, you will switch automatically to the newly spawned TTY containing that environment.
In order to be able to switch back, you should find out which TTY you are in, before starting LightDM.
Run `sudo fgconsole` to receive the current TTY.
You can switch between TTYs with `sudo chvt X` where `X` is the TTY to switch to.

You can start/stop LightDM (and thus the desktop environment) if you run `sudo systemctl start lightdm` or `sudo systemctl stop lightdm` from within a container.
### Execution of a shell script at container start
You may use the shell script [entrypoint.sh](https://github.com/polygamma/auv/blob/main/src/entrypoint.sh) to include commands to be executed automatically when a container starts.
The script is automatically available in containers at `/entrypoint.sh` and is being executed by a systemd service `entrypoint.service`

> You may use `systemctl status entrypoint.service` (from within a container) to get information about the service

> You **do not** have to rebuild the image after changing entrypoint.sh
### Additional arguments for `podman run` when starting a container
See the [official documentation](http://docs.podman.io/en/latest/markdown/podman-run.1.html) for possible arguments.
To set the arguments, one has to write them into the [args.json](https://github.com/polygamma/auv/blob/main/src/args.json) file.
All arguments have to be `,` separated between square brackets `[]` enclosed in quotation marks `""`

> The user to be used in the containers is pod, which sets the home folder to `/home/pod`

Keep in mind, that **shutting down containers resets everything inside it to the state of the base image**, so you want to think about what you need to have persistent, e.g. settings of applications.
Mount the folders and files you need to have persistent into containers via `--volume` arguments.
See [XDG Base Directory specifications](https://wiki.archlinux.org/index.php/XDG_Base_Directory) for common folders you may want to have persistent.

To cover a lot of cases with one `--volume` argument, you may want to let the whole home folder of the pod user reside on your host system.
An example on how to mount the home folder of the pod user into a container together with a folder named "code":
```json
[
  "--volume=/home/user-on-host/home_pod:/home/pod",
  "--volume=/home/user-on-host/code:/home/pod/code"
]
```
> The Python helper is going to rewrite the args.json file in case of correct syntax, but with an optimal formatting, without changing the content of what you wrote

> You **do not** have to rebuild the image after changing args.json

> You **have to** `Create and install systemd service file` again with the Python helper, after changing args.json if you want to include those changes in the systemd service file
