"""llm_client.py - OpenAI 兼容协议 LLM 调用封装"""
import httpx
from typing import AsyncIterator
from ..config import config


class LLMClient:
    def __init__(self, base_url: str = None, api_key: str = None, model: str = None):
        self.base_url = (base_url or config.llm_base_url).rstrip("/")
        self.api_key = api_key or config.llm_api_key
        self.model = model or config.llm_model

    async def chat(self, messages: list, stream: bool = False) -> str:
        """非流式：返回完整文本"""
        if not self.api_key:
            # 无 key：返回空，让上层走规则兜底
            return ""
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "messages": messages, "stream": False,
                      "temperature": 0.3},
            )
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]

    async def chat_stream(self, messages: list) -> AsyncIterator[str]:
        """流式：yield 文本分片"""
        if not self.api_key:
            return
        async with httpx.AsyncClient(timeout=120) as c:
            async with c.stream(
                "POST", f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "messages": messages, "stream": True,
                      "temperature": 0.3},
            ) as r:
                async for line in r.aiter_lines():
                    if line.startswith("data: "):
                        chunk = line[6:]
                        if chunk.strip() == "[DONE]":
                            break
                        try:
                            import json
                            d = json.loads(chunk)
                            delta = d["choices"][0].get("delta", {}).get("content")
                            if delta:
                                yield delta
                        except Exception:
                            pass


llm_client = LLMClient()