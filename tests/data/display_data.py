"""Sample DisplayData class."""

import sys
from typing import Dict, List


class DisplayData:
    """Sample Display."""

    DISPLAY_DATA_1 = {
        "name": b"Monitor 1, Output DP-2",
        "description": b"Monitor 1, Output DP-2 at 0, 0, width 1280, height 1024",
        "pos": (0, 0),
        "size": (1280, 1024),
        "size_mm": (338, 270),
        "x11_screen": 0,
        "screen": 0,
        "ramdac_screen": 0,
        "icc_profile_atom_id": 551,
        "edid": b"\x00\xff\xff\xff\xff\xff\xff\x00Zc:z\x0f\x01\x01\x011\x1e\x01\x04"
        b'\xb5<"x;\xb0\x91\xabRN\xa0&\x0fPT\xbf\xef\x80\xe1\xc0\xd1\x00\xd1\xc0'
        b"\xb3\x00\xa9@\x81\x80\x81\x00\x81\xc0V^\x00\xa0\xa0\xa0)P0 5\x00UP!"
        b"\x00\x00\x1a\x00\x00\x00\xff\x00W8U204900104\n\x00\x00\x00\xfd\x00"
        b"\x18K\x0fZ\x1e\x00\n      \x00\x00\x00\xfc\x00VP2768a\n     "
        b'\x01{\x02\x03"\xf1U\x90\x1f\x05\x14ZY\x04\x13\x1e\x1d\x0f\x0e\x07'
        b"\x06\x12\x11\x16\x15\x03\x02\x01#\t\x7f\x07\x83\x01\x00\x00\x02:"
        b"\x80\x18q8-@X,E\x00UP!\x00\x00\x1e\x01\x1d\x80\x18q\x1c\x16 X,%"
        b"\x00UP!\x00\x00\x9e\x02:\x80\xd0r8-@\x10,E\x80UP!\x00\x00\x1e\x01"
        b"\x1d\x00rQ\xd0\x1e n(U\x00UP!\x00\x00\x1eXM\x00\xb8\xa18\x14@\xf8,K"
        b"\x00UP!\x00\x00\x1e\x00\x00\x00\xd2",
        "output": 472,
        "icc_profile_output_atom_id": 551,
    }

    DISPLAY_DATA_2 = {
        "blue_x": 0.1474609375,
        "blue_y": 0.04296875,
        "checksum": 44,
        "checksum_valid": True,
        "edid": b"\x00\xff\xff\xff\xff\xff\xff\x00\x10\xac\xe0@L405\x05\x1b\x01\x04"
        b"\xb57\x1fx:U\xc5\xafO3\xb8%\x0bPT\xa5K\x00qO\xa9@\x81\x80"
        b"\xd1\xc0\x01\x01\x01\x01\x01\x01\x01\x01V^\x00\xa0\xa0\xa0)P0 "
        b"5\x00)7!\x00\x00\x1a\x00\x00\x00\xff\x00TYPR371U504L\n\x00\x00"
        b"\x00\xfc\x00DELL UP2516D\n\x00\x00\x00\xfd\x002K\x1eX\x19\x01\n    "
        b"  \x01,\x02\x03\x1c\xf1O\x90\x05\x04\x03\x02\x07\x16\x01\x06\x11\x12"
        b"\x15\x13\x14\x1f#\t\x1f\x07\x83\x01\x00\x00\x02:\x80\x18q8-@X,E\x00"
        b")7!\x00\x00\x1e~9\x00\xa0\x808\x1f@0 :\x00)7!\x00\x00\x1a"
        b"\x01\x1d\x00rQ\xd0\x1e n(U\x00)7!\x00\x00\x1e\xbf\x16\x00\xa0\x808"
        b"\x13@0 :\x00)7!\x00\x00\x1a\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x86",
        "edid_revision": 4,
        "edid_version": 1,
        "ext_flag": 1,
        "features": 58,
        "gamma": 2.2,
        "green_x": 0.2001953125,
        "green_y": 0.7197265625,
        "hash": "40cf706d53476076b828fb8a78af796d",
        "header": b"\x00\xff\xff\xff\xff\xff\xff\x00",
        "manufacturer": "Dell, Inc.",
        "manufacturer_id": "DEL",
        "max_h_size_cm": 55,
        "max_v_size_cm": 31,
        "monitor_name": "DELL UP2516D",
        "product_id": 16608,
        "red_x": 0.6845703125,
        "red_y": 0.3095703125,
        "serial_32": 892351564,
        "serial_ascii": "TYPR371U504L",
        "week_of_manufacture": 5,
        "white_x": 0.3134765625,
        "white_y": 0.3291015625,
        "year_of_manufacture": 2017,
    }

    DISPWIN_OUTPUT_1 = b"""Test display patch window, Set Video LUTs, Install profiles, Version 3.3.0
Author: Graeme W. Gill, licensed under the AGPL Version 3
Diagnostic: -d parameter '0' is out of range
usage: dispwin [options] [calfile]
 -v                   Verbose mode
 -d n                 Choose the display from the following list (default 1)
    1 = 'Built-in Retina Display, at 0, 0, width 1728, height 1117 (Primary Display)'
 -dweb[:port]         Display via web server at port (default 8080)
 -dcc[:n]             Display via n'th ChromeCast (default 1, ? for list)
 -d dummy             Display via dummy (non-existant, invisible) display
 -P ho,vo,ss[,vs]     Position test window and scale it
 -F                   Fill whole screen with black background
 -E                   Video encode output as (16-235)/255 "TV" levels
 -i                   Run forever with random values
 -G filename          Display RGB colors from CGATS (ie .ti1) file
 -C r.rr,g.gg,b.bb    Add this RGB color to list to be displayed
 -m                   Manually cycle through values
 -Y msec              patch delay in msec (default 2000)
 -f                   Test grey ramp fade
 -r                   Test just Video LUT loading & Beeps
 -n                   Test native output (rather than through Video LUT and C.M.)
 -s filename          Save the currently loaded Video LUT to 'filename'
 -c                   Load a linear display calibration
 -V                   Verify that calfile/profile cal. is currently loaded in LUT
 -I                   Install profile for display and use its calibration
 -U                   Un-install profile for display
 -S d                 Specify the install/uninstall scope for OS X [nlu] or X11/Vista [lu]
                      d is one of: n = network, l = local system, u = user (default)
 -L                   Load installed profile & calibration
 -D [level]           Print debug diagnostics to stderr
 calfile              Load calibration (.cal or .icc) into Video LUT"""

    DISPWIN_OUTPUT_2 = b"""Test display patch window, Set Video LUTs, Install profiles, Version 3.3.0
Author: Graeme W. Gill, licensed under the AGPL Version 3
Diagnostic: -d parameter '0' is out of range
usage: dispwin [options] [calfile]
 -v                   Verbose mode
 -d n                 Choose the display from the following list (default 1)
    1 = 'Built-in Retina Display, at 0, 0, width 1728, height 1117 (Primary Display)'
    2 = 'DELL U2720Q, at 1728, -575, width 3008, height 1692'
 -dweb[:port]         Display via web server at port (default 8080)
 -dcc[:n]             Display via n'th ChromeCast (default 1, ? for list)
 -d dummy             Display via dummy (non-existant, invisible) display
 -P ho,vo,ss[,vs]     Position test window and scale it
 -F                   Fill whole screen with black background
 -E                   Video encode output as (16-235)/255 "TV" levels
 -i                   Run forever with random values
 -G filename          Display RGB colors from CGATS (ie .ti1) file
 -C r.rr,g.gg,b.bb    Add this RGB color to list to be displayed
 -m                   Manually cycle through values
 -Y msec              patch delay in msec (default 2000)
 -f                   Test grey ramp fade
 -r                   Test just Video LUT loading & Beeps
 -n                   Test native output (rather than through Video LUT and C.M.)
 -s filename          Save the currently loaded Video LUT to 'filename'
 -c                   Load a linear display calibration
 -V                   Verify that calfile/profile cal. is currently loaded in LUT
 -I                   Install profile for display and use its calibration
 -U                   Un-install profile for display
 -S d                 Specify the install/uninstall scope for OS X [nlu] or X11/Vista [lu]
                      d is one of: n = network, l = local system, u = user (default)
 -L                   Load installed profile & calibration
 -D [level]           Print debug diagnostics to stderr
 calfile              Load calibration (.cal or .icc) into Video LUT"""

    DISPWIN_OUTPUT_3 = b"""Test display patch window, Set Video LUTs, Install profiles, Version 3.3.0
    Author: Graeme W. Gill, licensed under the AGPL Version 3
    Diagnostic: -d parameter '0' is out of range
    usage: dispwin [options] [calfile]
     -v                   Verbose mode
     -d n                 Choose the display from the following list (default 1)
     -dweb[:port]         Display via web server at port (default 8080)
     -dcc[:n]             Display via n'th ChromeCast (default 1, ? for list)
     -d dummy             Display via dummy (non-existant, invisible) display
     -P ho,vo,ss[,vs]     Position test window and scale it
     -F                   Fill whole screen with black background
     -E                   Video encode output as (16-235)/255 "TV" levels
     -i                   Run forever with random values
     -G filename          Display RGB colors from CGATS (ie .ti1) file
     -C r.rr,g.gg,b.bb    Add this RGB color to list to be displayed
     -m                   Manually cycle through values
     -Y msec              patch delay in msec (default 2000)
     -f                   Test grey ramp fade
     -r                   Test just Video LUT loading & Beeps
     -n                   Test native output (rather than through Video LUT and C.M.)
     -s filename          Save the currently loaded Video LUT to 'filename'
     -c                   Load a linear display calibration
     -V                   Verify that calfile/profile cal. is currently loaded in LUT
     -I                   Install profile for display and use its calibration
     -U                   Un-install profile for display
     -S d                 Specify the install/uninstall scope for OS X [nlu] or X11/Vista [lu]
                          d is one of: n = network, l = local system, u = user (default)
     -L                   Load installed profile & calibration
     -D [level]           Print debug diagnostics to stderr
     calfile              Load calibration (.cal or .icc) into Video LUT"""

    DISPWIN_OUTPUT_4 = b"""Test display patch window, Set Video LUTs, Install profiles, Version 3.3.0
    Author: Graeme W. Gill, licensed under the AGPL Version 3
    Diagnostic: -d parameter '0' is out of range
    usage: dispwin [options] [calfile]
     -v                   Verbose mode
     -d n                 Choose the display from the following list (default 1)
        let's say for some reason these lines
        don't match the requested format
     -dweb[:port]         Display via web server at port (default 8080)
     -dcc[:n]             Display via n'th ChromeCast (default 1, ? for list)
     -d dummy             Display via dummy (non-existant, invisible) display
     -P ho,vo,ss[,vs]     Position test window and scale it
     -F                   Fill whole screen with black background
     -E                   Video encode output as (16-235)/255 "TV" levels
     -i                   Run forever with random values
     -G filename          Display RGB colors from CGATS (ie .ti1) file
     -C r.rr,g.gg,b.bb    Add this RGB color to list to be displayed
     -m                   Manually cycle through values
     -Y msec              patch delay in msec (default 2000)
     -f                   Test grey ramp fade
     -r                   Test just Video LUT loading & Beeps
     -n                   Test native output (rather than through Video LUT and C.M.)
     -s filename          Save the currently loaded Video LUT to 'filename'
     -c                   Load a linear display calibration
     -V                   Verify that calfile/profile cal. is currently loaded in LUT
     -I                   Install profile for display and use its calibration
     -U                   Un-install profile for display
     -S d                 Specify the install/uninstall scope for OS X [nlu] or X11/Vista [lu]
                          d is one of: n = network, l = local system, u = user (default)
     -L                   Load installed profile & calibration
     -D [level]           Print debug diagnostics to stderr
     calfile              Load calibration (.cal or .icc) into Video LUT"""

    DISPWIN_OUTPUT_5 = b"""Test display patch window, Set Video LUTs, Install profiles, Version 3.3.0
        Author: Graeme W. Gill, licensed under the AGPL Version 3
        Diagnostic: -d parameter '0' is out of range
        usage: dispwin [options] [calfile]
         -v                   Verbose mode
         -d n                 Choose the display from the following list (default 1)
            1 = 'Built-in Retina Display, at 0, 0, width 1728, so we have a partial match'
         -dweb[:port]         Display via web server at port (default 8080)
         -dcc[:n]             Display via n'th ChromeCast (default 1, ? for list)
         -d dummy             Display via dummy (non-existant, invisible) display
         -P ho,vo,ss[,vs]     Position test window and scale it
         -F                   Fill whole screen with black background
         -E                   Video encode output as (16-235)/255 "TV" levels
         -i                   Run forever with random values
         -G filename          Display RGB colors from CGATS (ie .ti1) file
         -C r.rr,g.gg,b.bb    Add this RGB color to list to be displayed
         -m                   Manually cycle through values
         -Y msec              patch delay in msec (default 2000)
         -f                   Test grey ramp fade
         -r                   Test just Video LUT loading & Beeps
         -n                   Test native output (rather than through Video LUT and C.M.)
         -s filename          Save the currently loaded Video LUT to 'filename'
         -c                   Load a linear display calibration
         -V                   Verify that calfile/profile cal. is currently loaded in LUT
         -I                   Install profile for display and use its calibration
         -U                   Un-install profile for display
         -S d                 Specify the install/uninstall scope for OS X [nlu] or X11/Vista [lu]
                              d is one of: n = network, l = local system, u = user (default)
         -L                   Load installed profile & calibration
         -D [level]           Print debug diagnostics to stderr
         calfile              Load calibration (.cal or .icc) into Video LUT"""

    DISPWIN_OUTPUT_6 = b"""Test display patch window, Set Video LUTs, Install profiles, Version 3.3.0
        Author: Graeme W. Gill, licensed under the AGPL Version 3
        Diagnostic: -d parameter '0' is out of range
        usage: dispwin [options] [calfile]
         -v                   Verbose mode
         -d n                 Choose the display from the following list (default 1)
            1 = 'Monitor 1, Output Virtual-1 at 0, 0, width 1920, height 1080'
         -dweb[:port]         Display via web server at port (default 8080)
         -dcc[:n]             Display via n'th ChromeCast (default 1, ? for list)
         -d dummy             Display via dummy (non-existant, invisible) display
         -P ho,vo,ss[,vs]     Position test window and scale it
         -F                   Fill whole screen with black background
         -E                   Video encode output as (16-235)/255 "TV" levels
         -i                   Run forever with random values
         -G filename          Display RGB colors from CGATS (ie .ti1) file
         -C r.rr,g.gg,b.bb    Add this RGB color to list to be displayed
         -m                   Manually cycle through values
         -Y msec              patch delay in msec (default 2000)
         -f                   Test grey ramp fade
         -r                   Test just Video LUT loading & Beeps
         -n                   Test native output (rather than through Video LUT and C.M.)
         -s filename          Save the currently loaded Video LUT to 'filename'
         -c                   Load a linear display calibration
         -V                   Verify that calfile/profile cal. is currently loaded in LUT
         -I                   Install profile for display and use its calibration
         -U                   Un-install profile for display
         -S d                 Specify the install/uninstall scope for OS X [nlu] or X11/Vista [lu]
                              d is one of: n = network, l = local system, u = user (default)
         -L                   Load installed profile & calibration
         -D [level]           Print debug diagnostics to stderr
         calfile              Load calibration (.cal or .icc) into Video LUT"""

    @classmethod
    def CFG_DATA(self, name, fallback=True, raw=False, cfg=None):
        return {
            "3dlut.tab.enable": 0,
            "3dlut.tab.enable.backup": 0,
            "app.dpi": 72.0 if sys.platform == "darwin" else 96.0,
            "argyll.dir": None,
            "argyll.version": "0.0.0",
            "calibration.use_video_lut.backup": 1,
            "displays": [
                "Monitor 1, Output DP-2 @ 0, 0, 1280x1024",
            ],
            "display.number": 0,
        }[name]

    values_to_smooth = [
        2.3293030318929384,
        2.3293030318929384,
        2.3426010372805486,
        2.355899255439649,
        2.3694314039614146,
        2.382963559969191,
        2.3544295784237055,
        2.325894148385542,
        2.31237864362089,
        2.298863114871476,
        2.284257393638482,
        2.2696516724054874,
        2.2554919758895817,
        2.2413324132212455,
        2.228930828649169,
        2.216534872357199,
        2.2209686877389485,
        2.225402599021943,
        2.2314347684988607,
        2.237466937975778,
        2.240495779254389,
        2.243524139923591,
        2.2463668023639056,
        2.249212582329651,
        2.259645930327104,
        2.2700766987102226,
        2.2676119750357664,
        2.26514725136131,
        2.2689192971808345,
        2.272691467738244,
        2.271807024935035,
        2.2709214642763333,
        2.2659462953971485,
        2.2609671314876794,
        2.2497755371588553,
        2.238585027759058,
        2.236434508653862,
        2.2342839895486666,
        2.233290317040858,
        2.2322967602292785,
        2.23393579763363,
        2.2355742286184195,
        2.234195110024527,
        2.2328135846940014,
        2.2221777867439694,
        2.2115426084432537,
        2.216398043394586,
        2.221253478345919,
        2.216669809165891,
        2.212084440641238,
        2.207992966303771,
        2.203904686093491,
        2.2073046355349235,
        2.210702635568557,
        2.2032725416809096,
        2.195842447793262,
        2.1985575301349205,
        2.201273018299861,
        2.200510485741649,
        2.199747048662873,
        2.201464894333514,
        2.203184843223363,
        2.207752729002515,
        2.2123201947894233,
        2.2126881581315416,
        2.21305612147366,
        2.2038316219757528,
        2.194605971244157,
        2.1909004523391036,
        2.187199409716638,
        2.18914533225574,
        2.191090683580704,
        2.1906565472102946,
        2.1902225204154284,
        2.1952671612214343,
        2.2003118020274397,
        2.2064622584991818,
        2.212612936178298,
        2.212736442951479,
        2.2128551476873,
        2.207003590564385,
        2.2011527621337197,
        2.199855531566799,
        2.198558300999878,
        2.1997248123751523,
        2.200891471583813,
        2.2052362641362024,
        2.209581946815164,
        2.209081169916441,
        2.2085709540482528,
        2.18468599452245,
        2.1608006937236754,
        2.132649822043214,
        2.1044989503627525,
        2.08789147368802,
        2.071285613314871,
        2.0390831980523547,
        2.00688112036438,
        1.9882057163732578,
        1.9695344209710133,
        1.9695344209710133,
    ]

    expected_smooth_values = [
        2.3293030318929384,
        2.3337357003554753,
        2.3426011082043785,
        2.355977232227204,
        2.3694314064567514,
        2.3689415141181036,
        2.354429095592813,
        2.3309007901433794,
        2.31237863562597,
        2.2984997173769495,
        2.284257393638482,
        2.269800347311184,
        2.255492020505438,
        2.2419184059199986,
        2.228932704742538,
        2.222144796248439,
        2.2209687197060304,
        2.2259353517532507,
        2.2314347684988607,
        2.2364658285763426,
        2.2404956190512526,
        2.2434622405139617,
        2.2463678415390493,
        2.2517417716735535,
        2.2596450704556594,
        2.2657782013576977,
        2.2676119750357664,
        2.26722617452597,
        2.2689193387601296,
        2.2711392632847045,
        2.2718066523165374,
        2.2695582615361722,
        2.2659449637203872,
        2.2588963213478945,
        2.249775898801864,
        2.2415983578572587,
        2.2364345086538626,
        2.234669605081129,
        2.2332903556062678,
        2.233174291634589,
        2.233935595493776,
        2.234568378758859,
        2.2341943077789828,
        2.2297288271541658,
        2.2221779932937413,
        2.216706146193936,
        2.216398043394586,
        2.218107110302132,
        2.2166692427176824,
        2.212249072036967,
        2.2079940310128334,
        2.206400762644062,
        2.207303985732324,
        2.20709327092813,
        2.2032725416809096,
        2.19922417320303,
        2.198557665409348,
        2.2001136780588104,
        2.2005101842347945,
        2.2005741429126786,
        2.2014655954065834,
        2.2041341555197973,
        2.2077525890051004,
        2.21092036064116,
        2.2126881581315416,
        2.209858633860318,
        2.20383123823119,
        2.196446015186338,
        2.1909019444332993,
        2.1890817314371604,
        2.1891451418510273,
        2.1902975210155797,
        2.1906565837354757,
        2.1920487429490527,
        2.195267161221434,
        2.200680407249352,
        2.2064623322349735,
        2.210603879209653,
        2.212734842272359,
        2.210865060401055,
        2.2070038334618016,
        2.2026706280883013,
        2.199855531566799,
        2.1993795483139427,
        2.199724861652948,
        2.201950849365056,
        2.20523656084506,
        2.2079664602892692,
        2.209078023593286,
        2.200779372829048,
        2.1846858807647926,
        2.1593788367631137,
        2.132649822043214,
        2.108346748697995,
        2.0878920124552143,
        2.066086761685082,
        2.0390833105772015,
        2.011390011596664,
        1.9882070859028838,
        1.9757581861050948,
        1.9695344209710133,
    ]

    @property
    def Geometry(self):
        """Return a wx Rect as display geometry."""
        from wx import Rect

        return Rect(
            self.DISPLAY_DATA_1["pos"][0],
            self.DISPLAY_DATA_1["pos"][1],
            self.DISPLAY_DATA_1["size"][0],
            self.DISPLAY_DATA_1["size"][1],
        )

    @staticmethod
    def enumerate_displays() -> List[Dict]:
        """Return the display data itself."""
        return [DisplayData.DISPLAY_DATA_1]

    @staticmethod
    def dispwin_output_1(*args, **kwargs) -> bytes:
        """Return dispwin output."""
        return DisplayData.DISPWIN_OUTPUT_1

    @staticmethod
    def dispwin_output_2(*args, **kwargs) -> bytes:
        """Return dispwin output."""
        return DisplayData.DISPWIN_OUTPUT_2
