# -*- coding: utf-8 -*-
"""Bilingual test set built from the sample wavs that ship with sherpa-onnx models.

References for the mixed zh/en clips were hand-labelled by listening + cross-checking
five models; treat a ±1 token disagreement as noise.
"""
TESTSET = [
    # (category, relative path under models root, reference)
    ("zh", "sherpa-onnx-paraformer-zh-2024-03-09/test_wavs/0.wav",
     "对我做了介绍啊那么我想说的是呢大家如果对我的研究感兴趣呢嗯"),
    ("zh", "sherpa-onnx-paraformer-zh-2024-03-09/test_wavs/1.wav",
     "重点呢想谈三个问题首先呢就是这一轮全球金融动荡的表现"),
    ("zh", "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/test_wavs/zh.wav",
     "开放时间早上九点至下午五点"),
    ("en", "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/test_wavs/en.wav",
     "the tribal chieftain called for the boy and presented him with fifty pieces of gold"),
    ("en", "sherpa-onnx-whisper-turbo/test_wavs/0.wav",
     "after early nightfall the yellow lamps would light up here and there the squalid quarter of the brothels"),
    ("en", "sherpa-onnx-whisper-turbo/test_wavs/1.wav",
     "god as a direct consequence of the sin which man thus punished had given her a lovely child "
     "whose place was on that same dishonoured bosom to connect her parent for ever with the race "
     "and descent of mortals and to be finally a blessed soul in heaven"),
    ("mix", "sherpa-onnx-paraformer-zh-2024-03-09/test_wavs/2-zh-en.wav",
     "yesterday was 星期一 today is tuesday 明天是星期三"),
    ("mix", "sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20/test_wavs/0.wav",
     "昨天是 monday today is 礼拜二 the day after tomorrow 是星期三"),
    ("mix", "sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20/test_wavs/1.wav",
     "这是第一种第二种叫呃与 always always 什么意思啊"),
    ("mix", "sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20/test_wavs/2.wav",
     "这个是频繁的啊不认识记下来 frequently 频繁的"),
    ("mix", "sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20/test_wavs/3.wav",
     "第一句是个什么时态加了 es 是一般现在时对后面把它时态写上"),
]
