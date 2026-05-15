from datetime   import datetime
from enum       import IntEnum
from os         import system, name


MAX_TITLE_LENGTH = 6


class LogLevel(IntEnum):
    INFO   = 1
    WARN   = 2
    FAILED = 3
    OK     = 4
    DEBUG  = 5


_LEVEL_COLORS: dict[int, str] = {
    LogLevel.INFO  : "\033[34m",  # blue
    LogLevel.WARN  : "\033[33m",  # yellow
    LogLevel.FAILED: "\033[31m",  # red
    LogLevel.OK    : "\033[32m",  # green
}
_RESET = "\033[0m"


class Logger:
    def __init__(self, filepath: str = None, clear_previous: bool = True, display_line_num: int = 20, reserve_line_num: int = 2):
        self.filepath         = filepath
        self.clear_previous   = clear_previous
        self.display_line_num = display_line_num
        self.reserve_line_num = reserve_line_num
        self.logs             = []

    def print(self, message: str, level: LogLevel = LogLevel.INFO):
        if len(level.name) <= 6:
            left_space_num  = (MAX_TITLE_LENGTH - len(level.name)) // 2
            right_space_num = (MAX_TITLE_LENGTH - len(level.name)) - left_space_num
            message         = f'[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{" " * left_space_num}{level.name.upper()}{" " * right_space_num}] {message}'

        if self.filepath:
            with open(self.filepath, 'a') as f:
                f.write(message + '\n')

        color   = _LEVEL_COLORS.get(level, '')
        display = f'{color}{message}{_RESET}' if color else message

        if self.reserve_line_num != 0 and len(self.logs) == 0:
            self.logs.append('-' * 100)
        self.logs.append(display)
        if self.reserve_line_num != 0 and len(self.logs) == self.reserve_line_num + 1:
            self.logs.append('-' * 100)

        if self.display_line_num > -1 and len(self.logs) > self.display_line_num:
            if self.reserve_line_num == 0:
                self.logs.pop(0)
            else:
                self.logs.pop(self.reserve_line_num + 2)

        self.__display()

    def __clear(self, clear_by_ansi: bool = False):
        if clear_by_ansi:
            print("\x1b[2J\033[H")
        else:
            if name == 'nt':
                _ = system('cls')
            else:
                _ = system('clear')

    def __display(self):
        if self.clear_previous:
            self.__clear()
        for log in self.logs:
            print(log)


class LoggerV2:
    def __init__(self, filepath: str = None, display_line_num: int = 20) -> None:
        self.filepath         = filepath
        self.display_line_num = display_line_num
        self.top_logs         = []
        self.normal_logs      = []
        self.display_logs     = []

    def print(self, message: str, level: LogLevel = LogLevel.INFO, always_top: bool = False, show_top_and_normal: bool = False) -> None:
        if len(level.name) <= 6:
            left_space_num  = (MAX_TITLE_LENGTH - len(level.name)) // 2
            right_space_num = (MAX_TITLE_LENGTH - len(level.name)) - left_space_num
            message         = f'[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{" " * left_space_num}{level.name.upper()}{" " * right_space_num}] {message}'

        if self.filepath:
            with open(self.filepath, 'a') as f:
                f.write(message + '\n')

        color   = _LEVEL_COLORS.get(level, '')
        display = f'{color}{message}{_RESET}' if color else message

        if always_top                        : self.top_logs   .append(display)
        else                                 : self.normal_logs.append(display)
        if always_top and show_top_and_normal: self.normal_logs.append(display)

        self.display_logs = []
        if self.top_logs:
            self.display_logs.append('-' * 100)
            for top_log in self.top_logs:
                self.display_logs.append(top_log)
            self.display_logs.append('-' * 100)

        while len(self.normal_logs) > self.display_line_num:
            self.normal_logs.pop(0)
        for log in self.normal_logs:
            self.display_logs.append(log)
        self.__display()

    def get_top_logs(self, index: int = -1) -> list[str]:
        if index == -1:
            return self.top_logs
        else:
            return [self.top_logs[index]] if index < len(self.top_logs) else []

    def remove_top_log(self, index: int = -1) -> None:
        if index >= len(self.top_logs):
            return
        if index == -1:
            self.top_logs = []
        else:
            self.top_logs.pop(index)

    def __clear(self, clear_by_ansi: bool = False) -> None:
        if clear_by_ansi:
            print("\x1b[2J\033[H")
        else:
            if name == 'nt':
                _ = system('cls')
            else:
                _ = system('clear')

    def __display(self):
        self.__clear()
        for log in self.display_logs:
            print(log)
