"""
工具注册表模块
实现全局工具注册、动态机器枚举、错误处理
"""

from typing import Dict, Type, Optional, List
from .base import BaseTool
from ..core.connection import ConnectionManager
import logging


logger = logging.getLogger(__name__)


class ToolRegistryError(Exception):
    """工具注册表异常"""
    pass


class ToolRegistry:
    """
    全局工具注册表
    
    支持动态注册工具、获取工具定义、机器枚举、错误处理
    """

    _tools: Dict[str, BaseTool] = {}
    _connection_manager: Optional[ConnectionManager] = None
    _initialized: bool = False

    @classmethod
    def initialize(cls, connection_manager: ConnectionManager):
        """
        初始化注册表
        必须在工具注册前调用
        """
        cls._connection_manager = connection_manager
        cls._initialized = True
        logger.info("✅ ToolRegistry initialized")

    @classmethod
    def ensure_initialized(cls):
        """确保已初始化"""
        if not cls._initialized:
            if not cls._connection_manager:
                logger.warning("ToolRegistry not initialized, returning empty registry")

    @classmethod
    def set_connection_manager(cls, manager: ConnectionManager):
        """设置全局连接管理器（在 Agent 初始化时调用）"""
        cls._connection_manager = manager
        logger.info("✅ Connection Manager set in ToolRegistry")

    @classmethod
    def get_connection_manager(cls) -> ConnectionManager:
        """获取全局连接管理器"""
        if not cls._connection_manager:
            raise ToolRegistryError(
                "ConnectionManager not initialized. Call initialize() first."
            )
        return cls._connection_manager

    @classmethod
    def register(cls, tool: BaseTool):
        """
        注册单个工具
        
        Args:
            tool: 工具实例
            
        Raises:
            ToolRegistryError: 如果工具名已存在
        """
        if tool.name in cls._tools:
            logger.warning(f"Tool '{tool.name}' is already registered. Overwriting.")
        cls._tools[tool.name] = tool
        logger.debug(f"🔧 Registered tool: {tool.name}")

        return cls

    @classmethod
    def register_multiple(cls, tools: List[BaseTool]) -> None:
        """批量注册工具"""
        for tool in tools:
            cls.register(tool)
        logger.info(f"✅ Registered {len(tools)} tools")

    @classmethod
    def unregister(cls, name: str) -> bool:
        """
        注销工具
        
        Returns:
            bool: 是否成功注销
        """
        if name in cls._tools:
            del cls._tools[name]
            logger.debug(f"🔧 Unregistered tool: {name}")
            return True
        return False

    @classmethod
    def get(cls, name: str) -> BaseTool:
        """
        获取工具实例
        
        Args:
            name: 工具名称
            
        Returns:
            BaseTool: 工具实例
            
        Raises:
            ToolRegistryError: 如果工具不存在
        """
        if name not in cls._tools:
            available = list(cls._tools.keys())
            raise ToolRegistryError(
                f"Tool '{name}' not found. Available: {available}"
            )
        return cls._tools[name]

    @classmethod
    def get_all(cls):
        """
        获取所有已注册工具
        """
        return cls._tools.copy()

    @classmethod
    def get_all_names(cls) -> List[str]:
        """
        获取所有工具名称
        """
        return list(cls._tools.keys())

    @classmethod
    def get_all_definitions(cls) -> List[Dict[str, Any]]:
        """
        获取所有工具的 LLM Function Definition
        Returns:
            List[Dict]: 工具定义列表
        """
        definitions = []

        for tool in cls._tools.values():
            # 简化版本：生成基础定义
            definition = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            }

            # TODO: 动态更新 target 参数的 enum 值
            # cls._update_target_enum(definition)

            definitions.append(definition)

        logger.info(f"📋 Generated {len(definitions)} tool definitions")
        return definitions

    @classmethod
    def has_tool(cls, name: str) -> bool:
        """
        检查工具是否已注册
        """
        return name in cls._tools

    @classmethod
    def clear(cls):
        """
        清空所有注册的工具
        """
        cls._tools.clear()
        logger.info("🧹 ToolRegistry cleared")

    @classmethod
    def get_tool_stats(cls) -> Dict:
        """
        获取注册表统计信息
        """
        return {
            "total_tools": len(cls._tools),
            "tool_names": list(cls._tools.keys()),
            "initialized": cls._initialized,
            "machines_available": cls._connection_manager.list_machines() if cls._connection_manager else []
        } if cls._connection_manager else []

    @classmethod
    def _update_target_enum(cls, definition):
        """
        动态更新工具定义中的 target 参数 enum 值
        确保 LLM 知道可用的机器列表
        """
        try:
            if not cls._connection_manager:
                return

            func_def = definition.get("function", {})
            params = func_def.get("parameters", {})
            properties = params.get("properties", {})

            # 更新 target 参数的 enum
            if "target" in properties and cls._connection_manager:
                machines = cls._connection_manager.list_machines()
                if len(machines) > 0:
                    properties["target"]["enum"] = machines
                    properties["target"][
                        "description": properties["target"].get("description", "")
                    ]

            definition["function"]["parameters"]["properties"] = properties

        except Exception as e:
            # 静默失败也不抛错
            logger.debug(f"Failed to update target enum: {e}")

# 全局快捷函数
register_tool = ToolRegistry.register
get_tool = ToolRegistry.get
get_all_tools = ToolRegistry.get_all_definitions
