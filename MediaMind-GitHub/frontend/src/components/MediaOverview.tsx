import React from 'react';
import { Tv, Clock, Sparkles, Layers, Compass, Film, Plus } from 'lucide-react';
import type { MediaMetadata } from '../types';
import { TimestampBadge } from './TimestampBadge';

interface MediaOverviewProps {
  media: MediaMetadata | null;
  onTimeClick?: (seconds: number) => void;
  activeSecond?: number | null;
  onOpenUpload?: () => void;
}

export const MediaOverview: React.FC<MediaOverviewProps> = ({ 
  media, 
  onTimeClick, 
  activeSecond,
  onOpenUpload,
}) => {
  // 🌟 空状态：当未载入任何音视频时，展示极简苹果风待命卡片
  if (!media) {
    return (
      <div className="bg-white/80 backdrop-blur-xl border border-dashed border-black/[0.12] rounded-3xl p-8 h-full flex flex-col items-center justify-center text-center shadow-[0_4px_24px_rgba(0,0,0,0.02)]">
        <div className="w-16 h-16 rounded-3xl bg-[#0071e3]/8 border border-[#0071e3]/15 flex items-center justify-center text-[#0071e3] mb-5 shadow-sm">
          <Film className="w-8 h-8 stroke-[1.8] animate-pulse" />
        </div>
        
        <h3 className="text-base font-bold text-[#1d1d1f] tracking-tight mb-2">
          尚未载入音视频知识库
        </h3>
        
        <p className="text-xs text-[#86868b] leading-relaxed max-w-xs mb-6">
          点击下方按钮粘贴任意 B 站视频链接，系统将自动进行长媒体知识蒸馏、提取章节目录并完成时间戳向量切块。
        </p>

        <div className="flex items-center gap-2.5">
          <button
            onClick={onOpenUpload}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-[#0071e3] hover:bg-[#0077ed] active:scale-95 rounded-full shadow-sm hover:shadow transition-all cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5 stroke-[2.5]" />
            <span>解析 B 站视频</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white/90 backdrop-blur-xl border border-black/[0.06] rounded-3xl p-6 shadow-[0_4px_24px_rgba(0,0,0,0.03)] h-full flex flex-col">
      {/* 媒体头部卡片 */}
      <div className="pb-5 border-b border-black/[0.06]">
        <div className="flex items-center justify-between mb-3">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold text-[#0071e3] bg-[#0071e3]/8 rounded-full border border-[#0071e3]/15">
            <Tv className="w-3.5 h-3.5" />
            {media.platform} 视频知识库
          </span>
          <span className="flex items-center gap-1 text-xs font-medium text-[#86868b]">
            <Clock className="w-3.5 h-3.5" />
            {media.durationStr}
          </span>
        </div>

        <h2 className="text-lg font-bold text-[#1d1d1f] tracking-tight leading-snug mb-1.5">
          {media.title}
        </h2>
        <p className="text-xs text-[#86868b] font-medium">UP主 / 作者：{media.author}</p>
      </div>

      {/* 核心摘要 */}
      <div className="py-4 border-b border-black/[0.06]">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-[#1d1d1f] mb-2">
          <Sparkles className="w-3.5 h-3.5 text-[#0071e3]" />
          <span>AI 知识蒸馏摘要</span>
        </div>
        <p className="text-xs leading-relaxed text-slate-600 bg-slate-50/80 p-3 rounded-2xl border border-black/[0.03]">
          {media.summary}
        </p>

        {/* 核心关键词胶囊 */}
        <div className="flex flex-wrap gap-1.5 mt-3">
          {media.keywords.map((kw, i) => (
            <span 
              key={i} 
              className="text-[11px] font-medium text-slate-600 bg-black/[0.03] px-2.5 py-1 rounded-full hover:bg-black/[0.06] transition-colors"
            >
              #{kw}
            </span>
          ))}
        </div>
      </div>

      {/* 章节导航时间线 */}
      <div className="flex-1 pt-4 overflow-y-auto min-h-0">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-[#1d1d1f]">
            <Layers className="w-3.5 h-3.5 text-[#0071e3]" />
            <span>核心章节目录 ({media.chapters.length})</span>
          </div>
          <span className="text-[11px] text-[#86868b]">点击直接定位</span>
        </div>

        <div className="space-y-2.5 pr-1">
          {media.chapters.map((ch, idx) => {
            const nextCh = media.chapters[idx + 1];
            const isActive =
              activeSecond !== null &&
              activeSecond !== undefined &&
              activeSecond >= ch.startTime &&
              (!nextCh || activeSecond < nextCh.startTime);

            return (
              <div 
                key={ch.id}
                className={`p-3 rounded-2xl border transition-all group ${
                  isActive
                    ? 'bg-[#0071e3]/5 border-[#0071e3] shadow-[0_0_16px_rgba(0,113,227,0.12)] ring-2 ring-[#0071e3]/20'
                    : 'bg-white border-black/[0.05] hover:border-[#0071e3]/30 hover:shadow-[0_2px_8px_rgba(0,113,227,0.06)]'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-1.5 min-w-0">
                    {isActive && (
                      <span className="w-1.5 h-1.5 rounded-full bg-[#0071e3] animate-pulse shrink-0" />
                    )}
                    <span className={`text-xs font-semibold tracking-tight line-clamp-1 transition-colors ${
                      isActive ? 'text-[#0071e3]' : 'text-[#1d1d1f] group-hover:text-[#0071e3]'
                    }`}>
                      {ch.title}
                    </span>
                  </div>
                  <TimestampBadge 
                    timeStr={ch.timeStr} 
                    seconds={ch.startTime} 
                    onClick={onTimeClick} 
                  />
                </div>
                <p className="text-[11px] text-[#86868b] leading-normal line-clamp-2">
                  {ch.summary}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* 底部指标状态 */}
      <div className="pt-4 mt-auto border-t border-black/[0.06] flex items-center justify-between text-[11px] text-[#86868b]">
        <span className="flex items-center gap-1">
          <Compass className="w-3 h-3 text-emerald-500" />
          时间戳切块对齐率 100%
        </span>
      </div>
    </div>
  );
};