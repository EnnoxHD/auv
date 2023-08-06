from collections.abc import Sequence
from enum import Enum
from functools import partial
from json import loads, dumps, JSONDecodeError
from os import getuid, getgid
from os.path import abspath, dirname, pardir
from os.path import join as os_join
from platform import machine
from re import compile, match, split
from shlex import quote as shlex_quote
from shutil import get_terminal_size
from subprocess import run, CompletedProcess, PIPE, STDOUT
from sys import exit, argv, stdout, stdin
from termios import tcgetattr, tcsetattr, ECHO, ICANON, TCSAFLUSH
from threading import Thread
from typing import Any


def script_dir() -> str:
    """
    Returns the directory of this script as absolute path

    :return: The absolute path of the directory of this script
    """
    return dirname(abspath(__file__))


def repo_base_dir() -> str:
    """
    Returns the base directory of this git repository as absolute path

    :return: The absolute path of the base directory of this git repository
    """
    return abspath(os_join(script_dir(), pardir))


class Colors:
    """
    Class used for colored output
    """

    @staticmethod
    def concat_str(*args: Any) -> str:
        """
        Concatenates objects via the str() function on every object to return a string

        :param args:    The arguments to concatenate
        :return:        The concatenated objects as string
        """
        return "".join([str(arg) for arg in args])

    @staticmethod
    def red(*x: Any) -> str: return Colors.concat_str("\033[31m", *x, "\033[39m")

    @staticmethod
    def cyan(*x: Any) -> str: return Colors.concat_str("\033[36m", *x, "\033[39m")

    @staticmethod
    def light_green(*x: Any) -> str: return Colors.concat_str("\033[92m", *x, "\033[39m")

    @staticmethod
    def light_yellow(*x: Any) -> str: return Colors.concat_str("\033[93m", *x, "\033[39m")

    @staticmethod
    def light_magenta(*x: Any) -> str: return Colors.concat_str("\033[95m", *x, "\033[39m")

    @staticmethod
    def light_cyan(*x: Any) -> str: return Colors.concat_str("\033[96m", *x, "\033[39m")

    @staticmethod
    def bold(*x: Any) -> str: return Colors.concat_str("\033[1m", *x, "\033[22m")

    @staticmethod
    def invert(*x: Any) -> str: return Colors.concat_str("\033[7m", *x, "\033[27m")


