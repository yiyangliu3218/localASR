# LocalASR

Apple Silicon Mac 上的离线、按住 Fn 即说、松开自动输入的菜单栏听写工具。

按住 **Fn** 键说话，松开自动用本地 Whisper 模型（`mlx-whisper`，Apple Silicon GPU 加速）转成文字，
自动输入到当前光标处（默认转换为简体中文，可配置）；只有在检测不到可编辑光标时，才会额外把文本存一份到剪贴板兜底。

全程本地推理，不联网、不上传语音，支持中英文（含中英混说，自动识别语言）。第一次运行需要联网下载模型，
下载完成后可以完全离线使用。

## 环境要求

- Apple Silicon (M 系列) Mac
- Python 3.13（目前只在这个版本上测试过）

## 安装

```bash
git clone https://github.com/yiyangliu3218/localASR.git
cd localASR
./install.sh
```

`install.sh` 会创建虚拟环境 `.venv` 并安装依赖（第一次运行时依赖下载可能需要几分钟）。

## 首次使用前的准备

### 1. 关闭系统对 Fn 键的占用（重要）

系统设置 → 键盘：

- 「按下 🌐 / Fn 键时」 改成 **无操作**（否则会一起弹出表情符号面板或触发系统听写）
- 如果开启了「按 Fn 键两次」调出听写，也建议关闭，避免和本工具的录音混在一起

### 2. 给终端授予权限

第一次运行时，如果没有权限，程序会报错提示。需要在
**系统设置 → 隐私与安全性** 里，把你用来运行本程序的终端 App（Terminal / iTerm 等）
同时加到：

- **辅助功能**（Accessibility）— 用于模拟键盘输入文字
- **输入监控**（Input Monitoring）— 用于全局监听 Fn 键

加完之后需要**完全退出并重新打开终端**再运行一次。

## 运行

```bash
./run.sh
```

菜单栏会出现一个图标：

| 图标 | 含义 |
|---|---|
| ⏳ | 模型加载中（第一次运行会自动下载模型，之后都是本地离线运行） |
| 🎙 | 就绪，可以按住 Fn 说话 |
| 🔴 | 正在录音 |
| ⌛ | 正在转录 |
| ⚠️ | 权限没给对（热键监听启动失败），或模型加载失败 |

用法：**按住 Fn 说话 → 松开 → 文字自动出现在光标处**（找不到可编辑光标时会额外复制到剪贴板）。

如果模型加载失败（比如下载中断、网络断开、磁盘空间不足），菜单栏图标会变成 ⚠️，点开菜单可以看到
「查看错误」（显示具体报错信息）和「重新加载模型」（不用重启整个 App，直接重试）。

退出：点菜单栏图标 → 退出。

## 配置（`config.py`）

```python
MODEL_REPO = "mlx-community/whisper-large-v3-turbo"  # mlx-whisper 模型，Apple Silicon GPU 加速
LANGUAGE = None          # None=自动识别中英文；也可强制填 "zh" 或 "en"
CUSTOM_VOCABULARY = []   # 常识别错的专业名词/人名，加进来提高识别率
OUTPUT_CHINESE = "simplified"  # "simplified" / "traditional" / "preserve"（不转换，保留模型原始输出）
AUTO_TYPE = True         # False 则只放剪贴板，不自动输入
ALWAYS_COPY_TO_CLIPBOARD = False  # True 则不管有没有找到光标，都额外存一份到剪贴板
MAX_RECORD_SECONDS = 60  # 单次最长录音时长
```

改完 `config.py` 后，退出菜单栏图标重新 `./run.sh` 即可生效。换 `MODEL_REPO` 会在下次启动时
自动从 Hugging Face 下载对应模型（可选的 mlx-community 仓库还有 `whisper-large-v3-turbo-q4` 等量化版本，
下载更小、速度更快，但准确率略低）。

## License

MIT，见 [LICENSE](LICENSE)。
