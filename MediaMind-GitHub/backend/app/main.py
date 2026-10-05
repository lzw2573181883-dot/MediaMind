import logging
import re
from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.schemas.extraction import VideoExtractRequest, MediaChapter, VideoExtractionResult
from app.schemas.chat import ChatRequest, ChatResponse

# 导入 B 站外勤服务与 AI 智囊服务
from app.services.bilibili import BilibiliService
from app.services.llm import LLMService

# 导入共享的 RAG 全局服务单例与 Agent 智能体执行器（彻底复用，杜绝重复创建）
from app.rag import vector_store, bm25_service, chunking_service
from app.agent.executor import agent_executor

logger = logging.getLogger(__name__)
EXTRACTION_FAILURE_MESSAGE = "解析失败，请稍后重试。"

# 1. 实例化一个服务生（FastAPI 应用）
app = FastAPI(
    title="MediaMind-RAG 智能中台",
    description="多模态长视频知识蒸馏与精准时间戳检索后端",
    version="0.1.0"
)

# 2. 发一张“通行证”（CORS 跨域配置）中间件
# 允许我们前端（http://localhost:5173）跨端口访问后端接口
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(request: Request, exc: RequestValidationError):
    if request.url.path == "/api/v1/extract":
        logger.warning("视频解析请求格式错误：%s", exc.errors())
        return JSONResponse(status_code=422, content={"detail": EXTRACTION_FAILURE_MESSAGE})
    return await request_validation_exception_handler(request, exc)

# 3. 根路径与健康检查接口
@app.get("/")
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "message": "MediaMind 后端服务运行正常，随时待命！",
        "app": "MediaMind-RAG 智能中台",
        "version": "0.1.0",
        "docs_url": "http://127.0.0.1:8000/docs"
    }


# 4. 长视频知识抽取与入库接口
@app.post("/api/v1/extract", response_model=VideoExtractionResult, tags=["Knowledge Extraction"])
async def extract_video(req: VideoExtractRequest):
    try:
        return await _extract_video(req)
    except Exception as exc:
        logger.exception("视频解析失败，url=%r", req.url)
        status_code = exc.status_code if isinstance(exc, HTTPException) else 500
        raise HTTPException(status_code=status_code, detail=EXTRACTION_FAILURE_MESSAGE) from exc


