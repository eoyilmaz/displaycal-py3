"""Audio wrapper module.

Can use SDL, pyglet, pyo or wx.
pyglet or SDL will be used by default if available.
pyglet can only be used if version >= 1.2.2 is available.
pyo is still buggy under Linux and has a few quirks under Windows.
wx doesn't support fading, changing volume, multiple concurrent sounds,
and only supports wav format.

Example:
sound = Sound("test.wav", loop=True)
sound.Play(fade_ms=1000)
"""

from __future__ import annotations

import contextlib
import ctypes.util
import os
import sys
import threading
import time
from ctypes import (
    POINTER,
    Structure,
    c_int,
    c_uint8,
    c_uint16,
    c_uint32,
)
from typing import TYPE_CHECKING, ClassVar

if sys.platform == "win32":
    try:
        import pywintypes
        import win32api
    except ImportError:
        win32api = None

from DisplayCAL.config import PYDIR
from DisplayCAL.util_os import dlopen, getenvu
from DisplayCAL.util_str import safe_str

if TYPE_CHECKING:
    import pyglet.media  # noqa: TC004
    import pyo  # noqa: TC004
    import sdl  # noqa: TC004
    import sdl2  # noqa: TC004
    import wx

_CH = {}
_INITIALIZED = False
_LIB = None
_LIB_VERSION = None
_SERVER = None
_SND = {}
_SOUNDS = {}

SDL_INIT_AUDIO = 16
AUDIO_S16LSB = 0x8010
AUDIO_S16MSB = 0x9010
MIX_DEFAULT_FORMAT = AUDIO_S16LSB if sys.byteorder == "little" else AUDIO_S16MSB


def init(
    lib: None | str = None,
    samplerate: int = 22050,
    channels: int = 2,
    buffersize: int = 2048,
    reinit: str = False,
) -> None | pyglet.media | pyo.Server | sdl.Mixer | sdl2.Mixer | wx.Sound:
    """(Re-)Initialize sound subsystem.

    Args:
        lib (str): The audio library to use (e.g., "SDL", "pyglet", "pyo", "wx").
        samplerate (int): The sample rate to use.
        channels (int): The number of audio channels.
        buffersize (int): The size of the audio buffer.
        reinit (bool): Whether to reinitialize the sound subsystem.

    Returns:
        None | pyglet.media | pyo.Server | sdl.Mixer | sdl2.Mixer | wx.Sound:
            The initialized audio library or None if no suitable library was found.
    """
    # Note on buffer size: Too high values cause crackling during fade, too low
    # values cause choppy playback of ogg files when using pyo (good value for
    # pyo is >= 2048)
    global _INITIALIZED, _LIB, _LIB_VERSION, _SERVER, pyglet, pyo, sdl, wx
    if _INITIALIZED and not reinit:
        # To re-initialize, explicitly set reinit to True
        return None
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
        for lib_ in libs:
            try:
                audio_lib = init(lib_, samplerate, channels, buffersize, reinit)
                break
            except Exception:
                pass

        if not audio_lib:
            raise RuntimeError("No suitable audio library found!")
        return audio_lib

    if lib == "pyglet":
        _init_pyglet()
    elif lib == "pyo":
        _init_pyo(samplerate, channels, buffersize)
    elif lib == "SDL":
        _init_sdl(samplerate, channels, buffersize)
    elif lib == "wx":
        _init_wx()
    if not _LIB:
        raise RuntimeError("No audio library available")
    _INITIALIZED = True
    return _SERVER

def _init_wx() -> None:
    """Initialize wx audio subsystem."""
    global _SERVER, _LIB, _LIB_VERSION, wx
    try:
        import wx

        _LIB = "wx"
    except ImportError:
        _LIB = None
    else:
        _SERVER = wx
        _LIB_VERSION = wx.__version__


