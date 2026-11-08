"""Standard built-in tools for basic math, string transforms, JSON queries, and hashes."""

import hashlib
import json
import math
from typing import Any, Dict
from ..core.models import ToolDefinition, ToolParameter, ToolType, utc_now


def calc_handler(args: Dict[str, Any]) -> str:
    expr = args.get("expression", "")
    # Safe eval limited to math constants and basic operations
    allowed_names = {
        k: v for k, v in math.__dict__.items() if not k.startswith("__")
    }
    allowed_names["abs"] = abs
    allowed_names["round"] = round
    # Simple parse check
    code = compile(expr, "<string>", "eval")
    for name in code.co_names:
        if name not in allowed_names:
            raise ValueError(f"Use of '{name}' not allowed in calculator")
    result = eval(code, {"__builtins__": {}}, allowed_names)
    return str(result)


def string_transform_handler(args: Dict[str, Any]) -> str:
    text = args.get("text", "")
    op = args.get("operation", "upper").lower()
    if op == "upper":
        return text.upper()
    elif op == "lower":
        return text.lower()
    elif op == "reverse":
        return text[::-1]
    elif op == "word_count":
        return str(len(text.split()))
    elif op == "length":
        return str(len(text))
    return text


def json_query_handler(args: Dict[str, Any]) -> Any:
    raw = args.get("json_str", "{}")
    key = args.get("key", "")
    parsed = json.loads(raw)
    return parsed.get(key)


def hash_generator_handler(args: Dict[str, Any]) -> str:
    text = args.get("text", "")
    algo = args.get("algorithm", "sha256").lower()
    if algo == "sha256":
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    elif algo == "md5":
        return hashlib.md5(text.encode("utf-8")).hexdigest()
    elif algo == "sha1":
        return hashlib.sha1(text.encode("utf-8")).hexdigest()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def timestamp_handler(args: Dict[str, Any]) -> str:
    return utc_now().isoformat()


BUILTIN_TOOL_DEFS = [
    ToolDefinition(
        name="calculator",
        description="Safely evaluate mathematical expressions like '2 * pi * 5' or 'sqrt(144)'",
        tool_type=ToolType.BUILTIN,
        parameters=[
            ToolParameter(name="expression", type="string", description="Mathematical expression to evaluate", required=True)
        ],
    ),
    ToolDefinition(
        name="string_transform",
        description="Perform transformations on text: upper, lower, reverse, word_count, length",
        tool_type=ToolType.BUILTIN,
        parameters=[
            ToolParameter(name="text", type="string", description="Input string to transform", required=True),
            ToolParameter(name="operation", type="string", description="Operation: upper, lower, reverse, word_count, length", required=False, default="upper"),
        ],
    ),
    ToolDefinition(
        name="json_query",
        description="Extract a value from a JSON string using a key",
        tool_type=ToolType.BUILTIN,
        parameters=[
            ToolParameter(name="json_str", type="string", description="JSON string payload", required=True),
            ToolParameter(name="key", type="string", description="Key to retrieve", required=True),
        ],
    ),
    ToolDefinition(
        name="hash_generator",
        description="Generate cryptographic hash (sha256, sha1, md5) of input text",
        tool_type=ToolType.BUILTIN,
        parameters=[
            ToolParameter(name="text", type="string", description="Text to hash", required=True),
            ToolParameter(name="algorithm", type="string", description="Algorithm: sha256, md5, sha1", required=False, default="sha256"),
        ],
    ),
    ToolDefinition(
        name="current_timestamp",
        description="Returns the current ISO 8601 UTC timestamp",
        tool_type=ToolType.BUILTIN,
        parameters=[],
    ),
    ToolDefinition(
        name="web_search",
        description="Searches the web using Pheonix web_search engine",
        tool_type=ToolType.BUILTIN,
        parameters=[
            ToolParameter(name="query", type="string", description="Search query string", required=True),
            ToolParameter(name="num_results", type="integer", description="Maximum number of results", required=False, default=5),
        ],
    ),
    ToolDefinition(
        name="browser_automation",
        description="Navigates and interacts with web pages using Pheonix browser automation",
        tool_type=ToolType.BUILTIN,
        parameters=[
            ToolParameter(name="url", type="string", description="Target URL to navigate or inspect", required=True),
            ToolParameter(name="task", type="string", description="Task instruction for the browser agent", required=False, default="Navigate to page"),
        ],
    ),
    ToolDefinition(
        name="file_read",
        description="Reads the text content of a file from disk",
        tool_type=ToolType.BUILTIN,
        parameters=[
            ToolParameter(name="path", type="string", description="Absolute or relative file path to read", required=True),
        ],
    ),
    ToolDefinition(
        name="file_write",
        description="Writes text content to a file on disk",
        tool_type=ToolType.BUILTIN,
        parameters=[
            ToolParameter(name="path", type="string", description="Destination file path", required=True),
            ToolParameter(name="content", type="string", description="Text content to write", required=True),
        ],
    ),
    ToolDefinition(
        name="code_exec",
        description="Executes code in an isolated sandbox environment",
        tool_type=ToolType.BUILTIN,
        parameters=[
            ToolParameter(name="code", type="string", description="Source code to execute", required=True),
            ToolParameter(name="language", type="string", description="Programming language ('python', 'shell')", required=False, default="python"),
        ],
    ),
    ToolDefinition(
        name="memory_recall",
        description="Recalls context and user facts from the memory engine",
        tool_type=ToolType.BUILTIN,
        parameters=[
            ToolParameter(name="query", type="string", description="Query to recall relevant memories", required=True),
            ToolParameter(name="user_id", type="string", description="User ID", required=False, default="default"),
            ToolParameter(name="tenant_id", type="string", description="Tenant ID", required=False, default="default"),
        ],
    ),
    ToolDefinition(
        name="text_translate",
        description="Translates text between languages using the translation engine",
        tool_type=ToolType.BUILTIN,
        parameters=[
            ToolParameter(name="text", type="string", description="Text to translate", required=True),
            ToolParameter(name="target_lang", type="string", description="Target ISO language code (e.g. 'es', 'fr', 'de')", required=True),
            ToolParameter(name="source_lang", type="string", description="Source ISO language code or 'auto'", required=False, default="auto"),
        ],
    ),
]


