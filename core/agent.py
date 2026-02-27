"""
Agent 核心模块
完整的 Agent Loop 实现，包括 LLM 调用、工具执行、结果回传
"""

import json
import asyncio
from typing import Optional, List, Dict, Any, Callable

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

import logging

from .memory import ConversationMemory
from .connection import ConnectionManager

from llm.client import LLMClient
from tools.registry import ToolRegistry
from tools.builtin import register_builtin_tools

from config import AgentConfig

logger = logging.getLogger(__name__)

console = Console()


class AgentError(Exception):
    """Agent 异常"""
    pass


class Agent:
    """
    Agent 核心执行器

    完整的 Agent Loop：
    思考 → 工具调用 → 执行 → 结果回传 → 最终回复
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.llm: Optional[LLMClient] = None
        self.memory: Optional[ConversationMemory] = None
        self.connection_manager: Optional[ConnectionManager] = None
        self.tools_definitions: List[Dict[str, Any]] = []
        self.iteration = 0
        self._running = False
        self._callbacks: Dict[str, List[Callable]] = {
            "on_think": [],
            "on_tool_execute": [],
            "on_tool_result": [],
            "on_final_response": [],
            "on_error": []
        }

    def register_callback(self, event: str, callback: Callable) -> None:
        """注册回调函数"""
        if event in self._callbacks:
            self._callbacks[event].append(callback)
        else:
            raise ValueError(f"Unknown event: {event}")

    def _trigger_callback(self, event: str, *args, **kwargs) -> None:
        """触发回调"""
        for callback in self._callbacks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(*args, **kwargs))
                else:
                    callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Callback error for {event}: {e}")

    async def initialize(self) -> None:
        """初始化 Agent"""
        logger.info("🚀 Initializing Agent...")

        # 初始化 LLM 客户端
        self.llm = LLMClient(self.config)

        # 初始化记忆
        self.memory = ConversationMemory(self.config)

        # 初始化连接管理器
        self.connection_manager = ConnectionManager(self.config)
        await self.connection_manager.initialize()

        # 初始化工具注册表（依赖注入）
        ToolRegistry.initialize(self.connection_manager)

        # 注册内置工具
        register_builtin_tools()

        # 获取工具定义
        self.tools_definitions = ToolRegistry.get_all_definitions()

        # 显示状态
        machines = self.connection_manager.list_machines()
        tools = ToolRegistry.get_all_names()

        console.print(Panel(
            f"[bold]🌐 Machines:[/bold] {', '.join(machines)}\n"
            f"[bold]🔧 Tools:[/bold] {', '.join(tools)}",
            title="Agent Initialized",
            border_style="green"
        ))

        logger.info(f"✅ Agent initialized. Machines: {machines}, Tools: {tools}")

    async def run(self, user_input: str) -> str:
        """运行 Agent 主循环"""
        if not self.connection_manager:
            raise AgentError("Agent not initialized. Call initialize() first.")

        self._running = True
        self.iteration = 0
        final_response = ""

        # 添加用户消息
        self.memory.add_user_message(user_input)

        console.print(f"\n[bold blue]👤 User:[/bold blue] {user_input}\n")
        logger.info(f"📥 Received: {user_input[:100]}...")

        try:
            while self._running and self.iteration < self.config.max_iterations:
                self.iteration += 1

                # Token 检查
                current_tokens = self.memory.get_token_count()

                if not self.memory.is_within_limit():
                    console.print(Panel(
                        f"⚠️ Token 上限 ({current_tokens} > {self.config.max_context_tokens})",
                        style="yellow"
                    ))
                    self.memory.truncate_oldest(keep_last_n=5)

                logger.info(f"--- Iteration {self.iteration}/{self.config.max_iterations} ---")

                # Step 1: LLM 思考
                self._trigger_callback("on_think", iteration=self.iteration)
                console.print(f"[dim]🤔 Thinking... (Step {self.iteration})[/dim]")

                llm_response = await self._call_llm()

                # 保存 Assistant 消息
                self.memory.add_assistant_message(
                    llm_response.get("content", ""),
                    llm_response.get("tool_calls")
                )

                # Step 2: 检查工具调用
                tool_calls = self._extract_tool_calls(llm_response)

                if not tool_calls:
                    final_response = llm_response.get("content", "")
                    self._trigger_callback("on_final_response", response=final_response)
                    break

                # Step 3: 执行工具
                console.print(f"[yellow]⚡ Executing {len(tool_calls)} tool(s)...[/yellow]")

                for tool_call in tool_calls:
                    self._trigger_callback("on_tool_execute", tool_call=tool_call)

                    tool_result = await self._execute_single_tool(tool_call)

                    self._trigger_callback("on_tool_result", tool_call=tool_call, result=tool_result)

                # Step 4: 结果回传
                self.memory.add_tool_result(
                    tool_call.get("id", "unknown"),
                    json.dumps(tool_result, ensure_ascii=False)
                )

                await asyncio.sleep(0.1)

                if self.iteration >= self.config.max_iterations:
                    final_response = "⚠️ 达到最大循环次数，任务终止。"
                    logger.warning("⚠️ Reached max iterations")

        except Exception as e:
            logger.error(f"Agent run error: {e}")
            self._trigger_callback("on_error", error=e)
            final_response = f"❌ 发生错误：{str(e)}"
            raise

        finally:
            self._running = False

        console.print(f"\n[bold green]🤖 Agent:[/bold green]")
        console.print(Markdown(final_response))

        return final_response

    async def _call_llm(self) -> Dict[str, Any]:
        """调用 LLM"""
        try:
            response = await self.llm.chat(
                messages=self.memory.get_history(),
                tools=self.tools_definitions if self.tools_definitions else None
            )
            return response
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise AgentError(f"LLM call failed: {str(e)}")

    def _extract_tool_calls(self, llm_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从 LLM 响应中提取工具调用"""
        tool_calls = llm_response.get("tool_calls", [])

        if not tool_calls:
            return []

        validated_calls = []

        for tc in tool_calls:
            if not all(k in tc for k in ["id", "name", "arguments"]):
                logger.warning(f"Invalid tool call format: {tc}")
                continue

            try:
                if isinstance(tc["arguments"], str):
                    tc["arguments"] = json.loads(tc["arguments"])
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse tool arguments: {e}")
                tc["arguments"] = {}

            validated_calls.append(tc)

        return validated_calls

    async def _execute_single_tool(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """执行单个工具调用"""
        name = tool_call.get("name")
        args = tool_call.get("arguments", {})
        call_id = tool_call.get("id", "unknown")

        if not name:
            return {"ok": False, "error": "Tool name is required"}

        try:
            logger.info(f"🔧 Executing tool: {name} with args: {args}")

            tool = ToolRegistry.get(name)
            result = await tool.execute(**args)

            target = args.get("target", "local")

            if result.get("ok"):
                console.print(f" ✅ [green]{name}[/green] on [cyan]{target}[/cyan]")
            else:
                console.print(
                    f" ❌ [red]{name}[/red] on [cyan]{target}[/cyan]: {result.get('error', 'Unknown error')}"
                )

            return result

        except Exception as e:
            logger.error(f"Tool execution failed: {name}: {e}")

            error_result = {
                "ok": False,
                "error": str(e)
            }

            console.print(f" ❌ [red]{name}[/red] failed: {e}")

            return error_result

    async def shutdown(self) -> None:
        """关闭 Agent"""
        logger.info("🛑 Shutting down Agent...")
        self._running = False

        if self.connection_manager:
            await self.connection_manager.shutdown()

        console.print("[dim]Agent shutdown complete.[/dim]")

    def get_stats(self) -> Dict[str, Any]:
        """获取 Agent 统计信息"""
        return {
            "iterations": self.iteration,
            "token_count": self.memory.get_token_count() if self.memory else 0,
            "message_count": len(self.memory.get_history()) if self.memory else 0,
            "machines": self.connection_manager.list_machines() if self.connection_manager else [],
            "tools": ToolRegistry.get_all_names()
        }
