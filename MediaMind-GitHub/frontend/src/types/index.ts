// 1. 视频时间戳锚点
export interface TimestampAnchor {
  seconds: number;        // 秒数（如 865 秒）
  timeStr: string;        // 格式化展示（如 "14:25"）
  quoteText?: string;     // 该时间点对应的原文字幕金句
}

// 2. 后端返回的工具执行记录；字典内的字段保留后端命名。
export interface BackendToolCall {
  tool_name: string;
  arguments: Record<string, unknown>;
  status: 'calling' | 'success' | 'error';
  result?: unknown;
}

export interface ChatResponse {
  answer: string;
  toolCalls: BackendToolCall[];
}

// 前端卡片使用的数据格式
export interface ToolCall {
  id: string;
  name: string;
  status: 'calling' | 'success' | 'error';
  args: Record<string, unknown>;
  result?: unknown;
  durationMs?: number;
}

// 3. 对话消息模型
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  toolCalls?: ToolCall[];
  anchors?: TimestampAnchor[];
  isStreaming?: boolean;
  requestDurationMs?: number; // 整次请求耗时，包含路由、模型调用等处理
}

// 4. 媒体结构化元数据（对应简历：非结构化音视频蒸馏看板）
export interface MediaChapter {
  id: string;
  title: string;
  startTime: number;
  timeStr: string;
  summary: string;
}

export interface MediaMetadata {
  id: string;
  title: string;
  platform: 'Bilibili';
  author: string;
  durationStr: string;
  totalSeconds: number;
  summary: string;
  chapters: MediaChapter[];
  keywords: string[];
}
