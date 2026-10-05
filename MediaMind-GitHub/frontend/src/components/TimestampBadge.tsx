import React from 'react';
import { Play } from 'lucide-react';

interface TimestampBadgeProps {
  timeStr: string;
  seconds?: number;
  quote?: string;
  onClick?: (seconds: number) => void;
}

export const TimestampBadge: React.FC<TimestampBadgeProps> = ({
  timeStr,
  seconds = 0,
  quote,
  onClick,
}) => {
  return (
    <button
      onClick={() => onClick?.(seconds)}
      title={quote ? `跳转到 ${timeStr}: "${quote}"` : `跳转到 ${timeStr}`}
      className="inline-flex items-center gap-1 px-2.5 py-0.5 mx-1 my-0.5 text-xs font-medium 
                 text-[#0071e3] bg-[#0071e3]/8 hover:bg-[#0071e3]/15 
                 border border-[#0071e3]/20 rounded-full 
                 transition-all duration-200 ease-out active:scale-95 group cursor-pointer"
    >
      <Play className="w-2.5 h-2.5 fill-current transition-transform duration-200 group-hover:translate-x-0.5" />
      <span className="font-mono font-semibold tracking-tight">{timeStr}</span>
    </button>
  );
};