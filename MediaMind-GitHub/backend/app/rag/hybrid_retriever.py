# 文件路径：backend/app/rag/hybrid_retriever.py
# 职责：统筹调度 VectorStore（向量检索）与 BM25Service（关键词检索）执行双路并发召回，并利用 RRF（倒数排名融合算法）进行无量纲重排与候选切片输出。
#混合召回
from typing import List, Dict, Any
from app.rag.vector_store import VectorStoreService
from app.rag.bm25 import BM25Service


class HybridRetriever:
    """
    双路混合检索与融合调度中台
    输入：用户的查询 Prompt与视频 ID
    运作模式：
      - 第一路：Chroma 向量语义召回（捕捉深层意图、近义词与宏观话题）
      - 第二路：BM25 词频关键词召回（捕捉精准专有名词、生僻型号与数字）
      - 融合算法：Reciprocal Rank Fusion（RRF，倒数排名融合）
    """

    def __init__(self, vector_store: VectorStoreService, bm25_service: BM25Service):
        # 依赖注入：持有向量存储与 BM25 服务的实例
        self.vector_store = vector_store
        self.bm25_service = bm25_service

    async def search(
        self, 
        query: str, 
        bvid: str, 
        top_k: int = 15,
        rrf_k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        执行双路混合检索，并用 RRF 算法进行排名融合
        :param query: 用户提问
        :param bvid: 目标视频 ID
        :param top_k: 粗排召回的候选片段数（宽口径设为 15，供下游 Reranker 进一步精选出 Top-3）
        :param rrf_k: RRF 平滑常数（学术界经典默认值 60，平滑前序排名的分数差距）
        """
        # 1. 第一路：向向量数据库请求 top_k 个候选（语义相似度）
        dense_hits = await self.vector_store.search(query=query, bvid=bvid, top_k=top_k)

        # 2. 第二路：向 BM25 引擎请求 top_k 个候选（关键词精确匹配）
        sparse_hits = self.bm25_service.search(query=query, bvid=bvid, top_k=top_k)

        # 3. 倒数排名融合（RRF 算法）：只看名次，消除余弦值（0~1）与 BM25 分数（0~几十）的量纲差异
        doc_scores: Dict[str, float] = {}
        doc_map: Dict[str, Dict[str, Any]] = {}

        # 统计向量一路的排名得分
        for rank, hit in enumerate(dense_hits):
            cid = hit["chunk_id"]
            doc_map[cid] = hit
            doc_scores[cid] = doc_scores.get(cid, 0.0) + 1.0 / (rrf_k + rank + 1)

        # 统计 BM25 一路的排名得分
        for rank, hit in enumerate(sparse_hits):
            cid = hit["chunk_id"]
            if cid not in doc_map:
                doc_map[cid] = hit
            doc_scores[cid] = doc_scores.get(cid, 0.0) + 1.0 / (rrf_k + rank + 1)

        # 4. 根据 RRF 融合总分从高到低排序，截取 Top-K
        sorted_cids = sorted(doc_scores.keys(), key=lambda cid: doc_scores[cid], reverse=True)[:top_k]

        # 5. 拼装融合后的最终结果列表返回
        final_hits: List[Dict[str, Any]] = []
        for cid in sorted_cids:
            item = dict(doc_map[cid])
            item["rrf_score"] = round(doc_scores[cid], 5)
            final_hits.append(item)

        return final_hits