class Terminal:
    """
    Class used for terminal manipulation
    """

    @staticmethod
    def print_plain(string: str):
        """
        Print the given string without an end string

        :param string:  The string to print
        """
        print(string, end="")

    @staticmethod
    def clear(include_buffer: bool = False):
        """
        Clears the terminal and optionally preserves the scroll buffer

        :param include_buffer:  Whether to also clear the scroll buffer or not
        """
        if include_buffer:
            # https://en.wikipedia.org/wiki/ANSI_escape_code#Fs_Escape_sequences
            Terminal.print_plain("\033c")
        else:
            # https://en.wikipedia.org/wiki/ANSI_escape_code#CSI_(Control_Sequence_Introducer)_sequences
            Terminal.print_plain("\033[2J")
            Terminal.cursor_set_position((1, 1))

    @staticmethod
    def size() -> tuple[int, int]:
        """
        Evaluates the current size of the terminal

        :return:    The terminal size as tuple (width/columns, height/rows)
        """
        size = get_terminal_size()
        return size.columns, size.lines

    @staticmethod
    def cursor_get_position() -> tuple[int, int]:
        """
        Retrieves the current position of the cursor in the terminal

        :return:    The current position of the cursor as tuple (column, row)
        """
        # https://en.wikipedia.org/wiki/ANSI_escape_code#CSI_(Control_Sequence_Introducer)_sequences
        # https://stackoverflow.com/a/69582478
        old_stdin_mode = tcgetattr(stdin)

        new_stdin_mode = tcgetattr(stdin)
        new_stdin_mode[3] = new_stdin_mode[3] & ~(ECHO | ICANON)
        tcsetattr(stdin, TCSAFLUSH, new_stdin_mode)

        try:
            stdout.write("\033[6n")
            stdout.flush()
            device_status_report = ""
            while not device_status_report.endswith("R"):
                device_status_report += stdin.read(1)
            position = match(r".*\[(?P<row>\d*);(?P<column>\d*)R", device_status_report)
        finally:
            tcsetattr(stdin, TCSAFLUSH, old_stdin_mode)

        current_position = (1, 1)
        if position:
            current_position = (int(position.group("column")), int(position.group("row")))
        return current_position

    @staticmethod
    def calculate_row_offset(initial_position: tuple[int, int], additional_rows: int = 0) -> int:
        """
        Calculates the offset from an initial position to accommodate for additional rows,
        especially if the initial position is near or at maximum height in the terminal

        :param initial_position:    The initial position of the cursor as tuple (column, row)
        :param additional_rows:     The number of rows added after the initial position
        :return:                    The number of rows
        """
        terminal_size_rows = Terminal.size()[1]
        initial_row = initial_position[1]
        new_row = initial_row + additional_rows
        num_of_rows = 0
        if new_row > terminal_size_rows:
            num_of_rows = terminal_size_rows - new_row
        return num_of_rows

    @staticmethod
    def cursor_set_position(position: tuple[int, int], row_offset: int = 0):
        """
        Sets the cursor to the given position inside the terminal

        :param position:    The cursor position to move the cursor to as tuple (column, row)
        :param row_offset:  Offset to accommodate for new rows, e.g. printed lines after the input
        """
        # https://en.wikipedia.org/wiki/ANSI_escape_code#CSI_(Control_Sequence_Introducer)_sequences
        column = position[0]
        if column <= 0:
            column = 1

        row = position[1]
        if row <= 0:
            row = 1

        Terminal.print_plain(f"\033[{row + row_offset};{column}H")

    @staticmethod
    def cursor_back(steps: int):
        """
        Moves the cursor in the terminal back

        :param steps:   The number of steps to move the cursor back
        """
        if steps <= 0:
            return
        # https://en.wikipedia.org/wiki/ANSI_escape_code#CSI_(Control_Sequence_Introducer)_sequences
        Terminal.print_plain(f"\033[{steps}D")

    @staticmethod
    def len_on_display(string: str) -> int:
        """
        Calculates the displayable length of a string, excluding ANSI escape codes

        :param string:  A string whose length is to be calculated
        :return:        The length of the string, excluding ANSI escape codes
        """
        # https://en.wikipedia.org/wiki/ANSI_escape_code#Description
        # https://stackoverflow.com/a/14693789
        ansi_escape_codes = compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        displayable_string = ansi_escape_codes.sub("", string)
        return len(displayable_string)

    @staticmethod
    def cut(string: str, excess: int, insert_end="") -> str:
        """
        Cuts a string to length preserving all ansi control characters in it

        :param string:      The string to cut to length
        :param excess:      Number of visible characters getting cut off
        :param insert_end:  Inserts the string at the end of the visible characters,
                            ansi control characters may follow, it has no impact on length calculation
        :return:            The string cut to length including all ansi control characters
        """
        # https://en.wikipedia.org/wiki/ANSI_escape_code#Description
        # https://stackoverflow.com/a/14693789
        ansi_escape_codes = r"(\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]))"
        splitted = split(ansi_escape_codes, string)
        cut_string_parts = []
        target_len = Terminal.len_on_display(string) - excess
        current_len = 0
        for part in splitted:
            part_len = Terminal.len_on_display(part)
            if part_len == 0:
                cut_string_parts.append(part)
            else:
                if current_len == target_len:
                    continue
                new_len = current_len + part_len
                if new_len <= target_len:
                    cut_string_parts.append(part)
                    current_len = new_len
                    if new_len == target_len:
                        cut_string_parts.append(insert_end)
                else:
                    cut_part = part[: -current_len + target_len]
                    cut_string_parts.append(cut_part)
                    current_len = current_len + Terminal.len_on_display(cut_part)
                    cut_string_parts.append(insert_end)
        return "".join(cut_string_parts)

    @staticmethod
    def ellipsify(string: str, length: int, preserve: bool = False) -> str:
        """
        Potentially caps a string at a certain length and includes an ellipsis

        :param string:      The string to check and potentially modify
        :param length:      The length limitation for the string representation
        :param preserve:    Do not strip the string and preserve the input as is
        :return:            The capped string with an ellipsis
        """
        if length <= 0:
            return ""

        if not preserve:
            string = string.strip()

        string_len = Terminal.len_on_display(string)
        if string_len <= length:
            return string

        ellipsis = "..."
        ellipsis_len = len(ellipsis)
        if ellipsis_len >= length:
            return ellipsis[ellipsis_len - length:]

        overshoot = string_len - length + ellipsis_len
        return Terminal.cut(string, overshoot, insert_end=ellipsis)

    @staticmethod
    def header(string: str):
        """
        Prints a header line in the terminal for the given string

        :param string:  The string to use inside the header
        """
        # https://en.m.wikipedia.org/wiki/Box-drawing_character#Box_Drawing
        decoration = ("\u250f", "\u252b", " ", " ", "\u2523", "\u2513")
        line = "\u2501"

        width = Terminal.size()[0]
        remaining_width = width - len(decoration)

        string = Terminal.ellipsify(string.strip(), remaining_width)

        remaining_width -= Terminal.len_on_display(string)
        remaining_width_half = remaining_width // 2

        to_print = decoration[0]
        to_print += line * remaining_width_half
        to_print += decoration[1]
        to_print += Colors.invert(decoration[2] + Colors.bold(string) + decoration[3])
        to_print += decoration[4]
        to_print += line * (remaining_width - remaining_width_half)
        to_print += decoration[5]
        print(to_print)

    @staticmethod
    def content(string: str = "", as_input: bool = False):
        """
        Prints a line of content in the terminal for the given string

        :param string:      The string to use inside the content line
        :param as_input:    Resets the cursor position after printing the decoration
        """
        # https://en.m.wikipedia.org/wiki/Box-drawing_character#Box_Drawing
        decoration = ("\u2503", " ", " ", "\u2503")
        space = " "

        width = Terminal.size()[0]
        remaining_width = width - len(decoration)

        if string.startswith("\n"):
            Terminal.content()

        string = Terminal.ellipsify(string, remaining_width, preserve=as_input)

        remaining_width -= Terminal.len_on_display(string)

        to_print = decoration[0] + decoration[1]
        to_print += string + space * remaining_width
        to_print += decoration[2] + decoration[3]
        if as_input:
            Terminal.print_plain(to_print)
            Terminal.cursor_back(remaining_width + 1)
        else:
            print(to_print)

    @staticmethod
    def divider():
        """
        Prints a simple divider in the terminal
        """
        # https://en.m.wikipedia.org/wiki/Box-drawing_character#Box_Drawing
        decoration = ("\u2520", "\u2528")
        line = "\u2500"

        width = Terminal.size()[0]
        remaining_width = width - len(decoration)

        to_print = decoration[0]
        to_print += line * remaining_width
        to_print += decoration[1]
        print(to_print)

    @staticmethod
    def footer():
        """
        Prints a simple footer in the terminal
        """
        # https://en.m.wikipedia.org/wiki/Box-drawing_character#Box_Drawing
        decoration = ("\u2517", "\u251B")
        line = "\u2501"

        width = Terminal.size()[0]
        remaining_width = width - len(decoration)

        to_print = decoration[0]
        to_print += line * remaining_width
        to_print += decoration[1]
        print(to_print)


