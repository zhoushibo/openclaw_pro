"""
OpenClaw Pro Configuration Management (Step 4)
支持从 .env 和 YAML 加载配置
"""

import os
import yaml
from typing import List, Optional, Dict, Any
from pathlib import Path
from pydantic import BaseModel, Field, SecretStr, validator, ValidationError
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()


class SSHConfig(BaseModel):
    """SSH 连接配置"""
    host: str
    port: int = 22
    username: str
    password: Optional[SecretStr] = None
    private_key_path: Optional[str] = None
    allowed_roots: List[str] = Field(default=["/home", "/tmp"])
    blocked_patterns: List[str] = Field(default=[
        "*/proc/*",
        "*/sys/*",
        "*/dev/*"
    ])

    @validator("private_key_path")
    def validate_key_path(cls, v):
        if v and not Path(v).expanduser().exists():
            logger.warning(f"SSH key path does not exist: {v}")
        return v

    @validator("password")
    def validate_auth(cls, v, values):
        if not v and not values.get("private_key_path"):
            logger.warning("SSH config has neither password nor private key_path")
        return v


class WinRMConfig(BaseModel):
    """WinRM 连接配置"""
    host: str
    port: int = 5986
    username: str
    password: SecretStr
    ssl: bool = True
    cert_validation: bool = False
    allowed_roots: List[str] = Field(default=["C:/", "D:/", "E:/"])
    blocked_patterns: List[str] = Field(default=[
        "*/Windows/System32/*",
        "*/Program Files/*"
    ])

    @validator("password")
    def validate_password(cls, v):
        if not v or len(v.get_secret_value()) < 1:
            raise ValueError("WinRM password is required")
        return v


class MachineConfig(BaseModel):
    """机器配置"""
    name: str
    type: str = "local"  # "local", "ssh", "winrm"
    is_default: bool = False
    ssh: Optional[SSHConfig] = None
    winrm: Optional[WinRMConfig] = None

    @validator("type")
    def validate_type(cls, v):
        if v not in ["local", "ssh", "winrm"]:
            raise ValueError(f"Invalid machine type: {v}. Must be local, ssh, or winrm")
        return v

    @validator("ssh")
    def validate_ssh_config(cls, v, values):
        if values.get("type") == "ssh" and not v:
            raise ValueError("SSH machine must have ssh config")
        return v

    @validator("winrm")
    def validate_winrm_config(cls, v, values):
        if values.get("type") == "winrm" and not v:
            raise ValueError("WinRM machine must have winrm config")
        return v


class AgentConfig(BaseModel):
    """Agent 主配置"""
    # LLM 配置
    llm_model: str = Field(default="gpt-4o")
    api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    base_url: str = Field(default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))

    # 资源限制
    max_iterations: int = Field(default=10, description="Agent 最大循环次数")
    max_context_tokens: int = Field(default=8000, description="最大上下文 Token 数")
    shell_timeout: int = Field(default=60, description="Shell 命令执行超时时间（秒）")

    # 本地配置
    local_workspace: str = Field(default="./workspace")
    local_allowed_roots: List[str] = Field(default=["./workspace"])
    local_blocked_patterns: List[str] = Field(default=[
        "*/Windows/*",
        "*/System32/*",
        "*/etc/*",
        "*/bin/*",
        "*/proc/*"
    ])

    # 远程机器配置
    machines: List[MachineConfig] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True
        extra = "ignore"

    @validator("api_key")
    def validate_api_key(cls, v):
        if not v:
            logger.warning("OPENAI_API_KEY not set. LLM calls will fail.")
        return v

    @validator("local_allowed_roots")
    def validate_local_roots(cls, v):
        if not v:
            return ["./workspace"]
        return v

    def get_machine_by_name(self, name: str) -> Optional[MachineConfig]:
        """根据名称获取机器配置"""
        for machine in self.machines:
            if machine.name == name:
                return machine
        return None

    def get_default_machine(self) -> str:
        """获取默认机器名称"""
        for machine in self.machines:
            if machine.is_default:
                return machine.name
        return "local"

    def list_all_machines(self) -> List[str]:
        """列出所有可用机器名称"""
        names = ["local"]
        for machine in self.machines:
            names.append(machine.name)
        return names


