# -*- coding: utf-8 -*-
"""
Audio wrapper module.

Can use SDL, pyglet, pyo or wx. pyglet or SDL will be used by default if available.
pyglet can only be used if version >= 1.2.2 is available.
pyo is still buggy under Linux and has a few quirks under Windows.
wx doesn't support fading, changing volume, multiple concurrent sounds,
and only supports wav format.

Example:
sound = Sound("test.wav", loop=True)
sound.Play(fade_ms=1000)
"""

from ctypes import (
    CFUNCTYPE,
    POINTER,
    Structure,
    c_int,
    c_uint8,
    c_uint16,
    c_uint32,
    c_void_p,
)
import ctypes.util
import os
import sys
import threading
import time

if sys.platform == "win32":
    try:
        import win32api
        import pywintypes
    except ImportError:
        win32api = None

from DisplayCAL.config import pydir
from DisplayCAL.util_os import dlopen, getenvu
from DisplayCAL.util_str import safe_str


_ch = {}
_initialized = False
_lib = None
_lib_version = None
_server = None
_snd = {}
_sounds = {}


def init(lib=None, samplerate=22050, channels=2, buffersize=2048, reinit=False):
    """(Re-)Initialize sound subsystem"""
    # Note on buffer size: Too high values cause crackling during fade, too low
    # values cause choppy playback of ogg files when using pyo (good value for
    # pyo is >= 2048)
    global _initialized, _lib, _lib_version, _server, pyglet, pyo, sdl, wx
    if _initialized and not reinit:
        # To re-initialize, explicitly set reinit to True
        return
    # Select the audio library we're going to use.
    # User choice or SDL > pyglet > pyo > wx
    if not lib:
        if sys.platform in ("darwin", "win32"):
            # Mac OS X, Windows
            libs = ("pyglet", "SDL", "pyo", "wx")
        else:
            # Linux
            libs = ("SDL", "pyglet", "pyo", "wx")

        audio_lib = None
        for lib in libs:
            try:
                audio_lib = init(lib, samplerate, channels, buffersize, reinit)
                break
            except Exception:
                pass

        if not audio_lib:
            raise RuntimeError("No suitable audio library found!")
        else:
            return audio_lib
    elif lib == "pyglet":
        if not getattr(sys, "frozen", False):
            # Use included pyglet
            lib_dir = os.path.join(os.path.dirname(__file__), "lib")
            if lib_dir not in sys.path:
                sys.path.insert(0, lib_dir)
        try:
            import pyglet

            version = []
            for item in pyglet.version.split("."):
                try:
                    version.append(int(item))
                except ValueError:
                    version.append(item)
            if version < [1, 2, 2]:
                raise ImportError("pyglet version %s is too old" % pyglet.version)
            _lib = "pyglet"
        except ImportError:
            _lib = None
        else:
            # Work around localization preventing fallback to RIFFSourceLoader
            pyglet.lib.LibraryLoader.darwin_not_found_error = ""
            pyglet.lib.LibraryLoader.linux_not_found_error = ""
            # Set audio driver preference
            pyglet.options["audio"] = ("pulse", "openal", "directsound", "silent")
            _server = pyglet.media
            _lib_version = pyglet.version
    elif lib == "pyo":
        try:
            import pyo

            _lib = "pyo"
        except ImportError:
            _lib = None
        else:
            if isinstance(_server, pyo.Server):
                _server.reinit(
                    sr=samplerate, nchnls=channels, buffersize=buffersize, duplex=0
                )
            else:
                _server = pyo.Server(
                    sr=samplerate,
                    nchnls=channels,
                    buffersize=buffersize,
                    duplex=0,
                    winhost="asio",
                ).boot()
                _server.start()
                _lib_version = ".".join(str(v) for v in pyo.getVersion())
    elif lib == "SDL":
        SDL_INIT_AUDIO = 16
        AUDIO_S16LSB = 0x8010
        AUDIO_S16MSB = 0x9010
        if sys.byteorder == "little":
            MIX_DEFAULT_FORMAT = AUDIO_S16LSB
        else:
            MIX_DEFAULT_FORMAT = AUDIO_S16MSB
        if sys.platform == "win32":
            pth = getenvu("PATH")
            libpth = os.path.join(pydir, "lib")
            if not pth.startswith(libpth + os.pathsep):
                pth = libpth + os.pathsep + pth
                os.environ["PATH"] = safe_str(pth)
        elif sys.platform == "darwin":
            x_framework_pth = os.getenv("X_DYLD_FALLBACK_FRAMEWORK_PATH")
            if x_framework_pth:
                framework_pth = os.getenv("DYLD_FALLBACK_FRAMEWORK_PATH")
                if framework_pth:
                    x_framework_pth = os.pathsep.join([x_framework_pth, framework_pth])
                os.environ["DYLD_FALLBACK_FRAMEWORK_PATH"] = x_framework_pth
        for libname in ("SDL2", "SDL2_mixer", "SDL", "SDL_mixer"):
            handle = None
            if sys.platform in ("darwin", "win32"):
                libfn = ctypes.util.find_library(libname)
            if sys.platform == "win32":
                if libfn and win32api:
                    # Support for unicode paths
                    libfn = str(libfn)
                    try:
                        handle = win32api.LoadLibrary(libfn)
                    except pywintypes.error:
                        pass
            elif sys.platform != "darwin":
                # Hard-code lib names for Linux
                libfn = f"lib{libname}"
                if libname.startswith("SDL2"):
                    # SDL 2.0
                    libfn += "-2.0.so.0"
                else:
                    # SDL 1.2
                    libfn += "-1.2.so.0"
            dll = dlopen(libfn, handle=handle)
            if dll:
                print(f"{libname}:", libfn)
            if libname.endswith("_mixer"):
                if not dll:
                    continue
                if not sdl:
                    raise RuntimeError("SDL library not loaded")
                sdl.SDL_RWFromFile.restype = POINTER(SDL_RWops)
                _server = dll
                _server.Mix_OpenAudio.argtypes = [c_int, c_uint16, c_int, c_int]
                _server.Mix_LoadWAV_RW.argtypes = [POINTER(SDL_RWops), c_int]
                _server.Mix_LoadWAV_RW.restype = POINTER(Mix_Chunk)
                _server.Mix_PlayChannelTimed.argtypes = [
                    c_int,
                    POINTER(Mix_Chunk),
                    c_int,
                    c_int,
                ]
                _server.Mix_VolumeChunk.argtypes = [POINTER(Mix_Chunk), c_int]
                if _initialized:
                    _server.Mix_Quit()
                    sdl.SDL_Quit()
                sdl.SDL_Init(SDL_INIT_AUDIO)
                _server.Mix_OpenAudio(
                    samplerate, MIX_DEFAULT_FORMAT, channels, buffersize
                )
                _lib = "SDL"
                if libname.startswith("SDL2"):
                    _lib_version = "2.0"
                else:
                    _lib_version = "1.2"
                break
            else:
                sdl = dll
                _server = None
    elif lib == "wx":
        try:
            import wx

            _lib = "wx"
        except ImportError:
            _lib = None
        else:
            _server = wx
            _lib_version = wx.__version__
    if not _lib:
        raise RuntimeError("No audio library available")
    _initialized = True
    return _server


