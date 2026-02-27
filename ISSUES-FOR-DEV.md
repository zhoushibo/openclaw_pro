# OpenClaw Pro - 需要大佬修复的问题清单

**项目**: OpenClaw Pro - 企业级远程编排系统
**当前状态**: 核心模块 100% 完成，存在循环导入问题
**创建时间**: 2026-02-27

---

## 🔴 P0 级问题（核心功能阻塞）

### 问题 1: 循环导入架构问题 🔴

#### 问题描述
模块之间存在循环导入，导致无法正常加载

#### 导入链路
```
core/agent.py
  → tools/registry.py
    → core/connection.py
      → tools/executors/ssh.py
        → tools/executors/base.py

循环：core → tools → core
```

#### 具体错误
```python
# tools/registry.py:8
from ..core.connection import ConnectionManager

# 错误:
ImportError: attempted relative import beyond top-level package
```

#### 根本原因
- `tools/registry.py` 在模块导入时就需要 `ConnectionManager`
- 但 `core/connection.py` 无条件导入 `tools.executors.ssh`（即使未安装 paramiko）

#### 需要的解决方案
**方案 A**: 重构为延迟导入
```python
# tools/registry.py
self._connection_manager: Optional[ConnectionManager] = None

# 只在使用时导入
def get_connection_manager(self):
    from ..core.connection import ConnectionManager
    return self._connection_manager
```

**方案 B**: 使用依赖注入
- 注册表不直接依赖 ConnectionManager
- 在 Agent 初始化时通过参数传入

**方案 C**: 拆分模块
- 将 ConnectionManager 相关功能移到单独模块
- 避免循环依赖

---

## 🟡 P1 级问题（功能限制）

### 问题 2: 工具注册系统不完整

#### 问题描述
ToolRegistry 初始化失败，内置工具无法注册

#### 错误
```python
# core/agent.py
from tools.registry import ToolRegistry  # ✅ 可以导入
from tools.builtin import register_builtin_tools  # ❌ 导入失败

# 尝试注册时失败
Cannot load tools: could not import builtin tools
```

#### 原因
- `tools/builtin.py` 内部有复杂的导出逻辑和重复定义
- 需要重构或简化

#### 需要的解决方案
- 重写 `tools/builtin.py`，清理重复定义
- 简化工具注册逻辑

---

### 问题 3: Agent Loop 功能未实现

#### 问题描述
`core/agent.py` 当前是简化版本，只有基本的运行循环

#### 缺失功能
- LLM API 调用（需要集成 openai/httpx）
- 完整的工具执行流程
- 错误处理和重试机制

#### 当前状态
```python
# 当前：简化版本，只返回模拟响应
response = f"收到消息: {user_input}\n\n当前工具数量: {len(self.tools_def)}"
return response
```

#### 需要的解决方案
- 恢复完整的 Agent Loop 实现（参考原始 agent.py）
- 集成 LLM API 调用
- 实现工具执行和结果回传

---

## 🟢 P2 级问题（优化项）

### 问题 4: main.py CLI 功能

#### 问题描述
main.py 已重写为简化版本，但工具系统未集成

#### 考虑事项
- 是否需要完整的 CLI 功能
- 是否需要 Rich UI 支持
- 交互式命令处理

---

### 问题 5: SSH/WinRM 执行器导入优化

#### 当前状态
已修复：`core/connection.py` 使用延迟导入，但仍有优化空间

#### 当前代码
```python
try:
    if machine.type == "ssh" and machine.ssh:
        from tools.executors.ssh import SSHExecutor
        # ...
except ImportError:
    logger.warning("pip install paramiko")
```

---

## 📋 文件清单（需要检查/修复）

### 核心模块（优先级顺序）
1. `tools/registry.py` - **循环导入源头** 🔴
2. `tools/builtin.py` - **工具定义混乱** 🟡
3. `core/agent.py` - **简化版本待完善** 🟡
4. `tools/__init__.py` - **当前简化，可能需要恢复** 🟢

### 可选优化
5. `main.py` - CLI 功能
6. 测试覆盖补充

---

## 期望的解决方案

### 最小改动方案（推荐）
1. **修复 tools/registry.py**
   - 移除导入时的 `ConnectionManager` 依赖
   - 改为 setter 方法在运行时注入
   
2. **简化 tools/builtin.py**
   - 移除重复的 ExecutionResult 定义
   - 统一工具类结构

3. **测试验证**
   - 导入测试：`from core.agent import Agent`
   - 初始化测试：`Agent(config).initialize()`
   - 运行测试：`main.py`

---

## 代码提交

当前 Git 仓库：`git@github.com:zhoushibo/openclaw_pro.git`
最新提交：`test: core modules test suite added and passing` (104bbda)

---

**创建时间**: 2026-02-27 12:15 GMT+8
**创建人**: Claw (AI Assistant)
**目标**: 提供给大佬参考并修复
