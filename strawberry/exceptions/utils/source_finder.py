import importlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional, Sequence, Type

from strawberry.utils.cached_property import cached_property

from ..exception_source import ExceptionSource


if TYPE_CHECKING:
    from libcst import CSTNode


@dataclass
class SourcePath:
    path: Path
    code: str


class LibCSTSourceFinder:
    def __init__(self) -> None:
        self.cst = importlib.import_module("libcst")

    def find_source(self, module: str) -> Optional[SourcePath]:
        # todo: support for pyodide

        source_module = sys.modules.get(module)

        if source_module is None or source_module.__file__ is None:
            return None

        path = Path(source_module.__file__)

        if not path.exists() or path.suffix != ".py":
            return None

        source = path.read_text()

        return SourcePath(path=path, code=source)

    def _find(self, source: SourcePath, matcher: Any) -> Sequence["CSTNode"]:
        from libcst.metadata import (
            MetadataWrapper,
            ParentNodeProvider,
            PositionProvider,
        )

        module = self.cst.parse_module(source.code)
        _metadata_wrapper = MetadataWrapper(module)
        self._position_metadata = _metadata_wrapper.resolve(PositionProvider)
        self._parent_metadata = _metadata_wrapper.resolve(ParentNodeProvider)

        import libcst.matchers as m

        return m.findall(_metadata_wrapper, matcher)

    def _find_definition_by_qualname(
        self, qualname: str, nodes: Sequence["CSTNode"]
    ) -> Optional["CSTNode"]:
        from libcst import ClassDef, CSTNode, FunctionDef

        for definition in nodes:
            parent: Optional[CSTNode] = definition
            stack = []

            while parent:
                if isinstance(parent, ClassDef):
                    stack.append(parent.name.value)

                if isinstance(parent, FunctionDef):
                    stack.extend(("<locals>", parent.name.value))

                parent = self._parent_metadata.get(parent)

            if stack[0] == "<locals>":
                stack.pop(0)

            found_class_name = ".".join(reversed(stack))

            if found_class_name == qualname:
                return definition

        return None

    def _find_function_definition(
        self, source: SourcePath, function: Callable
    ) -> Optional["CSTNode"]:
        import libcst.matchers as m

        matcher = m.FunctionDef(name=m.Name(value=function.__name__))

        function_defs = self._find(source, matcher)

        return self._find_definition_by_qualname(function.__qualname__, function_defs)

    def find_class(self, cls: Type) -> Optional[ExceptionSource]:
        source = self.find_source(cls.__module__)

        if source is None:
            return None

        import libcst.matchers as m

        matcher = m.ClassDef(name=m.Name(value=cls.__name__))

        class_defs = self._find(source, matcher)
        class_def = self._find_definition_by_qualname(cls.__qualname__, class_defs)

        if class_def is None:
            return None

        position = self._position_metadata[class_def]
        column_start = position.start.column + len("class ")

        return ExceptionSource(
            path=source.path,
            code=source.code,
            start_line=position.start.line,
            error_line=position.start.line,
            end_line=position.end.line,
            error_column=column_start,
            error_column_end=column_start + len(cls.__name__),
        )

    def find_function(self, function: Callable) -> Optional[ExceptionSource]:
        source = self.find_source(function.__module__)

        if source is None:
            return None

        function_def = self._find_function_definition(source, function)

        if function_def is None:
            return None

        position = self._position_metadata[function_def]

        function_prefix = len("def ")
        error_column = position.start.column + function_prefix
        error_column_end = error_column + len(function.__name__)

        return ExceptionSource(
            path=source.path,
            code=source.code,
            start_line=position.start.line,
            error_line=position.start.line,
            end_line=position.end.line,
            error_column=error_column,
            error_column_end=error_column_end,
        )

    def find_argument(
        self, function: Callable, argument_name: str
    ) -> Optional[ExceptionSource]:
        source = self.find_source(function.__module__)

        if source is None:
            return None

        function_def = self._find_function_definition(source, function)

        if function_def is None:
            return None

        import libcst.matchers as m

        argument_defs = m.findall(
            function_def,
            m.Param(name=m.Name(value=argument_name)),
        )

        if not argument_defs:
            return None

        argument_def = argument_defs[0]

        function_position = self._position_metadata[function_def]
        position = self._position_metadata[argument_def]

        return ExceptionSource(
            path=source.path,
            code=source.code,
            start_line=function_position.start.line,
            end_line=function_position.end.line,
            error_line=position.start.line,
            error_column=position.start.column,
            error_column_end=position.end.column,
        )


class SourceFinder:
    # this might need to become a getter
    @cached_property
    def cst(self) -> Optional[LibCSTSourceFinder]:
        try:
            return LibCSTSourceFinder()
        except ImportError:
            return None

    def find_class_from_object(self, cls: Type) -> Optional[ExceptionSource]:
        return self.cst.find_class(cls) if self.cst else None

    def find_function_from_object(
        self, function: Callable
    ) -> Optional[ExceptionSource]:
        return self.cst.find_function(function) if self.cst else None

    def find_argument_from_object(
        self, function: Callable, argument_name: str
    ) -> Optional[ExceptionSource]:
        return self.cst.find_argument(function, argument_name) if self.cst else None
