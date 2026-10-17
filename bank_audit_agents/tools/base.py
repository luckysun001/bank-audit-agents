"""
工具层基础抽象

此前各 Agent 的 ``get_tools()`` 只返回工具名字符串（"pdf_parser"、"aml_rule_engine" …），
属于「声明了工具但没有可执行实现」。本模块补上真正的执行骨架：

- :class:`ToolSpec`  工具描述（名称、说明、参数 schema、可执行函数）
- :class:`ToolResult` 统一的执行结果
- :class:`ToolRegistry` 工具注册表，支持按名查找与调用
- :func:`get_default_registry` 全局默认注册表（文档工具 + 规则引擎）

设计上保持向后兼容：Agent 的 ``get_tools()`` 仍可返回字符串列表，
:meth:`BaseAgent.resolve_tools` 会把它解析成真正可调用的 :class:`ToolSpec`。
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from bank_audit_agents.utils.logger import get_logger

logger = get_logger(__name__)

__all__ = [
    "ToolSpec",
    "ToolResult",
    "ToolRegistry",
    "tool",
    "get_default_registry",
    "reset_default_registry",
]


@dataclass
class ToolResult:
    """工具执行结果"""

    tool_name: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    duration_seconds: float = 0.0
    call_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "duration_seconds": round(self.duration_seconds, 4),
        }


@dataclass
class ToolSpec:
    """工具描述

    Args:
        name: 工具唯一名称（Agent 的 ``get_tools()`` 通过它引用）
        description: 一句话说明，会进入 LLM 的工具列表
        func: 真正执行的函数
        parameters: 参数 JSON Schema 风格的说明（仅用于文档与提示词，不做强校验）
        category: 归类，便于按场景筛选
    """

    name: str
    description: str
    func: Callable[..., Any]
    parameters: Dict[str, Any] = field(default_factory=dict)
    category: str = "general"

    def run(self, **kwargs: Any) -> ToolResult:
        """执行工具，捕获异常并统一包装为 :class:`ToolResult`"""
        start = time.time()
        try:
            output = self.func(**kwargs)
            return ToolResult(
                tool_name=self.name,
                success=True,
                output=output,
                duration_seconds=time.time() - start,
            )
        except Exception as exc:  # noqa: BLE001 - 工具失败不应中断 Agent 主流程
            logger.warning(f"工具 {self.name} 执行失败: {exc}")
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                duration_seconds=time.time() - start,
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": self.parameters,
        }

    def __repr__(self) -> str:
        return f"<ToolSpec {self.name} ({self.category})>"


class ToolRegistry:
    """工具注册表"""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec, override: bool = False) -> ToolSpec:
        if spec.name in self._tools and not override:
            raise ValueError(f"工具已注册: {spec.name}（如需覆盖请设置 override=True）")
        self._tools[spec.name] = spec
        return spec

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        return name in self._tools

    def list_tools(self, category: Optional[str] = None) -> List[ToolSpec]:
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return tools

    def names(self, category: Optional[str] = None) -> List[str]:
        return [t.name for t in self.list_tools(category)]

    def call(self, name: str, **kwargs: Any) -> ToolResult:
        """按名调用工具；未注册时返回失败的 :class:`ToolResult`（不抛异常）"""
        spec = self.get(name)
        if spec is None:
            return ToolResult(
                tool_name=name,
                success=False,
                error=f"工具未注册: {name}",
            )
        return spec.run(**kwargs)

    def resolve(self, names: List[str]) -> List[ToolSpec]:
        """把字符串名列表解析为工具对象，跳过未注册项"""
        resolved = []
        for name in names:
            spec = self.get(name)
            if spec is None:
                logger.debug(f"工具未注册，已跳过: {name}")
                continue
            resolved.append(spec)
        return resolved

    def to_dict(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self.list_tools()]

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


def tool(
    name: str,
    description: str,
    category: str = "general",
    parameters: Optional[Dict[str, Any]] = None,
    registry: Optional[ToolRegistry] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """装饰器：把函数注册为工具

    用法::

        @tool("extract_amounts", "从文本中抽取金额", category="document")
        def extract_amounts(text: str) -> list:
            ...
    """
    target = registry or get_default_registry()

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        target.register(
            ToolSpec(
                name=name,
                description=description,
                func=func,
                parameters=parameters or {},
                category=category,
            ),
            override=True,
        )
        return func

    return decorator


_default_registry: Optional[ToolRegistry] = None


def get_default_registry() -> ToolRegistry:
    """获取全局默认工具注册表（惰性初始化并注册内置工具）"""
    global _default_registry
    if _default_registry is None:
        _default_registry = ToolRegistry()
        # 延迟导入避免循环依赖：这两个模块会用 @tool 注册到本注册表
        from bank_audit_agents.tools import document_tools, rules  # noqa: F401

    return _default_registry


def reset_default_registry() -> ToolRegistry:
    """重置全局注册表（主要用于测试）"""
    global _default_registry
    _default_registry = None
    return get_default_registry()
