"""
LLM 客户端模块

统一封装 OpenAI / LangChain LLM 调用，支持 mock fallback 机制。

核心功能:
    1. 统一的 LLM 调用接口
    2. Mock fallback 机制（未配置 API Key 时返回示例数据）
    3. 自动重试和错误处理
    4. JSON 格式响应支持

设计思想:
    - 生产模式：配置 openai_api_key 后使用真实 LLM
    - 开发模式：未配置 API Key 时自动切换到 mock 模式
    - 容错机制：LLM 调用失败时自动使用 fallback 函数

使用示例:
    llm = get_llm_client()

    # 带 fallback 的调用（推荐）
    result = await llm.call_with_fallback(
        system_prompt="你是一位专家",
        user_prompt="请分析这段文本",
        fallback_fn=lambda: {"data": "mock result"},
        response_format_json=True,
    )

    # 直接调用（需要 LLM 可用）
    result = await llm.chat(system_prompt, user_prompt)
"""

import json
import asyncio
from typing import Any, Dict, List, Optional

from bank_audit_agents.config.settings import get_settings
from bank_audit_agents.utils.logger import get_logger

# 获取模块级日志记录器
logger = get_logger(__name__)


class LLMClient:
    """
    LLM 客户端

    提供统一的大语言模型调用接口，支持真实 API 和 mock 两种模式。

    工作模式:
        - 真实 API 模式：当配置了 openai_api_key 时，使用 OpenAI AsyncOpenAI 客户端
        - Mock 模式：未配置 API Key 时，调用方必须提供 fallback 函数

    核心特性:
        - 自动检测 API Key 配置状态
        - 支持 JSON 格式响应
        - 内置重试机制（指数退避）
        - 同步/异步 fallback 函数支持
    """

    def __init__(self, settings=None):
        """
        初始化 LLM 客户端

        Args:
            settings: 配置对象（可选，不提供则自动获取全局配置）
        """
        # 获取配置（如果未提供）
        self.settings = settings or get_settings()
        # OpenAI 客户端实例
        self._client = None
        # LLM 是否可用（取决于是否配置了 API Key）
        self._is_available = bool(self.settings.openai_api_key)

        # 如果 API Key 已配置，尝试初始化 OpenAI 客户端
        if self._is_available:
            try:
                # 延迟导入，避免在没有安装 openai 包时出错
                from openai import AsyncOpenAI

                # 创建 AsyncOpenAI 客户端
                self._client = AsyncOpenAI(
                    api_key=self.settings.openai_api_key,
                    base_url=self.settings.openai_base_url or None,
                )
                logger.info("LLM 客户端已初始化（真实 API 模式）")

            except ImportError:
                # openai 包未安装，回退到 mock 模式
                logger.warning("openai 包未安装，LLM 客户端回退到 mock 模式")
                self._is_available = False

            except Exception as e:
                # 其他初始化错误，回退到 mock 模式
                logger.warning(f"LLM 客户端初始化失败: {e}，回退到 mock 模式")
                self._is_available = False

        else:
            # 未配置 API Key，运行在 mock 模式
            logger.info("LLM 客户端运行在 mock 模式（未配置 openai_api_key）")

    @property
    def is_mock_mode(self) -> bool:
        """
        判断当前是否处于 mock 模式

        Returns:
            bool: True 表示 mock 模式，False 表示真实 API 模式
        """
        return not self._is_available

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format_json: bool = False,
    ) -> str:
        """
        调用 LLM 对话接口（仅真实 API 模式可用）

        核心流程:
            1. 验证 LLM 可用性
            2. 准备请求参数（系统提示词、用户提示词、温度、最大 token）
            3. 调用 OpenAI API（带指数退避重试）
            4. 返回 LLM 响应内容

        Args:
            system_prompt: 系统提示词，定义 LLM 的角色和行为
            user_prompt: 用户输入，具体的问题或指令
            temperature: 温度参数，控制输出的随机性（0-2，默认 0.7）
            max_tokens: 最大 token 数，限制响应长度
            response_format_json: 是否要求 JSON 格式输出

        Returns:
            str: LLM 返回的文本内容

        Raises:
            RuntimeError: 如果处于 mock 模式且未提供 fallback
        """
        # 验证 LLM 可用性
        if not self._is_available:
            raise RuntimeError("LLM 不可用（mock 模式），请提供 mock fallback")

        # 获取参数值（使用配置的默认值）
        temp = temperature if temperature is not None else self.settings.llm_temperature
        tokens = max_tokens or self.settings.llm_max_tokens

        # 构建消息列表
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # 构建 API 调用参数
        kwargs: Dict[str, Any] = {
            "model": self.settings.default_llm_model,
            "messages": messages,
            "temperature": temp,
            "max_tokens": tokens,
        }

        # 如果要求 JSON 格式输出
        if response_format_json:
            kwargs["response_format"] = {"type": "json_object"}

        # 带指数退避的重试机制
        for attempt in range(self.settings.llm_max_retries):
            try:
                # 调用 OpenAI API
                response = await self._client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                logger.debug(f"LLM 调用成功，返回 {len(content)} 字符")
                return content

            except Exception as e:
                # 记录重试日志
                logger.warning(f"LLM 调用失败（第 {attempt + 1} 次）: {e}")
                # 如果不是最后一次尝试，等待后重试
                if attempt < self.settings.llm_max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避：2^0, 2^1, 2^2...
                else:
                    # 最后一次尝试也失败，抛出异常
                    raise

    async def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        调用 LLM 并解析 JSON 响应

        封装 chat 方法，自动解析 JSON 格式响应。

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户输入
            temperature: 温度参数

        Returns:
            Dict[str, Any]: 解析后的 JSON 字典
        """
        # 调用 chat 方法（要求 JSON 格式输出）
        content = await self.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            response_format_json=True,
        )

        # 解析 JSON
        return json.loads(content)

    async def call_with_fallback(
        self,
        system_prompt: str,
        user_prompt: str,
        fallback_fn,
        temperature: Optional[float] = None,
        response_format_json: bool = False,
    ) -> Any:
        """
        调用 LLM，失败或 mock 模式时使用 fallback 函数

        这是推荐的调用方式，具有以下优点:
            1. 支持 mock 模式（开发环境无需配置 API Key）
            2. 自动处理 LLM 调用失败的情况
            3. 支持同步和异步 fallback 函数

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户输入
            fallback_fn: 回退函数，返回 mock 结果（支持同步或异步）
            temperature: 温度参数
            response_format_json: 是否要求 JSON 格式输出

        Returns:
            Any: LLM 结果或 fallback 结果
        """
        # 如果 LLM 可用，尝试调用
        if self._is_available:
            try:
                if response_format_json:
                    return await self.chat_json(system_prompt, user_prompt, temperature)
                else:
                    return await self.chat(system_prompt, user_prompt, temperature)

            except Exception as e:
                # LLM 调用失败，记录日志后使用 fallback
                logger.warning(f"LLM 调用失败，使用 fallback: {e}")

        # 执行 fallback 函数
        result = fallback_fn()

        # 如果 fallback 函数返回的是协程，等待其完成
        if asyncio.iscoroutine(result):
            result = await result

        return result


# 全局单例实例（懒加载）
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """
    获取全局 LLM 客户端实例

    使用单例模式，确保全局只有一个 LLM 客户端实例。

    Returns:
        LLMClient: LLM 客户端实例
    """
    global _llm_client

    # 懒加载：首次调用时创建实例
    if _llm_client is None:
        _llm_client = LLMClient()

    return _llm_client