import React, { useState, useRef, useEffect } from 'react';
import { Sparkles, Bot, User, ArrowUp, RotateCcw } from 'lucide-react';
import type { ChatMessage } from '../types';
import { TimestampBadge } from './TimestampBadge';
import { ToolCallCard } from './ToolCallCard';

import { quickPrompts } from '../constants/ui';

interface ChatContainerProps {
  messages: ChatMessage[];
  isSending?: boolean;
  onSendMessage: (content: string) => void;
  onTimeClick?: (seconds: number) => void;
  onReset?: () => void;
}

// 快捷视频提问建议
const QUICK_PROMPTS = quickPrompts;

export const ChatContainer: React.FC<ChatContainerProps> = ({
  messages,
  isSending = false,
  onSendMessage,
  onTimeClick,
  onReset,
}) => {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 消息自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim() || isSending) return;
    onSendMessage(input.trim());
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // 输入法正在选字或确认文字时，交给输入法处理，不发送消息
    if (e.nativeEvent.isComposing || e.nativeEvent.keyCode === 229) {
      return;
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // 将回答里的 [MM:SS] 转为可点击的视频跳转按钮。
  const renderFormattedContent = (content: string) => {
    const timestampRegex = /\[(\d{1,2}:\d{2}(?::\d{2})?)\]/g;
    const parts: (string | React.ReactNode)[] = [];
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    while ((match = timestampRegex.exec(content)) !== null) {
      const matchIndex = match.index;
      if (matchIndex > lastIndex) {
        parts.push(content.substring(lastIndex, matchIndex));
      }

      const timeStr = match[1];
      const timeSegments = timeStr.split(':').map(Number);
      let totalSeconds = 0;
      if (timeSegments.length === 2) {
        totalSeconds = timeSegments[0] * 60 + timeSegments[1];
      } else if (timeSegments.length === 3) {
        totalSeconds = timeSegments[0] * 3600 + timeSegments[1] * 60 + timeSegments[2];
      }

      parts.push(
        <TimestampBadge
          key={`${timeStr}-${matchIndex}`}
          timeStr={timeStr}
          seconds={totalSeconds}
          onClick={onTimeClick}
        />
      );

      lastIndex = timestampRegex.lastIndex;
    }

    if (lastIndex < content.length) {
      parts.push(content.substring(lastIndex));
    }

    return parts;
  };

  return (
    <div className="flex flex-col h-full bg-white/90 backdrop-blur-xl border border-black/[0.06] rounded-3xl shadow-[0_4px_24px_rgba(0,0,0,0.03)] overflow-hidden">
      {/* 对话区头部操作条 */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-black/[0.06]">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-xs font-semibold text-[#1d1d1f] tracking-tight">
            MediaMind Agent 智能交互中台
          </span>
          <span className="text-[10px] font-medium text-[#86868b] bg-black/[0.03] px-2 py-0.5 rounded-full">
            支持连续追问
          </span>
        </div>
        <button
          onClick={onReset}
          title="清空重置对话"
          className="p-1.5 text-[#86868b] hover:text-[#1d1d1f] hover:bg-black/[0.03] rounded-full transition-colors"
        >
          <RotateCcw className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* 消息流主区域 */}
      <div className="flex-1 p-6 overflow-y-auto space-y-6">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3.5 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}
          >
            {/* 头像 */}
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-xs font-semibold shadow-sm ${
                msg.role === 'user'
                  ? 'bg-[#1d1d1f] text-white'
                  : 'bg-[#0071e3]/10 text-[#0071e3] border border-[#0071e3]/20'
              }`}
            >
              {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
            </div>

            {/* 消息主体 */}
            <div className={`max-w-[82%] space-y-2 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
              {/* 后端报告的工具执行记录 */}
              {msg.toolCalls && msg.toolCalls.length > 0 && (
                <div className="w-full space-y-2">
                  {msg.toolCalls.map((tool) => (
                    <ToolCallCard key={tool.id} tool={tool} />
                  ))}
                </div>
              )}

              {/* 文本气泡：苹果风圆角气泡 */}
              <div
                className={`p-4 rounded-2xl text-xs leading-relaxed tracking-normal select-text shadow-sm ${
                  msg.role === 'user'
                    ? 'bg-[#0071e3] text-white rounded-tr-none'
                    : 'bg-[#f5f5f7] text-[#1d1d1f] rounded-tl-none border border-black/[0.04]'
                }`}
              >
                <div className={`whitespace-pre-wrap ${msg.isStreaming ? 'cursor-blink' : ''}`}>
                  {renderFormattedContent(msg.content)}
                </div>
              </div>

              {/* 发送时间戳 */}
              <div
                className={`text-[10px] text-[#86868b] px-1 ${
                  msg.role === 'user' ? 'text-right' : 'text-left'
                }`}
              >
                {msg.timestamp}
                {msg.requestDurationMs !== undefined && (
                  <span className="ml-2">
                    本次请求用时 {(msg.requestDurationMs / 1000).toFixed(1)} 秒
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* 底部悬浮输入区域 */}
      <div className="p-5 border-t border-black/[0.06] bg-white/70 backdrop-blur-md">
        {/* 快捷推荐提问建议 */}
        <div className="flex items-center gap-2 mb-3 overflow-x-auto pb-1 scrollbar-none">
          <Sparkles className="w-3.5 h-3.5 text-[#0071e3] shrink-0" />
          {QUICK_PROMPTS.map((prompt, i) => (
            <button
              key={i}
              onClick={() => onSendMessage(prompt)}
              disabled={isSending}
              className="text-[11px] font-medium text-slate-600 bg-black/[0.03] hover:bg-[#0071e3]/8 hover:text-[#0071e3] px-3 py-1 rounded-full border border-black/[0.04] transition-all whitespace-nowrap cursor-pointer"
            >
              {prompt}
            </button>
          ))}
        </div>

        {/* 输入框与发送按钮 */}
        <div className="flex items-end gap-2 bg-[#f5f5f7] border border-black/[0.06] rounded-2xl p-2 focus-within:bg-white focus-within:border-[#0071e3]/50 focus-within:shadow-[0_0_0_4px_rgba(0,113,227,0.08)] transition-all">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={2}
            placeholder="针对视频提问（例如：这款相机录制4K120帧发热严重吗，或视频在第几分第几秒说了什么）..."
            className="flex-1 bg-transparent border-0 focus:outline-none resize-none text-xs text-[#1d1d1f] placeholder:text-[#86868b] px-2 py-1 leading-relaxed"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isSending}
            className="w-8 h-8 rounded-xl bg-[#0071e3] hover:bg-[#0077ed] active:scale-95 text-white flex items-center justify-center disabled:opacity-30 disabled:cursor-not-allowed transition-all shrink-0 cursor-pointer shadow-sm"
          >
            <ArrowUp className="w-4 h-4 stroke-[2.5]" />
          </button>
        </div>
      </div>
    </div>
  );
};
