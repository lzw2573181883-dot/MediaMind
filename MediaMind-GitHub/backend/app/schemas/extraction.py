from pydantic import BaseModel, ConfigDict, Field#严格规定类的类型
from pydantic.alias_generators import to_camel
from typing import List

# 0. 企业级基础驼峰模具：配置自动同声传译
# Python代码内部继续使用规范的下划线（如 start_time），但转成 JSON 发给前端时，Pydantic 会自动转为小驼峰（startTime）
class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

# 1. 客户端提交的提取请求入参模具
class VideoExtractRequest(CamelModel):
    url: str = Field(description="用户输入的B站视频链接，例如：https://www.bilibili.com/video/BV1cSec6tEux")

# 2. 单个视频章节小模具
class MediaChapter(CamelModel):
    id: str = Field(description="章节唯一标识ID，例如：ch-1")
    title: str = Field(description="章节标题，例如：显存优化策略")
    start_time: int = Field(description="该章节起始秒数，例如：865")
    time_str: str = Field(description="时间戳展示字符，例如：14:25")
    summary: str = Field(description="该章节的简明要点讲解")

# 3. 整个长视频一键蒸馏后的大模具（与前端 MediaMetadata 100% 对齐）
class VideoExtractionResult(CamelModel):
    id: str = Field(description="全局唯一媒体ID")
    title: str = Field(description="视频整体标题")
    platform: str = Field(default="Bilibili", description="平台类型，默认为 Bilibili")
    author: str = Field(description="主讲人或UP主名称")
    duration_str: str = Field(description="总时长，如 01:25:40")
    total_seconds: int = Field(description="总秒数")
    summary: str = Field(description="整期长视频的全局核心概要")
    keywords: List[str] = Field(description="技术关键词标签列表")
    chapters: List[MediaChapter] = Field(description="章节目录树列表")