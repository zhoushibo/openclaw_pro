"""
Main Entry Point - OpenClaw 主程序
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console

from config import ConfigManager, AgentConfig
from core.agent import Agent
from tools.builtin import register_builtin_tools


async def interactive_mode(agent):
    """交互式 CLI 模式"""
    console.print("[bold blue]🚀 OpenClaw 启动中...[/bold]\n")

    try:
        # 加载配置
        config = AgentConfig()
        
        # 创建并初始化 Agent
        agent = Agent(config)
        await agent.initialize()

        # 自动加载内置工具
        register_builtin_tools()

        # 显示可用信息
        console.print("[green]✅ 初始化完成！[/green]")
        console.print("[bold blue]输入 'quit' 或 'exit' 退出[/bold blue]")
        print()

        # 交互式循环
        while True:
            try:
                user_input = console.input("[bold blue]👤 You:[/bold blue] ").strip()
                if not user_input or user_input.lower() in ['quit', 'exit', 'q', 'exit']:
                    break

                if user_input.startswith('stats'):
                    # 显示统计
                    stats = agent.get_stats()
                    console.print("[dim]当前状态:[/dim]")
                    console.print(f"迭代次数: {stats['iterations']}")
                    console.print(f"消息数: {stats['message_count']}")
                    console.print(f"机器: {', '.join(stats['machines'])}")
                    continue

                await agent.run(user_input)

            except KeyboardInterrupt:
                console.print("\n[yellow]⛔ 用户中断[/yellow]")
                break

    except Exception as e:
        console.print(f"[bold red]❌ 错误: {e}[/bold red]")
        finally:
            # 关闭所有连接
            if 'agent' in locals():
                await agent.shutdown()


async def main():
    """主函数"""
    console.print("[bold]🚀 OpenCl Starting...[/bold]\n")

    try:
        # 加载配置
        config_manager = ConfigManager(config_path="config.yaml")  # 优先从 YAML 加载
        config = config_manager.get_config()

        # 创建 Agent
        agent = Agent(config)

        # 初始化（加载配置，连接机器，注册工具）
        await agent.initialize()

        # 运行交互式模式
        await interactive_mode(agent)

    except KeyboardInterrupt:
        console.print("\n👋 OpenClaw 停止")
    except Exception as e:
        console.print(f"❌ Critical Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
