# LocalASR：Code Review、性能测试与优化方案

> 测试环境：Linux x86_64，4 核 CPU，无 GPU；sherpa-onnx 1.12，全部 int8 模型，4 线程。
> 这台机器不是 Mac，没法跑 `mlx-whisper`。Whisper 的数字用的是**同一份
> whisper-large-v3-turbo 权重**的 ONNX int8 CPU 版，代表“CPU 跑 Whisper”这一档。
> M 系列 GPU 上 mlx 会比这快（本次未实测具体倍数），但 Whisper 30 s 固定窗口的结构性开销依然存在。
> 在你的 Mac 上执行 `python bench/run_bench.py --models-root ~/.cache/localasr/models --mlx`，
> 可以用你当前的 mlx 配置跑出同口径的对比。

---

## 1. 结论（TL;DR）

| 问题 | 根因 | 方案（已实现） |
|---|---|---|
| 响应慢 | ① Whisper 每次把音频补齐到 30 s 窗口再跑 encoder，2 s 的话也要付整窗成本；② mlx-whisper 默认 6 档 temperature fallback，一次“看起来不好”的解码会再重跑最多 5 次；③ 松开 Fn 之后才开始识别，等待时间随说话时长线性增长 | 默认引擎换成 **SenseVoice-Small**（比 Whisper 快 5–11 倍）；Whisper 改为单次贪心解码；加 **VAD 实时分段** |
| 中英混说差 | ① `INITIAL_PROMPT` 是纯中文，会把英文往中文方向带；② Whisper 每个 30 s 窗口只判一次语种；③ 静音段会产生“谢谢观看”这类幻觉 | SenseVoice 在中英混说上更强；Whisper prompt 改成中英混合；加静音门限和幻觉过滤 |
| 做不到 realtime | 整体架构是录完再识别 | `DictationSession`：边说边按停顿切句，每句在后台立刻识别，松开时只剩最后一句；可选 `TYPE_WHILE_SPEAKING` 边说边上屏 |
| 不能花钱 | — | 方案全部本地、开源、免费（Apache/MIT 模型），见第 5 节 |

**实测效果（同一台 CPU）**：长段口述（约 90 s，在句子中间松开 Fn），从松开到出字：

| 管线 | 松开 → 出字 |
|---|---|
| 原架构：Whisper-turbo，整段识别 | 30 s 音频约 6 s；超过 30 s 要按 30 s 窗口依次串行多跑几轮 |
| 原架构，引擎换成 SenseVoice | 23 s 音频 0.9 s，56 s 音频 2.5 s，87 s 音频 5.1 s |
| **新架构：VAD 分段 + SenseVoice（默认）** | **中位数 0.11 s，最大 0.20 s**（与说话时长无关） |
| 新架构：VAD 分段 + Whisper-turbo | 中位数 1.1 s，最大 2.0 s |
| 真流式 zipformer（参考对比） | 中位数 0.10 s |

---

## 2. Code Review 发现

严重程度：🔴 bug / 用户可见的问题，🟠 性能问题，🟡 健壮性 / 可维护性

### 🔴 B1 长文本被截断（`text_output.py` `_type_text`）
macOS 上，一个合成按键事件附带的 Unicode 字符串只会被处理前 **20 个 UTF-16 code unit**
（`CGEventKeyboardSetUnicodeString` 的已知限制）。原代码把整句放进一个事件，
所以超过约 20 个字的句子在很多 App 里会被截断。另外它传的长度是 `len(text)`，
也就是 Python 的 code point 数，不是 UTF-16 长度：只要句子里有 emoji，长度就会对不上。
**修复**：按不超过 20 个 UTF-16 单元切片，不会切断代理对（surrogate pair）；长度按 UTF-16 计算；
每个事件都 `CGEventSetFlags(ev, 0)`，避免继承当时按住的 Fn/Shift。测试：`tests/test_text_output.py`。

### 🔴 B2 模型加载失败时报错无法显示（`app.py` `_load_model`）
```python
except Exception as exc:
    run_on_main(lambda: self._show_model_error(str(exc)))
```
Python 3 会在 `except` 块结束时删除 `exc`。这个 lambda 是之后才在主线程执行的，
执行时会抛 `NameError`，于是错误菜单不出现，图标一直停在 ⏳。
**修复**：在 except 块里先把错误信息存进变量。回归测试
`test_model_load_failure_shows_error` 模拟主队列延迟执行：对原代码会失败，对修复后的代码会通过。

### 🔴 B3 转录异常时图标卡死（`_transcribe_and_output`）
没有 try/except。模型一旦抛异常（OOM、音频设备等问题），图标会永远停在 ⌛。
**修复**：加 `try/finally`，保证图标恢复，并弹出通知。

### 🔴 B4 并发推理
上一句还在识别时再按一次 Fn，就会有两个线程同时调用 `mlx_whisper.transcribe`。
MLX/ONNX 并不保证线程安全，并发推理还会互相抢资源，两句都会变慢。
**修复**：加全局 `_model_lock`，所有推理串行执行。测试：`test_inference_is_serialized_across_overlapping_dictations`。

