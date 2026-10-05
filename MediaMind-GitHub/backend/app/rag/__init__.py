"""
RAG 核心服务群单例
全局共享同一份 ChromaDB 连接、BM25 实例与 QAService，避免重复创建和内存浪费
"""
from app.rag.vector_store import VectorStoreService
from app.rag.bm25 import BM25Service
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.reranker import RerankerService
from app.rag.chunking import ChunkingService
from app.rag.qa import QAService

# 全局唯一单例，常驻内存随时待命
vector_store = VectorStoreService(persist_dir="./data/chroma_db")
bm25_service = BM25Service()
hybrid_retriever = HybridRetriever(vector_store=vector_store, bm25_service=bm25_service)
reranker_service = RerankerService()
chunking_service = ChunkingService()

# 导出专精的 QAService 实例（包含严格的防幻觉提示词、[MM:SS] 时间戳强契约与 0.2 低温）
qa_service = QAService(retriever=hybrid_retriever, reranker=reranker_service)