def safe_init(lib=None, samplerate=22050, channels=2, buffersize=2048, reinit=False):
    """Like init(), but catch any exceptions"""
    global _initialized
    try:
        return init(lib, samplerate, channels, buffersize, reinit)
    except Exception as exception:
        # So we can check if initialization failed
        _initialized = exception
        return exception


def Sound(filename, loop=False, raise_exceptions=False):
    """Sound caching mechanism"""
    if (filename, loop) in _sounds:
        # Cache hit
        return _sounds[(filename, loop)]
    else:
        try:
            sound = _Sound(filename, loop)
        except Exception as exception:
            if raise_exceptions:
                raise exception
            print(exception)
            sound = _Sound(None, loop)
        _sounds[(filename, loop)] = sound
        return sound


class DummySound(object):
    """Dummy sound wrapper class"""

    def __init__(self, filename=None, loop=False):
        pass

    def fade(self, fade_ms, fade_in=None):
        return True

    @property
    def is_playing(self):
        return False

    def play(self, fade_ms=0):
        return True

    @property
    def play_count(self):
        return 0

    def safe_fade(self, fade_ms, fade_in=None):
        return True

    def safe_play(self, fade_ms=0):
        return True

    def safe_stop(self, fade_ms=0):
        return True

    def stop(self, fade_ms=0):
        return True

    volume = 0


