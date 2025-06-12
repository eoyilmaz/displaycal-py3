import pytest



def setup_test():
    """Setup test environment."""
    # TODO: Move the tests to the tests.
    from _thread import start_new_thread
    from time import sleep

    class Subprocess:
        """Mock subprocess class to simulate subprocess behavior."""

        def send(self, bytes_):
            start_new_thread(test, (bytes_,))

    class Worker:
        """Mock worker class to simulate subprocess behavior."""

        def __init__(self):
            self.subprocess = Subprocess()
            self.subprocess_abort = False

        def abort_subprocess(self):
            self.subprocess.send("Q")

        def safe_send(self, bytes_):
            self.subprocess.send(bytes_)
            return True

    config.initcfg()
    lang.init()
    lang.update_defaults()
    app = BaseApp(0)
    app.TopWindow = DisplayUniformityFrame(start_timer=False, rows=3, cols=3)
    app.TopWindow.worker = Worker()
    app.TopWindow.Show()
    i = 0



@pytest.mark.skip(reason="TODO: This test is moved from the module, properly implement it.")
def test(bytes_=None):
    global i
    menu = r"""Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:"""
    if not bytes_:
        txt = menu
    elif bytes_ == " ":
        txt = [
            [
                """
 Result is XYZ: 115.629826 123.903717 122.761510, D50 Lab: 108.590836 -5.813746 -13.529075
                           CCT = 6104K (Delta E 7.848119)
 Closest Planckian temperature = 5835K (Delta E 6.927113)
 Closest Daylight temperature  = 5963K (Delta E 3.547392)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",  # noqa: E501
                    """
 Result is XYZ: 65.336831 69.578641 68.180005, D50 Lab: 86.789788 -3.888434 -10.469442
                           CCT = 5983K (Delta E 6.816507)
 Closest Planckian temperature = 5757K (Delta E 5.996638)
 Closest Daylight temperature  = 5883K (Delta E 2.598118)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 26.944662 28.614568 28.107897, D50 Lab: 60.439948 -2.589848 -7.899247
                           CCT = 5969K (Delta E 6.279024)
 Closest Planckian temperature = 5760K (Delta E 5.519000)
 Closest Daylight temperature  = 5887K (Delta E 2.119333)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 6.153402 6.500147 6.625585, D50 Lab: 30.640770 -1.226804 -5.876967
                           CCT = 6123K (Delta E 4.946609)
 Closest Planckian temperature = 5943K (Delta E 4.353019)
 Closest Daylight temperature  = 6082K (Delta E 0.985734)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 0.104401 0.110705 0.109155, D50 Lab: 0.640770 -1.226804 -5.876967
                           CCT = 6123K (Delta E 4.946609)
 Closest Planckian temperature = 5943K (Delta E 4.353019)
 Closest Daylight temperature  = 6082K (Delta E 0.985734)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                ],
                [
                    """
 Result is XYZ: 116.565941 124.165894 121.365684, D50 Lab: 108.678651 -4.762572 -12.508939
                           CCT = 5972K (Delta E 6.890329)
 Closest Planckian temperature = 5745K (Delta E 6.060831)
 Closest Daylight temperature  = 5871K (Delta E 2.660205)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",  # noqa: E501
                    """
 Result is XYZ: 64.511790 68.522425 66.980369, D50 Lab: 86.267011 -3.491468 -10.263432
                           CCT = 5945K (Delta E 6.363056)
 Closest Planckian temperature = 5735K (Delta E 5.590753)
 Closest Daylight temperature  = 5862K (Delta E 2.186503)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 26.905684 28.417087 27.988741, D50 Lab: 60.263695 -1.987837 -8.005457
                           CCT = 5930K (Delta E 5.234243)
 Closest Planckian temperature = 5755K (Delta E 4.591707)
 Closest Daylight temperature  = 5884K (Delta E 1.187672)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 6.144071 6.471379 6.584408, D50 Lab: 30.571861 -1.030833 -5.816641
                           CCT = 6083K (Delta E 4.418192)
 Closest Planckian temperature = 5923K (Delta E 3.883022)
 Closest Daylight temperature  = 6062K (Delta E 0.510176)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 0.104401 0.110705 0.109155, D50 Lab: 0.571861 -1.030833 -5.816641
                           CCT = 6083K (Delta E 4.418192)
 Closest Planckian temperature = 5923K (Delta E 3.883022)
 Closest Daylight temperature  = 6062K (Delta E 0.510176)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                ],
                [
                    """
 Result is XYZ: 116.611176 123.928350 121.363808, D50 Lab: 108.599092 -4.350754 -12.644938
                           CCT = 5960K (Delta E 6.444925)
 Closest Planckian temperature = 5747K (Delta E 5.664879)
 Closest Daylight temperature  = 5873K (Delta E 2.263144)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",  # noqa: E501
                    """
 Result is XYZ: 64.672460 68.441938 67.178377, D50 Lab: 86.226954 -2.956057 -10.516177
                           CCT = 5931K (Delta E 5.640857)
 Closest Planckian temperature = 5744K (Delta E 4.950818)
 Closest Daylight temperature  = 5872K (Delta E 1.545901)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 26.708397 28.224354 27.854805, D50 Lab: 60.090889 -2.043543 -8.080532
                           CCT = 5946K (Delta E 5.317449)
 Closest Planckian temperature = 5768K (Delta E 4.666630)
 Closest Daylight temperature  = 5897K (Delta E 1.265350)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 6.154005 6.469558 6.599849, D50 Lab: 30.567493 -0.904424 -5.891430
                           CCT = 6079K (Delta E 4.041262)
 Closest Planckian temperature = 5932K (Delta E 3.549922)
 Closest Daylight temperature  = 6072K (Delta E 0.177697)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 0.104401 0.110705 0.109155, D50 Lab: 0.567493 -0.904424 -5.891430
                           CCT = 6079K (Delta E 4.041262)
 Closest Planckian temperature = 5932K (Delta E 3.549922)
 Closest Daylight temperature  = 6072K (Delta E 0.177697)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                ],
                [
                    """
 Result is XYZ: 120.030166 127.667344 125.560879, D50 Lab: 109.839774 -4.542272 -13.098348
                           CCT = 5991K (Delta E 6.554213)
 Closest Planckian temperature = 5772K (Delta E 5.765044)
 Closest Daylight temperature  = 5899K (Delta E 2.368586)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",  # noqa: E501
                    """
 Result is XYZ: 66.590402 70.542611 69.377397, D50 Lab: 87.262309 -3.134252 -10.747149
                           CCT = 5951K (Delta E 5.807812)
 Closest Planckian temperature = 5758K (Delta E 5.100360)
 Closest Daylight temperature  = 5886K (Delta E 1.698719)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 27.489125 29.158690 28.738045, D50 Lab: 60.921426 -2.478038 -8.105322
                           CCT = 5976K (Delta E 6.028851)
 Closest Planckian temperature = 5773K (Delta E 5.298263)
 Closest Daylight temperature  = 5902K (Delta E 1.900430)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 6.326874 6.649709 6.776715, D50 Lab: 30.995780 -0.896754 -5.916062
                           CCT = 6071K (Delta E 4.005433)
 Closest Planckian temperature = 5926K (Delta E 3.517820)
 Closest Daylight temperature  = 6065K (Delta E 0.144142)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 0.104401 0.110705 0.109155, D50 Lab: 0.995780 -0.896754 -5.916062
                           CCT = 6071K (Delta E 4.005433)
 Closest Planckian temperature = 5926K (Delta E 3.517820)
 Closest Daylight temperature  = 6065K (Delta E 0.144142)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                ],
                [
                    """
 Result is XYZ: 121.643262 130.105649 128.560173, D50 Lab: 110.635861 -5.574898 -13.543244
                           CCT = 6071K (Delta E 7.533820)
 Closest Planckian temperature = 5815K (Delta E 6.643605)
 Closest Daylight temperature  = 5943K (Delta E 3.258868)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",  # noqa: E501
                    """
 Result is XYZ: 67.775736 72.266319 71.178047, D50 Lab: 88.096621 -4.123469 -10.928024
                           CCT = 6023K (Delta E 6.995424)
 Closest Planckian temperature = 5788K (Delta E 6.159783)
 Closest Daylight temperature  = 5915K (Delta E 2.767919)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 28.131948 29.978900 29.595129, D50 Lab: 61.636012 -3.012753 -8.258625
                           CCT = 6030K (Delta E 6.867980)
 Closest Planckian temperature = 5798K (Delta E 6.047536)
 Closest Daylight temperature  = 5926K (Delta E 2.657241)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 6.473470 6.765282 6.888164, D50 Lab: 31.266484 -0.517860 -5.923364
                           CCT = 6007K (Delta E 2.947859)
 Closest Planckian temperature = 5902K (Delta E 2.582843)
 Closest Daylight temperature  = 6042K (Delta E 0.798814)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 0.104401 0.110705 0.109155, D50 Lab: 0.266484 -0.517860 -5.923364
                           CCT = 6007K (Delta E 2.947859)
 Closest Planckian temperature = 5902K (Delta E 2.582843)
 Closest Daylight temperature  = 6042K (Delta E 0.798814)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                ],
                [
                    """
 Result is XYZ: 116.801943 124.624261 123.359911, D50 Lab: 108.831883 -5.063829 -13.483891
                           CCT = 6057K (Delta E 7.069302)
 Closest Planckian temperature = 5816K (Delta E 6.229078)
 Closest Daylight temperature  = 5944K (Delta E 2.843045)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",  # noqa: E501
                    """
 Result is XYZ: 64.869350 68.842421 67.977252, D50 Lab: 86.425958 -3.370123 -10.910497
                           CCT = 5991K (Delta E 6.099488)
 Closest Planckian temperature = 5785K (Delta E 5.362276)
 Closest Daylight temperature  = 5914K (Delta E 1.966958)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 26.750888 28.302175 27.882982, D50 Lab: 60.160759 -2.171950 -8.007010
                           CCT = 5948K (Delta E 5.551435)
 Closest Planckian temperature = 5762K (Delta E 4.873477)
 Closest Daylight temperature  = 5891K (Delta E 1.471926)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 6.255018 6.563924 6.746680, D50 Lab: 30.792814 -0.788285 -6.137368
                           CCT = 6105K (Delta E 3.641727)
 Closest Planckian temperature = 5970K (Delta E 3.198805)
 Closest Daylight temperature  = 6113K (Delta E 0.167052)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 0.104401 0.110705 0.109155, D50 Lab: 0.792814 -0.788285 -6.137368
                           CCT = 6105K (Delta E 3.641727)
 Closest Planckian temperature = 5970K (Delta E 3.198805)
 Closest Daylight temperature  = 6113K (Delta E 0.167052)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                ],
                [
                    """
 Result is XYZ: 115.081771 122.300809 119.963479, D50 Lab: 108.051237 -4.328489 -12.711256
                           CCT = 5969K (Delta E 6.425079)
 Closest Planckian temperature = 5755K (Delta E 5.648226)
 Closest Daylight temperature  = 5882K (Delta E 2.248055)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",  # noqa: E501
                    """
 Result is XYZ: 62.334621 66.118418 64.979303, D50 Lab: 85.056784 -3.250929 -10.473103
                           CCT = 5960K (Delta E 6.051574)
 Closest Planckian temperature = 5758K (Delta E 5.316783)
 Closest Daylight temperature  = 5886K (Delta E 1.916058)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 25.849804 27.374348 27.163845, D50 Lab: 59.319238 -2.248166 -8.249728
                           CCT = 5996K (Delta E 5.653680)
 Closest Planckian temperature = 5804K (Delta E 4.968356)
 Closest Daylight temperature  = 5934K (Delta E 1.575347)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 5.898029 6.233309 6.427531, D50 Lab: 29.993614 -1.240610 -6.124217
                           CCT = 6197K (Delta E 4.937751)
 Closest Planckian temperature = 6011K (Delta E 4.350182)
 Closest Daylight temperature  = 6153K (Delta E 0.996499)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 0.104401 0.110705 0.109155, D50 Lab: 0.993614 -1.240610 -6.124217
                           CCT = 6197K (Delta E 4.937751)
 Closest Planckian temperature = 6011K (Delta E 4.350182)
 Closest Daylight temperature  = 6153K (Delta E 0.996499)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                ],
                [
                    """
 Result is XYZ: 114.661874 122.077962 119.963424, D50 Lab: 107.975846 -4.649371 -12.841206
                           CCT = 5996K (Delta E 6.745175)
 Closest Planckian temperature = 5771K (Delta E 5.934859)
 Closest Daylight temperature  = 5898K (Delta E 2.538832)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",  # noqa: E501
                    """
 Result is XYZ: 61.818899 65.859246 64.979340, D50 Lab: 84.924570 -3.876653 -10.701093
                           CCT = 6024K (Delta E 6.822442)
 Closest Planckian temperature = 5794K (Delta E 6.006530)
 Closest Daylight temperature  = 5922K (Delta E 2.615316)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 25.795743 27.295989 27.081138, D50 Lab: 59.247303 -2.163010 -8.233441
                           CCT = 5988K (Delta E 5.511791)
 Closest Planckian temperature = 5800K (Delta E 4.842103)
 Closest Daylight temperature  = 5931K (Delta E 1.447924)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 5.925222 6.263326 6.427544, D50 Lab: 30.067324 -1.256015 -5.997186
                           CCT = 6170K (Delta E 5.014894)
 Closest Planckian temperature = 5984K (Delta E 4.416741)
 Closest Daylight temperature  = 6124K (Delta E 1.057856)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 0.104401 0.110705 0.109155, D50 Lab: 0.067324 -1.256015 -5.997186
                           CCT = 6170K (Delta E 5.014894)
 Closest Planckian temperature = 5984K (Delta E 4.416741)
 Closest Daylight temperature  = 6124K (Delta E 1.057856)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                ],
                [
                    """
 Result is XYZ: 116.839314 123.894968 122.159446, D50 Lab: 108.587904 -3.955352 -13.160232
                           CCT = 5975K (Delta E 5.963774)
 Closest Planckian temperature = 5774K (Delta E 5.240593)
 Closest Daylight temperature  = 5903K (Delta E 1.842768)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",  # noqa: E501
                    """
 Result is XYZ: 63.469751 67.164836 66.177725, D50 Lab: 85.587118 -2.928291 -10.687360
                           CCT = 5951K (Delta E 5.590334)
 Closest Planckian temperature = 5764K (Delta E 4.908104)
 Closest Daylight temperature  = 5892K (Delta E 1.506948)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 26.106117 27.645671 27.403890, D50 Lab: 59.567264 -2.255152 -8.227727
                           CCT = 5991K (Delta E 5.663331)
 Closest Planckian temperature = 5798K (Delta E 4.976351)
 Closest Daylight temperature  = 5928K (Delta E 1.582241)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 6.001154 6.326623 6.508185, D50 Lab: 30.221991 -1.083417 -6.086282
                           CCT = 6157K (Delta E 4.496558)
 Closest Planckian temperature = 5990K (Delta E 3.957006)
 Closest Daylight temperature  = 6131K (Delta E 0.597640)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
                    """
 Result is XYZ: 0.104401 0.110705 0.109155, D50 Lab: 0.221991 -1.083417 -6.086282
                           CCT = 6157K (Delta E 4.496558)
 Closest Planckian temperature = 5990K (Delta E 3.957006)
 Closest Daylight temperature  = 6131K (Delta E 0.597640)

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
            ],
        ][app.TopWindow.index][i]
        if i < 3:
            i += 1
        else:
            i -= 3
    elif bytes_ in ("Q", "q"):
        wx.CallAfter(app.TopWindow.Close)
        return
    else:
        return
    for line in txt.split("\n"):
        sleep(0.03125)
        wx.CallAfter(app.TopWindow.write, line)
        print(line)

    start_new_thread(test, ())
    app.MainLoop()