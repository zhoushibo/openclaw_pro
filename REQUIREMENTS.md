# OpenClaw Pro - 企业级远程编排系统

> **需求文档 v1.0**
> 创建时间：2026-02-27
> 状态：待实现

---

## 1. 项目概述

### 1.1 项目目标
OpenClaw Pro 是一个基于 Agent Loop 的企业级远程编排系统，支持跨多台机器（本地、SSH、WinRM）执行工具调用，实现自动化运维和任务编排。

### 1.2 核心特性
- ✅ **Agent Loop 执行循环**（已完成，需优化）
- ❌ **工具系统**（部分完成，需补充）
- ❌ **多执行器支持**（本地/SSH/WinRM）
- ❌ **记忆系统**（上下文 + Token 管理）
- ❌ **安全策略**（路径控制、危险命令拦截）

---

## 2. 当前进度分析

### 2.1 已完成模块
| 模块 | 文件 | 状态 | 备注 |
|------|------|------|------|
| 配置管理 | `config.py` | ✅ 完成 | 支持 YAML + .env，多源配置 |
| 工具注册表 | `tools/registry.py` | ✅ 完成 | 全局工具管理 |
| 内置工具 | `tools/builtin.py` | 🟡 部分完成 | 工具类定义完成，但基类缺失 |
| 入口文件 | `main.py` | ✅ 完成 | 交互式 CLI 框架 |

### 2.2 缺失/不完整模块
| 模块 | 文件 | 问题 | 优先级 |
|------|------|------|--------|
| **工具基类** | `tools/base.py` | 空文件（26 字节） | **P0** |
| **记忆模块** | `core/memory.py` | 空文件（55 字节） | **P0** |
| **本地执行器** | `tools/executors/local.py` | 缺失 | **P0** |
| **连接管理器** | `core/connection.py` | 部分实现 | **P0** |
| **SSH 执行器** | `tools/executors/ssh.py` | 缺失 | P1 |
| **WinRM 执行器** | `tools/executors/winrm.py` | 缺失 | P1 |
| 安全策略 | `tools/security.py` | 缺失 | P1 |

---

## 3. 模块需求详解

### 3.1 工具基类 - `tools/base.py`

#### 需求描述
定义工具的抽象接口，所有工具必须继承此基类。

#### 接口定义
```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseTool(ABC):
    """工具基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """工具唯一标识符"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述（给 LLM 看）"""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """
        OpenAI Function Call 参数定义
        {
            "type": "object",
            "properties": {
                "param_name": {
                    "type": "string",
                    "description": "参数说明"
                }
            },
            "required": ["param1", "param2"]
        }
        """
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行工具
        
        Returns:
            {
                "ok": bool,
                "result": Any,  # 执行结果
                "error": str   # 错误信息（如果 ok=False）
            }
        """
        pass
```

#### 验收标准
- [ ] 定义了 `BaseTool` 抽象类
- [ ] 包含所有必需的抽象方法和属性
- [ ] 类型注解完整
- [ ] 文档字符串完整

---

### 3.2 记忆模块 - `core/memory.py`

#### 需求描述
实现对话记忆和 Token 计数功能，支持上下文窗口管理。

#### 接口定义
```python
from typing import List, Dict, Any, Optional
from datetime import datetime

class ConversationMemory:
    """对话记忆管理器"""
    
    def __init__(self, max_tokens: int = 8000):
        """
        Args:
            max_tokens: 最大上下文 token 数
        """
        self.max_tokens = max_tokens
        self._messages: List[Dict[str, Any]] = []
        self._token_count: int = 0
    
    async def add_user_message(self, content: str):
        """添加用户消息"""
        pass
    
    async def add_assistant_message(
        self, 
        content: str, 
        tool_calls: Optional[List[Dict]] = None
    ):
        """添加助手消息"""
        pass
    
    async def add_tool_result(self, tool_id: str, result: Dict):
        """添加工具执行结果"""
        pass
    
    async def get_history(self) -> List[Dict[str, Any]]:
        """获取当前对话历史"""
        pass
    
    def get_token_count(self) -> int:
        """获取当前 token 数"""
        pass
    
    async def is_within_limit(self) -> bool:
        """检查是否在 token 限制内"""
        pass
    
    async def truncate_oldest(self, keep_last_n: int = 5):
        """截断最旧的消息，保留最近 N 条"""
        pass
```

#### Token 计算规则
- 简单估算：中文字符 ≈ 1.5 tokens，英文字符 ≈ 0.3 tokens
- 或使用 `tiktoken` 库精确计算（可选）

