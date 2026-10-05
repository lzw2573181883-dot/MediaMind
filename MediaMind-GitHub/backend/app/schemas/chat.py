# 文件路径：backend/app/schemas/chat.py
# 职责：定义前端与后端在“AI 智能问答 / Agent 工具调用”场景下的数据通信协议（数据模具）

from pydantic import Field
from typing import List, Dict, Any, Literal
from app.schemas.extraction import CamelModel


class ChatHistoryMessage(CamelModel):
    role: Literal["user", "assistant"]
    content: str


# 1. 前端向后端发起的提问请求体
class ChatRequest(CamelModel):
    bvid: str = Field(default="", description="目标视频的BV号；未解析视频时留空，进行普通聊天")
    query: str = Field(description="用户输入的提问文本，例如：这相机发热严重吗？")
    history: List[ChatHistoryMessage] = Field(
        default_factory=list, description="此前完成的问答历史，不包含当前问题"
    )


# 2. 单个参考切片证据卡片
class ChatSourceChunk(CamelModel):
    chunk_id: str = Field(default="", description="切片唯一ID，如 chunk_18")
    time_str: str = Field(default="00:00", description="时间戳展示字符，如 12:09")
    start_time: int = Field(default=0, description="开始秒数，如 729")
    end_time: int = Field(default=0, description="结束秒数，如 806")
    text: str = Field(default="", description="原片切片台词内容摘录")


# 3. 后端最终返回给前端的完整回答体（升级支持 Agent 工具调用透明化）
class ChatResponse(CamelModel):
    answer: str = Field(description="大模型生成的严谨回答（内含 [MM:SS] 时间戳标记）")
    sources: List[ChatSourceChunk] = Field(default_factory=list, description="Top-3 黄金参考切片列表")
    tool_used: bool = Field(default=False, description="是否触发了工具调用")
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list, description="Agent 工具调用历史记录")
