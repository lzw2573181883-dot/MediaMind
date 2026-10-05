import { useState, useRef } from 'react';
import { MediaOverview } from './components/MediaOverview';
import { ChatContainer } from './components/ChatContainer';
import { MediaUploadModal } from './components/MediaUploadModal';
import type { MediaMetadata, ChatMessage, ChatResponse } from './types';
import { Tv, ExternalLink, Cpu, Plus } from 'lucide-react';

import { initialMessages } from './constants/ui';

type HistoryMessage = {
  role: 'user' | 'assistant';
  content: string;
};

const MAX_HISTORY_TURNS = 10;

export function App() {
  const [media, setMedia] = useState<MediaMetadata | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [currentActiveSecond, setCurrentActiveSecond] = useState<number | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSending, setIsSending] = useState(false);
  // 只保存真实问答，不包含欢迎语、工具卡片和通信错误。
  const historyRef = useRef<HistoryMessage[]>([]);
  const sendingRef = useRef(false);

  // 当新视频解析完成后，整个工作台无缝换血联动
  const handleNewMediaSuccess = (newMedia: MediaMetadata) => {
    historyRef.current = [];
    setMedia(newMedia);
    setCurrentActiveSecond(null);
    setMessages([
      {
        id: `m-welcome-${Date.now()}`,
        role: 'assistant',
        content: `🎉 知识蒸馏完成！我已经完成了对《${newMedia.title}》的全文结构化提取与时间戳切块（共 ${newMedia.chapters.length} 个章节）。\n\n你可以针对本期内容的任何细节向我提问，点击回答里的 [mm:ss] 即可秒级跳转对应音频位置！`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
  };

  // 真正的 B 站原片秒级精准跳转与章节联动脚本
  const handleTimeClick = (seconds: number) => {
    if (!media) return;

    // 1. 记录当前点击的秒数，驱动左侧章节目录亮起高亮光环
    setCurrentActiveSecond(seconds);

    // 2. 从当前媒体唯一标识中嗅探真实的 BV 号（例如 BV1cSec6tEux / BV1j2Y36jEHu）
    const match = media.id.match(/(BV[0-9a-zA-Z]{10})/);
    const bvid = match ? match[1] : (media.id.startsWith('BV') ? media.id : 'BV1cSec6tEux');

    // 3. 构造 B 站官方带精准秒数定位参数的播放链接（?t=秒数）
    const bilibiliUrl = `https://www.bilibili.com/video/${bvid}?t=${seconds}`;

    // 4. 在浏览器新标签页秒开 B 站视频，直达对应秒数精准起播！
    window.open(bilibiliUrl, '_blank');
  };

  // 向后端发送聊天请求，再用打字机动画展示完整回答。
  const handleSendMessage = async (content: string) => {
    if (sendingRef.current) return;
    sendingRef.current = true;
    setIsSending(true);
    const history = historyRef.current;
    // 未解析视频时不指定 BV 号，由后端进行普通聊天。
    const bvid = media?.id.match(/(BV[0-9a-zA-Z]{10})/)?.[1] || '';
    // 1. 创建用户气泡
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    // 2. 路由结果尚未返回时，只显示通用等待提示。
    const assistantMsgId = `assistant-${Date.now()}`;
    const initialAssistantMsg: ChatMessage = {
      id: assistantMsgId,
      role: 'assistant',
      content: '正在处理你的请求…',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      isStreaming: true,
      toolCalls: [],
    };

    setMessages((prev) => [...prev, userMsg, initialAssistantMsg]);

    const startTime = Date.now();

    try {
      // 4. 向 FastAPI 后端发起真实网络请求！
      const response = await fetch('http://127.0.0.1:8000/api/v1/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          bvid,
          query: content,
          history,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP 错误码: ${response.status}`);
      }

      const data: ChatResponse = await response.json();
      // 请求期间切换视频或清空会话后，忽略旧会话的结果。
      if (historyRef.current !== history) return;
      const fullResponse = data.answer || '未能从视频中检索到相关内容。';
      historyRef.current = history.concat(
        { role: 'user', content },
        { role: 'assistant', content: fullResponse },
      ).slice(-MAX_HISTORY_TURNS * 2);
      const durationMs = Date.now() - startTime;

      // 5. 展示后端报告的工具记录，整次请求耗时单独保存。
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsgId
            ? {
                ...m,
                requestDurationMs: durationMs,
                toolCalls: (data.toolCalls || []).map((tool, index) => ({
                  id: `${assistantMsgId}-tool-${index}`,
                  name: tool.tool_name,
                  status: tool.status,
                  args: tool.arguments,
                  result: tool.result,
                })),
              }
            : m
        )
      );

      // 6. 完整响应已经收到，逐字展示回答中的文字与时间戳。
      let currentIdx = 0;
      const interval = setInterval(() => {
        currentIdx += 2;
        const currentText = fullResponse.slice(0, currentIdx);

        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? {
                  ...m,
                  content: currentText,
                  isStreaming: currentIdx < fullResponse.length,
                }
              : m
          )
        );

        if (currentIdx >= fullResponse.length) {
          clearInterval(interval);
        }
      }, 25);
    } catch (err) {
      if (historyRef.current !== history) return;
      // 7. 优雅异常兜底
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsgId
            ? {
                ...m,
                content: `⚠️ 通信异常：无法连接至知识库问答后端（${err instanceof Error ? err.message : '请求失败'}）。`,
                isStreaming: false,
                toolCalls: [],
              }
            : m
        )
      );
    } finally {
      sendingRef.current = false;
      setIsSending(false);
    }
  };

  const handleReset = () => {
    historyRef.current = [];
    setMedia(null);
    setMessages(initialMessages);
    setCurrentActiveSecond(null);
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#f5f5f7] text-[#1d1d1f]">
      {/* 苹果风格极简导航栏 */}
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-white/75 border-b border-black/[0.06] px-8 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-2xl bg-[#0071e3] text-white flex items-center justify-center shadow-sm">
            <Tv className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-bold tracking-tight text-[#1d1d1f]">MediaMind-RAG</h1>
              <span className="text-[10px] font-semibold text-[#0071e3] bg-[#0071e3]/10 px-2 py-0.5 rounded-full border border-[#0071e3]/20">
                v1.0.0 
              </span>
            </div>
            <p className="text-[11px] text-[#86868b] font-medium">
              B站长视频知识蒸馏与时间轴精准问答智能体中台
            </p>
          </div>
        </div>

        {/* 顶部右侧系统状态与操作 */}
        <div className="flex items-center gap-3">
          {/* 解析新视频按钮 */}
          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-white bg-[#0071e3] hover:bg-[#0077ed] active:scale-95 rounded-full shadow-sm hover:shadow transition-all cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5 stroke-[2.5]" />
            <span>解析 B 站视频</span>
          </button>

          <div className="flex items-center gap-2 text-xs text-[#86868b] font-medium bg-black/[0.03] px-3 py-1.5 rounded-full border border-black/[0.04]">
            <Cpu className="w-3.5 h-3.5 text-emerald-500" />
            <span>Dual-RAG 知识库已就绪</span>
            {currentActiveSecond !== null && (
              <span className="text-[#0071e3] font-mono font-semibold">
                [当前锚点: {currentActiveSecond}s]
              </span>
            )}
          </div>

          <a
            href="https://github.com"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 text-xs font-medium text-[#1d1d1f] hover:text-[#0071e3] bg-white border border-black/[0.08] px-3.5 py-1.5 rounded-full shadow-[0_1px_2px_rgba(0,0,0,0.04)] hover:shadow-sm transition-all"
          >
            <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24">
              <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
            </svg>
            <span>GitHub 仓库</span>
            <ExternalLink className="w-3 h-3 text-[#86868b]" />
          </a>
        </div>
      </header>

      {/* 主工作台区域：左侧结构化看板 + 右侧流式对话 */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-0">
        {/* 左侧：音视频结构化看板（占 5 列） */}
        <section className="lg:col-span-5 h-[calc(100vh-100px)]">
          <MediaOverview 
            media={media} 
            onTimeClick={handleTimeClick} 
            activeSecond={currentActiveSecond} 
            onOpenUpload={() => setIsModalOpen(true)}
          />
        </section>

        {/* 右侧：打字机流式对话工作台（占 7 列） */}
        <section className="lg:col-span-7 h-[calc(100vh-100px)]">
          <ChatContainer
            messages={messages}
            isSending={isSending}
            onSendMessage={handleSendMessage}
            onTimeClick={handleTimeClick}
            onReset={handleReset}
          />
        </section>
      </main>

      {/* 挂载音视频导入与解析弹窗 */}
      <MediaUploadModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={handleNewMediaSuccess}
      />
    </div>
  );
}

export default App;
//超级大组件：要包含所有的页的容器（不同页可以路由），有它就不用入口文件了
