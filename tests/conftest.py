"""测试共享 fixtures。

各 Agent 在 ``__init__`` 时就通过 ``get_llm_client()`` 取走客户端引用，
所以注入 FakeLLM **必须在创建 Agent 之前**完成 —— 这里用 fixture 保证顺序正确。
"""

import pytest

from bank_audit_agents.utils.llm_client import reset_llm_client, set_llm_client


class FakeLLM:
    """不发真实请求的 LLM 客户端替身。

    三种模式：
    - 默认：直接返回构造时给定的 ``result``
    - ``use_fallback=True``：执行调用方提供的 fallback（模拟 mock 模式）
    - ``raise_exc``：先抛异常再走 fallback（模拟真实客户端"调用失败即回退"的行为）
    """

    def __init__(self, result=None, use_fallback: bool = False, raise_exc=None):
        self.result = result
        self.use_fallback = use_fallback
        self.raise_exc = raise_exc
        self.calls = []

    @property
    def is_mock_mode(self) -> bool:
        return self.use_fallback

    async def call_with_fallback(
        self,
        system_prompt: str,
        user_prompt: str,
        fallback_fn,
        temperature=None,
        response_format_json: bool = False,
    ):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "response_format_json": response_format_json,
            }
        )

        if self.raise_exc is not None:
            # 与真实客户端一致：异常被吞掉后回退，不让整个任务失败
            try:
                raise self.raise_exc
            except Exception:  # noqa: BLE001 - 故意捕获全部
                pass
            return await self._resolve_fallback(fallback_fn)

        if self.use_fallback:
            return await self._resolve_fallback(fallback_fn)

        return self.result

    async def chat(self, system_prompt: str, user_prompt: str, temperature=None) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        if self.raise_exc is not None:
            raise self.raise_exc
        return str(self.result)

    async def chat_json(self, system_prompt: str, user_prompt: str, temperature=None):
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.result

    @staticmethod
    async def _resolve_fallback(fallback_fn):
        result = fallback_fn()
        if hasattr(result, "__await__"):
            result = await result
        return result


@pytest.fixture
def fake_llm():
    """注入一个 FakeLLM，返回该实例以便断言调用情况。

    用法::

        def test_x(fake_llm):
            fake_llm.result = {"risks": []}
            agent = SomeAgent()   # 必须在注入之后创建
    """
    client = FakeLLM()
    set_llm_client(client)
    yield client
    reset_llm_client()
