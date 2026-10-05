import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Terminal, CheckCircle2, Loader2, AlertCircle } from 'lucide-react';
import type { ToolCall } from '../types';

interface ToolCallCardProps {
  tool: ToolCall;
}

// 后端实际工具名称对应的中文说明
const TOOL_NAME_MAP: Record<string, string> = {
  search_video_rag: '检索视频内容',
  export_word_document: '导出 Word 笔记',
};

export const ToolCallCard: React.FC<ToolCallCardProps> = ({ tool }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const displayName = TOOL_NAME_MAP[tool.name] || tool.name;

  return (
    <div className="my-2.5 overflow-hidden transition-all duration-200 
                    bg-white/80 backdrop-blur-md 
                    border border-black/[0.06] rounded-2xl 
                    shadow-[0_2px_8px_rgba(0,0,0,0.02)] hover:shadow-[0_4px_16px_rgba(0,0,0,0.05)]">
      {/* 顶部状态条 */}
      <div 
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center justify-between px-4 py-3 cursor-pointer select-none hover:bg-black/[0.01]"
      >
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded-lg bg-black/[0.04] text-[#1d1d1f]">
            <Terminal className="w-3.5 h-3.5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-[#1d1d1f] tracking-tight">{displayName}</span>
              <code className="text-[10px] text-[#86868b] font-mono px-1.5 py-0.5 bg-black/[0.03] rounded-md">
                {tool.name}
              </code>
            </div>
          </div>
        </div>

        {/* 状态徽章与折叠按钮 */}
        <div className="flex items-center gap-2">
          {tool.status === 'calling' && (
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-[11px] font-medium text-amber-600 bg-amber-50 rounded-full border border-amber-200/60">
              <Loader2 className="w-3 h-3 animate-spin" />
              执行中...
            </span>
          )}
          {tool.status === 'success' && (
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-[11px] font-medium text-emerald-600 bg-emerald-50 rounded-full border border-emerald-200/60">
              <CheckCircle2 className="w-3 h-3" />
              {tool.durationMs ? `${tool.durationMs}ms` : '完成'}
            </span>
          )}
          {tool.status === 'error' && (
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-[11px] font-medium text-rose-600 bg-rose-50 rounded-full border border-rose-200/60">
              <AlertCircle className="w-3 h-3" />
              异常
            </span>
          )}

          <button className="text-[#86868b] hover:text-[#1d1d1f] p-1 rounded-full transition-colors">
            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* 展开内容：入参与执行结果预览 */}
      {isExpanded && (
        <div className="px-4 pb-3.5 pt-1 text-xs border-t border-black/[0.04] bg-slate-50/50 space-y-2.5">
          <div>
            <span className="text-[11px] font-medium text-[#86868b] uppercase tracking-wider block mb-1">
              调用入参 (Arguments)
            </span>
            <pre className="p-2.5 bg-white border border-black/[0.06] rounded-xl text-[11px] font-mono text-slate-700 overflow-x-auto">
              {JSON.stringify(tool.args, null, 2)}
            </pre>
          </div>
          {tool.result !== undefined && (
            <div>
              <span className="text-[11px] font-medium text-[#86868b] uppercase tracking-wider block mb-1">
                执行返回 (Result)
              </span>
              <pre className="p-2.5 bg-white border border-black/[0.06] rounded-xl text-[11px] font-mono text-slate-700 overflow-x-auto max-h-40">
                {typeof tool.result === 'string' ? tool.result : JSON.stringify(tool.result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
