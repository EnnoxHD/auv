from __future__ import annotations

from re import compile, match, split
from shutil import get_terminal_size
from sys import stdout, stdin
from termios import tcgetattr, tcsetattr, ECHO, ICANON, TCSAFLUSH
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


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
    def cursor_set_position(position: tuple[int, int], additional_rows: int = 0):
        """
        Sets the cursor to the given position inside the terminal

        :param position:            The cursor position to move the cursor to as tuple (column, row)
        :param additional_rows:     The number of rows added after the initial position
        """
        # https://en.wikipedia.org/wiki/ANSI_escape_code#CSI_(Control_Sequence_Introducer)_sequences
        column = position[0]
        if column <= 0:
            column = 1

        row = position[1]
        if row <= 0:
            row = 1

        row_offset = Terminal.calculate_row_offset(position, additional_rows)
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
    def cut(string: str, excess: int, insert_end: str = "") -> str:
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
    def header(string: str, fn_color_invert: Callable[[str], str], fn_color_bold: Callable[[str], str]):
        """
        Prints a header line in the terminal for the given string

        :param string:          The string to use inside the header
        :param fn_color_invert: Function to invert colors of a string in terminal
        :param fn_color_bold:   Function to change a string to bold in terminal
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
        to_print += fn_color_invert(decoration[2] + fn_color_bold(string) + decoration[3])
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
    def prepare_input(string: str, new_line: bool = False) -> tuple[int, int]:
        """
        Prints the specified string and then records the cursor position.
        The cursor is then optionally moved to the next line.

        :param string:      The string to print
        :param new_line:    Whether to move the cursor to the next line
        :return:            The cursor postition after priting the string
        """
        Terminal.content(string, as_input=True)
        input_position = Terminal.cursor_get_position()
        if new_line:
            Terminal.print_plain("\n")
        return input_position

    @staticmethod
    def capture_input(input_pos: tuple[int, int], additional_rows: int = 0) -> str:
        """
        Moves the cursor to the specified position and then caputures user input.
        It also saves the original position of the cursor beforehand and restores it afterwards.

        :param input_pos:       The input position at which to display and capture user input
        :param additional_rows: The number of rows added after the input position
        :return:                The captured user input
        """
        saved_pos = Terminal.cursor_get_position()
        Terminal.cursor_set_position(input_pos, additional_rows)
        captured_input = input()
        Terminal.cursor_set_position(saved_pos)
        return captured_input

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
