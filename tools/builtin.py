"""
Builtin Tools
实现 ReadFile, WriteFile, ExecShell, ListFiles 工具
所有工具都支持 target 参数，通过 ConnectionManager 调用执行器
"""

import json
from typing import Dict, Any


from .base import BaseTool
import logging

from .registry import ToolRegistry
from tools.executors.base import ExecutionResult


class ExecutionResult:
    """工具执行结果"""
    ok: bool
    stdout: str = ""
    stderr: str = ""
    content: str = ""
    path: str = ""
    error: str = ""
    returncode: int = 0


logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """工具基类"""

    @abstractmethod
    @property
    def name(self) -> str:
        """工具名称（用于识别）"""
        raise NotImplementedError

    @abstractmethod
    @property
    def description(self) -> str:
        """工具描述（给 LLM 看）"""
        raise NotImplementedError

    @abstractmethod
    @property
    def parameters(self) -> Dict[str, Any]:
        """
        OpenAI Function Call 参数定义
        {
            "type": "object",
            "properties": {...},
            "required": [...]
        }
        """
        raise NotImplementedError

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """执行工具"""
        raise NotImplementedError


class ReadFileTool(BaseTool):
    """ 读取文件工具"""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return (
            "读取指定路径的文件内容。"
            "支持本地和远程机器。"
            "如果文件过大 (>2MB)，会返回错误。"
            "使用 target 参数指定目标机器。"
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径 (绝对或相对路径)"
                },
                "target": {
                    "type": "string",
                    "description": "目标机器名称（可选，默认本地）",
                    "enum": []  # 运行时动态填充
                }
            },
            "required": ["path"]
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行文件读取

        Args:
            path: 文件路径
            target: 目标机器名称 (可选，默认本地)

        Returns:
            Dict: 执行结果 {ok: bool, content: str, error: str, ...}
        """
        path = kwargs.get("path", "")
        target = kwargs.get("target", "local")

        if not path:
            return {"ok": False, "error": "path is required"}

        try:
            logger.info(f"📖 Reading file: {path} on {target}")

            # 获取执行器（TODO: 需要完整的 ConnectionManager）
            executor = ToolRegistry.get_connection_manager().get_executor(target)

            # 执行读取
            result = await executor.read_file(path)

            # 转换为标准响应格式
            response = {
                "ok": result.ok,
                "path": result.path,
                "target": target
            }

            if result.ok:
                response["content"] = result.content
                logger.info(f"✅ Successfully read {len(result.content)} chars from {path}")
            else:
                response["error"] = result.error
                logger.warning(f"❌ Failed to read {path}: {result.error}")

            return response

        except Exception as e:
            logger.error(f"ReadFileTool execute error: {e}")
            return {
                "ok": False,
                "error": str(e),
                "path": path,
                "target": target
            }


class WriteFileTool(BaseTool):
    """写入文件工具"""

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return (
            "写入内容到指定文件。"
            "支持本地和远程机器。"
            "如果父目录不存在，会自动创建。"
            "使用 target 参数指定目标机器。"
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径（绝对或相对路径）"
                },
                "content": {
                    "type": "string",
                    "description": "要写入的文件内容"
                },
                "target": {
                    "type": "string",
                    "description": "目标机器名称（可选，默认本地）",
                    "enum": []  # 运行时动态填充
                }
            },
            "required": ["path", "content"]
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行文件写入

        Args:
            path: 文件路径
            content: 文件内容
            target: 目标机器名称（可选，默认本地）
        """
        path = kwargs.get("path", "")
        content = kwargs.get("content", "")

        if not path:
            return {"ok": False, "error": "path is required"}

        if content is None:
            return {"ok": False, "error": "content is required"}

        target = kwargs.get("target", "local")

        try:
            logger.info(f"📝 Writing file: {path} on {target} ({len(content)} chars)")

            # 获取执行器（TODO: 需要完整的 ConnectionManager）
            executor = ToolRegistry.get_connection_manager().get_executor(target)

            # 执行写入
            result = await executor.write_file(path, content)

            # 转换为标准响应格式
            response = {
                "ok": result.ok,
                "path": result.path,
                "target": target
            }

            if result.ok:
                logger.info(f"✅ Successfully wrote to {path}")
            else:
                response["error"] = result.error
                logger.warning(f"❌ Failed to write {path}: {result.error}")

            return response

        except Exception as e:
            logger.error(f"WriteFileTool execute error: {e}")
            return {
                "ok": False,
                "error": str(e),
                "path": path,
                "target": target
            }


