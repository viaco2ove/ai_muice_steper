"""llm_client.py - OpenAI 兼容协议 LLM 调用封装

支持技能级模型配置:
- models.json 的 models[] 定义可用模型(id/url/apiKey/model)
- skill_ai 指定默认模型 id
- 各 skill 可覆盖: { "<skill>": {"model": "<id>"} }
"""
import httpx
from typing import AsyncIterator, Optional
from ..config import config


class LLMClient:
    def __init__(self, base_url: str = None, api_key: str = None, model: str = None):
        self.base_url = (base_url or config.llm_base_url).rstrip("/")
        # url 可能已含 /chat/completions, 统一截到 base
        if self.base_url.endswith("/chat/completions"):
            self.base_url = self.base_url[: -len("/chat/completions")]
        self.api_key = api_key or config.llm_api_key
        # model: 实际请求体里的 model 名(如 deepseek-v4-pro), 不等于 id
        self.model = model or config.llm_model

    async def chat(self, messages: list, stream: bool = False) -> str:
        """非流式：返回完整文本"""
        if not self.api_key:
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


class LLMRegistry:
    """按 skill 名解析对应 LLMClient。
    models.json 结构:
      models: [{id, url, apiKey, model, ...}]
      skill_ai: {model: <id>}          # 默认
      <skill>: {model: <id>}           # 覆盖
    """

    def __init__(self):
        self.cfg = config.models_config
        self.models = {m["id"]: m for m in self.cfg.get("models", [])}
        self._cache = {}

    def _default_model_id(self) -> Optional[str]:
        return self.cfg.get("skill_ai", {}).get("model")

    def get_model_id_for(self, skill: str) -> Optional[str]:
        """skill=None 或 'skill_ai' 返回默认; 否则查 skill 覆盖, 回退默认"""
        if skill and skill != "skill_ai":
            ov = self.cfg.get(skill, {}).get("model")
            if ov and ov in self.models:
                return ov
        return self._default_model_id()

    def get_client(self, skill: str = None) -> LLMClient:
        """返回该 skill 对应的 LLMClient(带缓存)"""
        mid = self.get_model_id_for(skill)
        if mid in self._cache:
            return self._cache[mid]
        m = self.models.get(mid)
        if not m:
            # 找不到配置, 用全局默认
            c = LLMClient()
        else:
            c = LLMClient(
                base_url=m.get("url"),
                api_key=m.get("apiKey"),
                model=m.get("model") or m.get("id"),
            )
        self._cache[mid] = c
        return c


# 全局默认 client(向后兼容 llm_client 引用) + registry
llm_client = LLMClient()
registry = LLMRegistry()


def get_llm(skill: str = None) -> LLMClient:
    """获取 skill 对应的 LLMClient。skill=None 用默认(skill_ai)"""
    return registry.get_client(skill)