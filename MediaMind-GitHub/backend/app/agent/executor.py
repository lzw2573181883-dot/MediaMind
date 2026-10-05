"""
文件路径：backend/app/agent/executor.py
核心职责：MediaMind 意图路由智能体 (Intent Router AgentExecutor)
架构优势：
1. 彻底淘汰复杂 while 循环与一堆容易混淆的临时变量
2. 100% 原汁原味保留 QAService 专精的防幻觉 Prompt、禁止代词禁令与 0.2 低温
3. 真正做到“各司其职”：QA 专精查事实、LLM 专精写笔记、Word 工具专精打印存盘
4. 工业级确定性与响应速度：直来直去的 if-elif-else，执行效率翻倍！
"""

import re
import logging
from typing import Dict, Any, List
from openai import AsyncOpenAI

from app.config import settings
from app.rag import qa_service, vector_store
from app.agent.tools import agent_tools

logger = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 10
MAX_HISTORY_CHARS = 6000


class AgentExecutor:
    """
    智能体路由器（调度总指挥）：
    通过极速意图识别，将用户需求精准路由到对应专精科室（闲聊 / 原版 QA 问答 / Word 笔记撰写与导出）
    """

    def __init__(self):
        # 1. 统一读取全局配置中的首选模型与兜底模型
        self.model = settings.ZHIPUAI_MODEL or "glm-4.7-flash"
        self.fallback_model = "glm-4-flash"

        # 2. 直连智谱大模型开放平台的异步客户端（通用发动机）
        # 设置 max_retries=0，避免 429 时客户端自带的数十秒指数退避卡顿，由我们业务层毫秒级平滑降级
        self.client = AsyncOpenAI(
            api_key=settings.ZHIPUAI_API_KEY,
            base_url=settings.ZHIPUAI_BASE_URL,
            max_retries=0
        )

        # 3. 挂载原汁原味、精心打磨的 QAService（事实侦察特种兵）
        self.qa_service = qa_service

        # 4. 挂载向量库服务（用于按需调取整部视频的全量切片，避免局部问答以偏概全）
        self.vector_store = vector_store

        # 5. 挂载 Word 办公工具箱（排版打印机）
        self.tools = agent_tools

    async def _safe_create_completion(self, messages: list, temperature: float = 0.2, model: str | None = None):
        """
        弹性容灾通用调用：优先使用指定模型，若遭遇 429 访问峰值、超时或任何网络抖动，自动平滑降级至极速备用模型
        """
        target_model = model or self.model
        try:
            return await self.client.chat.completions.create(
                model=target_model,
                messages=messages,
                temperature=temperature
            )
        except Exception as e:
            if target_model != self.fallback_model:
                print(f"\n⚠️ [弹性容灾生效] 模型 {target_model} 调用异常 ({e})，自动毫秒级降级至备用模型 {self.fallback_model}...")
                return await self.client.chat.completions.create(
                    model=self.fallback_model,
                    messages=messages,
                    temperature=temperature
                )
            raise e

    async def _classify_intent(self, user_prompt: str) -> str:
        """只判断当前消息的意图，返回 CHAT / QA / EXPORT。"""
        system_prompt = (
            "你是一个极速意图分类专家。请判断用户的输入意图，只返回下列对应的一个大写英文单词，严禁输出任何其他废话：\n"
            "- CHAT: 日常打招呼、问候、感谢、自我介绍（例如：'你好'、'你是谁'、'谢谢'）\n"
            "- EXPORT: 明确要求导出、下载、保存为 Word/文档/笔记（例如：'导出简报'、'生成Word'、'把笔记保存下来'）\n"
            "- QA: 询问视频内容、评测事实、参数、性能、优缺点等知识点（例如：'发热严重吗'、'支持4K120帧吗'、'续航多久'）"
        )
        try:
            resp = await self._safe_create_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.01,
                model=self.fallback_model
            )
            intent = resp.choices[0].message.content.strip().upper()
            if "EXPORT" in intent:
                return "EXPORT"
            if "CHAT" in intent:
                return "CHAT"
            return "QA"
        except Exception:
            logger.exception("意图判断失败，默认使用视频问答")
            return "QA"

    async def _classify_export_scope(self, user_prompt: str) -> str:
        """判断本轮导出是否需要历史，返回 VIDEO / CONTEXT。"""
        system_prompt = """
判断用户本轮导出要求是否需要历史对话。
只返回 VIDEO 或 CONTEXT，不输出其他内容。

VIDEO：当前要求已经明确，不需要历史对话。
例如：导出整部视频的笔记；整理视频里三种低配芯片的来历。
普通的“导出视频笔记”也属于 VIDEO。

CONTEXT：需要历史才能确定主题、范围或之前约定的格式。
例如：把刚才讨论的内容导出；把上一个回答整理成笔记；
按照刚才说的格式导出。

以当前明确要求为准，不要仅因为出现“刚才”就选择 CONTEXT。
例如“导出整部视频，不参考刚才的讨论”属于 VIDEO。
"""
        resp = await self._safe_create_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.01,
            model=self.fallback_model,
        )
        scope = resp.choices[0].message.content.strip().upper()
        if scope not in {"VIDEO", "CONTEXT"}:
            raise ValueError("导出范围判断结果无效")
        return scope

    async def _write_study_note(self, user_prompt: str, bvid: str, fact_material: str) -> str:
        """
        【金牌撰稿人】：根据真实事实素材，由大模型负责排版、提炼，撰写出包含表格与时间戳的高质量长篇笔记
        """
        system_prompt = (
            "你是一个金牌科技专栏作家兼知识管理专家。\n"
            "你的任务是根据提供的【视频评测真实数据与结论】，为用户排版撰写一份条理极其清晰、包含多级标题、核心要点对比表格与时间戳标记的专业学习笔记正文。\n"
            "【撰写要求】：\n"
            "1. 语言客观精炼，结构严谨；\n"
            "2. 充分保留关键事实后附带的 [MM:SS] 时间戳标记；\n"
            "3. 核心性能对比请优先使用 Markdown 表格呈现，便于后续生成美观文档。"
        )
        user_content = (
            f"【视频真实数据素材】：\n{fact_material}\n\n"
            f"【用户要求】：{user_prompt}\n\n"
            f"请直接输出撰写好的完整笔记正文："
        )

        resp = await self._safe_create_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.3
        )
        return resp.choices[0].message.content.strip()

    async def _write_context_note(
        self,
        user_prompt: str,
        fact_material: str,
        history: List[Dict[str, str]],
    ) -> str:
        """结合历史理解讨论范围，依据视频素材整理笔记正文。"""
        system_prompt = """
你是一个讨论笔记整理助手。

请结合历史对话，理解用户本轮要求整理的内容，并生成笔记正文。

要求：
1. 当前用户要求优先，历史用于理解指代、讨论主题和格式。
2. 只整理用户要求的讨论范围，不自动扩展为整部视频笔记。
3. 视频事实必须依据提供的字幕素材，历史回答不能作为事实依据。
4. 历史回答与字幕不一致时，以字幕为准；字幕未提供的信息不要编造。
5. 保留字幕素材中支持相关事实的 [MM:SS] 时间戳。
6. 只输出笔记正文，不声称文件已经生成或保存。
"""
        user_content = (
            f"【视频字幕素材】：\n{fact_material}\n\n"
            f"【本轮导出要求】：{user_prompt}"
        )
        resp = await self._safe_create_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                *history,
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()

    async def run(
        self, user_prompt: str, bvid: str = "",
        history: List[Dict[str, str]] | None = None,
    ) -> Dict[str, Any]:
        """
        核心路由入口：完全摒弃 while 循环，清晰直白的 if-elif-else 三路分流！
        """
        # 没有当前视频时直接聊天；解析视频后再按意图分流。
        bvid = bvid.strip()
        # 历史由前端按用户、助手成对发送；最多 10 轮，超长时整轮删除。
        history = (history or [])[-MAX_HISTORY_TURNS * 2:]
        while history and sum(len(message["content"]) for message in history) > MAX_HISTORY_CHARS:
            history = history[2:]
        if bvid:
            intent = await self._classify_intent(user_prompt)
        else:
            intent = "CHAT"

        # ============================================================
        # 场景 1：日常闲聊问候 (CHAT)
        # ============================================================
        if intent == "CHAT":
            chat_prompt = "你是 MediaMind Agent，一个专业的长音视频知识库助手。请礼貌亲切地回答用户，并介绍你能帮用户查视频事实和生成/导出笔记。"
            if not bvid:
                chat_prompt += "当前用户尚未解析视频，可以正常进行普通聊天；涉及视频具体内容或导出视频笔记时，请提示先解析视频，不要推测视频内容。"
            resp = await self._safe_create_completion(
                messages=[
                    {"role": "system", "content": chat_prompt},
                    *history,
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7
            )
            content = (resp.choices[0].message.content or "").strip()
            return {
                "answer": content or "你好！我是 MediaMind 知识库 AI 助理，很高兴认识你！请问有什么关于长视频或文档整理的问题可以帮您？",
                "tool_used": False,
                "tool_calls": [],
                "sources": [],
                "model": self.model
            }

        # ============================================================
        # 场景 2：查视频细节 (QA) —— 100% 走原汁原味的 QAService！
        # ============================================================
        elif intent == "QA":
            # 将用户原始提问与已裁剪的历史一起交给 QA。
            qa_res = await self.qa_service.answer(
                query=user_prompt,
                bvid=bvid,
                history=history,
            )
            return {
                "answer": qa_res["answer"],
                "tool_used": True,
                "tool_calls": [
                    {
                        "tool_name": "search_video_rag",
                        "arguments": {"query": user_prompt, "bvid": bvid},
                        "status": "success",
                        "result": f"成功命中 {len(qa_res.get('sources', []))} 个黄金切片"
                    }
                ],
                "sources": qa_res.get("sources", []),
                "model": self.model
            }

        # ============================================================
        # 场景 3：导出 Word 文档 (EXPORT) —— 提取素材 + 大模型撰稿 + 打印机存盘
        # ============================================================
        else:
            # 1. 尝试从向量库提取整部视频的【全量切片】（100% 完整语义，杜绝以偏概全）
            all_material = self.vector_store.get_all_chunks_text(bvid=bvid) if bvid else ""

            # 👉 卫语句（Early Return）：如果连切片都没有，立刻刹车退出！不浪费任何算力与时间！
            if not all_material:
                return {
                    "answer": "抱歉，在当前知识库中未找到该视频的切片内容，无法为您生成并导出笔记。请先确保该视频已成功解析入库！",
                    "tool_used": False,
                    "tool_calls": [],
                    "sources": [],
                    "model": self.model
                }

            # 2. 按本轮要求选择视频笔记或带历史的讨论笔记。
            try:
                scope = await self._classify_export_scope(user_prompt)
                if scope == "CONTEXT":
                    if not history:
                        return {
                            "answer": "目前没有历史对话，请明确要整理的主题或内容。",
                            "tool_used": False,
                            "tool_calls": [],
                            "sources": [],
                            "model": self.model,
                        }
                    written_note = await self._write_context_note(
                        user_prompt=user_prompt,
                        fact_material=all_material,
                        history=history,
                    )
                else:
                    written_note = await self._write_study_note(
                        user_prompt=user_prompt,
                        bvid=bvid,
                        fact_material=all_material,
                    )
            except Exception as e:
                print(f"⚠️ 撰写笔记异常: {e}")
                return {
                    "answer": f"抱歉，大模型在排版生成学习笔记时遇到网络波动 ({str(e)})，请稍后重新尝试！",
                    "tool_used": False,
                    "tool_calls": [],
                    "sources": [],
                    "model": self.model
                }

            # 3. 解析文件名并由 Word 工具在本地磁盘真正存盘
            filename = "评测分析简报.docx"
            match = re.search(r"([^\s，,]+\.docx)", user_prompt)
            if match:
                filename = match.group(1)

            try:
                doc_res = self.tools.export_word_document(
                    filename=filename,
                    title=f"视频 {bvid} 核心知识评测简报",
                    content=written_note
                )
            except Exception as e:
                print(f"⚠️ 导出Word异常: {e}")
                return {
                    "answer": f"✅ **学习笔记已撰写完成！**（但本地写盘时遇到提示：{str(e)}）\n\n**文档内容预览：**\n\n{written_note}",
                    "tool_used": True,
                    "tool_calls": [],
                    "sources": self.vector_store.get_all_chunks(bvid=bvid)[:5],
                    "model": self.model
                }

            # 4. 汇报成功并展示排版优良的预览
            final_text = (
                f"✅ **评测简报已成功生成并保存！**\n\n"
                f"- 📄 **文件名**：{doc_res['filename']}\n"
                f"- 📂 **保存路径**：{doc_res['filepath']}\n\n"
                f"**文档内容预览：**\n\n{written_note}"
            )

            return {
                "answer": final_text,
                "tool_used": True,
                "tool_calls": [
                    {"tool_name": "search_video_rag", "arguments": {"query": user_prompt, "bvid": bvid}, "status": "success", "result": "已完成全量切片知识提取"},
                    {"tool_name": "export_word_document", "arguments": {"filename": filename}, "status": "success", "result": f"已成功保存至 {doc_res['filepath']}"}
                ],
                "sources": self.vector_store.get_all_chunks(bvid=bvid)[:5],
                "model": self.model
            }


# 实例化全局单例，供系统各模块直接调用
agent_executor = AgentExecutor()