def _load_audio_dll(
    sdl: None | sdl.Mixer | sdl2.Mixer,
    samplerate: int,
    channels: int,
    buffersize: int,
    libname: str,
    libfn: str | None,
    handle: None | int | str = None,
) -> None | sdl.Mixer | sdl2.Mixer:
    """Load the audio DLL.

    Args:
        sdl (None | sdl.Mixer | sdl2.Mixer): The SDL audio library to use.
        samplerate (int): The sample rate to use.
        channels (int): The number of audio channels.
        buffersize (int): The size of the audio buffer.
        libname (str): The name of the audio library.
        libfn (str | None): The filename of the audio library.
        handle (None | int | str): The handle to the loaded library.

    Returns:
        None | sdl.Mixer | sdl2.Mixer: The loaded SDL audio library or None if
            the library could not be loaded.
    """
    global _SERVER, _LIB, _LIB_VERSION, _INITIALIZED
    dll = dlopen(libfn, handle=handle)
    if dll:
        print(f"{libname}:", libfn)
    if libname.endswith("_mixer"):
        if not dll:
            return None
        if not sdl:
            raise RuntimeError("SDL library not loaded")
        sdl.SDL_RWFromFile.restype = POINTER(SDL_RWops)
        _SERVER = dll
        _SERVER.Mix_OpenAudio.argtypes = [c_int, c_uint16, c_int, c_int]
        _SERVER.Mix_LoadWAV_RW.argtypes = [POINTER(SDL_RWops), c_int]
        _SERVER.Mix_LoadWAV_RW.restype = POINTER(Mix_Chunk)
        _SERVER.Mix_PlayChannelTimed.argtypes = [
                c_int,
                POINTER(Mix_Chunk),
                c_int,
                c_int,
            ]
        _SERVER.Mix_VolumeChunk.argtypes = [POINTER(Mix_Chunk), c_int]
        if _INITIALIZED:
            _SERVER.Mix_Quit()
            sdl.SDL_Quit()
        sdl.SDL_Init(SDL_INIT_AUDIO)
        _SERVER.Mix_OpenAudio(
                samplerate, MIX_DEFAULT_FORMAT, channels, buffersize
            )
        _LIB = "SDL"
        _LIB_VERSION = "2.0" if libname.startswith("SDL2") else "1.2"
        return sdl
    sdl = dll
    _SERVER = None
    return sdl


def _init_sdl_windows(samplerate: int, channels: int, buffersize: int) -> None:
    """Initialize SDL on Windows.

    Args:
        samplerate (int): The sample rate to use.
        channels (int): The number of audio channels.
        buffersize (int): The size of the audio buffer.
    """
    global _SERVER
    sdl = None
    pth = getenvu("PATH")
    libpth = os.path.join(PYDIR, "lib")
    if not pth.startswith(libpth + os.pathsep):
        pth = libpth + os.pathsep + pth
        os.environ["PATH"] = safe_str(pth)
    for libname in ("SDL2", "SDL2_mixer", "SDL", "SDL_mixer"):
        handle = None
        libfn = ctypes.util.find_library(libname)
        if libfn and win32api:
            # Support for unicode paths
            libfn = str(libfn)
            with contextlib.suppress(pywintypes.error):
                handle = win32api.LoadLibrary(libfn)

        sdl = _load_audio_dll(
            sdl,
            samplerate,
            channels,
            buffersize,
            libname,
            libfn,
            handle,
        )


def _init_sdl_macos(samplerate: int, channels: int, buffersize: int) -> None:
    """Initialize SDL on macOS.

    Args:
        samplerate (int): The sample rate to use.
        channels (int): The number of audio channels.
        buffersize (int): The size of the audio buffer.
    """
    global _SERVER
    sdl = None
    if x_framework_pth := os.getenv("X_DYLD_FALLBACK_FRAMEWORK_PATH"):
        if framework_pth := os.getenv("DYLD_FALLBACK_FRAMEWORK_PATH"):
            x_framework_pth = os.pathsep.join([x_framework_pth, framework_pth])
        os.environ["DYLD_FALLBACK_FRAMEWORK_PATH"] = x_framework_pth
    for libname in ("SDL2", "SDL2_mixer", "SDL", "SDL_mixer"):
        handle = None
        libfn = ctypes.util.find_library(libname)

        sdl = _load_audio_dll(
            sdl,
            samplerate,
            channels,
            buffersize,
            libname,
            libfn,
            handle,
        )


def _init_sdl_linux(samplerate: int, channels: int, buffersize: int) -> None:
    """Initialize SDL on Linux.

    Args:
        samplerate (int): The sample rate to use.
        channels (int): The number of audio channels.
        buffersize (int): The size of the audio buffer.
    """
    global _SERVER
    sdl = None
    for libname in ("SDL2", "SDL2_mixer", "SDL", "SDL_mixer"):
        handle = None
            # Hard-code lib names for Linux
        libfn = f"lib{libname}"
        if libname.startswith("SDL2"):
                # SDL 2.0
            libfn += "-2.0.so.0"
        else:
                # SDL 1.2
            libfn += "-1.2.so.0"

        sdl = _load_audio_dll(
            sdl,
            samplerate,
            channels,
            buffersize,
            libname,
            libfn,
            handle,
        )


