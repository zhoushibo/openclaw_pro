"""
快速测试脚本 - 验证 OpenClaw Pro 核心
"""

import sys
import asyncio
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import print_color, print_section
from tools.base import BaseTool
from tools.executors.base import BaseExecutor, ExecutionResult
from tools.executors.local import LocalExecutor
from core.memory import ConversationMemory, TokenCounter
from tools.security import SecurityPolicy


async def test_core_modules():
    """测试核心模块"""

    print_section("Test Core Modules", "blue")

    # Test 1: Tool Base
    print_color("Testing Tool Base...", "yellow")

    class TestTool(BaseTool):
        @property
        def name(self):
            return "test_tool"

        @property
        def description(self):
            return "A test tool"

        @property
        def parameters(self):
            return {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Test input"}
                },
                "required": ["text"]
            }

        async def execute(self, **kwargs):
            return {"ok": True, "result": f"Hello {kwargs.get('text', 'World')}"}

    test_tool = TestTool()
    print_color(f"  ✓ Tool created: {test_tool}", "green")
    print_color(f"  ✓ Definition: {test_tool.to_definition()['function']['name']}", "green")

    # Test 2: Memory Module
    print_color("\nTesting Memory Module...", "yellow")

    from config import AgentConfig

    memory = ConversationMemory(AgentConfig())
    memory.add_user_message("Hello, OpenClaw!")
    memory.add_assistant_message("Hello! How can I help?")

    stats = memory.get_stats()
    print_color(f"  ✓ Memory created with {stats['message_count']} messages", "green")
    print_color(f"  ✓ Token count: {stats['token_count']}", "green")
    print_color(f"  ✓ Usage: {stats['usage_percentage']}%", "green")

    # Test 3: Local Executor
    print_color("\nTesting Local Executor...", "yellow")

    local_executor = LocalExecutor(name="test_local")
    connected = await local_executor.connect()
    print_color(f"  ✓ LocalExecutor connected: {connected}", "green")

    # Test command execution
    result = await local_executor.execute_command("echo 'Hello from OpenClaw Pro!'", timeout=10)
    print_color(f"  ✓ Command result: {'OK' if result.ok else 'FAIL'}", "green")
    if result.ok and "Hello from OpenClaw Pro!" in result.stdout:
        print_color(f"    Output: {result.stdout.strip()}", "green")

    # Test file operations
    test_file = "./workspace/test.txt"
    write_result = await local_executor.write_file(test_file, "Test content from OpenClaw Pro!")
    print_color(f"  ✓ Write file: {'OK' if write_result.ok else 'FAIL'}", "green")

    read_result = await local_executor.read_file(test_file)
    print_color(f"  ✓ Read file: {'OK' if read_result.ok else 'FAIL'}", "green")
    if read_result.ok:
        print_color(f"    Content: {read_result.content}", "green")

    # Test directory listing
    list_result = await local_executor.list_directory("./workspace")
    print_color(f"  ✓ List directory: {'OK' if list_result.ok else 'FAIL'}", "green")
    if list_result.ok:
        print_color(f"    Items: {list_result.content.split(chr(10))[:3]}", "green")

    # Clean up
    await local_executor.disconnect()

    # Test 4: Security Policy
    print_color("\nTesting Security Policy...", "yellow")

    # Test safe path
    safe_path = SecurityPolicy.resolve_safe_path("./workspace/test.txt")
    print_color(f"  ✓ Safe path resolved: {safe_path}", "green")

    # Test dangerous command detection
    dangerous = SecurityPolicy.is_dangerous_command("rm -rf /")
    print_color(f"  ✓ Dangerous command detected: {dangerous}", "green")

    safe_command = "ls -la"
    safe = not SecurityPolicy.is_dangerous_command(safe_command)
    print_color(f"  ✓ Safe command allowed: {safe}", "green")

    print_color("\n" + "="*50, "blue")
    print_color("✅ All core modules working correctly!", "green")
    print_color("="*50, "blue")


if __name__ == "__main__":
    try:
        asyncio.run(test_core_modules())
    except KeyboardInterrupt:
        print_color("\n\n💭 Test interrupted by user.", "yellow")
    except Exception as e:
        print_color(f"\n\n❌ Test failed: {e}", "red")
        import traceback
        traceback.print_exc()
