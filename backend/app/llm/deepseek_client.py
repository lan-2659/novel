import json
import time
from typing import Any, Iterator

from openai import OpenAI

from ..config import get_settings


class LLMError(Exception):
    """LLM 调用或解析失败时抛出。"""


class LLMClient:
    """LLM 客户端抽象接口，便于测试时替换为假实现。"""

    def generate_json(self, system: str, user: str) -> dict[str, Any]:
        raise NotImplementedError

    def stream_text(self, system: str, user: str) -> Iterator[str]:
        raise NotImplementedError


class DeepSeekClient(LLMClient):
    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.deepseek_model
        self._client: OpenAI | None = None
        if settings.deepseek_api_key:
            self._client = OpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
            )

    def _ensure_client(self) -> OpenAI:
        if self._client is None:
            raise LLMError("未配置 DEEPSEEK_API_KEY，请在项目根目录 .env 中设置")
        return self._client

    def generate_json(self, system: str, user: str, attempts: int = 2) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        last_err: Exception | None = None
        for i in range(attempts):
            try:
                client = self._ensure_client()
                resp = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.8,
                    response_format={"type": "json_object"},
                )
                text = resp.choices[0].message.content or ""
                data = json.loads(text)
                if not isinstance(data, dict):
                    raise LLMError("LLM 返回的不是 JSON 对象")
                return data
            except json.JSONDecodeError as exc:
                last_err = LLMError(f"LLM 未返回合法 JSON：{text[:200]}")
            except LLMError as exc:
                last_err = exc
            except Exception as exc:  # 网络 / 超时等
                last_err = LLMError(f"LLM 调用失败：{exc}")
            if i < attempts - 1:
                time.sleep(1.5 * (i + 1))
        raise last_err or LLMError("LLM 生成失败")

    def stream_text(self, system: str, user: str) -> Iterator[str]:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        try:
            client = self._ensure_client()
            stream = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.8,
                stream=True,
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                content = getattr(delta, "content", None)
                if content:
                    yield content
        except Exception as exc:
            raise LLMError(f"LLM 流式生成失败：{exc}")