def _init_sdl(samplerate: int, channels: int, buffersize: int) -> None:
    """Initialize SDL audio subsystem.

    Args:
        samplerate (int): The sample rate to use.
        channels (int): The number of audio channels.
        buffersize (int): The size of the audio buffer.
    """
    if sys.platform == "win32":
        _init_sdl_windows(samplerate, channels, buffersize)
    elif sys.platform == "darwin":
        _init_sdl_macos(samplerate, channels, buffersize)
    else:
        _init_sdl_linux(samplerate, channels, buffersize)


def _init_pyo(samplerate: int, channels: int, buffersize: int) -> None:
    """Initialize pyo audio subsystem.

    Args:
        samplerate (int): The sample rate to use.
        channels (int): The number of audio channels.
        buffersize (int): The size of the audio buffer.

    Raises:
        ImportError: If pyo is not installed or cannot be imported.
        RuntimeError: If pyo server initialization fails.
    """
    global _SERVER, _LIB, _LIB_VERSION, pyo
    try:
        import pyo

        _LIB = "pyo"
    except ImportError:
        _LIB = None
    else:
        if isinstance(_SERVER, pyo.Server):
            _SERVER.reinit(
                    sr=samplerate, nchnls=channels, buffersize=buffersize, duplex=0
                )
        else:
            _SERVER = pyo.Server(
                    sr=samplerate,
                    nchnls=channels,
                    buffersize=buffersize,
                    duplex=0,
                    winhost="asio",
                ).boot()
            _SERVER.start()
            _LIB_VERSION = ".".join(str(v) for v in pyo.getVersion())

def _init_pyglet() -> None:
    """Initialize pyglet audio subsystem."""
    global _SERVER, _LIB, _LIB_VERSION, pyglet
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
            raise ImportError(f"pyglet version {pyglet.version} is too old")
        _LIB = "pyglet"
    except ImportError:
        _LIB = None
    else:
            # Work around localization preventing fallback to RIFFSourceLoader
        pyglet.lib.LibraryLoader.darwin_not_found_error = ""
        pyglet.lib.LibraryLoader.linux_not_found_error = ""
            # Set audio driver preference
        pyglet.options["audio"] = ("pulse", "openal", "directsound", "silent")
        _SERVER = pyglet.media
        _LIB_VERSION = pyglet.version


def safe_init(
    lib: None | str = None,
    samplerate: int = 22050,
    channels: int = 2,
    buffersize: int = 2048,
    reinit: bool = False,
) -> None | Exception:
    """Safely initialize the sound subsystem.

    Like init(), but catch any exceptions.

    Args:
        lib (str): The audio library to use (e.g., "SDL", "pyglet", "pyo", "wx").
        samplerate (int): The sample rate to use.
        channels (int): The number of audio channels.
        buffersize (int): The size of the audio buffer.
        reinit (bool): Whether to reinitialize the sound subsystem.

    Returns:
        None | Exception: None if initialization was successful, or an
            Exception if an error occurred.
    """
    global _INITIALIZED
    try:
        return init(lib, samplerate, channels, buffersize, reinit)
    except Exception as exception:
        # So we can check if initialization failed
        _INITIALIZED = exception
        return exception


