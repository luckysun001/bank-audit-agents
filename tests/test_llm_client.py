"""LLM 客户端测试。

覆盖：
- mock 模式（无 api key）下 chat 抛错、call_with_fallback 走 fallback
- 缓存键确定性、响应缓存命中
- 真实路径（monkeypatch 假 AsyncOpenAI）的 chat / chat_json / 重试
- 全局 get/set/reset_llm_client 单例
"""

import types

import pytest

from bank_audit_agents.config.settings import Settings
from bank_audit_agents.utils.llm_client import (
    LLMClient,
    get_llm_client,
    reset_llm_client,
    set_llm_client,
)


def _make_response(content: str):
    return types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=content))]
    )


class _FakeCompletions:
    def __init__(self, content: str, fail_times: int = 0):
        self.content = content
        self.fail_times = fail_times
        self.call_count = 0

    async def create(self, **kwargs):
        self.call_count += 1
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("simulated failure")
        return _make_response(self.content)


class _FakeClient:
    def __init__(self, content: str, fail_times: int = 0):
        self.chat = types.SimpleNamespace(completions=_FakeCompletions(content, fail_times))


def _mock_mode_client() -> LLMClient:
    return LLMClient(Settings(openai_api_key=None))


def _available_client(content: str, fail_times: int = 0) -> LLMClient:
    client = LLMClient(Settings(openai_api_key="sk-test"))
    client._is_available = True
    client._client = _FakeClient(content, fail_times)
    return client


# ---------------------------------------------------------------------------
# mock 模式
# ---------------------------------------------------------------------------


def test_mock_mode_reports_unavailable():
    client = _mock_mode_client()
    assert client.is_mock_mode is True
    assert client._is_available is False


async def test_mock_mode_chat_raises():
    client = _mock_mode_client()
    with pytest.raises(RuntimeError):
        await client.chat("sys", "user")


async def test_mock_mode_chat_json_raises():
    client = _mock_mode_client()
    with pytest.raises(RuntimeError):
        await client.chat_json("sys", "user")


async def test_mock_mode_call_with_fallback_returns_fallback():
    client = _mock_mode_client()
    result = await client.call_with_fallback("s", "u", lambda: {"ok": True})
    assert result == {"ok": True}


async def test_mock_mode_fallback_can_be_async():
    client = _mock_mode_client()

    async def afb():
        return "async-result"

    assert await client.call_with_fallback("s", "u", afb) == "async-result"


# ---------------------------------------------------------------------------
# 缓存
# ---------------------------------------------------------------------------


def test_cache_key_is_deterministic():
    client = _mock_mode_client()
    k1 = client._make_cache_key("sys", "user", 0.1, 100, False)
    k2 = client._make_cache_key("sys", "user", 0.1, 100, False)
    assert k1 == k2


def test_cache_key_differs_on_inputs():
    client = _mock_mode_client()
    k1 = client._make_cache_key("sys", "user", 0.1, 100, False)
    k2 = client._make_cache_key("sys", "user", 0.2, 100, False)
    k3 = client._make_cache_key("sys", "other", 0.1, 100, False)
    assert k1 != k2
    assert k1 != k3


async def test_response_is_cached():
    client = _available_client("hello world")
    assert await client.chat("s", "u") == "hello world"
    assert await client.chat("s", "u") == "hello world"
    # 第二次命中缓存，fake 的 create 只被调用一次
    assert client._client.chat.completions.call_count == 1


# ---------------------------------------------------------------------------
# 真实路径（假 AsyncOpenAI）
# ---------------------------------------------------------------------------


async def test_chat_returns_content():
    client = _available_client("the answer")
    assert await client.chat("sys", "user") == "the answer"


async def test_chat_json_parses():
    client = _available_client('{"risks": [1, 2]}')
    result = await client.chat_json("sys", "user")
    assert result == {"risks": [1, 2]}


async def test_call_with_fallback_uses_llm_when_available():
    # 内容必须是合法 JSON（response_format_json=True 会走 chat_json）
    client = _available_client('"via-llm"')
    result = await client.call_with_fallback(
        "s", "u", lambda: "via-fallback", response_format_json=True
    )
    # 可用时优先用 LLM，而非 fallback
    assert result == "via-llm"


async def test_retry_eventually_succeeds():
    # 前两次失败，第三次成功；max_retries=3 应足够
    client = _available_client("recovered", fail_times=2)
    client.settings.llm_max_retries = 3
    assert await client.chat("s", "u") == "recovered"
    assert client._client.chat.completions.call_count == 3


async def test_retry_exhaustion_raises():
    client = _available_client("never", fail_times=99)
    client.settings.llm_max_retries = 1
    with pytest.raises(RuntimeError):
        await client.chat("s", "u")


async def test_call_with_fallback_recovers_on_llm_failure():
    # 可用但 LLM 持续失败 → 回退到 fallback
    client = _available_client("never", fail_times=99)
    client.settings.llm_max_retries = 1
    result = await client.call_with_fallback("s", "u", lambda: "safe-fallback")
    assert result == "safe-fallback"


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------


def test_global_singleton_set_get_reset():
    fake = _mock_mode_client()
    set_llm_client(fake)
    try:
        assert get_llm_client() is fake
    finally:
        reset_llm_client()
    # reset 后重新得到一个新实例（mock 模式，无网络）
    fresh = get_llm_client()
    assert isinstance(fresh, LLMClient)
    assert fresh is not fake