# https://stackoverflow.com/a/40339397
class Printing(Enum):
    """
    Enum class defining printing styles
    """
    NO = partial(lambda *args: None)
    STANDARD = partial(print)
    MENU = partial(Terminal.content)

    def __call__(self, *args):
        self.value(*args)


def print_and_input(input_message: str, *prints_before_input: str):
    for print_before_input in prints_before_input:
        print(print_before_input)
    input(input_message)


def podman_message(string: str, new_line: bool, printing: Printing, color: Any, string_begin: str) -> str:
    """
    Generates a podman message of the following form: "color(string_begin) string"

    :param string:          The string for the message
    :param new_line:        Whether to start the message with a newline or not
    :param printing:        If the generated message should be printed and if so is it in a menu
    :param color:           The color of the Colors class to be used
    :param string_begin:    The string to be colored with the color parameter at the beginning of the message
    :return:                The generated message
    """
    to_return = "\n" if new_line else "" + f"{color(string_begin)} {string}"
    printing(to_return)
    return to_return


def podman_status(string: str, new_line: bool = False, printing: Printing = Printing.STANDARD) -> str:
    """
    Generates a podman status of the following form: "Light green(~~) string"

    :param string:      The string for the status message
    :param new_line:    Whether to start the status with a newline or not
    :param printing:    If the generated status should be printed and if so is it in a menu
    :return:            The generated status
    """
    return podman_message(string, new_line, printing, Colors.light_green, "~~")


def podman_error(string: str, new_line: bool = False, printing: Printing = Printing.STANDARD) -> str:
    """
    Generates a podman error of the following form: "Red(!!) string"

    :param string:      The string for the error message
    :param new_line:    Whether to start the error with a newline or not
    :param printing:    If the generated error should be printed and if so is it in a menu
    :return:            The generated error
    """
    return podman_message(string, new_line, printing, Colors.red, "!!")


def podman_note(string: str, new_line: bool = False, printing: Printing = Printing.STANDARD) -> str:
    """
    Generates a podman note of the following form: "Light cyan(::) string"

    :param string:      The string for the note message
    :param new_line:    Whether to start the note with a newline or not
    :param printing:    If the generated note should be printed and if so is it in a menu
    :return:            The generated note
    """
    return podman_message(string, new_line, printing, Colors.light_cyan, "::")


def podman_question(string: str, new_line: bool = False, printing: Printing = Printing.STANDARD) -> str:
    """
    Generates a podman question of the following form: "Light yellow(??) string"

    :param string:      The string for the question message
    :param new_line:    Whether to start the question with a newline or not
    :param printing:    If the generated question should be printed and if so is it in a menu
    :return:            The generated question
    """
    return podman_message(string, new_line, printing, Colors.light_yellow, "??")


def podman_input(string: str, new_line: bool = False) -> str:
    """
    Generates a podman message to be used with input() of the following form: "Light magenta(++) string"

    :param string:      The string for the input message
    :param new_line:    Whether to start the input message with a newline or not
    :return:            The generated input message
    """
    return podman_message(string, new_line, Printing.NO, Colors.light_magenta, "++")