class ConfigManager:
    """配置管理器
    支持 .env 和 YAML 文件加载配置
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config: Optional[AgentConfig] = None

    def load_from_env(self) -> AgentConfig:
        """从环境变量加载配置"""
        machines = []

        # 本地机器
        machines.append(MachineConfig(
            name="local",
            type="local",
            is_default=True
        ))

        # SSH 机器
        ssh_host = os.getenv("SSH_SERVER_HOST")
        ssh_name = os.getenv("SSH_SERVER_NAME", "server-01")
        if ssh_host:
            machines.append(MachineConfig(
                name=ssh_name,
                type="ssh",
                ssh=SSHConfig(
                    host=ssh_host,
                    port=int(os.getenv("SSH_SERVER_PORT", "22")),
                    username=os.getenv("SSH_SERVER_USER", "root"),
                    password=SecretStr(os.getenv("SSH_SERVER_PASSWORD", "")),
                    private_key_path=os.getenv("SSH_SERVER_KEY_PATH", ""),
                    allowed_roots=os.getenv("SSH_ALLOWED_ROOTS", "/,/,/home").split(",") if os.getenv("SSH_ALLOWED_ROOTS") else ["/home", "/tmp"],
                    blocked_patterns=os.getenv("SSH_BLOCKED_PATTERNS", "").split(",") if os.getenv("SSH_BLOCKED_PATTERNS") else [
                        "*/proc/*",
                        "*/sys/*",
                        "*/dev/*"
                    ]
                ),
                is_default=os.getenv("SSH_IS_DEFAULT", "false").lower() == "true"
            ))

        # WinRM 机器
        winrm_host = os.getenv("WINRM_SERVER_HOST")
        winrm_name = os.getenv("WINRM_SERVER_NAME", "win-server-01")
        if winrm_host:
            machines.append(MachineConfig(
                name=winrm_name,
                type="winrm",
                winrm=WinRMConfig(
                    host=winrm_host,
                    port=int(os.getenv("WINRM_SERVER_PORT", "5986")),
                    username=os.getenv("WINRM_SERVER_USER", "Administrator"),
                    password=SecretStr(os.getenv("WINRM_SERVER_PASSWORD", "")),
                    ssl=os.getenv("WINRM_SSL", "true").lower() == "true",
                    cert_validation=os.getenv("WINRM_CERT_VALIDATION", "false").lower() == "true",
                    allowed_roots=os.getenv("WINRM_ALLOWED_ROOTS", "C:/,D:/").split(",") if os.getenv("WINRM_ALLOWED_ROOTS") else ["C:/", "D:/"],
                    blocked_patterns=os.getenv("WINRM_BLOCKED_PATTERNS", "").split(",") if os.getenv("WINRM_BLOCKED_PATTERNS") else [
                        "*/Windows/System32/*",
                        "*/Program Files/*"
                    ]
                ),
                is_default=os.getenv("WINRM_IS_DEFAULT", "false").lower() == "true"
            ))

        self.config = AgentConfig(machines=machines)

        logger.info(f"✅ Loaded config from environment. Machines: {self.config.list_all_machines()}")
        return self.config

    def load_from_yaml(self, yaml_path: str) -> AgentConfig:
        """从 YAML 文件加载配置"""
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f)

            # 解析机器配置
            machines = []

            if 'machines' in yaml_data:
                for machine_data in yaml_data['machines']:
                    machine_type = machine_data.get('type', 'local')

                    if machine_type == 'ssh':
                        machine = MachineConfig(
                            name=machine_data['name'],
                            type=machine_data['type'],
                            ssh=SSHConfig(**machine_data.get('ssh', {})),
                            is_default=machine_data.get('is_default', False)
                        )
                    elif machine_type == 'winrm':
                        machine = MachineConfig(
                            name=machine_data['name'],
                            type=machine_data['type'],
                            winrm=WinRMConfig(**machine_data.get('winrm', {})),
                            is_default=machine_data.get('is_default', False)
                        )
                    else:
                        machine = MachineConfig(
                            name=machine_data['name'],
                            type='local',
                            is_default=machine_data.get('is_default', False)
                        )

                    machines.append(machine)

                # 如果没有默认机器，设置第一个为默认
                if machines and not any(m.is_default for m in machines):
                    machines[0].is_default = True

            # 合并其他配置
            config_data = {**yaml_data, 'machines': machines}
            self.config = AgentConfig(**config_data)

            logger.info(f"✅ Loaded config from YAML: {yaml_path}. Machines: {self.config.list_all_machines()}")
            return self.config

        except Exception as e:
            logger.error(f"Failed to load YAML config: {e}")
            raise

    def load(self) -> AgentConfig:
        """加载配置（优先 YAML，其次环境变量）"""
        if self.config_path and Path(self.config_path).exists():
            try:
                return self.load_from_yaml(self.config_path)
            except Exception as e:
                logger.warning(f"YAML config load failed ({e}), falling back to env")
                return self.load_from_env()
        else:
            return self.load_from_env()

    def get_config(self) -> AgentConfig:
        """获取已加载的配置"""
        if not self.config:
            return self.load()
        return self.config


# 全局配置实例
config_manager = ConfigManager()
config = config_manager.get_config()
