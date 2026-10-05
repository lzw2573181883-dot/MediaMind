import json
import httpx
from typing import Dict, Any
from app.config import settings

class LLMService:
    """专门负责与智谱 GLM 大语言模型进行异步知识蒸馏的业务服务"""

    @classmethod
    async def distill_knowledge(cls, title: str, content: str, duration_str: str = "未知") -> Dict[str, Any]:
        """
        输入：视频标题、内容/字幕、视频总时长
        输出：智谱大模型现场蒸馏出的真 summary、真 keywords、真 chapters 字典！
        """
        # 1. 检查 API Key 是否配置
        if not settings.ZHIPUAI_API_KEY or "your_zhipu" in settings.ZHIPUAI_API_KEY:
            raise Exception("未检测到有效的 ZHIPUAI_API_KEY，请先在 backend/.env 文件中配置！")

        # 2. 精心设计的结构化蒸馏提示词（Prompt）
        # 强约束：命令大模型必须严格输出标准 JSON 格式，且确保关键词数量与章节跨度合理、覆盖全片时间轴
        system_prompt = f"""你是一个顶级的多模态长视频知识蒸馏与结构化分析专家。
请根据提供的视频标题与带 [MM:SS] 时间戳的台词/字幕内容，提炼出 4~7 个覆盖全片完整时间线的核心章节目录。
你必须严格输出纯 JSON 格式，绝不要包含 markdown 代码块标记（如 ```json）或前后闲聊文字。

JSON 输出格式规范：
{{
  "summary": "100-250字全面深度的全局知识摘要，精准概括全片核心始末与要点",
  "keywords": ["标签1", "标签2", "标签3", "标签4", "标签5"],
  "chapters": [
    {{
      "title": "01. 开篇章节标题",
      "time_str": "00:00",
      "summary": "该章节主要讲述的内容要点"
    }},
    {{
      "title": "02. 关键节点章节标题",
      "time_str": "02:30",
      "summary": "该章节主要讲述的内容要点"
    }}
  ]
}}

【核心生成铁律（极其重要）】：
1. 时间戳真实性强约束：
   - time_str 必须直接取自字幕台词前面真实存在的 [MM:SS] 时间戳（例如台词前的 [04:02] 就写 "04:02"，严禁凭空臆造，绝不要写成个位数秒数）。
2. 全片覆盖硬约束：
   - 视频全片总时长为【{duration_str}】。
   - 章节必须按时间线从 00:00 均匀覆盖全片各个主要阶段（开篇背景、中期深入展开、后期实测/高潮、尾声总结），最后一个章节必须落在视频后半程或收尾阶段。
   - 根据全片时长宏观提炼 4 ~ 7 个核心章节，绝对禁止全部扎堆在前几分钟！"""

        user_prompt = f"【视频标题】：{title}\n【视频总时长】：{duration_str}\n\n【全片带时间戳台词/字幕】：\n{content}\n\n请针对以上全片内容，提取出覆盖全片完整时间轴的结构化知识蒸馏结果："

        # 3. 组装请求大门与通行证
        url = f"{settings.ZHIPUAI_BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.ZHIPUAI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": settings.ZHIPUAI_MODEL,  # 使用我们在 .env 里指定的 glm-4.7-flash
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2  # 低温模式，保证严格遵循格式且不胡编乱造
        }

        # 4. 使用异步非阻塞 httpx 发送请求（带高可用自动降级机制：优先主模型，高峰繁忙时自动无缝降级到 glm-4-flash）
        candidate_models = [settings.ZHIPUAI_MODEL]
        if settings.ZHIPUAI_MODEL != "glm-4-flash":
            candidate_models.append("glm-4-flash")

        last_error = None
        for model_name in candidate_models:
            payload["model"] = model_name
            try:
                async with httpx.AsyncClient(timeout=45.0) as client:
                    response = await client.post(url, headers=headers, json=payload)
                    res_data = response.json()

                    # 如果接口返回业务错误（如当前模型访问量过大），尝试下一个备选模型
                    if "error" in res_data:
                        err_msg = res_data["error"].get("message", "未知错误")
                        last_error = err_msg
                        print(f"⚠️ 模型 [{model_name}] 暂时繁忙 ({err_msg})，自动切换至高可用备选模型...")
                        continue

                    raw_content = res_data["choices"][0]["message"].get("content", "")
                    if not raw_content:
                        continue

                    # 5. 防御性清洗：去除大模型可能带上的 ```json 或 ``` 标记
                    clean_json_str = raw_content.replace("```json", "").replace("```", "").strip()
                    return json.loads(clean_json_str)
            except Exception as e:
                last_error = str(e)
                continue

        raise Exception(f"大模型调用异常: {last_error}")
