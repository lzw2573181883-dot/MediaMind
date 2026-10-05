# 文件路径：backend/app/rag/reranker.py
# 职责：负责对混合检索召回的 15 个候选切片进行 Cross-Encoder 深度交叉重排，挑出语义契合度最高的 Top-3 黄金切片。

import httpx
from typing import List, Dict, Any
from app.config import settings


class RerankerService:
    """
    Cross-Encoder 交叉重排服务中台
    架构模式：基于 LLM-as-a-Reranker（RankGPT 范式）的交叉注意力语义重排
    输入：用户的查询 Prompt + 粗排召回的 15 个候选切片
    输出：精选出的 Top-3 黄金切片，带 rerank_rank 与时间戳元数据
    """

    def __init__(self):
        pass

    async def rerank(
        self, 
        query: str, 
        candidates: List[Dict[str, Any]], 
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        对粗排候选集执行 Cross-Encoder 语义精排
        :param query: 用户问题
        :param candidates: 粗排召回的 15 个切片字典列表
        :param top_k: 最终精选的目标数量（默认 3）
        """
        # 1. 防御性检查：若候选集为空，直接返回空；若候选集本就不足 top_k，直接截取返回
        if not candidates:
            return []
        if len(candidates) <= top_k:
            return candidates[:top_k]

        # 2. 构造紧凑的候选切片列表，生成带索引编号的摘要文本
        docs_summary = []
        for idx, c in enumerate(candidates):
            # 截取整个字符作为语义研判样本，去掉换行符保持整洁
            text_preview = c["text"].replace("\n", " ").strip()
            time_str = c.get("time_str", "00:00")
            docs_summary.append(f"[{idx}] (时间戳: {time_str}) {text_preview}")

        candidates_text = "\n".join(docs_summary)

        # 3. 构造重排裁判 Prompt（让大模型对 Query 和所有 Document 进行全注意力交叉对比）
        prompt = f"""你是一个顶级的文档重排专家（Cross-Encoder Reranker）。
请严格根据以下候选切片与用户提问的“直接相关性”和“能回答问题的程度”，对候选切片进行重新排序。

【用户提问】：
{query}

【候选切片列表】：
{candidates_text}

【评判与输出规则】：
1. 找出最能准确、直接回答用户提问的切片编号。
2. 仅输出按照相关性从高到低排序后的编号，用英文逗号分隔，不要有任何多余文字、不要换行、不要解释！
例如输出格式：
3, 0, 7, 2, 5"""

        # 4. 调用极速轻量大模型（glm-4-flash）进行端到端重排打分
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{settings.ZHIPUAI_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.ZHIPUAI_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "glm-4-flash",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.01  # 极低温度，消除随机性，保证严格客观
                    }
                )
                response.raise_for_status()
                data = response.json()
                raw_rank_str = data["choices"][0]["message"]["content"].strip()

                # 5. 解析模型输出的编号序列（如 "3, 0, 7..."）
                ranked_indices = []
                for part in raw_rank_str.replace("，", ",").split(","):
                    clean_str = part.strip()
                    if clean_str.isdigit():
                        idx = int(clean_str)
                        if 0 <= idx < len(candidates) and idx not in ranked_indices:
                        #if 0<=idx<len(candiates)防止大模型出现幻觉，设立防越界，len(candiates)是指发过来的重拍列表中有多少个元素，and 后面是防止大模型发重复元素
                            ranked_indices.append(idx)

                # 6. 安全兜底：如果模型漏排了部分切片，把未排序的候选按原顺序补在末尾
                for idx in range(len(candidates)):
                    if idx not in ranked_indices:
                        ranked_indices.append(idx)

                # 7. 组装最终胜出的 Top-K 切片列表
                reranked_hits: List[Dict[str, Any]] = []
                for new_rank, idx in enumerate(ranked_indices[:top_k], 1):#（，1）的1是让newrank 从 1 开始数，因为数组是从 0，如果赋值给 0 则不符合逻辑
                    item = dict(candidates[idx])#把第idx个切片传给item这个字典
                    item["rerank_rank"] = new_rank
                    reranked_hits.append(item)

                return reranked_hits

        except Exception as e:
            # 容灾降级：万一网络抖动或解析异常，平滑降级为使用 RRF 粗排的前 top_k，保证系统永远不崩
            print(f"⚠️ Reranker 服务发生异常，平滑降级为粗排 Top-K: {e}")
            return candidates[:top_k]