def run_command(
        command: str, capture_output: bool = False, valid_return_codes: Sequence[int] | None = None,
) -> CompletedProcess:
    """
    Runs a given command in the shell, and may additionally check for valid return codes

    :param command:             The command to run
    :param capture_output:      Set to True, if you want to suppress the output of the command but instead capture it
                                You may retrieve the captured output via the object returned by this function
                                STDOUT and STDERR are going to be combined into STDOUT if you specify True
    :param valid_return_codes:  If you want to raise a RuntimeError in case of an invalid return code,
                                provide a sequence of valid return codes to be checked against
    :return:                    The subprocess.CompletedProcess object of the call
                                See https://docs.python.org/3/library/subprocess.html#subprocess.CompletedProcess
    """
    if capture_output:
        completed = run(command, shell=True, text=True, check=False, stdout=PIPE, stderr=STDOUT)
    else:
        completed = run(command, shell=True, text=True, check=False)

    if valid_return_codes and completed.returncode not in valid_return_codes:
        if capture_output:
            podman_error(f"'{command}' could not be executed correctly:\n   {completed.stdout.strip()}", new_line=True)
        else:
            podman_error(f"'{command}' could not be executed correctly", new_line=True)

        raise RuntimeError

    return completed


class Calls:
    """
    Contains various commands to be used to handle our Podman Image and Container
    """
    # See: https://man7.org/linux/man-pages/man8/findmnt.8.html
    mountInfoArgs = "sudo findmnt --json --all --target {}"

    # See: http://docs.podman.io/en/latest/markdown/podman-info.1.html
    # Calling `podman info` twice, because the first call may fail after changing/removing the graphRoot folder
    podmanInfo = "sudo podman info >/dev/null 2>&1; sudo podman info --format=json"

    # See: http://docs.podman.io/en/latest/markdown/podman.1.html#root-value
    podmanRoot = loads(run_command(podmanInfo, True, valid_return_codes=(0,)).stdout)["store"]["graphRoot"].strip()

    # See: http://docs.podman.io/en/latest/markdown/podman-system-reset.1.html
    podmanReset = "sudo podman system reset --force"

    # See: http://docs.podman.io/en/latest/markdown/podman-system-prune.1.html
    pruneSystem = "sudo podman system prune --force"

    # See: http://docs.podman.io/en/latest/markdown/podman-image-prune.1.html
    pruneImage = "sudo podman image prune --force"

    # See: http://docs.podman.io/en/latest/markdown/podman-rmi.1.html
    rmAUVImage = "sudo podman image rm --force auv"

    # See: http://docs.podman.io/en/latest/markdown/podman-rm.1.html
    rmAUVContainer = "sudo podman container rm --force auv"

    # See: http://docs.podman.io/en/latest/markdown/podman-save.1.html
    saveImageArgs = "sudo podman save --output {} auv:latest"

    # See: http://docs.podman.io/en/latest/markdown/podman-load.1.html
    loadImageArgs = "sudo podman load --input {}"

    # See: https://www.freedesktop.org/software/systemd/man/systemctl.html
    systemdEnable = "sudo systemctl enable container-auv.service"
    systemdDisable = "sudo systemctl disable container-auv.service"
    systemdStarted = "sudo systemctl is-active container-auv.service"
    systemdStart = "sudo systemctl start container-auv.service"
    systemdStop = "sudo systemctl stop container-auv.service"
    systemdReload = "sudo systemctl daemon-reload"

    # See: http://docs.podman.io/en/latest/markdown/podman-generate-systemd.1.html
    serviceFilePath = "/etc/systemd/system/container-auv.service"
    createService = "sudo podman generate systemd --name --new --restart-policy=always auv | " \
                    "sudo tee {} > /dev/null".format(serviceFilePath)

    # See: http://docs.podman.io/en/latest/markdown/podman-inspect.1.html
    containerRunning = "sudo podman container inspect auv"

    # See: https://wiki.archlinux.org/index.php/Xhost
    xhostFilePath = "/etc/profile.d/xhost.sh"
    xhostEnableStart = "sudo cp --force {} {} && sudo chmod 555 {} && . {}" \
                       "".format(os_join(script_dir(), "xhost.sh"), xhostFilePath, xhostFilePath, xhostFilePath)
    xhostDisableStop = f"sudo rm --force {xhostFilePath}"

    # See: http://docs.podman.io/en/latest/markdown/podman-build.1.html
    buildImage = "sudo TMPDIR={} podman build --force-rm --no-cache --pull=always --tag auv:latest " \
                 "--build-arg UID={} --build-arg GID={} --build-arg DISPLAY=$DISPLAY " \
                 "-f Containerfile_{} {}".format(podmanRoot, getuid(), getgid(), machine(), repo_base_dir())

    # See: http://docs.podman.io/en/latest/markdown/podman-run.1.html
    startContainerArgs = "sudo podman run -i -t --rm --name auv --privileged --network='host' --ipc='host' " \
                         "--systemd='true' --volume={}:/entrypoint.sh --volume=/lib/modules:/lib/modules:ro " \
                         "{} auv:latest".format(os_join(script_dir(), "entrypoint.sh"), "{}")

    # See: http://docs.podman.io/en/latest/markdown/podman-create.1.html
    createContainerArgs = "sudo podman create -t --rm --name auv --privileged --network='host' --ipc='host' " \
                          "--systemd='true' --volume={}:/entrypoint.sh --volume=/lib/modules:/lib/modules:ro " \
                          "{} auv:latest".format(os_join(script_dir(), "entrypoint.sh"), "{}")


