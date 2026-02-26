"""
安全策略模块
实现路径白名单/黑名单校验、危险命令检测
"""

import os
import fnmatch
from pathlib import Path
from typing import List, Optional

import logging

logger = logging.getLogger(__name__)


class SecurityPolicy:
    """安全策略管理器
    实现多根目录白名单 + 系统路径黑名单
    """

    # 危险命令模式
    DANGEROUS_COMMANDS = [
        "rm -rf /",
        "rm -rf /*",
        "format c:",
        "del /s /q c:\\",
        ":(){ :|:& };:",
        "mkfs",
        "dd if=/dev/zero",
        "chmod -R 777 /",
        "chown -R root:root /",
        "shutdown -h now",
        "init 0",
        "shutdown /s 0",
    ]

    @staticmethod
    def resolve_safe_path(
        requested_path: str,
        must_exist: bool = True,
        allowed_roots: Optional[List[str]] = None,
        blocked_patterns: Optional[List[str]] = None
    ) -> Path:
        """解析路径并校验安全性

        Args:
            requested_path: 用户请求的路径
            must_exist: 文件是否必须存在
            allowed_roots: 允许的根目录列表
            blocked_patterns: 禁止的路径模式列表

        Returns:
            Path: 安全的绝对路径

        Raises:
            PermissionError: 如果路径不安全
        """
        if allowed_roots is None:
            allowed_roots = ["./workspace"]

        if blocked_patterns is None:
            blocked_patterns = [
                "*/Windows/*",
                "*/System32/*",
                "*/etc/*",
                "*/bin/*",
                "*/proc/*",
                "*/sys/*",
                "*/dev/*"
            ]

        requested = Path(requested_path)

        try:
            if must_exist and requested.exists():
                target_path = requested.resolve()
            else:
                parent = requested.parent.resolve() if requested.parent else Path.cwd().resolve()
                target_path = parent / requested.name
        except Exception as e:
            raise PermissionError(f"Path resolution failed: {str(e)}")

        # 黑名单检查
        if SecurityPolicy.is_blocked(target_path, blocked_patterns):
            logger.warning(f"Security Block: {target_path} matched blocked pattern")
            raise PermissionError(
                f"Access Denied: Path '{target_path}' is in a blocked system directory."
            )

        # 白名单检查
        if not SecurityPolicy.is_allowed(target_path, allowed_roots):
            logger.warning(f"Security Block: {target_path} is outside allowed roots")
            allowed_str = ", ".join([str(Path(p).resolve()) for p in allowed_roots])
            raise PermissionError(
                f"Access Denied: Path '{target_path}' is outside allowed roots.\n"
                f"Allowed roots: [{allowed_str}]"
            )

        return target_path

    @staticmethod
    def is_allowed(path: Path, allowed_roots: List[str]) -> bool:
        """检查路径是否在任一允许根目录下"""
        path_str = str(path).replace('\\', '/')

        for root in allowed_roots:
            try:
                root_resolved = Path(root).resolve()
                root_str = str(root_resolved).replace('\\', '/')

                if path_str.startswith(root_str):
                    if len(path_str) == len(root_str) or path_str[len(root_str)] == '/':
                        return True
            except Exception:
                continue

        return False

    @staticmethod
    def is_blocked(path: Path, blocked_patterns: List[str]) -> bool:
        """检查路径是否匹配任一黑名单模式"""
        path_str = str(path).replace('\\', '/')

        for pattern in blocked_patterns:
            pattern_std = pattern.replace('\\', '/')

            if fnmatch.fnmatch(path_str, f"*{pattern_std}*"):
                return True

        return False

    @staticmethod
    def is_dangerous_command(command: str) -> bool:
        """检查命令是否危险"""
        command_lower = command.lower()

        for pattern in SecurityPolicy.DANGEROUS_COMMANDS:
            if pattern.lower() in command_lower:
                return True

        return False

    @staticmethod
    def check_workspace_permissions(workspace: str = "./workspace") -> bool:
        """启动时检查工作目录权限"""
        workspace_path = Path(workspace)

        if not workspace_path.exists():
            try:
                workspace_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"✅ Created workspace: {workspace_path.resolve()}")
            except Exception as e:
                raise PermissionError(f"Cannot create workspace: {e}")

        if not os.access(workspace_path, os.R_OK | os.W_OK):
            raise PermissionError(f"Workspace '{workspace_path}' is not readable/writable.")

        logger.info(f"✅ Workspace permissions verified: {workspace_path.resolve()}")
        return True
