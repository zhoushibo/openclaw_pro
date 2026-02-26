"""
记忆模块
管理对话历史和 Token 计数
"""

import logging
from typing import List, Dict, Any, Optional
import tiktoken

from config import AgentConfig

logger = logging.getLogger(__name__)


class TokenCounter:
    """Token 计数器
    使用 tiktoken 精确计算 Token 数
    """

    def __init__(self, model_name: str = "gpt-4o"):
        try:
            self.encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            self.encoding = tiktoken.get_encoding("cl100k_base")
            logger.warning(f"Model {model_name} not found, using cl100k_base")

    def count_text(self, text: str) -> int:
        """计算文本 Token 数"""
        if not text:
            return 0
        return len(self.encoding.encode(text))

    def count_message(self, message: Dict[str, Any]) -> int:
        """计算单条消息的 Token 数

        包含：
        - 内容 Token
        - 角色 Token（约 4 个）
        - 工具调用额外开销
        """
        tokens = 4  # 基础开销

        # 角色
        role = message.get("role", "")
        tokens += self.count_text(role)

        # 内容
        content = message.get("content", "")
        if content:
            tokens += self.count_text(content)

        # 工具调用
        if "tool_calls" in message:
            for tc in message["tool_calls"]:
                tokens += self.count_text(str(tc))

        # 工具结果
        if "tool_call_id" in message:
            tokens += 4  # 额外开销

        return tokens

    def count_messages(self, messages: List[Dict[str, Any]]) -> int:
        """计算消息列表的总 Token 数"""
        total = 0
        for msg in messages:
            total += self.count_message(msg)
        return total + 100  # 额外预留系统提示开销


class ConversationMemory:
    """对话记忆管理器
    维护对话历史，管理 Token 预算
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.messages: List[Dict[str, Any]] = []
        self.token_counter = TokenCounter(config.llm_model)
        self.max_tokens = config.max_context_tokens

        logger.info(f"ConversationMemory initialized (max_tokens={self.max_tokens})")

    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        self.messages.append({
            "role": "user",
            "content": content
        })
        logger.debug(f"Added user message ({len(content)} chars)")

    def add_assistant_message(self, content: str, tool_calls: Optional[List] = None) -> None:
        """添加助手消息"""
        message = {
            "role": "assistant",
            "content": content
        }
        if tool_calls:
            message["tool_calls"] = tool_calls

        self.messages.append(message)
        logger.debug(f"Added assistant message ({len(content)} chars, {len(tool_calls or [])} tool calls)")

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        """添加工具执行结果"""
        # 限制结果长度防止 Token 爆炸
        if len(content) > 4000:
            content = content[:4000] + "... (truncated)"

        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content
        })
        logger.debug(f"Added tool result ({len(content)} chars)")

    def get_history(self) -> List[Dict[str, Any]]:
        """获取完整对话历史"""
        return self.messages.copy()

    def get_token_count(self) -> int:
        """获取当前 Token 数"""
        return self.token_counter.count_messages(self.messages)

    def is_within_limit(self) -> bool:
        """检查是否在 Token 限制内"""
        count = self.get_token_count()
        if count > self.max_tokens:
            logger.warning(f"Token limit exceeded: {count}/{self.max_tokens}")
            return False
        return True

    def get_usage_percentage(self) -> float:
        """获取 Token 使用百分比"""
        count = self.get_token_count()
        return (count / self.max_tokens) * 100

    def truncate_oldest(self, keep_last_n: int = 5) -> int:
        """截断最旧的消息

        Args:
            keep_last_n: 保留最近 N 条消息

        Returns:
            int: 删除的消息数
        """
        if len(self.messages) <= keep_last_n:
            return 0

        removed = len(self.messages) - keep_last_n
        self.messages = self.messages[-keep_last_n:]

        logger.info(f"Truncated {removed} messages, kept {keep_last_n}")
        return removed

    def truncate_to_fit(self, target_tokens: Optional[int] = None) -> int:
        """自动截断直到符合 Token 限制

        Args:
            target_tokens: 目标 Token 数（默认 80% 上限）

        Returns:
            int: 删除的消息数
        """
        if target_tokens is None:
            target_tokens = int(self.max_tokens * 0.8)

        removed = 0
        while self.get_token_count() > target_tokens and len(self.messages) > 2:
            # 保留第一条（通常是系统/用户），删除第二条
            self.messages.pop(1)
            removed += 1

        logger.info(f"Truncated {removed} messages to fit token limit")
        return removed

    def clear(self) -> None:
        """清空所有记忆"""
        self.messages.clear()
        logger.info("ConversationMemory cleared")

    def get_stats(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        return {
            "message_count": len(self.messages),
            "token_count": self.get_token_count(),
            "max_tokens": self.max_tokens,
            "usage_percentage": round(self.get_usage_percentage(), 2),
            "within_limit": self.is_within_limit()
        }

    def __len__(self) -> int:
        return len(self.messages)

    def __repr__(self) -> str:
        return f"ConversationMemory(messages={len(self.messages)}, tokens={self.get_token_count()})"
