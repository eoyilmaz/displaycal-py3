import pytest



def setup_test():
    """Setup test environment."""
    from _thread import start_new_thread
    from time import sleep

    class Subprocess:
        """Mock subprocess class to simulate sending commands."""

        def send(self, bytes_):
            start_new_thread(test, (bytes_,))

    class Worker:
        """Mock worker class to simulate subprocess."""

        def __init__(self):
            self.subprocess = Subprocess()

        def safe_send(self, bytes_):
            self.subprocess.send(bytes_)
            return True

    config.initcfg()
    lang.init()
    app = BaseApp(0)

    if "--crt" in sys.argv[1:]:
        setcfg("measurement_mode", "c")
    else:
        setcfg("measurement_mode", "l")

    app.TopWindow = DisplayAdjustmentFrame(start_timer=False)
    app.TopWindow.worker = Worker()
    app.TopWindow.Show()
    i = 0

    yield app, i

    start_new_thread(test, ())
    app.MainLoop()


@pytest.mark.skip(reason="TODO: This test is moved from the module, properly implement it.")
def test_from_modules(bytes_=None):
    global i
    # 0 = dispcal -v -yl
    # 1 = dispcal -v -yl -b130
    # 2 = dispcal -v -yl -B0.5
    # 3 = dispcal -v -yl -t5200
    # 4 = dispcal -v -yl -t5200 -b130 -B0.5
    menu = r"""
Press 1 .. 7
1) Black level (CRT: Offset/Brightness)
2) White point (Color temperature, R,G,B, Gain/Contrast)
3) White level (CRT: Gain/Contrast, LCD: Brightness/Backlight)
4) Black point (R,G,B, Offset/Brightness)
5) Check all
6) Measure and set ambient for viewing condition adjustment
7) Continue on to calibration
8) Exit
"""
    if bytes_ == " ":
        txt = "\n" + menu
    elif bytes_ == "1":
        # Black level
        txt = [
            r"""Doing some initial measurements
Black = XYZ   0.19   0.20   0.28
Grey  = XYZ  27.20  27.79  24.57
White = XYZ 126.48 128.71 112.75

Adjust CRT brightness to get target level. Press space when done.
   Target 1.29
/ Current 2.02  -""",
            r"""Doing some initial measurements
Black = XYZ   0.19   0.20   0.29
Grey  = XYZ  27.11  27.76  24.72
White = XYZ 125.91 128.38 113.18

Adjust CRT brightness to get target level. Press space when done.
   Target 1.28
/ Current 2.02  -""",
            r"""Doing some initial measurements
Black = XYZ   0.19   0.21   0.28
Grey  = XYZ  27.08  27.72  24.87
White = XYZ 125.47 127.86 113.60

Adjust CRT brightness to get target level. Press space when done.
   Target 1.28
/ Current 2.02  -""",
            r"""Doing some initial measurements
Black = XYZ   0.19   0.20   0.29
Grey  = XYZ  27.11  27.77  25.01
White = XYZ 125.21 127.80 113.90

Adjust CRT brightness to get target level. Press space when done.
   Target 1.28
/ Current 2.03  -""",
            r"""Doing some initial measurements
Black = XYZ   0.19   0.20   0.30
Grey  = XYZ  23.56  24.14  21.83
White = XYZ 124.87 130.00 112.27

Adjust CRT brightness to get target level. Press space when done.
   Target 1.28
/ Current 1.28""",
        ][i]
    elif bytes_ == "2":
        # White point
        txt = [
            r"""Doing some initial measurements
Red   = XYZ  81.08  39.18   2.41
Green = XYZ  27.63  80.13  10.97
Blue  = XYZ  18.24   9.90  99.75
White = XYZ 126.53 128.96 112.57

Adjust R,G & B gain to desired white point. Press space when done.
  Initial Br 128.96, x 0.3438 , y 0.3504 , VDT 5152K DE 2K  4.7
/ Current Br 128.85, x 0.3439-, y 0.3502+  VDT 5151K DE 2K  4.8  R-  G++ B-""",
            r"""Doing some initial measurements
Red   = XYZ  80.48  38.87   2.43
Green = XYZ  27.58  79.99  10.96
Blue  = XYZ  18.34   9.93 100.24
White = XYZ 125.94 128.32 113.11

Adjust R,G & B gain to desired white point. Press space when done.
  Initial Br 130.00, x 0.3428 , y 0.3493 , VDT 5193K DE 2K  4.9
/ Current Br 128.39, x 0.3428-, y 0.3496+  VDT 5190K DE 2K  4.7  R-  G++ B-""",
            r"""Doing some initial measurements
Red   = XYZ  80.01  38.57   2.44
Green = XYZ  27.51  79.85  10.95
Blue  = XYZ  18.45   9.94 100.77
White = XYZ 125.48 127.88 113.70

Adjust R,G & B gain to desired white point. Press space when done.
  Initial Br 127.88, x 0.3419 , y 0.3484 , VDT 5232K DE 2K  5.0
/ Current Br 127.87, x 0.3419-, y 0.3485+  VDT 5231K DE 2K  4.9  R-  G++ B-""",
            r"""Doing some initial measurements
Red   = XYZ  79.69  38.48   2.44
Green = XYZ  27.47  79.76  10.95
Blue  = XYZ  18.50   9.95 101.06
White = XYZ 125.08 127.71 113.91

Adjust R,G & B gain to get target x,y. Press space when done.
   Target Br 127.71, x 0.3401 , y 0.3540
/ Current Br 127.70, x 0.3412-, y 0.3481+  DE  4.8  R-  G++ B-""",
            r"""Doing some initial measurements
Red   = XYZ  79.47  38.41   2.44
Green = XYZ  27.41  79.72  10.94
Blue  = XYZ  18.52   9.96 101.20
White = XYZ 124.87 130.00 112.27

Adjust R,G & B gain to get target x,y. Press space when done.
   Target Br 130.00, x 0.3401 , y 0.3540
/ Current Br 130.00, x 0.3401=, y 0.3540=  DE  0.0  R=  G= B=""",
        ][i]
    elif bytes_ == "3":
        # White level
        txt = [
            r"""Doing some initial measurements
White = XYZ 126.56 128.83 112.65

Adjust CRT Contrast or LCD Brightness to desired level. Press space when done.
  Initial 128.83
/ Current 128.85""",
            r"""Doing some initial measurements
White = XYZ 125.87 128.23 113.43

Adjust CRT Contrast or LCD Brightness to get target level. Press space when done.
   Target 130.00
/ Current 128.24  +""",
            r"""Doing some initial measurements
White = XYZ 125.33 127.94 113.70

Adjust CRT Contrast or LCD Brightness to desired level. Press space when done.
  Initial 127.94
/ Current 127.88""",
            r"""Doing some initial measurements
White = XYZ 125.00 127.72 114.03

Adjust CRT Contrast or LCD Brightness to desired level. Press space when done.
  Initial 127.72
/ Current 127.69""",
            r"""Doing some initial measurements
White = XYZ 124.87 130.00 112.27

Adjust CRT Contrast or LCD Brightness to get target level. Press space when done.
   Target 130.00
/ Current 130.00""",
        ][i]
    elif bytes_ == "4":
        # Black point
        txt = [
            r"""Doing some initial measurements
Black = XYZ   0.19   0.21   0.29
Grey  = XYZ  27.25  27.83  24.52
White = XYZ 126.60 128.86 112.54

Adjust R,G & B offsets to get target x,y. Press space when done.
   Target Br 1.29, x 0.3440 , y 0.3502
/ Current Br 2.03, x 0.3409+, y 0.3484+  DE  1.7  R++ G+  B-""",
            r"""Doing some initial measurements
Black = XYZ   0.19   0.21   0.29
Grey  = XYZ  27.19  27.87  24.94
White = XYZ 125.83 128.16 113.57

Adjust R,G & B offsets to get target x,y. Press space when done.
   Target Br 1.28, x 0.3423 , y 0.3487
/ Current Br 2.03, x 0.3391+, y 0.3470+  DE  1.7  R++ G+  B-""",
            r"""Doing some initial measurements
Black = XYZ   0.19   0.21   0.29
Grey  = XYZ  27.14  27.79  24.97
White = XYZ 125.49 127.89 113.90

Adjust R,G & B offsets to get target x,y. Press space when done.
   Target Br 1.28, x 0.3417 , y 0.3482
/ Current Br 2.02, x 0.3386+, y 0.3466+  DE  1.7  R++ G+  B-""",
            r"""Doing some initial measurements
Black = XYZ   0.19   0.21   0.30
Grey  = XYZ  27.10  27.79  25.12
White = XYZ 125.12 127.68 114.09

Adjust R,G & B offsets to get target x,y. Press space when done.
   Target Br 1.28, x 0.3401 , y 0.3540
/ Current Br 2.04, x 0.3373+, y 0.3465+  DE  4.4  R+  G++ B-""",
            r"""Doing some initial measurements
Black = XYZ   0.19   0.21   0.29
Grey  = XYZ  23.56  24.14  21.83
White = XYZ 124.87 130.00 112.27

Adjust R,G & B offsets to get target x,y. Press space when done.
   Target Br 1.28, x 0.3401 , y 0.3540
/ Current Br 1.28, x 0.3401=, y 0.3540=  DE  0.0  R=  G= B=""",
        ][i]
    elif bytes_ == "5":
        # Check all
        txt = [
            r"""Doing check measurements
Black = XYZ   0.19   0.20   0.29
Grey  = XYZ  27.22  27.80  24.49
White = XYZ 126.71 128.91 112.34
1%    = XYZ   1.94   1.98   1.76

  Current Brightness = 128.91
  Target 50% Level  = 24.42, Current = 27.80, error =  2.6%
  Target Near Black =  1.29, Current =  2.02, error =  0.6%
  Current white = x 0.3443, y 0.3503, VDT 5137K DE 2K  5.0
  Target black = x 0.3443, y 0.3503, Current = x 0.3411, y 0.3486, error =  1.73 DE

Press 1 .. 7""",
            r"""Doing check measurements
Black = XYZ   0.19   0.21   0.29
Grey  = XYZ  27.10  27.75  24.85
White = XYZ 125.78 128.17 113.53
1%    = XYZ   1.93   1.98   1.79

  Target Brightness = 130.00, Current = 128.17, error = -1.4%
  Target 50% Level  = 24.28, Current = 27.75, error =  2.7%
  Target Near Black =  1.28, Current =  2.02, error =  0.6%
  Current white = x 0.3423, y 0.3488, VDT 5215K DE 2K  4.9
  Target black = x 0.3423, y 0.3488, Current = x 0.3391, y 0.3467, error =  1.69 DE

Press 1 .. 7""",
            r"""Doing check measurements
Black = XYZ   0.19   0.21   0.29
Grey  = XYZ  27.09  27.74  24.95
White = XYZ 125.32 127.78 113.82
1%    = XYZ   1.93   1.98   1.80

  Current Brightness = 127.78
  Target 50% Level  = 24.21, Current = 27.74, error =  2.8%
  Target Near Black =  1.28, Current =  2.02, error =  0.6%
  Current white = x 0.3415, y 0.3483, VDT 5243K DE 2K  4.9
  Target black = x 0.3415, y 0.3483, Current = x 0.3386, y 0.3465, error =  1.55 DE

Press 1 .. 7""",
                r"""Doing check measurements
Black = XYZ   0.19   0.20   0.29
Grey  = XYZ  26.98  27.68  24.97
White = XYZ 125.00 127.56 113.99
1%    = XYZ   1.92   1.97   1.80

  Current Brightness = 127.56
  Target 50% Level  = 24.17, Current = 27.68, error =  2.8%
  Target Near Black =  1.28, Current =  2.02, error =  0.6%
  Target white = x 0.3401, y 0.3540, Current = x 0.3410, y 0.3480, error =  4.83 DE
  Target black = x 0.3401, y 0.3540, Current = x 0.3372, y 0.3464, error =  4.48 DE

Press 1 .. 7""",
                r"""Doing check measurements
Black = XYZ   0.19   0.21   0.29
Grey  = XYZ  23.56  24.14  21.83
White = XYZ 124.87 130.00 112.27
1%    = XYZ   1.92   1.97   1.80

  Target Brightness = 130.00, Current = 130.00, error = 0.0%
  Target 50% Level  = 24.14, Current = 24.14, error =  0.0%
  Target Near Black =  1.27, Current =  1.27, error =  0.0%
  Target white = x 0.3401, y 0.3540, Current = x 0.3401, y 0.3540, error =  0.00 DE
  Target black = x 0.3401, y 0.3540, Current = x 0.3401, y 0.3540, error =  0.00 DE

Press 1 .. 7""",
        ][i]
    elif bytes_ == "7" or not bytes_:
        if bytes_ == "7":
            if i < 4:
                i += 1
            else:
                i -= 4
            wx.CallAfter(app.TopWindow.reset)
        txt = (
            [
                r"""Setting up the instrument
Place instrument on test window.
Hit Esc or Q to give up, any other key to continue:
Display type is LCD
Target white = native white point
Target white brightness = native brightness
Target black brightness = native brightness
Target advertised gamma = 2.400000""",
                r"""Setting up the instrument
Place instrument on test window.
Hit Esc or Q to give up, any other key to continue:
Display type is LCD
Target white = native white point
Target white brightness = 130.000000 cd/m^2
Target black brightness = native brightness
Target advertised gamma = 2.400000""",
                r"""Setting up the instrument
Place instrument on test window.
Hit Esc or Q to give up, any other key to continue:
Display type is LCD
Target white = native white point
Target white brightness = native brightness
Target black brightness = 0.500000 cd/m^2
Target advertised gamma = 2.400000""",
                r"""Setting up the instrument
Place instrument on test window.
Hit Esc or Q to give up, any other key to continue:
Display type is LCD
Target white = 5200.000000 degrees kelvin Daylight spectrum
Target white brightness = native brightness
Target black brightness = native brightness
Target advertised gamma = 2.400000""",
                r"""Setting up the instrument
Place instrument on test window.
Hit Esc or Q to give up, any other key to continue:
Display type is CRT
Target white = 5200.000000 degrees kelvin Daylight spectrum
Target white brightness = 130.000000 cd/m^2
Target black brightness = 0.500000 cd/m^2
Target advertised gamma = 2.400000""",
            ][i]
            + r"""

Display adjustment menu:"""
            + menu
        )
    elif bytes_ == "8":
        wx.CallAfter(app.TopWindow.Close)
        return
    else:
        return
    for line in txt.split("\n"):
        sleep(0.0625)
        wx.CallAfter(app.TopWindow.write, line)
        print(line)