#### 验收标准
- [ ] 实现消息添加/获取功能
- [ ] 实现 token 计数和限制检查
- [ ] 实现自动截断机制
- [ ] 支持 tool_calls 格式
- [ ] 文档和类型注解完整

---

### 3.3 本地执行器 - `tools/executors/local.py`

#### 需求描述
实现本地机器上的文件操作和命令执行。

#### 接口定义
```python
from typing import Dict, Any
from pathlib import Path

class LocalExecutor:
    """本地机器执行器"""
    
    def __init__(
        self,
        allowed_roots: List[str] = None,
        blocked_patterns: List[str] = None
    ):
        """
        Args:
            allowed_roots: 允许访问的根路径（白名单）
            blocked_patterns: 禁止访问的路径模式（黑名单）
        """
        self.allowed_roots = allowed_roots or [Path.cwd()]
        self.blocked_patterns = blocked_patterns or [
            "*/proc/*",
            "*/sys/*",
            "*/dev/*",
            "*/Windows/*",
            "*/System32/*"
        ]
    
    async def read_file(self, path: str) -> Dict[str, Any]:
        """
        读取文件
        
        Returns:
            {
                "ok": bool,
                "content": str,
                "path": str,
                "error": str  # 如果 ok=False
            }
        """
        pass
    
    async def write_file(self, path: str, content: str) -> Dict[str, Any]:
        """
        写入文件（自动创建父目录）
        
        Returns:
            {
                "ok": bool,
                "path": str,
                "error": str
            }
        """
        pass
    
    async def execute_command(
        self, 
        command: str, 
        timeout: int = 60
    ) -> Dict[str, Any]:
        """
        执行 Shell 命令
        
        Returns:
            {
                "ok": bool,
                "stdout": str,
                "stderr": str,
                "returncode": int,
                "command": str,
                "error": str
            }
        """
        pass
    
    async def list_files(self, path: str = ".") -> Dict[str, Any]:
        """
        列出目录文件
        
        Returns:
            {
                "ok": bool,
                "content": str,  # ls -la 输出
                "path": str,
                "error": str
            }
        """
        pass
    
    def _validate_path(self, path: str) -> bool:
        """验证路径是否安全"""
        pass
```

#### 安全规则
- 只能访问 `allowed_roots` 下的文件
- 不能访问 `blocked_patterns` 匹配的路径
- 阻止危险命令（如 `rm -rf /`）

#### 验收标准
- [ ] 实现所有 CRUD 操作
- [ ] 路径安全验证
- [ ] 危险命令拦截
- [ ] 错误处理完整
- [ ] 异步实现（asyncio）

---

### 3.4 连接管理器 - `core/connection.py`

#### 需求描述
管理多台机器的连接，支持本地、SSH、WinRM 三种类型。

#### 接口定义
```python
from typing import Dict, Optional
from .executors.base import BaseExecutor
from .executors.local import LocalExecutor
from .executors.ssh import SSHExecutor
from .executors.winrm import WinRMExecutor

class ConnectionManager:
    """连接管理器"""
    
    def __init__(self, config: Dict):
        """
        Args:
            config: 机器配置
            {
                "local": {"type": "local"},
                "ssh_servers": [
                    {
                        "name": "server-01",
                        "host": "192.168.1.100",
                        "username": "root",
                        "password": "...",
                        "port": 22
                    }
                ],
                "winrm_servers": [...]
            }
        """
        self.config = config
        self._executors: Dict[str, BaseExecutor] = {}
        self._init_executors()
    
    def _init_executors(self):
        """初始化所有执行器"""
        pass
    
    def get_executor(self, target: str) -> BaseExecutor:
        """
        获取目标机器的执行器
        
        Args:
            target: "local" 或机器名称
        
        Returns:
            BaseExecutor 实例
        
        Raises:
            ValueError: 如果目标机器不存在
        """
        pass
    
    def add_executor(self, name: str, executor: BaseExecutor):
        """动态添加执行器"""
        pass
    
    def remove_executor(self, name: str):
        """移除执行器"""
        pass
    
    def list_machines(self) -> List[str]:
        """列出所有可用机器名称"""
        return list(self._executors.keys())
    
    async def shutdown(self):
        """关闭所有连接"""
        pass
```

#### 验收标准
- [ ] 支持多机器管理
- [ ] 动态添加/移除机器
- [ ] 统一的执行器接口
- [ ] 完善的错误处理

---

### 3.5 SSH 执行器 - `tools/executors/ssh.py`

#### 需求描述
通过 SSH 协议执行远程命令和文件操作。

#### 技术选型
- 使用 `paramiko` 库
- 支持 Password 和 Private Key 认证

