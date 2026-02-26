"""
工具基类模块
定义所有工具的统一接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """工具抽象基类
    所有工具必须继承此类并实现必要方法
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称（唯一标识）"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述（用于 LLM 理解）"""
        pass

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """
        工具参数定义（JSON Schema 格式）

        示例：
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"}
            },
            "required": ["path"]
        }
        """
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行工具逻辑

        Args:
            **kwargs: 工具参数

        Returns:
            Dict: 执行结果 {
                ok: bool,
                content/error: str,
                ...
            }
        """
        pass

    def to_definition(self) -> Dict[str, Any]:
        """转换为 LLM Function Calling 格式

        Returns:
            Dict: OpenAI Function Definition
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """验证参数是否符合定义

        Args:
            params: 待验证的参数

        Returns:
            bool: 是否有效
        """
        required = self.parameters.get("required", [])
        for param in required:
            if param not in params:
                logger.warning(f"Missing required parameter: {param}")
                return False
        return True

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"
