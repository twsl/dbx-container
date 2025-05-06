from collections.abc import Generator
from contextlib import contextmanager
from enum import StrEnum
from typing import Any, Self


class LineEnding(StrEnum):
    LF = "\n"
    CRLF = "\r\n"


class IndentStyle(StrEnum):
    Space = " "
    Tab = "\t"


class StringBuilder:
    def __init__(
        self, newline: LineEnding = LineEnding.LF, indent_style: IndentStyle = IndentStyle.Space, indent_size: int = 4
    ) -> None:
        self._indent_level = 0
        self._newline = newline
        self._indent_style = indent_style
        self._indent_size = indent_size
        self.content = []
        self.eol = newline.value
        self.indent_string = indent_style.value * (indent_size if indent_style == IndentStyle.Space else 1)

    def append(self, value: str) -> Self:
        if self._indent_level > 0:
            self.content.append(self.indent_string * self._indent_level + value)
        else:
            self.content.append(value)
        return self

    def append_newline(self) -> Self:
        self.append(self.eol)
        return self

    def append_line(self, value: str = "") -> Self:
        self.append(value + self.eol)
        return self

    def indent(self) -> Self:
        self._indent_level += 1
        return self

    def deindent(self) -> Self:
        if self._indent_level > 0:
            self._indent_level -= 1
        return self

    @contextmanager
    def scope(self) -> Generator[None, Any, None]:
        self.indent()
        yield
        self.deindent()

    def clear(self) -> None:
        self._indent_level = 0
        self.content.clear()

    def __str__(self) -> str:
        return "".join(self.content)