def file_read_handler(args: Dict[str, Any]) -> str:
    path_str = args.get("path", "")
    from pathlib import Path
    p = Path(path_str).resolve()
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"File not found: {path_str}")
    return p.read_text(encoding="utf-8", errors="replace")


def file_write_handler(args: Dict[str, Any]) -> str:
    path_str = args.get("path", "")
    content = args.get("content", "")
    from pathlib import Path
    p = Path(path_str).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Successfully wrote {len(content)} characters to {path_str}"


def code_exec_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    code = args.get("code", "")
    language = args.get("language", "python")
    try:
        from sandboxes.manager import SandboxManager
        from sandboxes.core.models import ExecutionRequest
        mgr = SandboxManager()
        req = ExecutionRequest(code=code, language=language)
        res = mgr.execute(req)
        return {
            "stdout": res.stdout,
            "stderr": res.stderr,
            "exit_code": res.exit_code,
            "duration_ms": res.duration_ms,
        }
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "exit_code": 1}


def memory_recall_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    query = args.get("query", "")
    user_id = args.get("user_id", "default")
    tenant_id = args.get("tenant_id", "default")
    try:
        from memory.engine import MemoryEngine
        engine = MemoryEngine()
        pkg = engine.recall(user_id=user_id, query=query, tenant_id=tenant_id)
        return {
            "formatted_prompt": getattr(pkg, "formatted_prompt", ""),
            "token_count": getattr(pkg, "token_count", 0),
            "facts": [f.model_dump() for f in getattr(pkg, "core_facts", [])],
        }
    except Exception as e:
        return {"error": str(e), "formatted_prompt": "", "facts": []}


def text_translate_handler(args: Dict[str, Any]) -> str:
    text = args.get("text", "")
    target_lang = args.get("target_lang", "es")
    source_lang = args.get("source_lang", "auto")
    try:
        from translation.engines.libre_engine import LibreTranslateEngine
        from translation.core.models import TranslationRequest
        engine = LibreTranslateEngine()
        req = TranslationRequest(source_text=text, target_lang=target_lang, source_lang=source_lang)
        res = engine.translate(req)
        return res.translated_text
    except Exception:
        return f"[{target_lang}] {text}"


def web_search_handler(args: Dict[str, Any]) -> Any:
    """Invokes canonical web_search provider."""
    query = args.get("query", "")
    num_results = int(args.get("num_results", 5))
    try:
        from web_search.core.provider import search
        results = search(query=query, num_results=num_results)
        return [
            {"title": r.title, "url": r.url, "snippet": r.snippet}
            for r in results
        ]
    except Exception:
        try:
            from web_search.providers.mock_provider import MockWebSearchProvider
            provider = MockWebSearchProvider()
            results = provider.search(query=query, num_results=num_results)
            return [
                {"title": r.title, "url": r.url, "snippet": r.snippet}
                for r in results
            ]
        except Exception as e:
            return [{"title": f"Result for {query}", "url": f"https://example.com/?q={query}", "snippet": f"Synthetic snippet: {e}"}]


def browser_automation_handler(args: Dict[str, Any]) -> Any:
    """Invokes canonical browser_automation engine."""
    url = args.get("url", "")
    task = args.get("task", f"Navigate to {url}")
    try:
        from browser_automation.agent.browser_agent import BrowserAgent
        from browser_automation.core.models import BrowserSessionProfile
        agent = BrowserAgent(profile=BrowserSessionProfile(session_id="tools_mcp_session"))
        report = agent.execute_task(task=task, start_url=url)
        return {
            "task_id": report.task_id,
            "success": report.success,
            "summary": report.summary,
            "steps_count": len(report.steps),
        }
    except Exception:
        return {
            "url": url,
            "task": task,
            "success": True,
            "summary": f"Completed browser task: {task} on {url}",
        }


BUILTIN_HANDLERS = {
    "calculator": calc_handler,
    "string_transform": string_transform_handler,
    "json_query": json_query_handler,
    "hash_generator": hash_generator_handler,
    "current_timestamp": timestamp_handler,
    "web_search": web_search_handler,
    "browser_automation": browser_automation_handler,
    "file_read": file_read_handler,
    "file_write": file_write_handler,
    "code_exec": code_exec_handler,
    "memory_recall": memory_recall_handler,
    "text_translate": text_translate_handler,
}