def acquire_sudo():
    """
    Sudo loop since we want sudo forever
    """

    def _sudo_loop():
        import time

        while True:
            run(["sudo", "--non-interactive", "-v"])
            time.sleep(60)

    if run(["sudo", "-v"]).returncode != 0:
        exit("--- EXITING - acquire sudo failed - EXITING ---")

    t = Thread(target=_sudo_loop)
    t.daemon = True
    t.start()


def args_from_file(file: str) -> list[str]:
    """
    Reads arguments to be provided to the Podman run call from a file in the JSON format.
    The file has to contain exactly one list, containing the arguments to be provided as strings.
    Notice: If the file contains valid arguments, file will be overridden with the read arguments but formatted nicely.

    :param file:    The JSON file to read from
    :return:        The list containing the arguments read from the file
    """
    with open(file) as f:
        read_args = loads(f.read())

    if not isinstance(read_args, list):
        raise ValueError(f"{read_args} is not a list")

    for argument in read_args:
        if not isinstance(argument, str):
            raise ValueError(f"{argument} is not a string")

    with open(file, "w") as f:
        f.write(dumps(read_args, indent=4))

    return read_args


def prune():
    """
    Calls various prune functions of Podman to clear our environment from unneeded stuff
    """
    run_command(Calls.pruneSystem, True, valid_return_codes=(0,))
    run_command(Calls.pruneImage, True, valid_return_codes=(0,))


def clear_before_building_or_after_failed_building():
    """
    Clears the Podman environment before building the image or after a failed build attempt
    """
    run_command(Calls.rmAUVImage, True, valid_return_codes=(0, 1, 2))
    prune()


def clear_after_building_or_before_starting():
    """
    Clears the Podman environment after building the image or before starting a container
    """
    run_command(Calls.rmAUVContainer, True, valid_return_codes=(0, 1, 2))
    prune()


def build_image(exec_from_cmd: bool):
    """
    Builds the Podman image
    If the function is called from the command line, building won't be retried if it fails

    :param exec_from_cmd:   Whether the script is executed from the command line or not
    """
    # Ask user if building should be retried until it succeeds
    podman_question("Do you want to automatically retry building if it fails?")
    podman_note("You may stop building with CTRL+C in that case")
    choice = "n" if exec_from_cmd else ""

    while choice not in ("y", "n"):
        choice = input(podman_input("Enter y for yes and n for no: ")).strip().lower()

    retry = choice in ("y",)

    # Actually start building the image
    try:
        clear_before_building_or_after_failed_building()
        while True:
            if run_command(Calls.buildImage).returncode != 0:
                clear_before_building_or_after_failed_building()

                podman_error(
                    "ERROR: Failed to build the image, take a look at the output to find the problem", new_line=True,
                )

                if not retry:
                    raise RuntimeError
            else:
                clear_after_building_or_before_starting()

                podman_note(
                    "SUCCESS: Image built successfully", new_line=True,
                )

                break
    except KeyboardInterrupt:
        clear_before_building_or_after_failed_building()
        print_and_input(
            podman_input("Press Enter to return to the menu: "),
        )


def prepare_starting() -> str:
    """
    Prepares starting of a container
    :return: The args.json file contents as a string to be used with the Podman run call
    """
    # Read and parse args.json
    try:
        args_from_json = " ".join(args_from_file(os_join(script_dir(), "args.json")))
    except (JSONDecodeError, OSError, ValueError) as e:
        error_type = type(e).__name__
        podman_error(f"{error_type} while parsing args.json: {e}", new_line=True)
        raise RuntimeError from e

    # Clean environment
    clear_after_building_or_before_starting()

    return args_from_json


def start_container(exec_from_cmd: bool):
    """
    Starts a Podman container
    """
    run_command(Calls.startContainerArgs.format(prepare_starting()))


