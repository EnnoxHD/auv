# Arch Userland Virtualization (AUV)
## What is this good for?
This project allows to create highly customizable Arch Linux [Podman](https://github.com/containers/podman) images based on the [official Arch Linux Docker image](https://hub.docker.com/_/archlinux/).
E.g. can the user configure packages which will be automatically installed during building of the image.
Installation is done using [pacman](https://wiki.archlinux.org/title/pacman) and [aurman](https://github.com/polygamma/aurman) with the supported "package sources" being:
- [Official Arch Linux packages](https://archlinux.org/packages/) (installed via pacman)
- [Chaotic-AUR](https://aur.chaotic.cx/) (installed via pacman)
- [Arch User Repository](https://aur.archlinux.org/packages) (installed via aurman)

The resulting images will also contain:
- [Xfce4 desktop environment](https://www.xfce.org/)
- [LightDM display manager](https://github.com/canonical/lightdm) (in general not needed, but can be used to spawn Xfce4 on hosts without desktop environment)
- [X2Go server](https://wiki.x2go.org/doku.php) (allows to graphically connect into containers utilizing Xfce4)
- [OpenSSH server](https://github.com/openssh/openssh-portable) (allows to connect into containers)

Some features:
- Python helper script, which allows intuitive and easy usage of this project
- The Python helper can also be used from commandline only, see e.g. the GitHub workflow of this project
- Built images can be imported and exported using the Python helper
- [systemd services](https://www.freedesktop.org/software/systemd/man/systemd.service.html) for automatic starting of containers can be created using the Python helper
- [Xhost](https://wiki.archlinux.org/title/Xhost) can be executed using the Python helper to grant containers access to the X screen of the host
- Automatic fetching of fastest [pacman mirrors](https://wiki.archlinux.org/title/mirrors) during building
- Some [makepkg optimizations](https://wiki.archlinux.org/title/makepkg#Tips_and_tricks) for aurman package installation
- Scripting capabilities for containers are available via a shell script that gets executed via a systemd service at container start
- USB hot plugging works, this is achieved via [mdev](https://git.busybox.net/busybox/plain/docs/mdev.txt)
- Additional parameters for [podman run](https://docs.podman.io/en/latest/markdown/podman-run.1.html) may be included e.g. to mount stuff into containers
- Podman works inside the containers, so this project can be developed using this project
## Prerequisites
- Have [Podman installed](https://podman.io/docs/installation) on a Linux machine.
- Have [Python](https://www.python.org/) (at least 3.7) installed (for the Python helper, which you probably want to use).
## Preface
A lot is happening here, even though it may seem otherwise when using the Python helper.
The [Containerfile_x86_64](https://github.com/polygamma/auv/blob/main/Containerfile_x86_64) file contains the whole build process.
You want to read (and change) it for a lot of reasons, some of them are:
- Default passwords
- User permissions
- Disabled signature checking
- Keyboard layout (see also [00-keyboard.conf](https://github.com/polygamma/auv/blob/main/containerfiles/00-keyboard.conf))
- Timezone
- mdev default for new devices
- Usage of environment variables given via the Python helper via `podman build --build-arg`
## How to use
### Overview
- You may want to configure the folder, in which Podman saves stuff: graphroot in [storage.conf](https://github.com/containers/storage/blob/main/docs/containers-storage.conf.5.md)
- You want to edit the [pacman](https://github.com/polygamma/auv/blob/main/software/x86_64/pacman) and [aurman](https://github.com/polygamma/auv/blob/main/software/x86_64/aurman) files to configure the software you want in your built image
- The Python helper can be executed from the base directory of this project with `python3 src/main.py` and usage should be self-explanatory
- To use the Python helper from the commandline, look for `if __name__ == '__main__':` in [main.py](https://github.com/polygamma/auv/blob/main/src/main.py).
  The `execution_possibilities` list contains all possible arguments, e.g. `build_image` to build the image.
  So `python3 src/main.py build_image save_image` would build the image and export it afterward to a file
- To update all packages, just rebuild the image
### Connecting into containers
After having started a container, a x2go connection is available at port `5910` on `localhost`.

This implies that an SSH connection is also available on the same port, which means if you don't need a graphical interface you may simply connect to the container via SSH instead of using x2go.

> You may use `ssh pod@127.0.0.1 -p 5910` to connect to a container on the same host

To use x2go, the x2goclient is needed on the client side (the container is the server).

Install instructions are found [here](https://wiki.x2go.org/doku.php/doc:installation:x2goclient).

In short:
*  Arch Linux: `sudo pacman -S x2goclient`
*  Ubuntu: `sudo apt-get install x2goclient`

When creating a session in the x2goclient, the following options in the `Session` tab need to be set:
*  Login: pod
*  SSH port: `5910`
*  Session type: Custom desktop with the command `/x2go_startup.sh`
*  Host: `localhost`, if you want to connect to a container on the same host, otherwise you need to enter the IP of the device on which the container is running

To circumvent a firewall you may use an [SSH tunnel](https://www.ssh.com/ssh/tunneling/example).
### Using the desktop environment of the container on headless hosts
On a headless system (system without graphical interface) you may want to use the desktop environment of the container on the host itself, without having to use x2go from another non-headless system.

> On non-headless systems should you use x2go or ssh to connect to the running container, even if the container is running on the same host

A fully configured LightDM (display manager) is ready to be started from within a container.

> You should make sure, that the correct graphic drivers are installed and running on the host system.
> Otherwise, the feature may not work as intended or not at all.

When you start LightDM and the desktop environment with it, you will switch automatically to the newly spawned TTY containing that environment.
In order to be able to switch back, you should find out which TTY you are in, before starting LightDM.
Run `sudo fgconsole` to receive the current TTY.
You can switch between TTYs with `sudo chvt X` where `X` is the TTY to switch to.

You can start/stop LightDM (and thus the desktop environment) if you run `sudo systemctl start lightdm` or `sudo systemctl stop lightdm` from within the Podman container.
### Execution of a shell script at container start
You may use the shell script [entrypoint.sh](https://github.com/polygamma/auv/blob/main/src/entrypoint.sh) to include commands to be automatically executed when a container starts.
The script is automatically available in the container at `/entrypoint.sh` and is being executed by a systemd service called `entrypoint.service`

> You may use `systemctl status entrypoint.service` (from within the container) to get information about the service

> You **do not** have to rebuild the image after changing entrypoint.sh
### Additional arguments for `podman run` when starting a container
See the [official documentation](http://docs.podman.io/en/latest/markdown/podman-run.1.html) for possible arguments.
To set the arguments, one has to write them into the [args.json](https://github.com/polygamma/auv/blob/main/src/args.json) file.
All arguments have to be `,` separated between square brackets `[]` enclosed in quotation marks `""`

> The user to be used in the container is pod, which sets the home folder to `/home/pod`

Keep in mind, that **shutting down a container resets everything inside it to the state of the base image**, so you want to think about which things you need to have persistent, e.g. settings of applications.
Mount the folders and files you need to have persistent into the container via `--volume` arguments.
Doing so lets the folders and files reside on your host system instead of the container and thus makes them persistent.

See [XDG Base Directory specifications](https://wiki.archlinux.org/index.php/XDG_Base_Directory) for common folders you may want to have persistent.

To cover a lot of cases with one `--volume` argument, you may want to let the whole home folder of the pod user reside on your host system.
An example on how to mount the home folder of the pod user into the container together with a folder named "code":
```json
[
  "--volume=/home/user-on-host/home_pod:/home/pod",
  "--volume=/home/user-on-host/code:/home/pod/code"
]
```
> The Python helper is going to rewrite the args.json file in case of correct syntax, but with an optimal formatting, without changing the content of what you wrote

> You **do not** have to rebuild the image after changing args.json

> You **have to** `Create and install systemd service file` again with the Python helper, after changing args.json if you want to include those changes in the systemd service file