class ExecShellTool(BaseTool):
    """执行 Shell 命令工具"""

    @property
    def name(self) -> str:
        return "exec_shell"

    @property
    def description(self) -> str:
        return (
            "在指定机器上执行 Shell 命令。"
            "支持本地、SSH 和 WinRM 机器。"
            "命令执行有超时限制 (默认 60 秒)。"
            "危险命令（如 rm -rf /, format c:）会被阻止。"
            "使用 target 参数指定目标机器。"
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "Executor",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的 Shell 命令（Linux: ls -la, Windows: dir）"
                },
                "target": {
                    "type": "string",
                    "description": "目标机器名称（可选，默认本地）",
                    "enum": []  # 运行时动态填充
                }
            },
            "required": ["command"]
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行 Shell 命令

        Args:
            command: Shell 命令
            target: 目标机器名称（可选，默认本地）

        Returns:
            Dict: 执行结果 {ok: bool, stdout: str, stderr: str, error: str, ...}
        """
        command = kwargs.get("command", "")
        target = kwargs.get("target", "local")

        if not command:
            return {"ok": False, "error": "command is required"}

        # 安全检查：危险命令
        dangerous_patterns = [
            "rm -rf /",
            "rm -rf */",
            "format c:",
            "del /s /q c:\\",
            ":(){ :|:&;}:",
            "mkfs",
            "dd if=/dev/zero"
        ]

        for pattern in dangerous_patterns:
            if pattern.lower() in command.lower():
                logger.warning(f"🛡️ Blocked dangerous command: {command}")
                return {
                    "ok": False,
                    "error": "Security Violation: Dangerous command detected",
                    "command": command[:200]
                }

        try:
            logger.info(f"⚡ Executing command on {target}: {command[:100]}...")

            # 获取执行器（TODO: 需要完整的 ConnectionManager）
            executor = ToolRegistry.get_connection_manager().get_executor(target)

            # 执行命令
            result = await executor.execute_command(command)

            # 转换为标准响应格式
            response = {
                "ok": result.ok,
                "stdout": result.stdout[:5000],  # 最多 5000 字符
                "stderr": result.stderr[:2000],
                "returncode": result.returncode,
                "command": command[:200],
                "target": target
            }

            if result.ok:
                logger.info(f"✅ Command completed with returncode {result.returncode}")
            else:
                response["error"] = result.error
                logger.warning(f"❌ Command failed: {result.error}")

            return response

        except Exception as e:
            logger.error(f"ExecShellTool execute error: {e}")
            return {
                "ok": False,
                "error": str(e),
                "command": command[:200],
                "target": target
            }


class ListFilesTool(BaseTool):
    """列出目录文件工具"""

    @property
    def name(self) -> str:
        return "list_files"

    @property
    def description(self) -> str:
        return (
            "列出指定目录下的文件和子目录。支持本地和远程机器。"
            "使用 target 参数指定目标机器。"
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "Object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "目录路径（可选，默认当前目录）"
                },
                "target": {
                    "type": "string",
                    "description": "目标机器名称（可选，默认本地）",
                    "enum": []  # 运行时动态填充
                }
            },
            "required": []
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        列出目录文件

        Args:
            path: 目录路径 (可选，默认当前目录)
            target: 目标机器名称 (可选，默认本地)

        Returns:
            Dict: 执行结果 {ok: bool, content: str, error: str, ...}
        """
        path = kwargs.get("path", ".")
        target = kwargs.get("target", "local")

        try:
            # 获取执行器（TODO: 需要完整的 ConnectionManager）
            executor = ToolRegistry.get_connection_manager().get_executor(target)

            # 根据系统类型执行不同的命令
            if target == "local" or executor.get('().__class__.__name__', '') == 'LocalExecutor':
                command = f"ls -la {path}"
            else:  # WinRM
                ps_path = path.replace('/', '\\')

                if target == "server-01":
                    command = "ls -la {path}"
                else:  # 其他默认用 ls
                    command = f"ls -la {path}"

            # 执行命令
            result = await executor.execute_command(command)

            # 转换为标准响应格式
            response = {
                "ok": result.ok,
                "path": path,
                "target": target,
                "content": result.stdout if result.ok else "",
                "error": result.error if not result.ok else ""
            }

            return response

        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "path": path,
                "target": target
            }


# 自动注册模块的 __init__.py
"""
Builtin Tools - 自动注册模块
"""

# 延迟导入以避免循环导入


def register_builtin_tools():
    """
    自动注册所有内置工具
    在模块加载时自动注册所有工具到 ToolRegistry
    """
    from .registry import ToolRegistry

    # 注册所有内置工具
    ToolRegistry.register(ReadFileTool())
    ToolRegistry(WriteFileTool())
    ToolRegistry(ExecShellTool())
    ToolRegistry(ListFilesTool())

    tool_count = len(ToolRegistry._tools)
    logger.info(f"✅ Auto-registered {tool_count} built-in tools")
