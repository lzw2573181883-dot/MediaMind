//小弹窗
import React, { useState } from 'react';
import { X, Link2, UploadCloud, CheckCircle2, Loader2, Sparkles, AlertCircle } from 'lucide-react';
import type { MediaMetadata } from '../types';

interface MediaUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (newMedia: MediaMetadata) => void;
}

import { pipelineSteps } from '../constants/ui';

const EXTRACTION_FAILURE_MESSAGE = '解析失败，请稍后重试。';
// 本地上传接入真实后端处理后，再开放入口。
const ENABLE_LOCAL_UPLOAD = false;

export const MediaUploadModal: React.FC<MediaUploadModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [activeTab, setActiveTab] = useState<'url' | 'file'>('url');
  const [urlInput, setUrlInput] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const PIPELINE_STEPS = pipelineSteps;

  const handleStartProcess = async () => {
    if (activeTab === 'url') {
      if (!urlInput.trim()) return;
      setIsProcessing(true);
      setErrorMessage(null);
      setCurrentStep(0);

      // 视觉流水线步进动画
      const stepInterval = setInterval(() => {
        setCurrentStep((prev) => (prev < PIPELINE_STEPS.length - 1 ? prev + 1 : prev));
      }, 700);

      try {
        // 向 FastAPI 后端发送真实 POST 请求
        const response = await fetch('http://127.0.0.1:8000/api/v1/extract', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ url: urlInput }),
        });

        if (!response.ok) {
          throw new Error(EXTRACTION_FAILURE_MESSAGE);
        }

        const data = await response.json();
        clearInterval(stepInterval);
        setCurrentStep(PIPELINE_STEPS.length - 1);

        // 🌟 企业级契约：后端 Pydantic CamelModel 已在网络层自动同声传译为小驼峰
        // 前端直接消费，0 行多余翻译代码！
        const newMedia = data as MediaMetadata;

        setTimeout(() => {
          setIsProcessing(false);
          onSuccess(newMedia);
          onClose();
        }, 600);
      } catch {
        clearInterval(stepInterval);
        setIsProcessing(false);
        setErrorMessage(EXTRACTION_FAILURE_MESSAGE);
      }
    } else {
      setErrorMessage('当前仅支持 B 站视频链接解析。');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-xl bg-white/95 backdrop-blur-2xl border border-black/[0.08] rounded-3xl shadow-[0_20px_60px_rgba(0,0,0,0.12)] overflow-hidden">
        {/* 顶部标题条 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-black/[0.06]">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-xl bg-[#0071e3]/10 text-[#0071e3]">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-[#1d1d1f]">导入 B 站长视频进行知识蒸馏</h3>
              <p className="text-[11px] text-[#86868b]">粘贴 B 站在线视频链接进行解析</p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isProcessing}
            className="p-1.5 text-[#86868b] hover:text-[#1d1d1f] hover:bg-black/[0.04] rounded-full transition-colors disabled:opacity-30"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* 弹窗主体 */}
        <div className="p-6">
          {!isProcessing ? (
            <>
              {/* 苹果分段控制器（Tab 切换） */}
              <div className="flex p-1 mb-5 bg-[#f5f5f7] rounded-xl border border-black/[0.04]">
                <button
                  onClick={() => setActiveTab('url')}
                  className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                    activeTab === 'url'
                      ? 'bg-white text-[#1d1d1f] shadow-sm'
                      : 'text-[#86868b] hover:text-[#1d1d1f]'
                  }`}
                >
                  <Link2 className="w-3.5 h-3.5" />
                  B 站视频在线解析
                </button>
                {ENABLE_LOCAL_UPLOAD && <button
                  onClick={() => setActiveTab('file')}
                  className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                    activeTab === 'file'
                      ? 'bg-white text-[#1d1d1f] shadow-sm'
                      : 'text-[#86868b] hover:text-[#1d1d1f]'
                  }`}
                >
                  <UploadCloud className="w-3.5 h-3.5" />
                  本地音视频/字幕上传
                </button>}
              </div>

              {/* 错误提示条 */}
              {errorMessage && (
                <div className="flex items-start gap-2.5 p-3 mb-4 bg-red-50/90 border border-red-200/80 rounded-2xl text-xs text-red-600 animate-fade-in">
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-red-500" />
                  <div className="flex-1 leading-relaxed">
                    <p className="font-semibold">解析请求未通过：</p>
                    <p className="text-[11px] opacity-90 mt-0.5">{errorMessage}</p>
                  </div>
                </div>
              )}

              {/* Tab 1: 链接模式 */}
              {activeTab === 'url' && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-[#1d1d1f] mb-1.5">
                      B 站视频链接 URL
                    </label>
                    <input
                      type="text"
                      value={urlInput}
                      onChange={(e) => {
                        setUrlInput(e.target.value);
                        if (errorMessage) setErrorMessage(null);
                      }}
                      placeholder="粘贴 B 站视频链接，例如 https://www.bilibili.com/video/BV1cSec6tEux..."
                      className="w-full px-3.5 py-2.5 bg-[#f5f5f7] border border-black/[0.06] rounded-xl text-xs text-[#1d1d1f] placeholder:text-[#86868b] focus:outline-none focus:bg-white focus:border-[#0071e3]/50 focus:shadow-[0_0_0_4px_rgba(0,113,227,0.08)] transition-all"
                    />
                  </div>
                </div>
              )}

              {/* Tab 2: 文件上传模式 */}
              {ENABLE_LOCAL_UPLOAD && activeTab === 'file' && (
                <div className="space-y-3">
                  <label className="block text-xs font-semibold text-[#1d1d1f]">
                    上传音视频或字幕文件
                  </label>
                  <label className="flex flex-col items-center justify-center p-6 border-2 border-dashed border-black/[0.12] hover:border-[#0071e3] hover:bg-[#0071e3]/5 rounded-2xl cursor-pointer transition-all group">
                    <UploadCloud className="w-8 h-8 text-[#86868b] group-hover:text-[#0071e3] mb-2 transition-colors" />
                    <span className="text-xs font-medium text-[#1d1d1f]">
                      {selectedFile ? selectedFile.name : '点击选择或将文件拖拽至此处'}
                    </span>
                    <span className="text-[11px] text-[#86868b] mt-1">
                      支持 .mp4, .mp3, .srt, .vtt (单文件最大 2GB)
                    </span>
                    <input
                      type="file"
                      accept=".mp4,.mp3,.wav,.srt,.vtt,.txt"
                      onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                      className="hidden"
                    />
                  </label>
                </div>
              )}
            </>
          ) : (
            /* 处理进度展示（四大工序流动流水线） */
            <div className="py-4 space-y-4">
              <div className="text-center space-y-1">
                <Loader2 className="w-6 h-6 text-[#0071e3] animate-spin mx-auto mb-2" />
                <h4 className="text-xs font-bold text-[#1d1d1f]">
                  MediaMind 后台智能流水线执行中...
                </h4>
                <p className="text-[11px] text-[#86868b]">正在对长音频进行解构、切块与重排建库</p>
              </div>

              {/* 进度列表 */}
              <div className="space-y-2 bg-[#f5f5f7] p-4 rounded-2xl border border-black/[0.04]">
                {PIPELINE_STEPS.map((step, idx) => (
                  <div key={idx} className="flex items-center gap-2.5 text-xs">
                    {idx < currentStep && (
                      <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                    )}
                    {idx === currentStep && (
                      <Loader2 className="w-4 h-4 text-[#0071e3] animate-spin shrink-0" />
                    )}
                    {idx > currentStep && (
                      <div className="w-4 h-4 rounded-full border border-black/[0.15] shrink-0" />
                    )}
                    <span
                      className={`transition-colors leading-relaxed ${
                        idx <= currentStep
                          ? 'text-[#1d1d1f] font-medium'
                          : 'text-[#86868b]'
                      }`}
                    >
                      {step}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 底部确认按钮 */}
        {!isProcessing && (
          <div className="px-6 py-4 bg-[#f5f5f7] border-t border-black/[0.06] flex justify-end gap-2.5">
            <button
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-[#1d1d1f] hover:bg-black/[0.05] rounded-xl transition-colors"
            >
              取消
            </button>
            <button
              onClick={handleStartProcess}
              disabled={activeTab === 'url' ? !urlInput.trim() : !selectedFile}
              className="flex items-center gap-1.5 px-5 py-2 text-xs font-semibold text-white bg-[#0071e3] hover:bg-[#0077ed] active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl transition-all shadow-sm"
            >
              <Sparkles className="w-3.5 h-3.5" />
              开始知识蒸馏
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