def save_image(exec_from_cmd: bool):
    """
    Saves the currently built Podman image with the name `auv` and the tag `latest` to a .tar archive
    If the function is called from the command line, the image will be saved to the base directory of this project

    :param exec_from_cmd:   Whether the script is executed from the command line or not
    """
    if exec_from_cmd:
        path_to_save = abspath(os_join(repo_base_dir(), "auv_latest.tar"))
    else:
        path_to_save = abspath(os_join(input(podman_input(
            "Enter the path to an existing folder to save the image in: ",
        )).strip(), "auv_latest.tar"))

    podman_question(f"Do you want to save the image auv:latest to {path_to_save} ?")
    choice = "y" if exec_from_cmd else ""

    while choice not in ("y", "n"):
        choice = input(podman_input("Enter y for yes and n for no: ")).strip().lower()

    if choice in ("n",):
        return

    if run_command(Calls.saveImageArgs.format(shlex_quote(path_to_save))).returncode == 0:
        run_command(f"sudo chown $USER:$USER {shlex_quote(path_to_save)}", True)
        podman_note(f"SUCCESS: Image auv:latest was successfully saved to {path_to_save}", new_line=True)
    else:
        podman_error(f"ERROR: Image auv:latest could not be saved to {path_to_save}", new_line=True)
        podman_error("       Take a look at the output to find the problem")
        raise RuntimeError


def load_image(exec_from_cmd: bool):
    """
    Loads a Podman image from a .tar archive
    If the function is called from the command line, the image will be loaded from the base directory of this project

    :param exec_from_cmd:   Whether the script is executed from the command line or not
    """
    if exec_from_cmd:
        path_to_load = abspath(os_join(repo_base_dir(), "auv_latest.tar"))
    else:
        path_to_load = abspath(input(podman_input(
            "Enter the path to the .tar archive you want to load as image: ",
        )).strip())

    clear_before_building_or_after_failed_building()
    if run_command(Calls.loadImageArgs.format(shlex_quote(path_to_load))).returncode == 0:
        clear_after_building_or_before_starting()
        podman_note(f"SUCCESS: Image loaded successfully from {path_to_load}", new_line=True)
    else:
        clear_before_building_or_after_failed_building()
        podman_error(f"ERROR: Image could not be loaded from {path_to_load}", new_line=True)
        podman_error("       Take a look at the output to find the problem")
        raise RuntimeError


def print_debug_info(exec_from_cmd: bool):
    """
    Prints debug information about Podman and the version of the Python helper itself
    """
    # See: https://wiki.archlinux.org/index.php/VCS_package_guidelines#Git
    podman_status("The version of the Python helper  is: {}".format(
        run(
            r"""git describe --long --tags --abbrev=7 | sed 's/\([^-]*-g\)/r\1/;s/-/./g'""",
            cwd=repo_base_dir(),
            shell=True, text=True, capture_output=True,
        ).stdout.strip(),
    ), new_line=True)

    podman_status(
        "The currently used Podman info    is:\n{}".format(
            dumps(loads(run_command(Calls.podmanInfo, True).stdout.strip()), indent=4),
        ),
    )

    with open(os_join(script_dir(), "args.json")) as args_json:
        podman_status(
            f"The currently used args.json:\n{args_json.read().strip()}",
        )

    with open(os_join(script_dir(), "entrypoint.sh")) as entrypoint_sh:
        podman_status(
            f"The currently used entrypoint.sh:\n{entrypoint_sh.read().strip()}",
        )

    podman_status(
        "Mount info for graphRoot:\n{}".format(
            dumps(loads(run_command(Calls.mountInfoArgs.format(Calls.podmanRoot), True).stdout.strip()), indent=4),
        ),
    )

    if not exec_from_cmd:
        print_and_input(
            podman_input("Press Enter to return to the menu: "),
        )


def systemd_started() -> bool:
    """
    Checks whether the systemd service is currently started

    :return: Whether the systemd service is currently started
    """
    return run_command(Calls.systemdStarted, True).returncode == 0


def container_running() -> bool:
    """
    Checks whether the container is currently running

    :return: Whether the container is currently running
    """
    return run_command(Calls.containerRunning, True).returncode == 0


def systemd_disable(exec_from_cmd: bool):
    """
    Disables the systemd service of the container
    """
    run_command(Calls.systemdDisable, True, valid_return_codes=(0,))


def systemd_stop():
    """
    Stops the systemd service of the container
    """
    run_command(Calls.systemdStop, True, valid_return_codes=(0,))


def systemd_create(exec_from_cmd: bool):
    """
    Creates and installs the systemd service of the container
    """
    # Create container
    run_command(Calls.createContainerArgs.format(prepare_starting()), True, valid_return_codes=(0,))

    # Create and install our service
    run_command(Calls.createService, True, valid_return_codes=(0,))

    # Reload systemd unit files
    run_command(Calls.systemdReload, True, valid_return_codes=(0,))

    # Remove our created container
    clear_after_building_or_before_starting()


def systemd_enable(exec_from_cmd: bool):
    """
    Enables the systemd service of the container
    """
    run_command(Calls.systemdEnable, True, valid_return_codes=(0,))


