"""
Main Entry Point - OpenClaw 主程序
"""

import asyncio
import sys
from pathlib import Path


# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console

from config import ConfigManager, AgentConfig
from core.agent import Agent
from core.connection import ConnectionManager
from tools.builtin import register_builtin_tools


async def interactive_mode(agent: Agent):
    """交互式 CLI 模式"""
    console = Console()

    console.print("[bold blue]🚀 OpenClaw Pro Starting...[/bold]\n")

    try:
        # 加载配置
        config_manager = ConfigManager()
        config = config_manager.get_config()

        # 创建连接管理器
        conn_manager = ConnectionManager(config)
        await conn_manager.initialize()

        # 创建并初始化 Agent
        agent = Agent(config)
        await agent.initialize(conn_manager)

        # 显示可用信息
        console.print("[green]✅ 初始化完成！[/green]")
        stats = agent.get_stats()
        console.print(
            f"[dim]当前状态:[/dim]\n"
            f"  工具数量: {stats['tools_count']}\n"
            f"  机器: {', '.join(stats['machines'])}\n"
        )
        console.print("[bold blue]输入 'quit' 或 'exit' 退出[/bold blue]")
        print()

        # 交互式循环
        while True:
            try:
                user_input = console.input("[bold blue]👤 You:[/bold blue] ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ['quit', 'exit', 'q', 'exit']:
                    break

                # 运行 Agent
                console.print("[dim]⏳ 思考中...[/dim]")
                response = await agent.run(user_input)

                # 显示回复
                console.print(f"[bold green]🤖 AI:[/bold green] {response}")

            except KeyboardInterrupt:
                console.print("\n[yellow]⛔ 用户中断[/yellow]")
                break
            except Exception as e:
                console.print(f"[bold red]❌ 错误: {e}[/bold red]")

    except Exception as e:
        console.print(f"[bold red]❌ Critical Error: {e}[/bold red]")
        import traceback
        traceback.print_exc()
    finally:
        # 关闭连接和 Agent
        if 'conn_manager' in locals():
            await conn_manager.shutdown()
        if 'agent' in locals():
            agent.shutdown()


async def main():
    """主函数"""
    console = Console()
    console.print("[bold]🚀 OpenClaw Pro 预备启动...[/bold]\n")

    try:
        await interactive_mode(None)
    except KeyboardInterrupt:
        console.print("\n👋 OpenClaw Pro Goodbye!")
    except Exception as e:
        console.print(f"❌ Critical Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