### 🟠 P1 temperature fallback 造成偶发的多秒卡顿
`mlx_whisper.transcribe` 默认 `temperature=(0.0, 0.2, …, 1.0)`。只要压缩比或 logprob 阈值没过，
就会整段重新解码，最多 6 次。这正是“有时候突然很慢”的典型原因。
**修复**：`temperature=0.0` 和 `condition_on_previous_text=False`（后者还能避免长音频里的重复循环）。

### 🟠 P2 Whisper 的 30 s 固定窗口
不管说 2 s 还是 20 s，Whisper encoder 都要处理 30 s 的 mel。CPU 实测：2 s 音频要 1.03 s，
而 SenseVoice 只要 0.09 s。短句听写正是 Whisper 最吃亏的场景。

### 🟠 P3 松开后才开始识别
等待时间等于整段识别耗时，说得越久等得越久。见第 4 节的实时方案。

### 🟠 Q1 纯中文 `INITIAL_PROMPT` 把英文往中文带
Prompt 会作为前文影响解码。纯中文 prompt 会提高英文被转写成中文的概率
（极端情况下会被“翻译”成中文），对 code-switch 不友好。现在改成了中英混合的 prompt。
⚠️ 这一点没能在 mlx 上实测，请在 Mac 上用 `bench/run_bench.py --mlx` 对比验证。

### 🟠 Q2 静音幻觉
Whisper 在静音或噪声上常会输出“谢谢观看”“字幕by…”“Thank you.”。
**修复**：先过 RMS 静音门限（静音不送进模型），再用正则过滤常见幻觉，只做整句匹配，
所以“谢谢你帮我 review”这样的正常句子会保留。

### 🟡 R1 剪贴板判断有竞态
原代码是先打字、再检查焦点，打字过程中焦点可能已经变了。现在改为先检查再打字。

### 🟡 R2 麦克风打开失败
`sd.InputStream` 抛异常后，`_recording` 会一直是 True，之后的录音全部失效。
现在会回滚状态并弹出通知。

### 🟡 R3 计时器和松开事件的竞态
达到最长录音时长的计时器和真正的 Fn 松开可能同时触发。现在用 `_state_lock` 加
“取出 session”的语义，保证只输出一次。测试：`test_timer_and_real_release_race_outputs_once`。

### 🟡 R4 录到上限后麦克风仍开着
原来录满上限后，回调直接丢弃数据，但流没关，橙色麦克风指示灯会一直亮到松开。
现在会精确截断到上限。上限从 60 s 提高到 300 s，因为分段识别不再受 30 s 窗口限制。

### 🟡 其他（建议，未改）
- **开麦延迟会吃掉开头的字**：按下 Fn 才打开 `InputStream`，macOS 上通常要 50–300 ms，
  蓝牙耳机更久。如果经常丢第一个字，可以改成常开流加环形缓冲（pre-roll），代价是橙色指示灯常亮。
- `requires-python = ">=3.13,<3.14"` 太严。代码本身兼容 3.10+，可以在 CI 里加一个版本矩阵后再放开。
- 应用名还是 `WhisperDictation`，换了引擎之后可以考虑改名。

---

## 3. 性能测试

### 3.1 测试集与指标
11 条真实录音，来自各模型自带的 test_wavs：中文 3 条、英文 3 条、中英混说 5 条。
指标是 **MER（mixed error rate）**：一个汉字算一个 token，一个英文单词算一个 token，
并归一化大小写、标点、繁简和阿拉伯/中文数字，只衡量“识别对没对”，不衡量书写风格。

> ⚠️ 偏差说明：5 条混说音频里有 4 条来自 zipformer 的测试集，参考文本是人工比对
> 5 个模型的输出后确定的，对 zipformer 可能略有偏向。样本量也小。下面的数字适合看
> 数量级和相对排序，不适合当作学术意义上的 WER。

### 3.2 准确率与速度

| 引擎 | 中文 MER | 英文 MER | 混说 MER | RTF（越小越快） | 2 s 音频 | 10 s 音频 | 30 s 音频 |
|---|---|---|---|---|---|---|---|
| **SenseVoice-Small int8** | **1.5%** | 1.2% | 15.1% | **0.041** | **0.09 s** | **0.42 s** | **1.16 s** |
| Whisper-large-v3-turbo int8（CPU） | 5.9%¹ | **0.0%** | 24.7% | 0.308 | 1.03 s | 3.54 s | 5.96 s |
| Paraformer-zh int8 | **0.0%** | 17.3% | 11.8% | 0.032 | 0.10 s | 0.39 s | 1.22 s |
| Streaming Zipformer zh-en | 5.9% | 4.9% | 4.3%² | 0.189 | 流式 | 流式 | 流式 |
| Streaming Paraformer zh-en | 4.4% | 37.0% | 17.2% | 0.163 | 流式 | 流式 | 流式 |

¹ Whisper 会主动删掉“呢”“啊”“嗯”这类语气词，对听写来说这往往是优点，但在 MER 里会算作错误。
² 见上面的偏差说明。

