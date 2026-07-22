# -*- coding: utf-8 -*-
"""Menu bar app for local speech-to-text dictation.

Hold the Fn key to speak; on release, transcribe locally with mlx-whisper
and try to type the result at the current cursor. If no editable cursor
is found, fall back to the clipboard.
"""
import threading
import time

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
        # Hide the Dock icon; this only lives in the menu bar
        NSApplication.sharedApplication().setActivationPolicy_(
            NSApplicationActivationPolicyAccessory
        )

        super().__init__("WhisperDictation", title=ICON_LOADING, quit_button="退出")
        self.menu = ["模型加载中…"]
        self.recorder = AudioRecorder()
        self.transcriber = None
        self._model_error = None
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
        try:
            transcriber = Transcriber()
        except Exception as exc:
            run_on_main(lambda: self._show_model_error(str(exc)))
            return

        self.transcriber = transcriber
        run_on_main(self._show_ready)

    def _show_ready(self):
        if self.title != ICON_ERROR:
            self.title = ICON_READY
        self.menu.clear()
        self.menu.add(rumps.MenuItem("按住 Fn 说话，松开自动输入到光标处"))

    def _show_model_error(self, message: str):
        self._model_error = message
        self.title = ICON_ERROR
        self.menu.clear()
        self.menu.add(rumps.MenuItem("模型加载失败"))
        self.menu.add(rumps.MenuItem("查看错误", callback=self._on_view_model_error))
        self.menu.add(rumps.MenuItem("重新加载模型", callback=self._on_reload_model))

    def _on_view_model_error(self, sender):
        rumps.alert("模型加载失败", self._model_error or "未知错误")

    def _on_reload_model(self, sender):
        self.transcriber = None
        self._model_error = None
        self.title = ICON_LOADING
        self.menu.clear()
        self.menu.add(rumps.MenuItem("模型加载中…"))
        threading.Thread(target=self._load_model, daemon=True).start()

    def on_fn_press(self):
        if self.transcriber is None:
            return
        self.recorder.start()
        run_on_main(lambda: setattr(self, "title", ICON_RECORDING))
        # Safety net: auto-finish once the max duration is hit instead of
        # waiting forever for the Fn release event (which can occasionally
        # get dropped when the system is busy, leaving the icon stuck)
        self._max_duration_timer = threading.Timer(MAX_RECORD_SECONDS + 1, self._on_max_duration)
        self._max_duration_timer.daemon = True
        self._max_duration_timer.start()

    def _on_max_duration(self):
        self.on_fn_release(True)

    def on_fn_release(self, valid: bool):
        t_release = time.time()
        with self._recording_lock:
            if self._max_duration_timer is not None:
                self._max_duration_timer.cancel()
                self._max_duration_timer = None
            audio = self.recorder.stop()
        print(f"[计时] 松开->停止录音: {time.time() - t_release:.2f}s", flush=True)
        if not valid or self.transcriber is None or audio.size == 0:
            run_on_main(lambda: setattr(self, "title", ICON_READY))
            return
        run_on_main(lambda: setattr(self, "title", ICON_TRANSCRIBING))
        threading.Thread(
            target=self._transcribe_and_output, args=(audio, t_release), daemon=True
        ).start()

    def _transcribe_and_output(self, audio, t_release):
        t0 = time.time()
        text = self.transcriber.transcribe(audio)
        t1 = time.time()
        result = output_text(text, auto_type=AUTO_TYPE, always_copy=ALWAYS_COPY_TO_CLIPBOARD)
        t2 = time.time()
        print(
            f"[计时] 转录: {t1 - t0:.2f}s, 输出: {t2 - t1:.2f}s, "
            f"松开到出字总计: {t2 - t_release:.2f}s",
            flush=True,
        )
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
