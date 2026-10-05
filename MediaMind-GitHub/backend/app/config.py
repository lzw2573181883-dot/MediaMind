from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    全局配置中台：统一从 .env 环境变量文件读取敏感配置
    """
    # 智谱开放平台相关配置
    ZHIPUAI_API_KEY: str = ""
    ZHIPUAI_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    ZHIPUAI_MODEL: str = "glm-4.7-flash"

    # 项目基础配置
    PROJECT_NAME: str = "MediaMind-RAG 智能中台"
    VERSION: str = "0.1.0"

    # 自动加载 .env 文件（若找不到则使用默认值）
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    BILIBILI_SESSDATA: str = ""  # 默认为空，用户可选配置

# 实例化全局单例配置对象，供全系统导入使用
settings = Settings()