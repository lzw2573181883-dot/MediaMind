# 文件路径：backend/app/rag/qa.py
# 职责：RAG 问答生成引擎（QA Engine）
# 1. 统筹调用 HybridRetriever（粗排 15 个）与 RerankerService（精选 Top-3）
# 2. 将精选出的 Top-3 黄金切片拼装为结构化参考上下文（Context）
# 3. 注入防幻觉强契约 Prompt，强制要求大模型在引用事实时附带 [MM:SS] 时间戳标记
# 4. 调用大语言模型（GLM-4），生成专业、严谨且可点击溯源跳转的最终回答

from typing import Dict, Any, List
import httpx
from app.config import settings
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.reranker import RerankerService


class QAService:
    """
    RAG 智能问答中台服务（总指挥官）
    """

    def __init__(self, retriever: HybridRetriever, reranker: RerankerService):
        # 依赖注入：明确持有混合检索器与重排服务实例
        self.retriever = retriever
        self.reranker = reranker

    async def answer(
        self, 
        query: str, 
        bvid: str, 
        recall_top_k: int = 15,
        final_top_k: int = 3,
        history: List[Dict[str, str]] | None = None,
    ) -> Dict[str, Any]:
        """
        端到端问答链路：粗排检索 -> 交叉重排 -> 组装上下文 -> 大模型生成
        """
        # 1. 粗排阶段：调用双路检索器，从向量库与 BM25 中召回候选切片
        candidates = await self.retriever.search(query=query, bvid=bvid, top_k=recall_top_k)
        if not candidates:
            return {
                "answer": "抱歉，在当前视频知识库中未找到与您提问相关的内容。",
                "sources": []
            }

        # 2. 重排阶段：把 15 个候选切片原样送给重排器，精挑 Top-3 黄金切片
        golden_chunks = await self.reranker.rerank(query=query, candidates=candidates, top_k=final_top_k)

        # 3. 上下文拼装：将 Top-3 切片的台词与时间戳整合成 Prompt 背景资料
        context_blocks = []
        for idx, c in enumerate(golden_chunks, 1):
            time_tag = c.get("time_str", "00:00")
            snippet = c.get("text", "")
            context_blocks.append(f"【参考切片 {idx} (时间戳 {time_tag})】\n{snippet}")
        context_str = "\n\n".join(context_blocks)

        # 4. 构建防幻觉强契约 Prompt，强制标注 [MM:SS] 时间戳锚点
        system_prompt = (
            "你是一个极度严谨的多模态长视频知识问答助手。\n"
            "你的任务是仅根据下方提供的【原片台词切片】回答用户的问题。\n\n"
            "【核心回答规则】：\n"
            "1. 必须在所有引用事实、观点、数据或结论的句子后，标注精确的时间戳格式，例如 [12:09] 或 [23:44]。\n"
            "2. 【绝对禁令】：严禁说“根据切片1”、“切片2提到”这种内部代词，用户根本看不见切片编号！必须直接陈述事实并在句尾打上时间戳！\n"
            "   - 错误范例：“根据切片2中的描述，持续录制3分钟手机会变烫。”\n"
            "   - 正确范例：“在持续录制 4K 视频约 3 分钟后，手机摄像头下方会极其滚烫，甚至能用来煎鸡蛋 [12:09]。”\n"
            "3. 严禁捏造切片中未提及的信息。如果提供的切片不足以完全回答，请如实说明。\n"
            "4. 保持回答清晰客观、逻辑严谨、用词精炼。"
        )
        system_prompt += (
            "\n历史对话仅用于理解指代和追问，不能作为视频事实依据。"
            "历史回答与本轮视频切片不一致时，以视频切片为准。"
        )
        user_prompt = f"【原片台词切片】\n{context_str}\n\n【用户提问】\n{query}\n\n请直接回答（牢记：每个关键事实后必须标注 [MM:SS] 时间戳，严禁使用“切片X”）："

        # 5. 调用大语言模型（GLM-4）进行推理生成
        headers = {
            "Authorization": f"Bearer {settings.ZHIPUAI_API_KEY}",
            "Content-Type": "application/json"
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.ZHIPUAI_BASE_URL}/chat/completions",
                headers=headers,
                json={
                    "model": "glm-4-flash",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        *(history or []),
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.2  # 低温模式，保证回答稳重严谨，消除幻觉
                }
            )
            response.raise_for_status()
            data = response.json()
            answer_text = data["choices"][0]["message"]["content"].strip()

        # 6. 打包输出：既返回最终答案，又附带参考资料切片（供前端渲染可点击卡片）
        return {
            "answer": answer_text,
            "sources": [
                {
                    "chunk_id": c.get("chunk_id", ""),
                    "time_str": c.get("time_str", "00:00"),
                    "start_time": c.get("start_time", 0),
                    "end_time": c.get("end_time", 0),
                    "text": c.get("text", "")
                }
                for c in golden_chunks
            ]
        }
