"""
测试工具函数
"""

from typing import Any, Optional
import sys

# Windows GBK 兼容 - 只在第一次导入时设置
_stdout_fixed = False
if sys.platform == "win32" and not _stdout_fixed:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    _stdout_fixed = True


def print_color(text: str, color: str = "white"):
    """彩色输出打印

    Args:
        text: 要打印的文本
        color: 颜色名称 (black, red, green, yellow, blue, magenta, cyan, white)
    """
    colors = {
        "black": "\033[30m",
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "magenta": "\033[35m",
        "cyan": "\033[36m",
        "white": "\033[37m",
    }
    reset = "\033[0m"

    code = colors.get(color, colors["white"])
    print(f"{code}{text}{reset}")


def print_section(title: str, color: str = "white"):
    """打印章节标题

    Args:
        title: 标题文本
        color: 颜色名称
    """
    separator = "=" * 50
    print_color(separator, color)
    print_color(f"  {title}", color)
    print_color(separator, color)


def print_success(message: str):
    """打印成功消息"""
    print_color(f"[OK] {message}", "green")


def print_error(message: str):
    """打印错误消息"""
    print_color(f"[ERROR] {message}", "red")


def print_warning(message: str):
    """打印警告消息"""
    print_color(f"[WARNING] {message}", "yellow")


def print_info(message: str):
    """打印信息消息"""
    print_color(f"[INFO] {message}", "cyan")


def format_results(results: dict[str, Any]) -> str:
    """格式化测试结果

    Args:
        results: 测试结果字典

    Returns:
        格式化的字符串
    """
    output = []
    for key, value in results.items():
        status = "[OK]" if value else "[FAIL]"
        output.append(f"{status} {key}")
    return "\n".join(output)
