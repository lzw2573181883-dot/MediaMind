# 文件路径：backend/app/rag/vector_store.py
# 职责：负责将带时间戳的 VideoChunk 转换为高维向量，存入本地持久化 Chroma 数据库，并提供毫秒级时间戳锚定的语义召回服务。

import chromadb
import httpx
from typing import List, Dict, Any, Optional
from app.config import settings
from app.rag.chunking import VideoChunk


class VectorStoreService:
    """
    向量存储与检索服务中台
    底层驱动：ChromaDB（本地嵌入式、轻量、无需额外维护独立数据库服务）
    向量模型：智谱 AI embedding-3（2048 维高精度稠密向量）
    """

    def __init__(self, persist_dir: str = "./data/chroma_db"):
        # 1. 初始化本地磁盘持久化客户端（重启服务数据不丢失）
        self.client = chromadb.PersistentClient(path=persist_dir)
        
        # 2. 获取或创建视频切片集合，指定使用余弦相似度（cosine）作为空间度量
        self.collection = self.client.get_or_create_collection(
            name="video_chunks",
            metadata={"hnsw:space": "cosine"}
        )

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:#把文本转化成向量
        """
        调用智谱 AI embedding-3 API，将一组文本批量转换成 2048 维向量
        """
        if not texts:
            return []

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.ZHIPUAI_BASE_URL}/embeddings",
                headers={
                    "Authorization": f"Bearer {settings.ZHIPUAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "embedding-3",
                    "input": texts
                }
            )
            response.raise_for_status()
            data = response.json()
            # 提取每个文本对应的 2048 维向量
            return [item["embedding"] for item in data["data"]]

    async def add_chunks(self, bvid: str, chunks: List[VideoChunk]):
        """
        将切块（VideoChunk）及其时间戳元数据一同写入 Chroma 数据库
        新向量准备好后，删除同一 bvid 的旧切片，再写入本次全部切片。
        """
        if not chunks:
            return

        texts = [chunk.text for chunk in chunks]
        
        # 1. 批量向量化
        embeddings = await self.get_embeddings(texts)

        # 2. 准备主键 ID
        ids = [chunk.chunk_id for chunk in chunks]

        # 3. 构造元数据字典（Metadata）：保存时间戳与视频对应关系
        metadatas = [
            {
                "bvid": chunk.bvid,
                "chunk_id": chunk.chunk_id,
                "start_time": chunk.start_time,
                "end_time": chunk.end_time,
                "time_str": chunk.time_str
            }
            for chunk in chunks
        ]

        # 4. 清除该视频的旧切片，再存入本次全部切片。
        self.collection.delete(where={"bvid": bvid})
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=texts
        )
####准备结束，开始召回重排和生成
#召回
    async def search(
        self, 
        query: str, 
        bvid: Optional[str] = None, 
        top_k: int = 15
    ) -> List[Dict[str, Any]]:
        """
        语义相似度检索：
        输入用户提问 -> 转换为向量 -> 在 Chroma 库中按余弦相似度召回最相关的 Top-K 个视频切块
        可选择通过 bvid 限定在特定视频内搜索
        """
        # 1. 将查询文本转换为 2048 维向量
        query_embeddings = await self.get_embeddings([query])
        if not query_embeddings:
            return []
        query_vec = query_embeddings[0]

        # 2. 构造元数据过滤条件（实现单视频隔离检索，防止跨视频产生幻觉）
        where_filter = {"bvid": bvid} if bvid else None

        # 3. 发起向量检索
        results = self.collection.query(
            query_embeddings=[query_vec],
            n_results=top_k,
            where=where_filter
        )

        # 4. 组装召回结果
        hits: List[Dict[str, Any]] = []
        if results and results.get("ids") and len(results["ids"]) > 0 and len(results["ids"][0]) > 0:
            for i in range(len(results["ids"][0])):
                meta = results["metadatas"][0][i]
                doc = results["documents"][0][i]
                dist = results["distances"][0][i] if "distances" in results else None
                
                # 余弦距离转相似度分数：score = 1 - distance (范围 0~1，越接近 1 越相似)
                score = round(1.0 - dist, 4) if dist is not None else None

                hits.append({
                    "chunk_id": meta.get("chunk_id", results["ids"][0][i]),
                    "bvid": meta.get("bvid", ""),
                    "start_time": meta.get("start_time", 0),
                    "end_time": meta.get("end_time", 0),
                    "time_str": meta.get("time_str", "00:00"),
                    "text": doc,
                    "distance": dist,
                    "score": score
                })
        return hits

    def get_all_chunks(self, bvid: str) -> List[Dict[str, Any]]:
        """
        全景知识提取：获取指定视频在 Chroma 库中的【所有切片】，按时间轴正序排列
        供全篇学习笔记与大纲导出使用，彻底避免 Top-3 局部问答导致的以偏概全
        """
        if not bvid:
            return []

        results = self.collection.get(where={"bvid": bvid})
        if not results or not results.get("ids"):
            return []

        chunks: List[Dict[str, Any]] = []
        for i in range(len(results["ids"])):
            meta = results["metadatas"][i] if results.get("metadatas") else {}
            doc = results["documents"][i] if results.get("documents") else ""
            chunks.append({
                "chunk_id": meta.get("chunk_id", results["ids"][i]),
                "bvid": meta.get("bvid", bvid),
                "start_time": meta.get("start_time", 0),
                "end_time": meta.get("end_time", 0),
                "time_str": meta.get("time_str", "00:00"),
                "text": doc
            })

        # 按时间轴从前到后排序，还原整部视频的完整讲述脉络
        chunks.sort(key=lambda c: c["start_time"])
        return chunks

    def get_all_chunks_text(self, bvid: str) -> str:
        """
        将全量切片整理为结构化时间轴长文本，供大模型作为完整的原始素材撰写全篇笔记
        """
        chunks = self.get_all_chunks(bvid)
        if not chunks:
            return ""

        blocks = []
        for c in chunks:
            blocks.append(f"[{c['time_str']}] {c['text']}")
        return "\n\n".join(blocks)