class DummySound:
    """Dummy sound wrapper class.

    Args:
        filename (str): The filename of the sound file (not used).
        loop (bool): Whether to loop the sound (not used).
    """

    def __init__(self, filename: None | str = None, loop: bool = False) -> None:
        pass

    def fade(self, fade_ms: int, fade_in: None | bool = None) -> bool:
        """Fade in/out.

        Args:
            fade_ms (int): Fade in/out duration in milliseconds.
            fade_in (bool): If True, fade in, if False, fade out. If None,
                fade in if currently not playing, otherwise fade out.

        Returns:
            bool: Always True for DummySound.
        """
        return True

    @property
    def is_playing(self) -> bool:
        """Return whether the sound is currently playing.

        Returns:
            bool: Always False for DummySound.
        """
        return False

    def play(self, fade_ms: int = 0) -> bool:
        """Play the sound.

        Args:
            fade_ms (int): Fade in duration in milliseconds.

        Returns:
            bool: True if the sound was played, False otherwise.
        """
        return True

    @property
    def play_count(self) -> int:
        """Return the number of times the sound has been played.

        Returns:
            int: The number of times the sound has been played.
        """
        return 0

    def safe_fade(self, fade_ms: int, fade_in: None | bool = None) -> bool:
        """Like fade(), but catch any exceptions.

        Args:
            fade_ms (int): Fade in/out duration in milliseconds.
            fade_in (None | bool): If True, fade in, if False, fade out. If
                None, fade in if currently not playing, otherwise fade out.

        Returns:
            bool: True if the fade was successful, False otherwise.
        """
        return True

    def safe_play(self, fade_ms: int = 0) -> bool:
        """Like play(), but catch any exceptions.

        Args:
            fade_ms (int): Fade in duration in milliseconds.

        Returns:
            bool: True if the sound was played, False otherwise.
        """
        return True

    def safe_stop(self, fade_ms: int = 0) -> bool:
        """Like stop(), but catch any exceptions.

        Args:
            fade_ms (int): Fade out duration in milliseconds.

        Returns:
            bool: True if the sound was stopped, False otherwise.
        """
        return True

    def stop(self, fade_ms: int = 0) -> bool:
        """Stop playback.

        Args:
            fade_ms (int): Fade out duration in milliseconds.

        Returns:
            bool: True if the sound was stopped, False otherwise.
        """
        return True

    volume = 0


class SDL_RWops(Structure):  # noqa: N801
    """SDL_RWops structure."""


class Mix_Chunk(Structure):  # noqa: N801
    """SDL_Mixer chunk structure."""

    _fields_: ClassVar[list[tuple]] = [
        ("allocated", c_int),
        ("abuf", POINTER(c_uint8)),
        ("alen", c_uint32),
        ("volume", c_uint8),
    ]


