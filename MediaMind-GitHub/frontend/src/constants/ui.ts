import type { ChatMessage } from '../types';

export const initialMessages: ChatMessage[] = [
  {
    "id": "welcome-0",
    "role": "assistant",
    "content": "你好！我是 MediaMind-RAG 智能体中台。请点击左侧「解析新音视频」输入任意 B 站视频链接，我将为您进行结构化章节蒸馏与时间戳精准切块！",
    "timestamp": "待命"
  }
];

export const pipelineSteps: string[] = [
  "正在通过 API 嗅探音视频原生带时间戳字幕...",
  "基于大模型知识引擎自动化提取章节树与核心摘要...",
  "按 512+64 滑动窗口切块，构建 BM25 与 Chroma 向量索引...",
  "知识蒸馏与双路索引完成，即将载入工作台！"
];

export const quickPrompts: string[] = [
  "请总结本期视频的核心主旨与论点",
  "视频中提到了哪些关键数据或结论？",
  "请将本期核心内容整理为简报并导出 Word 文档"
];

