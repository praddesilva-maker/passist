#!/usr/bin/env python3
"""
GLM / Qwen 30B LLM Client.

Provides a single factory function, :func:`create_chat_model`, that returns a
LangChain ``BaseChatModel``:

* Online  - ``langchain_openai.ChatOpenAI`` pointed at the OpenAI-compatible
  GLM 4 / Qwen endpoint configured via ``ModelConfig`` (``base_url`` +
  ``api_key``).  Works with any OpenAI-compatible API (Zhipu GLM-4, Qwen, etc).
* Offline - a deterministic :class:`OfflineChatModel` used when no API key is
  available (``USE_OFFLINE_MODEL=1`` or empty ``GLM_API_KEY``).  The offline
  model does no generation; ``invoke`` returns a structured ``AIMessage``
  carrying an ``[offline]`` notice, and exposes ``is_offline = True`` so callers
  can branch to their deterministic rule/template paths.  This keeps the whole
  system runnable and testable without network access.
"""

from typing import Any, ClassVar, List, Optional, Union

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from pydantic import Field

from config import ModelConfig


class OfflineModelUnavailableError(RuntimeError):
    """Raised when the offline (no-network) model is asked to generate text."""


class OfflineChatModel(BaseChatModel):
    """A deterministic stand-in chat model for offline/testing operation.

    It never touches the network.  ``invoke``/``ainvoke`` return a structured
    ``AIMessage`` containing an ``[offline]`` notice rather than raising, so a
    caller that forgets to branch still gets a well-formed response.  Callers
    should check ``is_offline = True`` and use their rule-based fallback.
    """

    model_name: str = Field(default="offline")
    temperature: float = Field(default=0.0)
    max_tokens: Optional[int] = None
    is_offline: bool = True

    @property
    def _llm_type(self) -> str:
        return "offline-chat-model"

    OFFLINE_NOTICE: ClassVar[str] = (
        "[offline] No GLM/Qwen API key is configured, so no text was generated. "
        "The caller should use its deterministic rule-based fallback."
    )

    def _result(self):
        from langchain_core.outputs import ChatGeneration, ChatResult

        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=self.OFFLINE_NOTICE))]
        )

    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None,
                  run_manager: Any = None, **kwargs: Any):
        # Returns a well-formed AIMessage rather than raising: a BaseChatModel
        # whose invoke() raises is surprising, and every caller already gates on
        # ``is_offline`` before generating.  Inspect ``is_offline`` to branch.
        return self._result()

    async def _agenerate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None,
                         run_manager: Any = None, **kwargs: Any):
        return self._result()

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        # Tool calling is unavailable offline.
        raise OfflineModelUnavailableError("Tool calling is not available offline.")


def create_chat_model(
    model_config: Optional[ModelConfig] = None,
    *,
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> BaseChatModel:
    """Create a chat model from a :class:`ModelConfig`.

    Returns ``ChatOpenAI`` (OpenAI-compatible) when credentials are present and
    the offline flag is not set; otherwise returns :class:`OfflineChatModel`.

    ``model_name`` / ``temperature`` / ``max_tokens`` override the corresponding
    config fields, so simple callers need not build a :class:`ModelConfig`.
    """
    from langchain_openai import ChatOpenAI

    cfg = model_config or ModelConfig()
    if model_name is not None:
        cfg.model_name = model_name
    if temperature is not None:
        cfg.temperature = temperature
    if max_tokens is not None:
        cfg.max_tokens = max_tokens

    if cfg.use_offline or not cfg.api_key:
        return OfflineChatModel(model_name="offline", temperature=cfg.temperature,
                                max_tokens=cfg.max_tokens)


    return ChatOpenAI(
        model=cfg.model_name,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        api_key=cfg.api_key,  # type: ignore[arg-type]
        base_url=cfg.base_url,
    )


def extract_text(response: Union[str, BaseMessage, AIMessage, Any]) -> str:
    """Normalize an LLM response (AIMessage / str / dict) to plain text."""
    if response is None:
        return ""
    if isinstance(response, str):
        return response
    content = getattr(response, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(response, dict):
        return str(response.get("content", ""))
    return str(response)