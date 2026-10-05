# 文件路径：backend/app/rag/bm25.py
# 职责：负责文本分词（jieba）与 BM25 词频倒排索引构建，提供纯内存级的快速关键词精确检索服务（稀疏检索 Sparse Search）。

import jieba
from typing import List, Dict, Any
from rank_bm25 import BM25Okapi
from app.rag.chunking import VideoChunk


class BM25Service:
    """
    BM25 关键词检索服务中台
    算法：Okapi BM25 词频-逆文档频率（TF-IDF）进阶算法
    特点：死磕专有名词、产品型号、具体代码与数字，弥补向量模型可能存在的语义泛化遗漏
    """

    def __init__(self):
        # 内存索引池：以 bvid 为 key，保存各个视频专属的 BM25 引擎与切片原始对象
        # 结构：{ "bvid": { "bm25": BM25Okapi实例, "chunks": [VideoChunk, ...] } }
        self.indices: Dict[str, Dict[str, Any]] = {}

    def index_chunks(self, bvid: str, chunks: List[VideoChunk]):
        """
        为指定视频的切片构建 BM25 倒排索引
        在切块完成后执行一次，建立内存索引字典
        """
        if not chunks:
            return

        # 1. 使用结巴分词对每个切块进行中文词条切分
        tokenized_corpus = [list(jieba.cut(c.text)) for c in chunks]

        # 2. 实例化 BM25 统计检索对象
        bm25 = BM25Okapi(tokenized_corpus)

        # 3. 存入内存字典管理
        self.indices[bvid] = {
            "bm25": bm25,
            "chunks": chunks
        }

    def search(self, query: str, bvid: str, top_k: int = 15) -> List[Dict[str, Any]]:
        """
        BM25 词频检索方法：
        输入用户提问 -> 分词 -> 匹配词频权重 -> 按相关度降序输出候选切片
        """
        if bvid not in self.indices:
            return []

        bm25 = self.indices[bvid]["bm25"]
        chunks = self.indices[bvid]["chunks"]

        # 1. 对用户提问也进行中文分词
        tokenized_query = list(jieba.cut(query))

        # 2. 获取所有切片的词频匹配得分
        scores = bm25.get_scores(tokenized_query)

        # 3. 按照得分从高到低排序，截取前 top_k 个候选切片的下标
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        # 4. 组装返回数据列表（天然保序）
        hits: List[Dict[str, Any]] = []
        for rank, idx in enumerate(ranked_indices):
            chunk = chunks[idx]
            hits.append({
                "chunk_id": chunk.chunk_id,
                "bvid": chunk.bvid,
                "start_time": chunk.start_time,
                "end_time": chunk.end_time,
                "time_str": chunk.time_str,
                "text": chunk.text,
                "bm25_rank": rank + 1,
                "bm25_score": round(float(scores[idx]), 4)
            })
        return hits