class SDL_RWops(Structure):
    pass


class Mix_Chunk(Structure):
    _fields_ = [
        ("allocated", c_int),
        ("abuf", POINTER(c_uint8)),
        ("alen", c_uint32),
        ("volume", c_uint8),
    ]


class _Sound(object):
    """Sound wrapper class."""

    def __init__(self, filename, loop=False):
        self._filename = filename
        self._is_playing = False
        self._lib = _lib
        self._lib_version = _lib_version
        self._loop = loop
        self._play_timestamp = 0
        self._play_count = 0
        self._thread = -1
        if not _initialized:
            self._server = init()
        else:
            self._server = _server
        if _initialized and not isinstance(_initialized, Exception):
            if not self._lib and _lib:
                self._lib = _lib
                self._lib_version = _lib_version
            if not self._snd and self._filename:
                if self._lib == "pyo":
                    self._snd = pyo.SfPlayer(safe_str(self._filename), loop=self._loop)
                elif self._lib == "pyglet":
                    snd = pyglet.media.load(self._filename, streaming=False)
                    self._ch = pyglet.media.Player()
                    self._snd = snd
                elif self._lib == "SDL":
                    rw = sdl.SDL_RWFromFile(safe_str(self._filename, "UTF-8"), "rb")
                    self._snd = self._server.Mix_LoadWAV_RW(rw, 1)
                elif self._lib == "wx":
                    self._snd = wx.Sound(self._filename)

    @property
    def _ch(self):
        return _ch.get((self._filename, self._loop))

    @_ch.setter
    def _ch(self, ch):
        _ch[(self._filename, self._loop)] = ch

    def _fade(self, fade_ms, fade_in, thread):
        volume = self.volume
        if fade_ms and ((fade_in and volume < 1) or (not fade_in and volume)):
            count = 200
            for i in range(count + 1):
                if fade_in:
                    self.volume = volume + i / float(count) * (1.0 - volume)
                else:
                    self.volume = volume - i / float(count) * volume
                time.sleep(fade_ms / 1000.0 / count)
                if self._thread is not thread:
                    # If we are no longer the current thread, return immediately
                    return
        if not self.volume:
            self.stop()

    @property
    def volume(self):
        volume = 1.0
        if self._snd:
            if self._lib == "pyo":
                volume = self._snd.mul
            elif self._lib == "pyglet":
                volume = self._ch.volume
            elif self._lib == "SDL":
                volume = float(self._server.Mix_VolumeChunk(self._snd, -1)) / 128
        return volume

    @volume.setter
    def volume(self, volume):
        if self._snd and self._lib != "wx":
            if self._lib == "pyo":
                self._snd.mul = volume
            elif self._lib == "pyglet":
                self._ch.volume = volume
            elif self._lib == "SDL":
                self._server.Mix_VolumeChunk(self._snd, int(round(volume * 128)))
            return True
        return False

    @property
    def _snd(self):
        return _snd.get((self._filename, self._loop))

    @_snd.setter
    def _snd(self, snd):
        _snd[(self._filename, self._loop)] = snd

    def fade(self, fade_ms, fade_in=None):
        """Fade in/out.

        If fade_in is None, fade in/out depending on current volume.
        """
        if fade_in is None:
            fade_in = not self.volume
        if fade_in and not self.is_playing:
            return self.play(fade_ms=fade_ms)
        elif self._snd and self._lib != "wx":
            self._thread += 1
            threading.Thread(
                target=self._fade,
                name="AudioFading-%d[%sms]" % (self._thread, fade_ms),
                args=(fade_ms, fade_in, self._thread),
            ).start()
            return True
        return False

    @property
    def is_playing(self):
        if self._lib == "pyo":
            return bool(self._snd and self._snd.isOutputting())
        elif self._lib == "pyglet":
            return bool(
                self._ch
                and self._ch.playing
                and self._ch.source
                and (
                    self._loop
                    or time.time() - self._play_timestamp < self._ch.source.duration
                )
            )
        elif self._lib == "SDL":
            return bool(self._ch is not None and self._server.Mix_Playing(self._ch))
        return self._is_playing

    def play(self, fade_ms=0, stop_already_playing=True):
        if self._snd:
            volume = self.volume
            if stop_already_playing:
                self.stop()
            if self._lib == "pyglet":
                # Can't reuse the player, won't replay the sound under Mac OS X
                # and Linux even when seeking to start position which allows
                # replaying the sound under Windows.
                if stop_already_playing:
                    try:
                        self._ch.delete()
                    except TypeError:
                        pass
                self._ch = pyglet.media.Player()
                if self._lib_version >= "1.4.0":
                    self._ch.loop = self._loop
                self.volume = volume
            if not self.is_playing and fade_ms and volume == 1:
                self.volume = 0
            self._play_timestamp = time.time()
            if self._lib == "pyo":
                self._snd.out()
            elif self._lib == "pyglet":
                if self._loop and self._lib_version < "1.4.0":
                    snd = pyglet.media.SourceGroup(
                        self._snd.audio_format, self._snd.video_format
                    )
                    snd.loop = True
                    snd.queue(self._snd)
                else:
                    snd = self._snd
                self._ch.queue(snd)
                self._ch.play()
            elif self._lib == "SDL":
                self._ch = self._server.Mix_PlayChannelTimed(
                    -1, self._snd, -1 if self._loop else 0, -1
                )
            elif self._lib == "wx" and self._snd.IsOk():
                flags = wx.SOUND_ASYNC
                if self._loop:
                    flags |= wx.SOUND_LOOP
                    # The best we can do is have the correct state reflected
                    # for looping sounds only
                    self._is_playing = True
                # wx.Sound.Play is supposed to return True on success.
                # When I tested this, it always returned False, but still
                # played the sound.
                self._snd.Play(flags)
            if self._lib:
                self._play_count += 1
            if fade_ms and self._lib != "wx":
                self.fade(fade_ms, True)
            return True
        return False

    @property
    def play_count(self):
        return self._play_count

    def safe_fade(self, fade_ms, fade_in=None):
        """Like fade(), but catch any exceptions"""
        if not _initialized:
            safe_init()
        try:
            return self.fade(fade_ms, fade_in)
        except Exception as exception:
            return exception

    def safe_play(self, fade_ms=0):
        """Like play(), but catch any exceptions"""
        if not _initialized:
            safe_init()
        try:
            return self.play(fade_ms)
        except Exception as exception:
            return exception

    def safe_stop(self, fade_ms=0):
        """Like stop(), but catch any exceptions"""
        try:
            return self.stop(fade_ms)
        except Exception as exception:
            return exception

    def stop(self, fade_ms=0):
        if self._snd and self.is_playing:
            if self._lib == "wx":
                self._snd.Stop()
                self._is_playing = False
            elif fade_ms:
                self.fade(fade_ms, False)
            else:
                if self._lib == "pyglet":
                    self._ch.pause()
                elif self._lib == "SDL":
                    self._server.Mix_HaltChannel(self._ch)
                else:
                    self._snd.stop()
            return True
        else:
            return False


if __name__ == "__main__":
    import wx
    from DisplayCAL.config import get_data_path

    sound = Sound(get_data_path("theme/engine_hum_loop.wav"), True)
    app = wx.App(0)
    frame = wx.Frame(None, -1, "Test")
    frame.Bind(
        wx.EVT_CLOSE,
        lambda event: (
            sound.stop(1000) and _lib != "wx" and time.sleep(1),
            event.Skip(),
        ),
    )
    panel = wx.Panel(frame)
    panel.Sizer = wx.BoxSizer()
    button = wx.Button(panel, -1, "Play")
    button.Bind(wx.EVT_BUTTON, lambda event: not sound.is_playing and sound.play(3000))
    panel.Sizer.Add(button, 1)
    button = wx.Button(panel, -1, "Stop")
    button.Bind(wx.EVT_BUTTON, lambda event: sound.is_playing and sound.stop(3000))
    panel.Sizer.Add(button, 1)
    panel.Sizer.SetSizeHints(frame)
    frame.Show()
    app.MainLoop()
