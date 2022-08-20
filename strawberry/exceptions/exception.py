from typing import TYPE_CHECKING, ClassVar, Dict, Optional

from backports.cached_property import cached_property

from .exception_source import ExceptionSource


if TYPE_CHECKING:
    from rich.console import RenderableType

    from .syntax import Syntax


class StrawberryException(Exception):
    message: str
    rich_message: str
    suggestion: str
    annotation_message: str
    documentation_url: ClassVar[str]

    def __init__(self, message: str) -> None:
        self.message = message

    def __str__(self) -> str:
        return self.message

    @cached_property
    def exception_source(self) -> Optional[ExceptionSource]:
        return None

    @property
    def __rich_header__(self) -> "RenderableType":
        assert self.exception_source

        source_file = self.exception_source.path
        relative_path = self.exception_source.path_relative_to_cwd
        error_line = self.exception_source.error_line

        return (
            f"[bold red]error: {self.rich_message}\n"
            f"[white]     @ [link=file://{source_file}]{relative_path}:{error_line}"
        )

    @property
    def __rich_body__(self) -> "RenderableType":
        assert self.exception_source
        exception_source = self.exception_source

        prefix = " " * exception_source.error_column
        caret = "^" * (
            exception_source.error_column_end - exception_source.error_column
        )

        message = self.annotation_message

        message = f"{prefix}[bold]{caret}[/] {message}"

        error_line = exception_source.error_line
        line_annotations = {error_line: message}

        return self.highlight_code(
            error_line=error_line, line_annotations=line_annotations
        )

    @property
    def __rich_footer__(self) -> "RenderableType":
        return (
            f"{self.suggestion}\n\n"
            "Read more about this error on [bold underline]"
            f"[link={self.documentation_url}]{self.documentation_url}"
        )

    def __rich__(self) -> Optional["RenderableType"]:
        from rich.box import SIMPLE
        from rich.console import Group
        from rich.panel import Panel

        content = (
            self.__rich_header__,
            "",
            self.__rich_body__,
            "",
            "",
            self.__rich_footer__,
        )

        if all(x == "" for x in content):
            return self.message

        return Panel.fit(
            Group(*content),
            box=SIMPLE,
        )

    def highlight_code(
        self, error_line: int, line_annotations: Dict[int, str]
    ) -> "Syntax":
        from .syntax import Syntax

        assert self.exception_source is not None

        return Syntax(
            code=self.exception_source.code,
            highlight_lines={error_line},
            line_offset=self.exception_source.start_line - 1,
            line_annotations=line_annotations,
            line_range=(
                self.exception_source.start_line,
                self.exception_source.end_line,
            ),
        )
