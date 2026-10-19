"""Audio decoding, pitch-preserving time-stretch, and playback with pause/resume."""
from __future__ import annotations

import threading

import numpy as np

SAMPLE_RATE = 48000


def decode(data: bytes, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Decode mp3/wav/flac/ogg bytes to mono float32 at `sample_rate`."""
    import miniaudio
    snd = miniaudio.decode(data, output_format=miniaudio.SampleFormat.FLOAT32, nchannels=1,
                           sample_rate=sample_rate)
    return np.frombuffer(snd.samples, dtype=np.float32).copy()


def trim_silence(x: np.ndarray, threshold: float = 0.004, keep_ms: int = 60,
                 sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Cut the long leading/trailing silence some services add, so chunks join smoothly."""
    idx = np.flatnonzero(np.abs(x) > threshold)
    if not len(idx):
        return x
    keep = int(sample_rate * keep_ms / 1000)
    return x[max(0, idx[0] - keep): min(len(x), idx[-1] + keep)]


def time_stretch(x: np.ndarray, rate: float, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """WSOLA time-stretch: rate > 1 is faster. Pitch is preserved."""
    if abs(rate - 1.0) < 0.02 or len(x) < sample_rate // 10:
        return x
    frame = int(sample_rate * 0.04)
    hop_out = frame // 2
    hop_in = hop_out * rate
    tol = int(sample_rate * 0.01)
    win = np.hanning(frame).astype(np.float32)
    out_len = int(len(x) / rate) + frame
    out = np.zeros(out_len + frame, dtype=np.float32)
    norm = np.zeros_like(out)
    xp = np.concatenate([x, np.zeros(frame + tol * 2 + int(hop_in) + 1, dtype=np.float32)])
    prev = 0
    k = 0
    while True:
        nominal = int(k * hop_in)
        if nominal >= len(x) or k * hop_out >= out_len:
            break
        if k == 0:
            pos = 0
        else:
            target = xp[prev + hop_out: prev + hop_out + frame]   # natural continuation
            lo = max(0, nominal - tol)
            region = xp[lo: nominal + tol + frame]
            corr = np.correlate(region, target, mode="valid")
            pos = lo + int(np.argmax(corr)) if len(corr) else nominal
        o = k * hop_out
        out[o:o + frame] += xp[pos:pos + frame] * win
        norm[o:o + frame] += win
        prev = pos
        k += 1
    norm[norm < 1e-3] = 1.0
    y = out / norm
    return y[: int(len(x) / rate)].astype(np.float32)


class Player:
    """Plays float32 buffers one after another; supports pause, resume and stop."""

    def __init__(self, sample_rate: int = SAMPLE_RATE, volume: float = 1.0):
        self.sample_rate = sample_rate
        self.volume = volume
        self._buf = np.zeros(0, dtype=np.float32)
        self._pos = 0
        self._paused = False
        self._lock = threading.Lock()
        self._done = threading.Event()
        self._stream = None

    def _ensure_stream(self):
        if self._stream is None:
            import sounddevice as sd
            self._stream = sd.OutputStream(samplerate=self.sample_rate, channels=1, dtype="float32",
                                           callback=self._callback, blocksize=1024, latency="low")
            self._stream.start()

    def _callback(self, outdata, frames, _time, _status):
        with self._lock:
            if self._paused or self._pos >= len(self._buf):
                outdata.fill(0)
                if not self._paused and self._pos >= len(self._buf):
                    self._done.set()
                return
            chunk = self._buf[self._pos:self._pos + frames]
            self._pos += len(chunk)
            outdata[:len(chunk), 0] = chunk * self.volume
            outdata[len(chunk):, 0] = 0
            if self._pos >= len(self._buf):
                self._done.set()

    def play(self, samples: np.ndarray, cancel: threading.Event) -> bool:
        """Block until `samples` finished playing (True) or `cancel` was set (False)."""
        self._ensure_stream()
        with self._lock:
            self._buf = samples
            self._pos = 0
            self._done.clear()
        while not self._done.wait(0.05):
            if cancel.is_set():
                self.clear()
                return False
        return not cancel.is_set()

    def progress(self) -> float:
        with self._lock:
            return self._pos / len(self._buf) if len(self._buf) else 0.0

    def clear(self):
        with self._lock:
            self._buf = np.zeros(0, dtype=np.float32)
            self._pos = 0
            self._done.set()

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    @property
    def paused(self):
        return self._paused

    def close(self):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
