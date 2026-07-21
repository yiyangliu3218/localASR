# -*- coding: utf-8 -*-
"""菜单栏本地语音转文字应用。

按住 Fn 键说话，松开后自动用本地 faster-whisper 模型转成文字，
并尝试直接输入到当前光标处；如果找不到可编辑的光标，就把文字放进剪贴板。
"""
import threading

import rumps
from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
from Foundation import NSOperationQueue

from audio_recorder import AudioRecorder
from config import ALWAYS_COPY_TO_CLIPBOARD, AUTO_TYPE, MAX_RECORD_SECONDS
from hotkey_listener import FnHotkeyListener
from text_output import output_text
from transcriber import Transcriber

ICON_LOADING = "⏳"
ICON_READY = "🎙"
ICON_RECORDING = "🔴"
ICON_TRANSCRIBING = "⌛"
ICON_ERROR = "⚠️"


def run_on_main(fn):
    NSOperationQueue.mainQueue().addOperationWithBlock_(fn)


class DictationApp(rumps.App):
    def __init__(self):
        # 不在 Dock 显示图标，只作为菜单栏小工具存在
        NSApplication.sharedApplication().setActivationPolicy_(
            NSApplicationActivationPolicyAccessory
        )

        super().__init__("WhisperDictation", title=ICON_LOADING, quit_button="退出")
        self.menu = ["模型加载中…"]
        self.recorder = AudioRecorder()
        self.transcriber = None
        self._max_duration_timer = None
        self._recording_lock = threading.Lock()

        self.listener = FnHotkeyListener(self.on_fn_press, self.on_fn_release)
        try:
            self.listener.start()
        except RuntimeError as e:
            self.title = ICON_ERROR
            rumps.alert("热键监听启动失败", str(e))

        threading.Thread(target=self._load_model, daemon=True).start()

    def _load_model(self):
        self.transcriber = Transcriber()

        def on_ready():
            if self.title != ICON_ERROR:
                self.title = ICON_READY
            self.menu.clear()
            self.menu.add(rumps.MenuItem("按住 Fn 说话，松开自动输入到光标处"))

        run_on_main(on_ready)

    def on_fn_press(self):
        if self.transcriber is None:
            return
        self.recorder.start()
        run_on_main(lambda: setattr(self, "title", ICON_RECORDING))
        # 兜底：录音到时长上限后自动结束本次录音，不死等 Fn 松开事件
        # （松开事件偶尔会因系统繁忙丢失，导致图标卡在录音状态）
        self._max_duration_timer = threading.Timer(MAX_RECORD_SECONDS + 1, self._on_max_duration)
        self._max_duration_timer.daemon = True
        self._max_duration_timer.start()

    def _on_max_duration(self):
        self.on_fn_release(True)

    def on_fn_release(self, valid: bool):
        with self._recording_lock:
            if self._max_duration_timer is not None:
                self._max_duration_timer.cancel()
                self._max_duration_timer = None
            audio = self.recorder.stop()
        if not valid or self.transcriber is None or audio.size == 0:
            run_on_main(lambda: setattr(self, "title", ICON_READY))
            return
        run_on_main(lambda: setattr(self, "title", ICON_TRANSCRIBING))
        threading.Thread(target=self._transcribe_and_output, args=(audio,), daemon=True).start()

    def _transcribe_and_output(self, audio):
        text = self.transcriber.transcribe(audio)
        result = output_text(text, auto_type=AUTO_TYPE, always_copy=ALWAYS_COPY_TO_CLIPBOARD)
        run_on_main(lambda: setattr(self, "title", ICON_READY))
        if result == "clipboard_only":
            rumps.notification(
                "语音转文字", "未开启自动输入", "已复制到剪贴板，请手动粘贴 (Cmd+V)"
            )
        elif result == "typed_and_clipboard":
            rumps.notification(
                "语音转文字", "未找到可编辑光标", "已尝试输入，同时也复制到了剪贴板 (Cmd+V) 备用"
            )


if __name__ == "__main__":
    DictationApp().run()
