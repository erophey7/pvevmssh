# helpers/lsp/protocol.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional, Literal


# ======================================================
# JSON-RPC 2.0 BASE
# ======================================================

JSONRPC_VERSION = "2.0"


@dataclass
class JsonRpcRequest:
    jsonrpc: Literal["2.0"]
    id: int | str | None
    method: str
    params: dict


@dataclass
class JsonRpcResponse:
    jsonrpc: Literal["2.0"]
    id: int | None
    result: Any


@dataclass
class JsonRpcError:
    jsonrpc: Literal["2.0"]
    id: int | None
    error: dict


@dataclass
class JsonRpcNotification:
    jsonrpc: Literal["2.0"]
    method: str
    params: dict


# ======================================================
# LSP TRANSPORT (SHELL MODE)
# ======================================================
# NOTE:
# This is STDIO-based LSP framing:
# Content-Length: <n>\r\n\r\n{json}

class LspTransport:
    framing: str = "content-length"
    encoding: str = "utf-8"
    stdio: bool = True


# ======================================================
# LSP METHODS
# ======================================================

class LspMethod:
    # lifecycle
    INITIALIZE = "initialize"
    INITIALIZED = "initialized"
    SHUTDOWN = "shutdown"
    EXIT = "exit"

    # document sync
    DID_OPEN = "textDocument/didOpen"
    DID_CHANGE = "textDocument/didChange"
    DID_CLOSE = "textDocument/didClose"

    # features
    COMPLETION = "textDocument/completion"
    HOVER = "textDocument/hover"
    DIAGNOSTIC = "textDocument/diagnostic"

    # SEMANTIC TOKENS
    SEMANTIC_TOKENS_FULL = "textDocument/semanticTokens/full"


# ======================================================
# LSP CORE TYPES
# ======================================================

@dataclass
class Position:
    line: int
    character: int


@dataclass
class Range:
    start: Position
    end: Position


@dataclass
class TextDocumentIdentifier:
    uri: str


@dataclass
class VersionedTextDocumentIdentifier(TextDocumentIdentifier):
    version: int


@dataclass
class TextDocumentItem:
    uri: str
    language_id: str
    version: int
    text: str


# ======================================================
# DOCUMENT EVENTS
# ======================================================

@dataclass
class DidOpenParams:
    textDocument: TextDocumentItem


@dataclass
class TextDocumentContentChangeEvent:
    text: str


@dataclass
class DidChangeParams:
    textDocument: VersionedTextDocumentIdentifier
    contentChanges: list[TextDocumentContentChangeEvent]


@dataclass
class DidCloseParams:
    textDocument: TextDocumentIdentifier


# ======================================================
# INITIALIZE HANDSHAKE
# ======================================================

@dataclass
class InitializeParams:
    processId: int | None
    rootUri: str | None
    capabilities: dict


@dataclass
class ServerCapabilities:
    textDocumentSync: int  # 1 = full, 2 = incremental
    completionProvider: dict | None
    hoverProvider: bool | None


@dataclass
class InitializeResult:
    capabilities: ServerCapabilities


# ======================================================
# COMPLETION
# ======================================================

@dataclass
class CompletionParams:
    textDocument: TextDocumentIdentifier
    position: Position
    context: dict | None = None


@dataclass
class CompletionItem:
    label: str
    kind: int = 1
    insertText: str | None = None
    detail: str | None = None
    documentation: str | None = None
    sortText: str | None = None


@dataclass
class CompletionList:
    isIncomplete: bool
    items: list[CompletionItem]


# ======================================================
# HOVER
# ======================================================

HoverContents = str | dict


@dataclass
class Hover:
    contents: HoverContents
    range: Range | None = None


@dataclass
class HoverParams:
    textDocument: TextDocumentIdentifier
    position: Position

# ======================================================
# SEMANTIC TOKENS 
# ======================================================

@dataclass
class SemanticTokensParams:
    textDocument: TextDocumentIdentifier
    text: str | None = None


@dataclass
class SemanticToken:
    start: int
    length: int
    style: str 


@dataclass
class SemanticTokens:
    tokens: list[SemanticToken]


# ======================================================
# DIAGNOSTICS
# ======================================================

@dataclass
class Diagnostic:
    range: Range
    message: str
    severity: int | None = None
    code: str | int | None = None
    source: str | None = None


@dataclass
class PublishDiagnosticsParams:
    uri: str
    diagnostics: list[Diagnostic]


# ======================================================
# SHELL-SPECIFIC EXTENSION (NON-STANDARD, SAFE NAMESPACE)
# ======================================================

class ShellExtensionMethod:
    """
    Non-LSP extension methods for shell integration.
    Must NOT conflict with official LSP namespace.
    """

    EXECUTE_COMMAND = "x-shell/execute"
    COMPLETE_COMMAND = "x-shell/complete"
    DESCRIBE_COMMAND = "x-shell/describe"


@dataclass
class ShellCommandParams:
    command: str
    args: list[str]
    cwd: str | None = None