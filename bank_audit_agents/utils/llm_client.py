"""
LLM 客户端模块
统一封装 OpenAI / LangChain LLM 调用，支持 mock fallback
"""
import json
import asyncio
from typing import Any, Dict, List, Optional

from bank_audit_agents.config.settings import get_settings
from bank_audit_agents.utils.logger import get_logger

logger = get_logger(__name__)


class LLMClient:
    """
    LLM 客户端
    - 当 openai_api_key 已配置时，使用真实 LLM 调用
    - 未配置时，回退到 mock 模式（调用方提供的 fallback 函数）
    """

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self._client = None
        self._is_available = bool(self.settings.openai_api_key)

        if self._is_available:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key=self.settings.openai_api_key,
                    base_url=self.settings.openai_base_url or None,
                )
                logger.info("LLM 客户端已初始化（真实 API 模式）")
            except ImportError:
                logger.warning("openai 包未安装，LLM 客户端回退到 mock 模式")
                self._is_available = False
            except Exception as e:
                logger.warning(f"LLM 客户端初始化失败: {e}，回退到 mock 模式")
                self._is_available = False
        else:
            logger.info("LLM 客户端运行在 mock 模式（未配置 openai_api_key）")

    @property
    def is_mock_mode(self) -> bool:
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
        调用 LLM 对话接口

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户输入
            temperature: 温度参数
            max_tokens: 最大 token 数
            response_format_json: 是否要求 JSON 格式输出

        Returns:
            LLM 返回的文本
        """
        if not self._is_available:
            raise RuntimeError("LLM 不可用（mock 模式），请提供 mock fallback")

        temp = temperature if temperature is not None else self.settings.llm_temperature
        tokens = max_tokens or self.settings.llm_max_tokens

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        kwargs: Dict[str, Any] = {
            "model": self.settings.default_llm_model,
            "messages": messages,
            "temperature": temp,
            "max_tokens": tokens,
        }

        if response_format_json:
            kwargs["response_format"] = {"type": "json_object"}

        for attempt in range(self.settings.llm_max_retries):
            try:
                response = await self._client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                logger.debug(f"LLM 调用成功，返回 {len(content)} 字符")
                return content
            except Exception as e:
                logger.warning(f"LLM 调用失败（第 {attempt + 1} 次）: {e}")
                if attempt < self.settings.llm_max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

    async def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        调用 LLM 并解析 JSON 响应

        Returns:
            解析后的 JSON 字典
        """
        content = await self.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            response_format_json=True,
        )
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

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户输入
            fallback_fn: 回退函数（同步或异步），返回 mock 结果
            temperature: 温度参数
            response_format_json: 是否要求 JSON 格式

        Returns:
            LLM 结果或 fallback 结果
        """
        if self._is_available:
            try:
                if response_format_json:
                    return await self.chat_json(system_prompt, user_prompt, temperature)
                else:
                    return await self.chat(system_prompt, user_prompt, temperature)
            except Exception as e:
                logger.warning(f"LLM 调用失败，使用 fallback: {e}")

        # 执行 fallback
        result = fallback_fn()
        if asyncio.iscoroutine(result):
            result = await result
        return result


# 全局单例
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """获取全局 LLM 客户端实例"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