**怎么读这张表**
- SenseVoice 中英文都很准，速度是 Whisper 的 **5–11 倍**（RTF 7.5 倍，2 s 短句 11 倍）。综合最适合做默认引擎。
- Whisper 英文最好，标点和书写风格最“像人写的”，但慢，而且中英混说时容易把整句按一种语言处理
  （样例里 “today is 礼拜二” 被写成繁体，`3.wav` 出现了“实在一些商品”这种幻觉）。
- Paraformer 纯中文最强，但英文弱。如果几乎只说中文可以考虑它（本次未接入 app）。
- 真流式模型的优势是边说边出字，但整体准确率和标点不如 SenseVoice。
  “SenseVoice + VAD 分段”在延迟上已经能达到和真流式相同的 0.1 s 级别。

### 3.3 实时性（`bench/bench_realtime.py`）
约 90 s 的连续口述，按 50–100 ms 一块实时喂入，在 8 个“句子中间”的位置松开 Fn，
结果见第 1 节的表格。要点：
- 分段管线下，说话期间的后台计算远小于说话时长（SenseVoice：90 s 语音只占 2.6 s CPU 时间），
  所以完全跟得上实时。
- Whisper-turbo 在 4 核 CPU 上做分段，后台要算 29 s，也勉强跟得上，但松开后仍要等 1–2 s。
  在 Mac GPU 上会好很多。

---

## 4. 实时方案（已实现）

```
mic(50ms 块) ──feed()──▶ DictationSession 队列 ──▶ worker 线程
                                              ├─ Silero VAD：停顿 ≥0.35 s 就切句（单句最长 15 s）
                                              ├─ 每句立刻 transcribe()（全局锁串行）
                                              └─ 可选 on_phrase → 立即上屏（TYPE_WHILE_SPEAKING）
Fn 松开 ──▶ recorder.stop() ──▶ session.finish()：flush 最后一句 → 拼接 → 上屏
```

- `feed()` 只做入队，**不会阻塞音频回调**（有测试保证）。
- 句子拼接 `join_segments()`：只在两边都是拉丁字符时加空格（`boy.` + `And` → `boy. And`），中文之间不加。
- 每次按 Fn 创建 VAD 的开销约 1 ms。
- 没有 VAD 时（比如首次启动离线、无法下载）自动退回整段识别。

可调参数（`config.py`）：`ENGINE`、`STREAMING`、`TYPE_WHILE_SPEAKING`、`NUM_THREADS`。

---

## 5. 部署方案（全部免费）

### 本地（推荐）
| 方案 | 适用 | 说明 |
|---|---|---|
| **SenseVoice + VAD（当前默认）** | 任何 Mac（包括 Intel）/ Linux / Windows | 模型约 230 MB（int8），CPU 即可，松开 → 出字约 0.1–0.2 s |
| mlx-whisper turbo + VAD | Apple Silicon，追求英文和标点质量 | `ENGINE = "mlx-whisper"`，已关闭 fallback |
| mlx-whisper `whisper-large-v3-turbo-q4` | 内存小的 Mac | 更快但精度略降 |

### 云端（免费额度，只作备选）
本地 SenseVoice 已经只要约 0.1 s。云端单是网络往返就要 100–300 ms，**不会更快**，
音频还得上传，与本项目“完全离线”的定位冲突。如果确实需要（比如在很弱的机器上用）：
- **Groq API 免费层**：whisper-large-v3-turbo，非常快，不需要绑卡，但有速率限制，音频要上传。
- **Cloudflare Workers AI 免费额度**：有 Whisper 模型，每天有免费额度。
- **自建**：Oracle Cloud Always Free 的 ARM 实例（4 核 / 24 GB）可以跑 `sherpa-onnx` 的
  SenseVoice WebSocket 服务；注册要验证信用卡，但不扣费。
- Hugging Face Spaces 免费 CPU 和 Colab 不适合做常驻服务（会休眠，有冷启动）。

---

## 6. 测试

```
tests/
  test_text_output.py        20 字截断、UTF-16 / emoji、修饰键、先判焦点再打字、剪贴板回退
  test_transcriber.py        句子拼接、幻觉过滤、繁简转换、自定义词表、静音门限、Whisper 解码参数
  test_audio_recorder.py     分块回调、精确截断、停止后忽略回调、开麦失败可恢复
  test_segmenter.py          说话期间就开始识别、无 VAD 回退、异常上抛、feed 不阻塞、真实 Silero VAD
  test_app.py                主流程、异常后图标恢复、短按丢弃、计时器竞态、推理串行、加载失败（B2 回归）
  test_integration_models.py 真实模型的准确率预算 + 端到端“松开 → 出字”< 1 s（下载了模型才会运行）
```
macOS 专属模块（Quartz/AppKit/rumps/sounddevice）在 `tests/conftest.py` 里替换成假实现，
所以测试在 Linux CI 上也能跑。当前结果：**48 passed**。

⚠️ 还没在真 Mac 上验证的部分：真实的按键注入和焦点判断、麦克风、mlx 路径和新的 prompt。
建议你本地跑一遍 `./run.sh`，再跑一遍 `bench/run_bench.py --mlx`。