#### 接口定义
```python
from typing import Dict, Any

class SSHExecutor:
    """SSH 远程执行器"""
    
    def __init__(
        self,
        host: str,
        username: str,
        port: int = 22,
        password: Optional[str] = None,
        private_key_path: Optional[str] = None,
        allowed_roots: List[str] = None
    ):
        pass
    
    async def read_file(self, path: str) -> Dict[str, Any]:
        """读取远程文件（通过 SCP）"""
        pass
    
    async def write_file(self, path: str, content: str) -> Dict[str, Any]:
        """写入远程文件（通过 SCP）"""
        pass
    
    async def execute_command(self, command: str) -> Dict[str, Any]:
        """执行远程命令（通过 SSH）"""
        pass
    
    async def close(self):
        """关闭 SSH 连接"""
        pass
```

---

### 3.6 WinRM 执行器 - `tools/executors/winrm.py`

#### 需求描述
通过 WinRM 协议管理 Windows 机器。

#### 技术选型
- 使用 `pywinrm` 库
- 支持 HTTP/HTTPS

#### 接口定义（与 SSH 执行器相同）
```python
class WinRMExecutor:
    """WinRM 远程执行器（Windows）"""
    
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 5986,
        ssl: bool = True
    ):
        pass
    
    # 实现相同的接口：read_file, write_file, execute_command, close
```

---

### 3.7 安全策略 - `tools/security.py`

#### 需求描述
定义安全规则，防止危险操作。

#### 接口定义
```python
from typing import List

class SecurityPolicy:
    """安全策略"""
    
    @staticmethod
    def is_dangerous_command(command: str) -> bool:
        """检查是否危险命令"""
        dangerous_patterns = [
            "rm -rf /",
            "rm -rf */",
            "format c:",
            "del /s /q c:\\",
            "mkfs",
            "dd if=/dev/zero"
        ]
        return any(pattern.lower() in command.lower() 
                   for pattern in dangerous_patterns)
    
    @staticmethod
    def is_safe_path(
        path: str,
        allowed_roots: List[str],
        blocked_patterns: List[str]
    ) -> bool:
        """检查路径是否安全"""
        # 实现白名单检查
        # 实现黑名单检查
        pass
```

---

## 4. 实现指南

### 4.1 开发顺序建议
1. **P0 核心模块**
   - `tools/base.py`（工具基类）
   - `core/memory.py`（记忆模块）
   - `tools/executors/local.py`（本地执行器）
   - `core/connection.py`（连接管理器）

2. **P1 扩展模块**
   - `tools/executors/ssh.py`（SSH 执行器）
   - `tools/executors/winrm.py`（WinRM 执行器）
   - `tools/security.py`（安全策略）

3. **P2 优化**
   - 性能优化
   - 错误处理增强
   - 单元测试

### 4.2 技术栈
- **Python 3.8+**
- **异步框架**: `asyncio`
- **SSH**: `paramiko`
- **WinRM**: `pywinrm`
- **LLM 集成**: `httpx` / `openai`
- **配置**: `pydantic`, `python-dotenv`, `pyyaml`

### 4.3 测试策略
```bash
# 单元测试
pytest tests/unit/

# 集成测试
pytest tests/integration/

# 本地执行器测试
python -m pytest tests/test_local_executor.py
```

---

## 5. 验收标准

### 5.1 核心功能验收
- [ ] 工具基类定义清晰，所有内置工具继承正确
- [ ] 记忆模块支持上下文管理，token 限制有效
- [ ] 本地执行器支持文件操作和命令执行
- [ ] 连接管理器支持多机器，切换无问题

### 5.2 扩展功能验收
- [ ] SSH 执行器可连接远程机器并执行命令
- [ ] WinRM 执行器可管理 Windows 机器（可选）
- [ ] 安全策略有效拦截危险操作

### 5.3 代码质量验收
- [ ] 所有模块有完整的文档字符串
- [ ] 类型注解覆盖 80% 以上
- [ ] 单元测试覆盖率 > 70%
- [ ] 无代码异味和明显的 bug

---

## 6. 项目里程碑

| 里程碑 | 截止日期 | 负责人 | 状态 |
|--------|----------|--------|------|
| P0 核心模块完成 | 待定 | 待定 | ⏸️ 待开始 |
| P1 扩展模块完成 | 待定 | 待定 | ⏸️ 待开始 |
| 集成测试通过 | 待定 | 待定 | ⏸️ 待开始 |
| 文档完善 | 待定 | 待定 | ⏸️ 待开始 |

---

## 7. 附录

### 7.1 参考文档
- OpenAI Function Calling 规范
- Best Practices for Python AsyncIO
- Paramiko 文档

### 7.2 联系方式
- 项目负责人: 博（博）
- 需求编写者: Claw (AI Assistant)

---