async def _extract_video(req: VideoExtractRequest):
    # 第一步：安检链接是否为空
    raw_url = req.url.strip()
    if not raw_url:
        raise HTTPException(status_code=400, detail="输入的视频链接不能为空！")

    # 第二步：使用正则表达式提取 BV 号
    match = re.search(r"(BV[a-zA-Z0-9]{10})", raw_url)
    if not match:
        raise HTTPException(
            status_code=400, 
            detail="无效的 B 站链接！未识别到形如 BV1xx411c7mD 的视频唯一标识符"
        )
    bvid = match.group(1)

    # 第三步：【外勤服务】抓取真实的视频元数据
    video_info = await BilibiliService.get_video_info(bvid)

    # 3.5 步：【字幕嗅探服务】尝试抓取该视频带精准时间戳的完整字幕
    cid = video_info.get("cid", 0)
    subtitles = await BilibiliService.get_subtitles(bvid=bvid, cid=cid)

    if not subtitles:
        raise ValueError(f"视频 {bvid} 未获取到可用字幕，无法建立知识库")
    content_for_llm = BilibiliService.format_subtitles_for_llm(subtitles)

    # 字幕切片、向量入库和 BM25 建索引必须完成，才能向前端报告成功。
    chunks = chunking_service.chunk_subtitles(bvid=bvid, subtitles=subtitles, chunk_size=512, overlap=64)
    if not chunks:
        raise ValueError(f"视频 {bvid} 字幕切片结果为空")
    await vector_store.add_chunks(bvid=bvid, chunks=chunks)
    bm25_service.index_chunks(bvid=bvid, chunks=chunks)
    logger.info("视频 %s 已完成入库，共 %s 个切片", bvid, len(chunks))

    # 第四步：【智囊服务】调用智谱 GLM 大模型进行真正的深度知识蒸馏！
    distilled = await LLMService.distill_knowledge(
        title=video_info["title"],
        content=content_for_llm,
        duration_str=video_info.get("duration_str", "未知")
    )

    # 第五步：将大模型蒸馏出的章节动态组装为 MediaChapter 列表（时间戳双向鲁棒校准与安全兜底）
    raw_chapters = distilled["chapters"]
    if not isinstance(raw_chapters, list) or not raw_chapters:
        raise ValueError("大模型返回的章节列表为空或格式不正确")
    parsed_chapters = []
    total_sec = video_info.get("total_seconds", 0)

    for idx, ch in enumerate(raw_chapters):
        raw_tstr = str(ch.get("time_str", "")).strip()
        raw_st = ch.get("start_time")

        parsed_from_tstr = None
        if ":" in raw_tstr:
            try:
                parts = [int(p) for p in raw_tstr.split(":") if p.isdigit()]
                if len(parts) == 2:
                    parsed_from_tstr = parts[0] * 60 + parts[1]
                elif len(parts) == 3:
                    parsed_from_tstr = parts[0] * 3600 + parts[1] * 60 + parts[2]
            except Exception:
                pass

        parsed_from_raw_st = None
        if raw_st is not None:
            try:
                if isinstance(raw_st, str) and ":" in raw_st:
                    parts = [int(p) for p in raw_st.split(":") if p.isdigit()]
                    if len(parts) == 2:
                        parsed_from_raw_st = parts[0] * 60 + parts[1]
                    elif len(parts) == 3:
                        parsed_from_raw_st = parts[0] * 3600 + parts[1] * 60 + parts[2]
                else:
                    parsed_from_raw_st = int(raw_st)
            except Exception:
                pass

        # 核心逻辑：优先使用大模型直接从字幕抓取的真实物理时间 time_str（MM:SS）
        if parsed_from_tstr is not None:
            st_secs = parsed_from_tstr
        elif parsed_from_raw_st is not None:
            st_secs = parsed_from_raw_st
        else:
            st_secs = 0

        # 防御性边界约束：章节时间绝不能超出视频总时长
        if total_sec > 0 and st_secs > total_sec:
            st_secs = max(0, total_sec - 10)

        m = st_secs // 60
        s = st_secs % 60
        normalized_time_str = f"{m:02d}:{s:02d}"

        parsed_chapters.append(
            MediaChapter(
                id=f"ch-{idx + 1}",
                title=ch.get("title", f"第 {idx + 1} 章节"),
                start_time=st_secs,
                time_str=normalized_time_str,
                summary=ch.get("summary", "")
            )
        )

    # 第六步：构建并返回最终的纯正真实数据！
    return VideoExtractionResult(
        id=f"media-{bvid}",
        platform="Bilibili",
        title=video_info["title"],
        author=video_info["author"],
        duration_str=video_info["duration_str"],
        total_seconds=video_info["total_seconds"],
        summary=distilled["summary"],
        keywords=distilled["keywords"],
        chapters=parsed_chapters
    )


# 5. Agent 智能问答接口（原生 Function Calling + ReAct 状态机闭环调度）
@app.post("/api/v1/chat", response_model=ChatResponse, tags=["Agent QA"])
async def chat_with_agent(req: ChatRequest):
    """
    智能体问答接口：前端输入指令，Agent 自主决策调用 RAG 切片检索或导出 Word 文档
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="提问内容不能为空！")

    try:
        # 交给 Agent 大脑进行自主意图识别与工具链调度！
        result = await agent_executor.run(
            user_prompt=req.query,
            bvid=req.bvid.strip(),
            history=[message.model_dump() for message in req.history],
        )
        return result
    except Exception as e:
        print(f"❌ Agent 调度链路异常: {e}")
        raise HTTPException(status_code=500, detail=f"Agent 处理失败: {str(e)}")