def systemd_start(exec_from_cmd: bool):
    """
    Starts the systemd service of the container
    """
    run_command(Calls.systemdStart, True, valid_return_codes=(0,))
    exit()


def xhost_enable_start(exec_from_cmd: bool):
    """
    Enables everyone on localhost to access the X server, which means also our Podman container
    """
    run_command(Calls.xhostEnableStart, True, valid_return_codes=(0,))


def xhost_disable_stop(exec_from_cmd: bool):
    """
    Disables everyone on localhost to access the X server, which means also our Podman container
    """
    run_command(Calls.xhostDisableStop, True, valid_return_codes=(0,))


def podman_reset(exec_from_cmd: bool):
    """
    Resets the Podman environment completely
    """
    try:
        run_command(f"sudo rm -rf {shlex_quote(Calls.podmanRoot)}", True, valid_return_codes=(0,))
        run_command(Calls.podmanReset, True, valid_return_codes=(0,))
    except RuntimeError:
        podman_error("Could not reset the Podman environment, look at the output to find the problem", new_line=True)
        podman_error("Restart your computer and try again")
        exit(1)


def exit_python_helper(exec_from_cmd: bool):
    """
    Exits the Python helper
    """
    exit()


def stop_systemd_service_or_container(is_systemd_service: bool):
    """
    Stops running systemd service or container

    :param is_systemd_service: Whether the execution type is a systemd service or a container
    """
    exec_type = "systemd service" if is_systemd_service else "container"

    podman_question(
        f"The {exec_type} is running. It must be stopped to use the Python helper. "
        "Can the Python helper stop it now?",
        new_line=True,
    )
    user_choice = ""

    while user_choice not in ("y", "n"):
        user_choice = input(podman_input("Enter y for yes and n for no: ")).strip().lower()

    if user_choice == "n":
        exit()

    if is_systemd_service:
        systemd_stop()
    else:
        clear_after_building_or_before_starting()

    print_and_input(
        podman_input("Press Enter to confirm that you have read that: "),
        podman_note(
            f"You need to re-start the {exec_type} with the Python helper in order to use it again",
            new_line=True,
            printing=Printing.NO,
        ),
        podman_note("Or reboot the system if you have enabled auto-starting at boot", printing=Printing.NO),
    )


