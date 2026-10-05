# 文件规划：backend/app/rag/chunking.py
#作用：把长视频的 864 行零散台词，切成一块块包含完整语义、且牢牢贴着时间戳的“知识切片（Chunks）”。
from pydantic import BaseModel
from typing import List, Dict, Any

# 1. 单个切片的数据模具（规约）
class VideoChunk(BaseModel):#数据库中，切好的每一块
    chunk_id: str       # 切片唯一身份证，例如 "BV1cSec6tEux_chunk_0"
    bvid: str           # 归属哪个视频
    text: str           # 这块切片的真实文字内容（约 300~512 字）
    start_time: int     # 本切片第一句话的起始秒数（例如 237 秒）
    end_time: int       # 本切片最后一句话的结束秒数（例如 290 秒）
    time_str: str       # 格式化时间戳字符串，方便前端展示（例如 "03:57"）


# 2. 时间戳滑动窗口切块引擎
class ChunkingService:
    @classmethod
    def chunk_subtitles(#方法规定的函数类型
        cls, 
        bvid: str, 
        subtitles: List[Dict[str, Any]], #字幕是列表（字典（字符串：任意类型））
        chunk_size: int = 512, #规定的最大块尺寸
        overlap: int = 64#规定重叠的尺寸
    ) -> List[VideoChunk]:#指定函数返回的类型必须是列表（规定的 VideoChunk）
        """
        输入：B 站抓到的 864 行字幕列表
        输出：按 512 字符 + 64 字符重叠 切割好的 VideoChunk 列表
        """
        if not subtitles:
            return []

        chunks: List[VideoChunk] = []#相当于大仓库，把current_sentences中每切好的部分存放到这里
        current_sentences: List[Dict[str, Any]] = []#表示当前的切块工作台，可以看作一个箱，每存够 512 的内容就把箱子放到仓库里
        current_len = 0#当前此时current_sentences的长度，（之前规定最长为 chunk_size）
        chunk_idx = 0#用来记录到第几个箱了

        for sub in subtitles:#让 sub遍历subtitles，并把每一轮循环的值也给 sub
            text = sub.get("text", "").strip()#.get（） 是取字典中值的函数.strip 是清除字符串首尾空白格
            if not text:#text若空（0），not 0 = 1； if 1，也就是说 text 为空时，执行 if 里面的内容
                continue

            current_sentences.append(sub)#此时将这轮的sub里的内容存放在这个暂存工作台中
            current_len += len(text)#用来记录当前工作台文字的长度

            # 当当前积攒的台词字数达到 512 字符时，打包成一个切片！
            if current_len >= chunk_size:#若当前工作台的内容超过了规定的最大长度（箱子装满该放仓库了）
                # 第一句话的秒数作为整个切片的起始时间
                st = current_sentences[0]["start_time"]#用st记录当前工作台处理这块字幕的开始时间，写法是 st=第0个列表所在的字典中【字符为 start_time】的值
                et = current_sentences[-1]["start_time"]
                
                # 换算成漂亮的时间戳 "03:57"
                m = st // 60
                s = st % 60
                time_str = f"{m:02d}:{s:02d}"

                # 拼装出这 500 字的纯文本
                full_text = " ".join([s["text"] for s in current_sentences])#用变量s在工作台中遍历，并把字典中的值给 s，然后在用join把s中存的字典给字符串列表。用空格去隔开每一个字典（把暂存工作台中的内容提取出来，把箱子装进仓库）

                chunks.append(VideoChunk(#把箱子正式添加到仓库的最后一个位置
                    chunk_id=f"{bvid}_chunk_{chunk_idx}",#记录箱子是哪个bvid，和这是关于这个bvid的第几个箱子
                    bvid=bvid,
                    text=full_text,#把刚才提取出来的箱子内容放进去。
                    start_time=st,#记录开始结束时间
                    end_time=et,
                    time_str=time_str
                ))
                chunk_idx += 1#装完箱让记录加一

                # 🌟 核心滑动窗口算法：保留末尾 64 个字符给下一个切片，防止语义被一刀切断。
                # 如：两句话如果刚好被拦腰截断在两个箱子里，上一箱看了上句，下一箱才看到下句，上下文就断片了
                kept_sentences = []#用来存放保留下来给下一个 chunk 用的字幕句子
                kept_len = 0#记录保留句子的长度有没有达到64
                for s_item in reversed(current_sentences):#reversed()把列表倒叙遍历，表示从装满箱子中往前挑几句话
                    kept_sentences.insert(0, s_item)#从倒数第一第一句话开始把他们插入到列表中，insert（0）是插入头部
                    kept_len += len(s_item["text"])#更新当前存放的文本长度
                    if kept_len >= overlap:#若超过规定的64，则表示已经存放足够多的语义
                        break
                
                current_sentences = kept_sentences#重置下一次工作台中的内容（下一工作台的初始化）
                                           #直接用上一次工作台后64个文本赋值给工作台，而不是加入到这个列表的底部
# 切片 1 (0 ~ 512 字):
#[台词 A ➔ 台词 B ➔ 台词 C ➔ ... ➔ 【台词 X ➔ 台词 Y】] (封箱打包第 1 块)
                           #              │
                           #  保留最后 64 个字不扔掉！
                           #              │
                           #              ▼
#切片 2:
                    #   [【台词 X ➔ 台词 Y】 ➔ 台词 Z ➔ 台词 1 ➔ ... ] (作为第 2 块的开头)
                current_len = kept_len#更新下一次工作台初始长度

        # 处理最后剩余不足 512 字的尾巴台词
        if current_sentences:
            st = current_sentences[0]["start_time"]
            et = current_sentences[-1]["start_time"]
            m = st // 60
            s = st % 60
            full_text = " ".join([s["text"] for s in current_sentences])
            chunks.append(VideoChunk(
                chunk_id=f"{bvid}_chunk_{chunk_idx}",
                bvid=bvid,
                text=full_text,
                start_time=st,
                end_time=et,
                time_str=f"{m:02d}:{s:02d}"
            ))

        return chunks