class Sound:
    """Sound wrapper class.

    Args:
        filename (str): The filename of the sound file.
        loop (bool): Whether to loop the sound.
    """

    def __new__(cls, filename: str, loop: bool = False) -> Sound:  # noqa: PYI034
        """Create a new Sound instance.

        Args:
            filename (str): The filename of the sound file.
            loop (bool): Whether to loop the sound.

        Returns:
            Sound: A new Sound instance.
        """
        if (filename, loop) in _SOUNDS:
            # Cache hit
            return _SOUNDS[(filename, loop)]
        # Create and instance and cache it
        sound = super().__new__(cls)
        _SOUNDS[(filename, loop)] = sound
        return sound

    def __init__(self, filename: str, loop: bool = False) -> None:
        self._filename = filename
        self._is_playing = False
        self._lib = _LIB
        self._lib_version = _LIB_VERSION
        self._loop = loop
        self._play_timestamp = 0
        self._play_count = 0
        self._thread = -1
        if not _INITIALIZED:
            self._server = init()
        else:
            self._server = _SERVER
        if not _INITIALIZED or isinstance(_INITIALIZED, Exception):
            return
        if not self._lib and _LIB:
            self._lib = _LIB
            self._lib_version = _LIB_VERSION
        if self._snd or not self._filename:
            return
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
    def _ch(self) -> None | int | pyglet.media.Player:
        """Return the channel object or value.

        Returns:
            None | int | pyglet.media.Player : The channel object or None if
                not available.
        """
        return _CH.get((self._filename, self._loop))

    @_ch.setter
    def _ch(self, ch: None | int | pyglet.media.Player) -> None:
        """Set the channel object or value.

        Args:
            ch (None | int | pyglet.media.Player): The channel object to set.
        """
        _CH[(self._filename, self._loop)] = ch

    def _fade(self, fade_ms: int, fade_in: bool, thread: int) -> None:
        """Fade in/out the sound.

        Args:
            fade_ms (int): Fade in/out duration in milliseconds.
            fade_in (bool): If True, fade in, if False, fade out.
            thread (int): Thread identifier to check if we are still the current thread.
        """
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
    def volume(self) -> float:
        """Return the current volume of the sound.

        If the sound is not playing, return 0.0.
        If the sound is not available, return 1.0.

        Returns:
            float: The current volume of the sound, between 0.0 and 1.0.
        """
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
    def volume(self, volume: float) -> None:
        """Set the volume of the sound.

        Args:
            volume (float): The volume to set, between 0.0 and 1.0.
        """
        if not self._snd or self._lib == "wx":
            return
        if self._lib == "pyo":
            self._snd.mul = volume
        elif self._lib == "pyglet":
            self._ch.volume = volume
        elif self._lib == "SDL":
            self._server.Mix_VolumeChunk(self._snd, round(volume * 128))

    @property
    def _snd(self) -> None | Sound:
        """Return the sound object.

        Returns:
            None | Sound: The sound object or None if not available.
        """
        return _SND.get((self._filename, self._loop))

    @_snd.setter
    def _snd(self, snd: Sound) -> None:
        """Set the sound object.

        Args:
            snd: The sound object to set.
        """
        _SND[(self._filename, self._loop)] = snd

    def fade(self, fade_ms: int, fade_in: None | bool = None) -> bool:
        """Fade in/out.

        If fade_in is None, fade in/out depending on current volume.

        Args:
            fade_ms (int): Fade in/out duration in milliseconds.
            fade_in (bool): If True, fade in, if False, fade out. If None,
                fade in if currently not playing, otherwise fade out.

        Returns:
            bool: True if the fade was started, False otherwise.
        """
        if fade_in is None:
            fade_in = not self.volume
        if fade_in and not self.is_playing:
            return self.play(fade_ms=fade_ms)
        if not self._snd or self._lib == "wx":
            return False
        self._thread += 1
        threading.Thread(
            target=self._fade,
            name=f"AudioFading-{self._thread}[{fade_ms}ms]",
            args=(fade_ms, fade_in, self._thread),
        ).start()
        return True

    @property
    def is_playing(self) -> bool:
        """Return whether the sound is currently playing.

        Returns:
            bool: True if the sound is playing, False otherwise.
        """
        if self._lib == "pyo":
            return bool(self._snd and self._snd.isOutputting())
        if self._lib == "pyglet":
            return bool(
                self._ch
                and self._ch.playing
                and self._ch.source
                and (
                    self._loop
                    or time.time() - self._play_timestamp < self._ch.source.duration
                )
            )
        if self._lib == "SDL":
            return bool(self._ch is not None and self._server.Mix_Playing(self._ch))
        return self._is_playing


    def _play_pyglet(self, fade_ms: int = 0, stop_already_playing: bool = True) -> bool:
        """Play the sound using pyglet.

        Args:
            fade_ms (int): Fade in duration in milliseconds.
            stop_already_playing (bool): If True, stop the sound if it is
                already playing before starting playback.

        Returns:
            bool: True if the sound was played, False otherwise.
        """
        if not self._snd:
            return False
        volume = self.volume
        if stop_already_playing:
            self.stop()
        # Can't reuse the player, won't replay the sound under Mac OS X
        # and Linux even when seeking to start position which allows
        # replaying the sound under Windows.
        if stop_already_playing:
            with contextlib.suppress(TypeError):
                self._ch.delete()
        self._ch = pyglet.media.Player()
        if self._lib_version >= "1.4.0":
            self._ch.loop = self._loop
        self.volume = volume
        if not self.is_playing and fade_ms and volume == 1:
            self.volume = 0
        self._play_timestamp = time.time()

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

        if self._lib:
            self._play_count += 1
        if fade_ms:
            self.fade(fade_ms, True)
        return True

    def _play_pyo(self, fade_ms: int = 0, stop_already_playing: bool = True) -> bool:
        """Play the sound using pyo.

        Args:
            fade_ms (int): Fade in duration in milliseconds.
            stop_already_playing (bool): If True, stop the sound if it is
                already playing before starting playback.

        Returns:
            bool: True if the sound was played, False otherwise.
        """
        if not self._snd:
            return False
        volume = self.volume
        if stop_already_playing:
            self.stop()

        if not self.is_playing and fade_ms and volume == 1:
            self.volume = 0
        self._play_timestamp = time.time()
        self._snd.out()
        if self._lib:
            self._play_count += 1
        if fade_ms:
            self.fade(fade_ms, True)
        return True

    def _play_sdl(self, fade_ms: int = 0, stop_already_playing: bool = True) -> bool:
        """Play the sound using SDL.

        Args:
            fade_ms (int): Fade in duration in milliseconds.
            stop_already_playing (bool): If True, stop the sound if it is
                already playing before starting playback.

        Returns:
            bool: True if the sound was played, False otherwise.
        """
        if not self._snd:
            return False
        volume = self.volume
        if stop_already_playing:
            self.stop()
        if not self.is_playing and fade_ms and volume == 1:
            self.volume = 0
        self._play_timestamp = time.time()
        self._ch = self._server.Mix_PlayChannelTimed(
            -1, self._snd, -1 if self._loop else 0, -1
        )
        if self._lib:
            self._play_count += 1
        if fade_ms:
            self.fade(fade_ms, True)
        return True

    def _play_wx(self, fade_ms: int = 0, stop_already_playing: bool = True) -> bool:
        """Play the sound using wx.

        Args:
            fade_ms (int): Fade in duration in milliseconds.
            stop_already_playing (bool): If True, stop the sound if it is
                already playing before starting playback.

        Returns:
            bool: True if the sound was played, False otherwise.
        """
        if not self._snd:
            return False
        volume = self.volume
        if stop_already_playing:
            self.stop()
        if not self.is_playing and fade_ms and volume == 1:
            self.volume = 0
        self._play_timestamp = time.time()
        if self._snd.IsOk():
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
        return True

    def play(self, fade_ms: int = 0, stop_already_playing: bool = True) -> bool:
        """Play the sound.

        Args:
            fade_ms (int): Fade in duration in milliseconds.
            stop_already_playing (bool): If True, stop the sound if it is
                already playing before starting playback.

        Returns:
            bool: True if the sound was played, False otherwise.
        """
        if not self._snd:
            return False
        if self._lib == "pyglet":
            return self._play_pyglet(fade_ms, stop_already_playing)
        if self._lib == "pyo":
            return self._play_pyo(fade_ms, stop_already_playing)
        if self._lib == "pyglet":
            return self._play_pyglet(fade_ms, stop_already_playing)
        if self._lib == "SDL":
            return self._play_sdl(fade_ms, stop_already_playing)
        if self._lib == "wx":
            return self._play_wx(fade_ms, stop_already_playing)
        return True

    @property
    def play_count(self) -> int:
        """Return the number of times the sound has been played.

        Returns:
            int: The number of times the sound has been played.
        """
        return self._play_count

    def safe_fade(self, fade_ms: int, fade_in: None | bool = None) -> bool | Exception:
        """Safely fade in/out.

        Like fade(), but catch any exceptions.

        Args:
            fade_ms (int): Fade in/out duration in milliseconds.
            fade_in (None | bool): If True, fade in, if False, fade out. If
                None, fade in if currently not playing, otherwise fade out.

        Returns:
            bool | Exception: True if the fade was successful, False otherwise,
                or an exception if an error occurred.
        """
        if not _INITIALIZED:
            safe_init()
        try:
            return self.fade(fade_ms, fade_in)
        except Exception as exception:
            return exception

    def safe_play(self, fade_ms: int = 0) -> bool | Exception:
        """Safely play the sound.

        Like play(), but catch any exceptions.

        Args:
            fade_ms (int): Fade in duration in milliseconds.

        Returns:
            bool | Exception: True if the sound was played, False otherwise,
                or an exception if an error occurred.
        """
        if not _INITIALIZED:
            safe_init()
        try:
            return self.play(fade_ms)
        except Exception as exception:
            return exception

    def safe_stop(self, fade_ms: int = 0) -> bool | Exception:
        """Safely stop playback.

        Like stop(), but catch any exceptions.

        Returns:
            bool | Exception: True if the sound was stopped, False otherwise,
                or an exception if an error occurred.
        """
        try:
            return self.stop(fade_ms)
        except Exception as exception:
            return exception

    def stop(self, fade_ms: int = 0) -> bool:
        """Stop playback.

        Args:
            fade_ms (int): Fade out duration in milliseconds.

        Returns:
            bool: True if the sound was stopped, False otherwise.
        """
        if self._snd and self.is_playing:
            if self._lib == "wx":
                self._snd.Stop()
                self._is_playing = False
            elif fade_ms:
                self.fade(fade_ms, False)
            elif self._lib == "pyglet":
                self._ch.pause()
            elif self._lib == "SDL":
                self._server.Mix_HaltChannel(self._ch)
            else:
                self._snd.stop()
            return True
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
            sound.stop(1000) and _LIB != "wx" and time.sleep(1),
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