if __name__ == "__main__":
    """
    Entry point for the program
    """
    # We want sudo priv
    acquire_sudo()

    Terminal.clear(True)

    # Set the execution possibilities for the user
    execution_possibilities = [
        ("Build", [
            "Builds a new image from the Containerfile_x86_64 in the base directory of this project",
            "VERY IMPORTANT: During building of the image, the UID and GID of the user executing this script",
            "are used to set the UID and GID of the pod user inside the image",
            "That makes working with files and folders you mount into the container via 'args.json' easier",
            "since you do not have to use chown on those files and folders, to get permissions right",
            "ALSO IMPORTANT: The DISPLAY environment variable that is set while executing the Python helper will be",
            "written into '/etc/profile.d/display.sh' inside the container",
            "The 'display.sh' is e. g. used in the 'entrypoint.sh' and is in general used to allow displaying",
            "of graphical programs on the host system without using 'x2go'",
            "Keep those two things in mind, when exporting and importing images with the Python helper",
            "If you have already built or imported an image, that images gets deleted first - automatically",
        ], build_image),

        ("Load", [
            "Loads an already built image from a .tar archive",
            "If you have already built or imported an image, that images gets deleted first - automatically",
        ], load_image),

        ("Start", [
            "Starts a container based on the image currently present on this system",
            "If you did not build or import an image before trying to start a container, the starting will fail",
        ], start_container),

        ("Save", [
            "Saves the image that is currently present on this system to a .tar archive",
            "If you did not build or import an image before trying to export the image, the exporting will fail",
        ], save_image),

        ("Create and install systemd service file", [
            f"The created systemd service file will be installed to '{Calls.serviceFilePath}'",
            "It will not be started or enabled via 'systemctl', it will just be copied to the mentioned location",
            "Use other options of this Python helper to start and enable the service",
            "You need to re-run this option after changing the 'args.json' to include the changes in the service file",
            "You also need to re-run this option after moving the folder containing this project to another location",
            "If you did not build or import an image before trying to create the service file, the creating will fail",
        ], systemd_create),

        ("Start via systemd", [
            "Starts a container based on the image currently present on this system",
            f"Starting is done via '{Calls.systemdStart}'",
            "After starting the container via systemd, the Python helper will exit",
            "The started container runs in the background and may be stopped when re-opening the Python helper",
            "You may connect to the started container with 'ssh' or 'x2go'",
            "If you did not create and install a systemd service file first, the starting will fail",
        ], systemd_start),

        ("Automatic start at boot and automatic restart via systemd", [
            "Enables the automatic starting of a container at boot",
            "Also enables automatic restarting of that container",
            "Automatic restarting happens in every case, which means regular shutdowns and crashes",
            f"Enabling is done via '{Calls.systemdEnable}'",
            "This does not start a container via systemd",
            "To start a container via systemd, reboot the system after enabling this option",
            "Or use the regarding option of the Python helper to start a container via systemd without rebooting",
            "If you did not create and install a systemd service file first, the enabling will fail",
        ], systemd_enable),

        ("Disable automatic start at boot and disable automatic restart via systemd", [
            "Just reverts the 'Automatic start at boot and automatic restart via systemd' option of the Python helper",
            f"Disabling is done via '{Calls.systemdDisable}'",
            "If you did not create and install a systemd service file first, the disabling will fail",
        ], systemd_disable),

        ("Enable Xhost", [
            "If you want to run graphical programs inside the Podman container and see them on your normal host system",
            "without using 'x2go', you need to grant the container access to your local X server",
            "This option does that, and repeats it automatically every time you login with any user on the host system",
            f"That is achieved by placing a shell script in '{Calls.xhostFilePath}'",
            "NOTICE: You need to have 'xhost' installed on your host system to use that feature",
            "You may check that via executing the 'xhost' command in a terminal to see if the command exists",
        ], xhost_enable_start),

        ("Disable Xhost", [
            "Just reverts the 'Enable Xhost' option of the Python helper",
        ], xhost_disable_stop),

        ("Debug", [
            "Prints debug information including the version of the Python helper",
            "Include this information in every Issue or Pull Request you open on GitHub",
        ], print_debug_info),

        ("Reset Podman environment", [
            "Completely resets the Podman environment",
            "That means: All pods, all images, all containers and all volumes",
        ], podman_reset),

        ("Exit", [
            "Exits the Python helper",
        ], exit_python_helper),
    ]

    # Create a dictionary mapping function names to functions of the execution possibilities
    name_to_f = {f.__name__: f for f in [f for _, _, f in execution_possibilities]}

    # The function names of the functions to execute given via command line arguments
    f_names_from_cmd = argv[1:]

    # Check that all function names from the command line are valid
    are_all_f_names_from_cmd_valid = True
    for f_name in f_names_from_cmd:
        if f_name not in name_to_f:
            podman_error(f"Invalid function name {f_name} given via command line argument", new_line=False)
            are_all_f_names_from_cmd_valid = False

    # If all function names are valid, make sure the container isn't running and execute the functions in order
    if are_all_f_names_from_cmd_valid and len(f_names_from_cmd) > 0:
        # If the container is started via systemd, stop it
        if systemd_started():
            systemd_stop()
        # If the container is running, stop it
        if container_running():
            clear_after_building_or_before_starting()
        # Execute the functions in order
        for f_name in f_names_from_cmd:
            name_to_f[f_name](exec_from_cmd=True)
    # If not all function names are valid, print the valid function names and exit
    elif not are_all_f_names_from_cmd_valid:
        raise RuntimeError("Invalid function name(s) in command line argument(s), valid function names are: {}".format(
            ", ".join(name_to_f.keys()),
        ))

    # Let the user execute things until he decides to exit the program
    while True:
        # Let the user only use the Python helper if the systemd service is not started
        if systemd_started():
            stop_systemd_service_or_container(is_systemd_service=True)
            continue

        # Let the user only use the Python helper if the container is not running
        if container_running():
            stop_systemd_service_or_container(is_systemd_service=False)
            continue

        Terminal.clear(False)
        Terminal.header("Arch Userland Virtualization (AUV) - Helper")

        # Let the user execute a thing
        podman_status("Choose, what you want to do next", new_line=True, printing=Printing.MENU)
        for i in range(0, len(execution_possibilities)):
            podman_note(
                f"Enter {Colors.cyan(Colors.bold(i + 1))} for: {Colors.cyan(execution_possibilities[i][0])}",
                new_line=True,
                printing=Printing.MENU,
            )
            for description_line in execution_possibilities[i][1]:
                podman_status(description_line, printing=Printing.MENU)

        Terminal.content()
        Terminal.divider()
        try:
            Terminal.content(podman_input("Enter your choice: "), as_input=True)
            input_position = Terminal.cursor_get_position()
            print()
            Terminal.footer()
            offset = Terminal.calculate_row_offset(input_position, additional_rows=2)
            Terminal.cursor_set_position(input_position, row_offset=offset)
            user_choice = int(input())
            if 1 <= user_choice <= len(execution_possibilities):
                Terminal.clear(True)
                execution_possibilities[user_choice - 1][2](exec_from_cmd=False)
            else:
                raise IndexError
        except (ValueError, IndexError):
            podman_error("That choice was not valid", new_line=True)
        except EOFError:
            podman_error("We caught an EOFError, which is not your fault, just restart the script", new_line=True)
            exit(1)
