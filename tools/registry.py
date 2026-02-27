"""
工具注册表模块
修复循环导入问题，使用依赖注入模式
"""

from typing import Dict, List, Any, Optional, TYPE_CHECKING
from .base import BaseTool
import logging

# 使用 TYPE_CHECKING 避免运行时导入
if TYPE_CHECKING:
    from core.connection import ConnectionManager

logger = logging.getLogger(__name__)


class ToolRegistryError(Exception):
    """工具注册表异常"""
    pass


class ToolRegistry:
    """
    全局工具注册表
    使用依赖注入模式，避免循环导入
    """

    _tools: Dict[str, BaseTool] = {}
    _connection_manager: Optional['ConnectionManager'] = None
    _initialized: bool = False

    @classmethod
    def initialize(cls, connection_manager: 'ConnectionManager') -> None:
        """
        初始化注册表（依赖注入）

        Args:
            connection_manager: 连接管理器实例
        """
        cls._connection_manager = connection_manager
        cls._initialized = True

        logger.info("✅ ToolRegistry initialized with ConnectionManager")

    @classmethod
    def is_initialized(cls) -> bool:
        """检查是否已初始化"""
        return cls._initialized and cls._connection_manager is not None

    @classmethod
    def get_connection_manager(cls) -> 'ConnectionManager':
        """获取连接管理器（延迟导入）"""
        if not cls._connection_manager:
            raise ToolRegistryError(
                "ConnectionManager not initialized. "
                "Call ToolRegistry.initialize() first."
            )
        return cls._connection_manager

    @classmethod
    def register(cls, tool: BaseTool) -> None:
        """
        注册单个工具

        Args:
            tool: 工具实例
        """
        if tool.name in cls._tools:
            logger.warning(f"Tool '{tool.name}' already registered. Overwriting.")
        cls._tools[tool.name] = tool
        logger.debug(f"🔧 Registered tool: {tool.name}")

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
    def get_all(cls) -> Dict[str, BaseTool]:
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

        动态更新 target 参数的 enum 值
        """
        definitions = []

        for tool in cls._tools.values():
            try:
                definition = tool.to_definition()
                cls._update_target_enum(definition)
                definitions.append(definition)
            except Exception as e:
                logger.error(f"Failed to get definition for {tool.name}: {e}")

        return definitions

    @classmethod
    def _update_target_enum(cls, definition: Dict[str, Any]) -> None:
        """
        动态更新工具定义中的 target 参数 enum 值
        """
        if not cls._connection_manager:
            return

        try:
            func_def = definition.get('function', {})
            params = func_def.get('parameters', {})
            properties = params.get('properties', {})

            if 'target' in properties:
                machines = cls._connection_manager.list_machines()

                properties['target']['enum'] = machines
                properties['target'][
                    'description'
                ] = (
                    f"目标机器名称 (可选，默认本地). Available: {', '.join(machines)}"
                )

        except Exception as e:
            logger.debug(f"Failed to update target enum: {e}")

    @classmethod
    def has_tool(cls, name: str) -> bool:
        """
        检查工具是否已注册
        """
        return name in cls._tools

    @classmethod
    def clear(cls) -> None:
        """
        清空所有注册的工具
        """
        cls._tools.clear()
        logger.info("🧹 ToolRegistry cleared")

    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """
        获取注册表统计信息
        """
        return {
            "total_tools": len(cls._tools),
            "tool_names": list(cls._tools.keys()),
            "initialized": cls._initialized,
            "machines_available": cls._connection_manager.list_machines() if cls._connection_manager else []
        }


# 全局快捷函数
def register_tool(tool: BaseTool) -> None:
    """快捷注册工具"""
    ToolRegistry.register(tool)


def get_tool(name: str) -> BaseTool:
    """快捷获取工具"""
    return ToolRegistry.get(name)


def get_all_tools() -> List[Dict[str, Any]]:
    """快捷获取所有工具定义"""
    return ToolRegistry.get_all_definitions()
