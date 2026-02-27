"""
LLM 客户端模块
封装 OpenAI API 调用，支持 Function Calling
"""

import logging
from typing import List, Dict, Any, Optional

from openai import AsyncOpenAI
from config import AgentConfig

logger = logging.getLogger(__name__)


class LLMClient:
    """LLM 客户端"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url
        )
        self.model = config.llm_model

        logger.info(f"✅ LLMClient initialized with model: {self.model}")

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """发送消息给 LLM"""
        try:
            logger.debug(f"Calling LLM with {len(messages)} messages")

            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature
            }

            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            if max_tokens:
                kwargs["max_tokens"] = max_tokens

            response = await self.client.chat.completions.create(**kwargs)

            choice = response.choices[0]
            message = choice.message

            result = {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": []
            }

            if message.tool_calls:
                for tc in message.tool_calls:
                    result["tool_calls"].append({
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    })

            logger.info(f"🔧 LLM returned {len(result['tool_calls'])} tool calls")

            return result

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def count_tokens(self, text: str) -> int:
        """估算文本 Token 数"""
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 0.6 + other_chars * 0.25)
