"""
Agent Loop Module
实现完整的 Agent 执行循环，包括 LLM 调用、工具执行、结果回传
"""

import json
import asyncio
from typing import Optional, Dict, List, Any
from loguru import logger

from .memory import ConversationMemory
from .connection import ConnectionManager
from config import AgentConfig


class AgentError(Exception):
    """Agent 异常"""
    pass


class ToolExecutionError(Exception):
    """工具执行异常"""
    pass


class Agent:
    """
    Agent 核心执行器
    实现完整的 Agent Loop：
    思考 → 工具调用 → 执行 → 结果回传 → 最终回复
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.connection_manager: Optional[ConnectionManager] = None
        self.tools_definitions: List[Dict[str, Any]] = []
        self.iteration: int = 0
        self._running = False
        self._memory: Optional[ConversationMemory] = None
        self._callbacks: Dict[str, List] = {}

    def register_callback(self, event: str, callback):
        """注册回调函数"""
        if event in self._callbacks:
            self._callbacks[event].append(callback)
        else:
            raise ValueError(f"Unknown event: {event}")

    def _trigger_callback(self, event: str):
        """触发回调"""
        if event in self._callbacks:
            for callback in self._callbacks[event]:
                try:
                    callback()
                except Exception as e:
                    pass

    async def initialize(self, connection_manager: ConnectionManager):
        """初始化 Agent 和连接"""
        self.connection_manager = connection_manager
        self._memory = ConversationMemory(config=self.config)
        self._running = True
        self.iteration = 0
        self._callbacks = {}

        # TODO: 加载工具定义（需要先实现 tools/registry.py）
        # from tools import ToolRegistry
        # from tools import builtin
        # ToolRegistry.initialize(connection_manager)

        # 注册所有工具
        from tools.builtin import register_builtin_tools
        from tools import ToolRegistry

        ToolRegistry.initialize(connection_manager)
        register_builtin_tools(self)

        # 获取工具定义
        self.tools_def = ToolRegistry.get_all_definitions()

        # 显示可用机器
        machines = self.connection_manager.list_machines()
        tools = ToolRegistry.get_all_names()
        # TODO: 使用 Rich console UI（可选）

        logger.info(f"🤖 Agent initialized. Machines: {machines}, Tools: {tools}")
        logger.info(f"📋 Loaded {len(self.tools_def)} tool definitions")

    async def run(self, user_input: str, callback=None) -> str:
        """运行 Agent 主循环"""
        if not self.connection_manager:
            logger.error("❌ Agent not initialized")
            return "❌ Agent not initialized"

        self._running = True
        self.iteration = 0

        # 添加用户消息到记忆
        await self._add_user_message(user_input)
        self._trigger_callback("on_thought", iteration=1)

        final_response = ""

        while self._running and self.iteration < self.config.max_iterations:
            self.iteration += 1

            # Token 检查
            from .config import AgentConfig
            current_tokens = self._memory.get_token_count()
            max_tokens = self.config.max_context_tokens

            if not await self._memory.is_within_limit():
                logger.warning(f"⚠️ Token 上限警告 ({current_tokens} > {max_tokens})")
                await self._memory.truncate_oldest(keep_last_n=5)

            logger.info(f"--- Agent Iteration {self.iteration}/{self.config.max_iterations} (Tokens: {current_tokens}) ---")
            self._trigger_callback("on_thought", iteration=self.iteration)

            # Step 1: LLM 思考
            llm_response = await self._call_llm()
            self._add_assistant_message(llm_response["content"], llm_response.get("tool_calls"))

            # Step 2: 检查工具调用
            tool_calls = self._extract_tool_calls(llm_response)

            # 如果没有工具调用，返回最终回复
            if not tool_calls:
                final_response = llm_response["content"]
                self._trigger_callback("on_final_response", response=final_response)
                break

            # Step 3: 执行工具
            self._trigger_callback("on_tool_execute", count=len(tool_calls))

            for tool_id, tool_call in tool_calls.items():
                await self._execute_single_tool(tool_id, tool_call, callback=callback)
                result = await self._execute_single_tool(tool_id, tool_call)
                self._add_tool_result(tool_id, result)
                self._trigger_callback("on_tool_result", tool=tool_call, result=result)

            # Step 4: 继续 Loop
            await asyncio.sleep(0.1)

            # 检查最大循环次数
            if self.iteration >= self.config.max_iterations:
                final_response = "⚠️ 达到最大循环次数，任务终止。"
                self._trigger_callback("on_error", error="Max iterations reached")
                break

        if self._running:
            self._running = False

        # 输出最终回复
        if final_response:
            self._add_final_response(final_response)
            self._trigger_callback("on_final_response", response=final_response)

        logger.info(f"✅ Agent 最终回复: {final_response[:100]}...")
        return final_response

    async def _call_llm(self) -> Dict[str, Any]:
        """调用 LLM API"""
        try:
            responses = []
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config.base_url,
                    headers={
                        "Authorization": f"Bearer {self.config.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.config.llm_model,
                        "messages": await self._memory.get_history(),
                        "temperature": 0.7,
                        "max_tokens": 2048,
                        "stream": False
                    }
                ) as resp:
                    return await resp.json()

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise AgentError(f"LLM call failed: {str(e)}")

    def _extract_tool_calls(self, llm_response: Dict) -> Dict[str, dict]:
        """从 LLM 响应中提取工具调用"""
        try:
            import json

            tc = llm_response.get("tool_calls", [])
            validated_calls = []

            for tc in tc:
                if not all(k in tc for k in ["id", "name", "arguments"]):
                    continue

                # 解析参数
                try:
                    if isinstance(tc["arguments"], str):
                        tc["arguments"] = json.loads(tc["arguments"])
                    else:
                        tc["arguments"] = {}

                validated_calls.append(tc)

            return {tc["id"]: tc for tc in validated_calls}

        except Exception as e:
            logger.warning(f"Tool call extraction failed: {e}")
            return {}

    async def _execute_single_tool(self, tool_id: str, tool_call: dict, callback=None) -> dict:
        """执行单个工具调用"""
        try:
            name = tool_call["name"]
            args = tool_call.get("arguments", {})

            # 获取工具实例（TODO: 需要完整的 ToolRegistry）
            # from tools import ToolRegistry
            # tool = ToolRegistry.get(name)
            # result = await tool.execute(**args)

            # 简化版：硬编码几个常用工具
            if name == "read_file":
                from .core.connection import ConnectionManager
                conn: ConnectionManager = self.connection_manager

                executor = conn.get_executor(args.get("target", "local"))

                # 执行读取
                result = await executor.read_file(args.get("path"))

                response = {
                    "ok": result.ok,
                    "content": result.content if result.ok else None,
                    "path": result.path,
                    "target": args.get("target", "local"),
                    "error": result.error if not result.ok else None
                }

            elif name == "write_file":
                from .core.connection import ConnectionManager
                conn: conn = self.connection_manager

                executor = conn.get_executor(args.get("target", "local"))

                # 执行写入
                result = await executor.write_file(
                    args.get("path"),
                    args.get("content", "")
                )

                response = {
                    "ok": result.ok,
                    "path": result.path,
                    "target": args.get("target", "local"),
                    "error": result.error if not result.ok else None
                }

            elif name == "exec_shell":
                from .core.connection import ConnectionManager
                conn = conn = self.connection_manager

                executor = conn.get_executor(args.get("target", "local"))

                # 执行命令
                result = await executor.execute_command(
                    args.get("command", "")
                )

                response = {
                    "ok": result.ok,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                    "target": args.get("target", "local"),
                    "command": args.get("command", "")[:200],  # 截断命令
                    "error": result.error if not result.ok else None
                }

            else:
                response = {
                    "ok": False,
                    "error": f"Unknown tool: {name}"
                }

            return response

        except Exception as e:
            logger.error(f"Tool execution failed ({name}): {e}")
            return {
                "ok": False,
                "error": str(e)
            }

    def _add_user_message(self, message: str):
        """添加用户消息"""
        if self._memory:
            asyncio.create_task(self._memory.add_user_message(message))

    def _add_assistant_message(self, content: str, tool_calls=None):
        """添加 Assistant 消息"""
        if self._memory:
            asyncio.create_task(self._memory.add_assistant_message(content, tool_calls=tool_calls))

    def _add_tool_result(self, tool_id: str, result: dict):
        """添加工具执行结果"""
        if self._memory:
            asyncio.create_task(self._memory.add_tool_result(tool_id, result))

    def _add_final_response(self, content: str):
        """添加最终回复"""
        if self._memory:
            asyncio.create_task(self._memory.add_final_response(content))

    def _add_thought(self, iteration: int, **kwargs):
        """记录思考过程"""
        if self._callbacks:
            for callback in self._callbacks.get("on_thought", []):
                try:
                    callback(iteration=iteration, **kwargs)
                except:
                    pass

    def _add_tool_execute(self, count: int, **kwargs):
        """记录工具执行"""
        if self._callbacks:
            for callback in self._callbacks.get("on_tool_execute", []):
                try:
                    callback(count=count, **kwargs)
                except:
                    pass

    def _add_tool_result(self, tool_id: str, result: dict, **kwargs):
        """记录工具结果"""
        if self._callbacks:
            for callback in self._callbacks.get("on_tool_result", []):
                try:
                    callback(tool_id=tool_id, result=result, **kwargs)
                except:
                    pass

    def _add_final_response(self, content: str, **kwargs):
        """记录最终回复"""
        if self._callbacks:
            for callback in self._callbacks.get("on_final_response", []):
                try:
                    response=content, **kwargs)
                except:
                    pass

    def _add_error(self, error: str, **kwargs):
        """记录错误"""
        if self._callbacks:
            for callback in self._callbacks.get("on_error", []):
                try:
                    error=error, **kwargs)
                except:
                    pass

    def get_stats(self) -> dict:
        """获取 Agent 统计信息"""
        return {
            "iterations": self.iteration,
            "is_running": self._running,
            "machines": self.connection_manager.list_machines() if self.connection_manager else [],
            "tools": self.tools_def,
            "callbacksRegistered": list(self._callbacks.keys())
        } if self._memory else {}

    def shutdown(self):
        """关闭所有连接"""
        if self.connection_manager:
            await self.connection_manager.shutdown()

        logger.info("🔌 Agent shutdown complete")
