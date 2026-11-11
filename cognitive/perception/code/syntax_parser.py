"""Syntax-Aware Source Code Parser (L1 Feature 1.07)."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class CodeSymbol:
    """Extracted symbol definition with kind and line span."""

    name: str
    kind: str  # "function", "class", "interface", "struct", "import"
    start_line: int
    end_line: int
    signature: str = ""


@dataclass
class ParsedCodeStructure:
    """Syntax-aware structural breakdown of a source code file."""

    language: str
    imports: List[str] = field(default_factory=list)
    symbols: List[CodeSymbol] = field(default_factory=list)
    line_count: int = 0


class SyntaxAwareCodeParser:
    """Parses Python via stdlib AST and TS/JS/Go/Rust via syntax patterns."""

    _JS_TS_FUNC_RE = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)")
    _JS_TS_CLASS_RE = re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z0-9_]+)")
    _GO_FUNC_RE = re.compile(r"^\s*func\s+(?:\([^)]+\)\s*)?([A-Za-z0-9_]+)\s*\(([^)]*)\)")
    _IMPORT_RE = re.compile(r"^\s*(?:import|from|use)\s+(.+)")

    def parse(self, code: str, language: str = "python") -> ParsedCodeStructure:
        lang = language.lower().strip()
        lines = code.splitlines()
        if lang in ("py", "python"):
            return self._parse_python(code, len(lines))
        return self._parse_generic(lines, lang)

    def _parse_python(self, code: str, line_count: int) -> ParsedCodeStructure:
        tree = ast.parse(code)
        imports: List[str] = []
        symbols: List[CodeSymbol] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [a.arg for a in node.args.args]
                symbols.append(
                    CodeSymbol(
                        name=node.name,
                        kind="function",
                        start_line=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                        signature=f"{node.name}({', '.join(args)})",
                    )
                )
            elif isinstance(node, ast.ClassDef):
                symbols.append(
                    CodeSymbol(
                        name=node.name,
                        kind="class",
                        start_line=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                        signature=f"class {node.name}",
                    )
                )
        symbols.sort(key=lambda s: s.start_line)
        return ParsedCodeStructure(language="python", imports=imports, symbols=symbols, line_count=line_count)

    def _parse_generic(self, lines: List[str], lang: str) -> ParsedCodeStructure:
        imports: List[str] = []
        symbols: List[CodeSymbol] = []
        for idx, ln in enumerate(lines, 1):
            if m_imp := self._IMPORT_RE.match(ln):
                imports.append(m_imp.group(1).strip().rstrip(";"))
            if m_cls := self._JS_TS_CLASS_RE.match(ln):
                symbols.append(CodeSymbol(name=m_cls.group(1), kind="class", start_line=idx, end_line=idx))
            elif m_fn := (self._JS_TS_FUNC_RE.match(ln) or self._GO_FUNC_RE.match(ln)):
                symbols.append(
                    CodeSymbol(
                        name=m_fn.group(1),
                        kind="function",
                        start_line=idx,
                        end_line=idx,
                        signature=f"{m_fn.group(1)}({m_fn.group(2).strip()})",
                    )
                )
        return ParsedCodeStructure(language=lang, imports=imports, symbols=symbols, line_count=len(lines))

