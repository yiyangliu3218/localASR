# -*- coding: utf-8 -*-
"""Menu bar app for local speech-to-text dictation.

Hold the Fn key to speak; speech is transcribed locally (SenseVoice or mlx-whisper)
phrase by phrase while you talk, and on release the text is typed at the cursor. If no editable cursor
is found, fall back to the clipboard.
"""
import threading
import time

import rumps
from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
from Foundation import NSOperationQueue

import config
from audio_recorder import AudioRecorder
from hotkey_listener import FnHotkeyListener
from segmenter import DictationSession, make_vad_factory
from text_output import output_text
from transcriber import Transcriber

ICON_LOADING = "⏳"
ICON_READY = "🎙"
ICON_RECORDING = "🔴"
ICON_TRANSCRIBING = "⌛"
ICON_ERROR = "⚠️"


def run_on_main(fn):
    NSOperationQueue.mainQueue().addOperationWithBlock_(fn)


def notify(title, subtitle, message):
    run_on_main(lambda: rumps.notification(title, subtitle, message))


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
        self._vad_factory = None
        self._model_error = None
        self._max_duration_timer = None
        self._session = None
        self._state_lock = threading.Lock()  # guards _session / _max_duration_timer
        # Models are not thread-safe and a second concurrent inference only slows
        # both down: every transcription goes through this lock.
        self._model_lock = threading.Lock()

        self.listener = FnHotkeyListener(self.on_fn_press, self.on_fn_release)
        try:
            self.listener.start()
        except RuntimeError as e:
            self.title = ICON_ERROR
            rumps.alert("热键监听启动失败", str(e))

        threading.Thread(target=self._load_model, daemon=True).start()

    def _load_model(self):
        print(f"[app] loading engine {config.ENGINE!r} (models dir: {config.MODELS_DIR})", flush=True)
        try:
            transcriber = Transcriber()
            vad_factory = make_vad_factory() if config.STREAMING else None
        except Exception as exc:
            # Bind the message now: Python deletes `exc` when the except block
            # ends, so a lambda referencing it would raise NameError later.
            message = f"{type(exc).__name__}: {exc}"
            print(f"[app] model failed to load: {message}", flush=True)
            run_on_main(lambda: self._show_model_error(message))
            return

        self._vad_factory = vad_factory
        self.transcriber = transcriber
        print("[app] ready - hold Fn to dictate", flush=True)
        run_on_main(self._show_ready)

    def _show_ready(self):
        if self.title != ICON_ERROR:
            self.title = ICON_READY
        self.menu.clear()
        self.menu.add(rumps.MenuItem("按住 Fn 说话，松开自动输入到光标处"))
        mode = "实时分段" if self._vad_factory else "整段"
        self.menu.add(rumps.MenuItem(f"引擎: {self.transcriber.backend.name} ({mode})"))

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

    def _transcribe(self, audio):
        with self._model_lock:
            return self.transcriber.transcribe(audio)

    def _type_phrase_live(self, text):
        output_text(text, auto_type=True, always_copy=False)

    def on_fn_press(self):
        if self.transcriber is None:
            return
        with self._state_lock:
            if self._session is not None:  # still recording (e.g. missed release)
                return
            vad = self._vad_factory() if self._vad_factory else None
            live = self._type_phrase_live if (config.TYPE_WHILE_SPEAKING and config.AUTO_TYPE) else None
            session = DictationSession(self._transcribe, vad=vad, on_phrase=live)
            try:
                self.recorder.start(on_chunk=session.feed)
            except Exception as exc:
                session.finish()
                notify("语音转文字", "无法打开麦克风", str(exc))
                return
            self._session = session
            # Safety net: auto-finish once the max duration is hit instead of
            # waiting forever for the Fn release event (which can occasionally
            # get dropped when the system is busy, leaving the icon stuck)
            self._max_duration_timer = threading.Timer(
                config.MAX_RECORD_SECONDS + 1, self._on_max_duration
            )
            self._max_duration_timer.daemon = True
            self._max_duration_timer.start()
        run_on_main(lambda: setattr(self, "title", ICON_RECORDING))

    def _on_max_duration(self):
        self.on_fn_release(True)

    def on_fn_release(self, valid: bool):
        t_release = time.time()
        with self._state_lock:
            session, self._session = self._session, None
            if self._max_duration_timer is not None:
                self._max_duration_timer.cancel()
                self._max_duration_timer = None
            if session is None:  # already handled (timer + real release race)
                return
            self.recorder.stop()
        if not valid:
            # Too-short tap: let the session wind down in the background, drop the text
            threading.Thread(target=session.finish, daemon=True).start()
            run_on_main(lambda: setattr(self, "title", ICON_READY))
            return
        run_on_main(lambda: setattr(self, "title", ICON_TRANSCRIBING))
        threading.Thread(
            target=self._finish_and_output, args=(session, t_release), daemon=True
        ).start()

    def _finish_and_output(self, session, t_release):
        result = "empty"
        try:
            text = session.finish()
            t1 = time.time()
            if config.TYPE_WHILE_SPEAKING and config.AUTO_TYPE:
                # Phrases were already typed live; only handle the clipboard here
                if text and config.ALWAYS_COPY_TO_CLIPBOARD:
                    output_text(text, auto_type=False)
            else:
                result = output_text(
                    text, auto_type=config.AUTO_TYPE, always_copy=config.ALWAYS_COPY_TO_CLIPBOARD
                )
            print(
                f"[计时] 松开->识别完成: {t1 - t_release:.2f}s, "
                f"松开到出字总计: {time.time() - t_release:.2f}s",
                flush=True,
            )
            print(
                f"[诊断] 录音 {session.samples_fed / config.SAMPLE_RATE:.1f}s, "
                f"峰值音量 {session.peak:.3f}, 语音段 {session.segments}, 文字: {text!r}",
                flush=True,
            )
            if not text.strip():
                result = "nothing_heard"
        except Exception as exc:  # never leave the icon stuck on ⌛
            print(f"[错误] 转录失败: {exc!r}", flush=True)
            notify("语音转文字", "转录失败", str(exc))
        finally:
            run_on_main(lambda: setattr(self, "title", ICON_READY))
        if result == "nothing_heard":
            notify("语音转文字", "没有识别到语音", "请按住 Fn 后再说话，说完再松开")
        elif result == "clipboard_only":
            notify("语音转文字", "未开启自动输入", "已复制到剪贴板，请手动粘贴 (Cmd+V)")
        elif result == "typed_and_clipboard":
            notify("语音转文字", "未找到可编辑光标", "已尝试输入，同时也复制到了剪贴板 (Cmd+V) 备用")


def main():
    DictationApp().run()


if __name__ == "__main__":
    main()
