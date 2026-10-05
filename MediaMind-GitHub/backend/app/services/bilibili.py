import httpx
import time
import urllib.parse
from functools import reduce
from hashlib import md5
from typing import Dict, Any, List, Optional
from app.config import settings

# B站 WBI 签名混淆编码表（用于安全请求播放器及字幕接口）
WBI_MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52
]

def _get_mixin_key(orig: str) -> str:
    return reduce(lambda s, i: s + orig[i], WBI_MIXIN_KEY_ENC_TAB, "")[:32]

def _enc_wbi(params: dict, img_key: str, sub_key: str) -> dict:
    mixin_key = _get_mixin_key(img_key + sub_key)
    curr_time = round(time.time())
    params["wts"] = curr_time
    params = dict(sorted(params.items()))
    params = {k: "".join(filter(lambda chr: chr not in "!*'()", str(v))) for k, v in params.items()}
    query = urllib.parse.urlencode(params)
    wbi_sign = md5((query + mixin_key).encode()).hexdigest()
    params["w_rid"] = wbi_sign
    return params


class BilibiliService:
    """专门负责与 B 站官方接口打交道的底层摄取服务"""
    
    BASE_URL = "https://api.bilibili.com/x/web-interface/view"
    PLAYER_URL = "https://api.bilibili.com/x/player/wbi/v2"

    @classmethod
    async def get_video_info(cls, bvid: str) -> Dict[str, Any]:
        """
        根据 BV 号，异步请求 B 站公开接口，提取出纯净的视频元数据
        """
        # 1. 模拟现代浏览器的 User-Agent，防止被简单风控拦截
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.bilibili.com"
        }
        
        # 2. 使用 httpx 异步客户端发送非阻塞 GET 请求
        async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
            response = await client.get(cls.BASE_URL, params={"bvid": bvid})
            data = response.json()
            
            # 3. 开箱验货：判断 B 站官方业务状态码 code 是否为 0
            if data.get("code") != 0:
                raise Exception(f"B站视频（{bvid}）解析失败: {data.get('message', '未知错误')}")
            
            video_data = data["data"]
            
            # 4. 时长格式化算法：把纯秒数（如 2046）换算成 "34:06" 或 "01:12:05"
            duration_secs = video_data["duration"]
            hours = duration_secs // 3600
            mins = (duration_secs % 3600) // 60
            secs = duration_secs % 60
            
            if hours > 0:
                duration_str = f"{hours:02d}:{mins:02d}:{secs:02d}"
            else:
                duration_str = f"{mins:02d}:{secs:02d}"

            # 5. 提炼并返回纯净字段字典（包含关键的 cid）
            return {
                "bvid": bvid,
                "cid": video_data.get("cid", 0),
                "title": video_data.get("title", ""),
                "author": video_data.get("owner", {}).get("name", "未知UP主"),
                "total_seconds": duration_secs,
                "duration_str": duration_str,
                "cover_url": video_data.get("pic", ""),
                "desc": video_data.get("desc", ""),
            }

    @classmethod
    async def get_subtitles(cls, bvid: str, cid: int) -> List[Dict[str, Any]]:
        """
        根据 bvid 和 cid，尝试从 B 站官方接口获取带时间戳的完整字幕列表。
        若视频无字幕或未配置 Cookie，优雅返回空列表 []，绝不中断系统。
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.bilibili.com"
        }
        cookies = {}
        if settings.BILIBILI_SESSDATA:
            cookies["SESSDATA"] = settings.BILIBILI_SESSDATA

        async with httpx.AsyncClient(headers=headers, cookies=cookies, timeout=12.0) as client:
            try:
                # 1. 尝试获取 WBI 动态签名密钥（若失败则直接请求普通 player/v2）
                nav_res = await client.get("https://api.bilibili.com/x/web-interface/nav")
                nav_data = nav_res.json()
                
                params = {"bvid": bvid, "cid": cid}
                
                if nav_data.get("code") == 0 and "wbi_img" in nav_data.get("data", {}):
                    wbi_img = nav_data["data"]["wbi_img"]
                    img_key = wbi_img.get("img_url", "").split("/")[-1].split(".")[0]
                    sub_key = wbi_img.get("sub_url", "").split("/")[-1].split(".")[0]
                    params = _enc_wbi(params, img_key, sub_key)

                # 2. 请求播放器接口
                player_res = await client.get(cls.PLAYER_URL, params=params)
                player_data = player_res.json()
                
                if player_data.get("code") != 0:
                    return []

                # 3. 提取字幕列表
                sub_list = player_data.get("data", {}).get("subtitle", {}).get("subtitles", [])
                if not sub_list:
                    return []

                # 优先选择中文（zh-CN 或 ai-zh），否则取第一个可用字幕
                target_sub = next(
                    (s for s in sub_list if "zh" in s.get("lan", "").lower()),
                    sub_list[0]
                )
                sub_url = target_sub.get("subtitle_url", "")
                if not sub_url:
                    return []

                # 补齐协议头（B站链接常以 // 开头）
                if sub_url.startswith("//"):
                    sub_url = "https:" + sub_url

                # 4. 下载字幕 JSON 实体内容
                content_res = await client.get(sub_url)
                body = content_res.json().get("body", [])

                # 5. 格式化提取带时间戳的结构化列表
                parsed_subtitles = []
                for item in body:
                    start_sec = float(item.get("from", 0.0))
                    mins = int(start_sec) // 60
                    secs = int(start_sec) % 60
                    time_str = f"{mins:02d}:{secs:02d}"
                    text = str(item.get("content", "")).strip()
                    if text:
                        parsed_subtitles.append({
                            "start_time": int(start_sec),
                            "time_str": time_str,
                            "text": text
                        })
                
                print(f"✅ 成功从 B 站提取到 [{len(parsed_subtitles)}] 条带时间戳的字幕逐字稿！")
                return parsed_subtitles

            except Exception as e:
                print(f"ℹ️ 字幕抓取轻量跳过或异常（无字幕/未填Cookie）: {e}")
                return []

    @classmethod
    def format_subtitles_for_llm(cls, subtitles: List[Dict[str, Any]], max_lines: int = 30000) -> str:
        """
        将结构化字幕转为带有时间戳的标准剧本文本，例如：
        [00:00] 大家好，欢迎来到本期大模型系统设计课。
        [03:20] 针对长视频问题，我们的第一大核心模块是时间感知切片...
        默认支持多达 30000 行字幕，彻底覆盖一小时以上的超长视频。
        """
        if not subtitles:
            return ""
        lines = [f"[{sub['time_str']}] {sub['text']}" for sub in subtitles[:max_lines]]
        return "\n".join(lines)
