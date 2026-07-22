# -*- coding: utf-8 -*-
"""全局配置"""

# ---- Whisper 模型 (mlx-whisper, Apple Silicon GPU 加速) ----
# 首次运行会从 Hugging Face 自动下载到本地缓存,之后离线可用
MODEL_REPO = "mlx-community/whisper-large-v3-turbo"
# None = 自动检测语言(中英文混合场景推荐);也可强制指定 "zh" 或 "en"
LANGUAGE = None
# 用带标点的示例文本"提示"模型,减少输出中缺逗号/句号的情况
INITIAL_PROMPT = "以下是带有标点符号的句子。你好，今天天气不错，我们去吃饭吧。"
# 中文输出转换："simplified"=转简体 / "traditional"=转繁体 / "preserve"=保留模型原始输出不转换
OUTPUT_CHINESE = "simplified"
# 自定义词汇表：把你常说但总识别错的专业名词、人名、项目名加进来（追加即可，不用管顺序）。
# 模型会参考这份清单，提高这些词被正确识别的概率。
CUSTOM_VOCABULARY = [
    # "Kubernetes",
    # "faster-whisper",
]

# ---- 录音 ----
SAMPLE_RATE = 16000
CHANNELS = 1
MAX_RECORD_SECONDS = 60  # 防止 Fn 卡住导致无限录音

# ---- 输出 ----
AUTO_TYPE = True  # True: 一律尝试直接输入到光标处
# False: 正常情况下只打字、不占用剪贴板；只有找不到可编辑光标时才会额外存一份到剪贴板兜底
# True: 不管有没有找到光标，每次都额外存一份到剪贴板
ALWAYS_COPY_TO_CLIPBOARD = False

# ---- 热键 ----
MIN_PRESS_MS = 150  # 短于这个时长的 Fn 按下会被忽略，防止误触发
