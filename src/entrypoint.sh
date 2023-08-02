#!/bin/bash

# If you want to run a graphical program, make sure to use 'Enable Xhost' in the Python helper
# This will allow the container to connect to the X server of the host

# Get DISPLAY environment variable that was used during building of the image
# This is needed for graphical programs, but no harm is done when executing this for non-graphical programs
. /etc/profile.d/display.sh

# Uncomment to wait until the display is ready:
# until xdpyinfo &>/dev/null; do :; done

# Example command to show whether or not OpenGL is working:
# while true; do glxgears; done

# Enter your own commands to be executed when the container starts:
