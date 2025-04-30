# -*- coding: utf-8 --*-
from __future__ import annotations
import sys
from typing import List, TypedDict, Dict, Tuple

import pytest
from _pytest.fixtures import SubRequest

from DisplayCAL.cgats import CGATS, stable_sort_by_L
from DisplayCAL.config import get_current_profile
from DisplayCAL.dev.mocks import check_call
from DisplayCAL.util_io import LineBufferedStream, Files
from DisplayCAL.worker import FilteredStream


def test_cgats_with_sample_data_1(data_files):
    """Test CGATS class with some sample data"""
    cgats = CGATS(cgats=data_files["cgats0.txt"].absolute())

    assert cgats[0]["DESCRIPTOR"] == b"Output Characterisation"
    assert (
        cgats[0]["ORIGINATOR"] == b"Barbieri Gateway MAC 4.5.0, Speclib Version: 4.59"
    )
    assert (
        cgats[0]["INSTRUMENTATION"]
        == b"Spectropad  ver:6.26-6.10 R DOC,SN=B5101140,MN=B11J0026,1"
    )
    assert (
        cgats[0]["BARBIERI_INFO_0"]
        == b"Mode=Reflection,Measurement Condition=M1,Aperture=6,IntegrationTime=7"
    )
    assert (
        cgats[0]["BARBIERI_INFO_1"]
        == b"<Type>eChartJob</Type>, <ReferenceCheck>1</ReferenceCheck>, <JobName>IT8_"
        b"7-4-M1</JobName>, Spectro_xy_version=1, Spectro_xy_version=1,File_Format="
        b"BARBIERI - Horizontal (default),Patches_X=24,"
    )
    assert (
        cgats[0]["BARBIERI_INFO_2"]
        == b"Patches_Y=17,Number_of_Patches=1617,Number_of_Pages=4,Target_Size_X=277,T"
        b"arget_Size_Y=206,MR,Illuminant=D50,Observer=10,Density=Status T,Save_Spec"
        b"tral=1,Save_Lab=1,Save_XYZ=1,Save_Density=1,"
    )
    assert (
        cgats[0]["BARBIERI_INFO_3"]
        == b"Save_CxF=255,Fast_Measuring_Mode=1,Use_AutoPositioning=1,Use_AutoRecognit"
        b"ion=0,Run_Profiler=0,Reference_File_Name=References/IT8_7-4 CMYK visual.r"
        b"ef,Quality_Control=0,Control_Reference_File=,"
    )
    assert (
        cgats[0]["BARBIERI_INFO_4"]
        == b"Control_Settings_File=,Profile_File_Name=,Target_Image_Preview=Previews/I"
        b"T8_7-4 CMYK visual.bmp,Spot_Measurement_Mode=0,Spot_Measurement=0,Display"
        b"_Values=0,Number_of_Measurements_per_Patch_y=1,"
    )
    assert (
        cgats[0]["BARBIERI_INFO_5"]
        == b"Distance_of_Measurements_per_Patch_y=10,Number_of_Measurements_per_Patch_"
        b"x=1,Distance_of_Measurements_per_Patch_x=10,Average_Method=1,Target_Heade"
        b"r_Size=20,AutoPositioning_Mode=0,"
    )
    assert (
        cgats[0]["BARBIERI_INFO_6"]
        == b"Continuous_Measurement_Mode=0,Save_Continuous_Measurement=0,Continuous_Me"
        b"asurement_Delay=0,CF_Option=1,Calibration_Frequency=0,Measuring_Aperture="
        b"6,Slope_Factor=1.000,Job_protection=-1,"
    )
    assert (
        cgats[0]["BARBIERI_INFO_7"]
        == b"Measurement_Condition=M1,Translucency_Mode=0,Translucency_IntTime=1000,Sa"
        b"ve_Debug=0,"
    )
    assert (
        cgats[0]["MEASUREMENT_SOURCE"]
        == b"Illumination=D50	ObserverAngle=10degree	WhiteBase=Abs	Filter=No"
    )
    assert cgats[0]["ILLUMINANT"] == b"D50"
    assert cgats[0]["OBSERVER"] == b"10"
    assert (
        cgats[0]["PRINT_CONDITIONS"]
        == b"No printer defined, No resolution defined, No ink defined, No paper defi"
        b"ned, No screening defined"
    )
    assert cgats[0]["NUMBER_OF_FIELDS"] == 52
    assert isinstance(cgats[0]["DATA_FORMAT"], CGATS)

    keys = [
        "CMYK_C",
        "CMYK_M",
        "CMYK_Y",
        "CMYK_K",
        "XYZ_X",
        "XYZ_Y",
        "XYZ_Z",
        "LAB_L",
        "LAB_A",
        "LAB_B",
        "SPECTRAL_380",
        "SPECTRAL_390",
        "SPECTRAL_400",
        "SPECTRAL_410",
        "SPECTRAL_420",
        "SPECTRAL_430",
        "SPECTRAL_440",
        "SPECTRAL_450",
        "SPECTRAL_460",
        "SPECTRAL_470",
        "SPECTRAL_480",
        "SPECTRAL_490",
        "SPECTRAL_500",
        "SPECTRAL_510",
        "SPECTRAL_520",
        "SPECTRAL_530",
        "SPECTRAL_540",
        "SPECTRAL_550",
        "SPECTRAL_560",
        "SPECTRAL_570",
        "SPECTRAL_580",
        "SPECTRAL_590",
        "SPECTRAL_600",
        "SPECTRAL_610",
        "SPECTRAL_620",
        "SPECTRAL_630",
        "SPECTRAL_640",
        "SPECTRAL_650",
        "SPECTRAL_660",
        "SPECTRAL_670",
        "SPECTRAL_680",
        "SPECTRAL_690",
        "SPECTRAL_700",
        "SPECTRAL_710",
        "SPECTRAL_720",
        "SPECTRAL_730",
        "SPECTRAL_740",
        "SPECTRAL_750",
        "SPECTRAL_760",
        "SPECTRAL_770",
        "SPECTRAL_780",
    ]

    # TO GENERATE DATA
    # for i in range(cgats[0]['NUMBER_OF_SETS']):
    #     values = ", ".join([str(x) for x in cgats[0]['DATA'][i].values()])
    #     print(f"        {i}: [{values}],")

    values = {
        0: [1, 0.0, 100.0, 20.0, 0.0, 36.266, 25.588, 21.129, 57.644, 43.118, -0.587, 0.22703, 0.158521, 0.198916, 0.233576, 0.273344, 0.281545, 0.275103, 0.268394, 0.2608, 0.25577, 0.240171, 0.224809, 0.213421, 0.19068, 0.164624, 0.13483, 0.12763, 0.129758, 0.126645, 0.130081, 0.177509, 0.272117, 0.429915, 0.576974, 0.683854, 0.746946, 0.776108, 0.794132, 0.808238, 0.815922, 0.816633, 0.81732, 0.824127, 0.824325, 0.824718, 0.83017, 0.831191, 0.83384, 0.83384, 0.83384, 0.83384,],
        1: [2, 0.0, 85.0, 20.0, 0.0, 38.662, 28.299, 23.364, 60.157, 40.057, -0.601, 0.274704, 0.168645, 0.211179, 0.250617, 0.295082, 0.305504, 0.300246, 0.295093, 0.289493, 0.286288, 0.273133, 0.258376, 0.247178, 0.223566, 0.194819, 0.161104, 0.15285, 0.155392, 0.15176, 0.155079, 0.207079, 0.306173, 0.463505, 0.604229, 0.70203, 0.758555, 0.784057, 0.800388, 0.813682, 0.820672, 0.82168, 0.823508, 0.831216, 0.828949, 0.829395, 0.835401, 0.838929, 0.841753, 0.841753, 0.841753, 0.841753,],
        2: [3, 0.0, 70.0, 20.0, 0.0, 41.428, 31.681, 25.498, 63.078, 36.05, 0.536, 0.23112, 0.172207, 0.221313, 0.264632, 0.311902, 0.325723, 0.321866, 0.318828, 0.317081, 0.317275, 0.308422, 0.29693, 0.287657, 0.264574, 0.234287, 0.197652, 0.18771, 0.190387, 0.185953, 0.18918, 0.245586, 0.347588, 0.502066, 0.633031, 0.719415, 0.768109, 0.789507, 0.803672, 0.81579, 0.82215, 0.821852, 0.822152, 0.829452, 0.828198, 0.828533, 0.834266, 0.835057, 0.842139, 0.842139, 0.842139, 0.842139,],
        3: [4, 0.0, 55.0, 20.0, 0.0, 45.513, 36.729, 28.22, 67.074, 30.828, 2.754, 0.218564, 0.182374, 0.235281, 0.284068, 0.336732, 0.353667, 0.350615, 0.348262, 0.34972, 0.353871, 0.352098, 0.348736, 0.344867, 0.325774, 0.294521, 0.253248, 0.241124, 0.244228, 0.238822, 0.241937, 0.305103, 0.41057, 0.55931, 0.673954, 0.743283, 0.78138, 0.797305, 0.808648, 0.819299, 0.824913, 0.824598, 0.824403, 0.831217, 0.829997, 0.830138, 0.83639, 0.839101, 0.842862, 0.842862, 0.842862, 0.842862,],
        4: [5, 0.0, 40.0, 20.0, 0.0, 51.41, 44.315, 32.297, 72.439, 23.822, 5.54, 0.179846, 0.193834, 0.252103, 0.307782, 0.366728, 0.388613, 0.389364, 0.393721, 0.402893, 0.413308, 0.421461, 0.427721, 0.430264, 0.415827, 0.384044, 0.339534, 0.325223, 0.329108, 0.322862, 0.325749, 0.395277, 0.502877, 0.636999, 0.72377, 0.769836, 0.795023, 0.804875, 0.813572, 0.822762, 0.827487, 0.827436, 0.82682, 0.834021, 0.832718, 0.831247, 0.836521, 0.838606, 0.844015, 0.844015, 0.844015, 0.844015,],
        5: [6, 0.0, 30.0, 20.0, 0.0, 55.008, 49.174, 34.85, 75.559, 19.608, 7.148, 0.37016, 0.1983, 0.263395, 0.324705, 0.38756, 0.409243, 0.41288, 0.422213, 0.436569, 0.450381, 0.464107, 0.476682, 0.484204, 0.474681, 0.443393, 0.397553, 0.381964, 0.386302, 0.379386, 0.381907, 0.4544, 0.559581, 0.679708, 0.747761, 0.781105, 0.799988, 0.806783, 0.813788, 0.822796, 0.827119, 0.826215, 0.825702, 0.832313, 0.830966, 0.829475, 0.834936, 0.83735, 0.841089, 0.841089, 0.841089, 0.841089,],
        6: [7, 0.0, 20.0, 20.0, 0.0, 59.581, 55.607, 37.455, 79.39, 14.273, 10.086, 0.14007, 0.203257, 0.271542, 0.337358, 0.405274, 0.434317, 0.438829, 0.448776, 0.466504, 0.485766, 0.510213, 0.534794, 0.550742, 0.549314, 0.521919, 0.478624, 0.462862, 0.467584, 0.461588, 0.463786, 0.532937, 0.627132, 0.724591, 0.773093, 0.794568, 0.807647, 0.811793, 0.817288, 0.825166, 0.829055, 0.827766, 0.826826, 0.830837, 0.830135, 0.829046, 0.831644, 0.83029, 0.831417, 0.831417, 0.831417, 0.831417,],
        7: [8, 0.0, 10.0, 20.0, 0.0, 65.621, 64.674, 40.962, 84.316, 6.956, 13.904, 0.140803, 0.212377, 0.285737, 0.359451, 0.433695, 0.46689, 0.472929, 0.485189, 0.508602, 0.533595, 0.568508, 0.606079, 0.633761, 0.648128, 0.632218, 0.603189, 0.589922, 0.594206, 0.591529, 0.590701, 0.641412, 0.7052, 0.765422, 0.792178, 0.803407, 0.811992, 0.814125, 0.81891, 0.82649, 0.829661, 0.82829, 0.827179, 0.831384, 0.82984, 0.82956, 0.834308, 0.836347, 0.838753, 0.838753, 0.838753, 0.838753,],
        8: [9, 0.0, 0.0, 20.0, 0.0, 74.173, 77.878, 45.546, 90.724, -2.356, 19.228, 0.212895, 0.226007, 0.307983, 0.391678, 0.473875, 0.510948, 0.519092, 0.535516, 0.563649, 0.592841, 0.637903, 0.691631, 0.734935, 0.778418, 0.788965, 0.794365, 0.789319, 0.793541, 0.79698, 0.789356, 0.795117, 0.802413, 0.809776, 0.810017, 0.810176, 0.814511, 0.814652, 0.81876, 0.825596, 0.829271, 0.827477, 0.826685, 0.830895, 0.829069, 0.827596, 0.830788, 0.829694, 0.832583, 0.832583, 0.832583, 0.832583,],
        9: [10, 0.0, 100.0, 10.0, 0.0, 37.003, 26.118, 24.382, 58.149, 43.369, -5.953, 0.349415, 0.18234, 0.23642, 0.283576, 0.333148, 0.340254, 0.329331, 0.314389, 0.296822, 0.28406, 0.258049, 0.23534, 0.220215, 0.195589, 0.169089, 0.139374, 0.132424, 0.134512, 0.131322, 0.134707, 0.181502, 0.274578, 0.430365, 0.576222, 0.682475, 0.7454, 0.77477, 0.792532, 0.806671, 0.81492, 0.815652, 0.81674, 0.824637, 0.824021, 0.824834, 0.831626, 0.836586, 0.843208, 0.843208, 0.843208, 0.843208,],
    }

    for i in values:
        for j, k in enumerate(keys):
            assert cgats[0]["DATA"][i][k] == values[i][j + 1]


def test_cgats_with_sample_data_1A(data_files):
    """Test CGATS class with some sample data"""
    cgats = CGATS(cgats=data_files["cgats0.txt"].absolute())

    assert cgats[0]["DESCRIPTOR"] == b"Output Characterisation"
    assert (
        cgats[0]["ORIGINATOR"] == b"Barbieri Gateway MAC 4.5.0, Speclib Version: 4.59"
    )
    assert (
        cgats[0]["INSTRUMENTATION"]
        == b"Spectropad  ver:6.26-6.10 R DOC,SN=B5101140,MN=B11J0026,1"
    )
    assert (
        cgats[0]["BARBIERI_INFO_0"]
        == b"Mode=Reflection,Measurement Condition=M1,Aperture=6,IntegrationTime=7"
    )
    assert (
        cgats[0]["BARBIERI_INFO_1"]
        == b"<Type>eChartJob</Type>, <ReferenceCheck>1</ReferenceCheck>, <JobName>IT8_"
        b"7-4-M1</JobName>, Spectro_xy_version=1, Spectro_xy_version=1,File_Format="
        b"BARBIERI - Horizontal (default),Patches_X=24,"
    )
    assert (
        cgats[0]["BARBIERI_INFO_2"]
        == b"Patches_Y=17,Number_of_Patches=1617,Number_of_Pages=4,Target_Size_X=277,T"
        b"arget_Size_Y=206,MR,Illuminant=D50,Observer=10,Density=Status T,Save_Spec"
        b"tral=1,Save_Lab=1,Save_XYZ=1,Save_Density=1,"
    )
    assert (
        cgats[0]["BARBIERI_INFO_3"]
        == b"Save_CxF=255,Fast_Measuring_Mode=1,Use_AutoPositioning=1,Use_AutoRecognit"
        b"ion=0,Run_Profiler=0,Reference_File_Name=References/IT8_7-4 CMYK visual.r"
        b"ef,Quality_Control=0,Control_Reference_File=,"
    )
    assert (
        cgats[0]["BARBIERI_INFO_4"]
        == b"Control_Settings_File=,Profile_File_Name=,Target_Image_Preview=Previews/I"
        b"T8_7-4 CMYK visual.bmp,Spot_Measurement_Mode=0,Spot_Measurement=0,Display"
        b"_Values=0,Number_of_Measurements_per_Patch_y=1,"
    )
    assert (
        cgats[0]["BARBIERI_INFO_5"]
        == b"Distance_of_Measurements_per_Patch_y=10,Number_of_Measurements_per_Patch_"
        b"x=1,Distance_of_Measurements_per_Patch_x=10,Average_Method=1,Target_Heade"
        b"r_Size=20,AutoPositioning_Mode=0,"
    )
    assert (
        cgats[0]["BARBIERI_INFO_6"]
        == b"Continuous_Measurement_Mode=0,Save_Continuous_Measurement=0,Continuous_Me"
        b"asurement_Delay=0,CF_Option=1,Calibration_Frequency=0,Measuring_Aperture="
        b"6,Slope_Factor=1.000,Job_protection=-1,"
    )
    assert (
        cgats[0]["BARBIERI_INFO_7"]
        == b"Measurement_Condition=M1,Translucency_Mode=0,Translucency_IntTime=1000,Sa"
        b"ve_Debug=0,"
    )
    assert (
        cgats[0]["MEASUREMENT_SOURCE"]
        == b"Illumination=D50	ObserverAngle=10degree	WhiteBase=Abs	Filter=No"
    )
    assert cgats[0]["ILLUMINANT"] == b"D50"
    assert cgats[0]["OBSERVER"] == b"10"
    assert (
        cgats[0]["PRINT_CONDITIONS"]
        == b"No printer defined, No resolution defined, No ink defined, No paper defi"
        b"ned, No screening defined"
    )
    assert cgats[0]["NUMBER_OF_FIELDS"] == 52
    assert isinstance(cgats[0]["DATA_FORMAT"], CGATS)

    keys = ["CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K", "XYZ_X", "XYZ_Y", "XYZ_Z", "LAB_L", "LAB_A", "LAB_B", "SPECTRAL_380", "SPECTRAL_390", "SPECTRAL_400", "SPECTRAL_410", "SPECTRAL_420", "SPECTRAL_430", "SPECTRAL_440", "SPECTRAL_450", "SPECTRAL_460", "SPECTRAL_470", "SPECTRAL_480", "SPECTRAL_490", "SPECTRAL_500", "SPECTRAL_510", "SPECTRAL_520", "SPECTRAL_530", "SPECTRAL_540", "SPECTRAL_550", "SPECTRAL_560", "SPECTRAL_570", "SPECTRAL_580", "SPECTRAL_590", "SPECTRAL_600", "SPECTRAL_610", "SPECTRAL_620", "SPECTRAL_630", "SPECTRAL_640", "SPECTRAL_650", "SPECTRAL_660", "SPECTRAL_670", "SPECTRAL_680", "SPECTRAL_690", "SPECTRAL_700", "SPECTRAL_710", "SPECTRAL_720", "SPECTRAL_730", "SPECTRAL_740", "SPECTRAL_750", "SPECTRAL_760", "SPECTRAL_770", "SPECTRAL_780",]

    # TO GENERATE DATA
    # for i in range(cgats[0]['NUMBER_OF_SETS']):
    #     values = ", ".join([str(x) for x in cgats[0]['DATA'][i].values()])
    #     print(f"        {i}: [{values}],")

    values = {
        0: [ 1, 0.0, 100.0, 20.0, 0.0, 36.266, 25.588, 21.129, 57.644, 43.118, -0.587, 0.22703, 0.158521, 0.198916, 0.233576, 0.273344, 0.281545, 0.275103, 0.268394, 0.2608, 0.25577, 0.240171, 0.224809, 0.213421, 0.19068, 0.164624, 0.13483, 0.12763, 0.129758, 0.126645, 0.130081, 0.177509, 0.272117, 0.429915, 0.576974, 0.683854, 0.746946, 0.776108, 0.794132, 0.808238, 0.815922, 0.816633, 0.81732, 0.824127, 0.824325, 0.824718, 0.83017, 0.831191, 0.83384, 0.83384, 0.83384, 0.83384,],
        1: [ 2, 0.0, 85.0, 20.0, 0.0, 38.662, 28.299, 23.364, 60.157, 40.057, -0.601, 0.274704, 0.168645, 0.211179, 0.250617, 0.295082, 0.305504, 0.300246, 0.295093, 0.289493, 0.286288, 0.273133, 0.258376, 0.247178, 0.223566, 0.194819, 0.161104, 0.15285, 0.155392, 0.15176, 0.155079, 0.207079, 0.306173, 0.463505, 0.604229, 0.70203, 0.758555, 0.784057, 0.800388, 0.813682, 0.820672, 0.82168, 0.823508, 0.831216, 0.828949, 0.829395, 0.835401, 0.838929, 0.841753, 0.841753, 0.841753, 0.841753,],
    }

    for i in values:
        for j, k in enumerate(keys):
            assert cgats[0]["DATA"][i][k] == values[i][j + 1]


def test_cgats_with_sample_data_2(data_files):
    """Test ``DisplayCAL.cgats.CGATS`` class with some sample data"""
    cgats = CGATS(cgats=data_files["ccxx.ti1"].absolute())

    assert (
        cgats[0]["DESCRIPTOR"]
        == b"Argyll Calibration Target chart information 1 for creating .ti3 for ccxxmake"
    )
    assert cgats[0]["ORIGINATOR"] == b"Argyll targen"
    assert cgats[0]["KEYWORDS"] == {0: b"APPROX_WHITE_POINT", 1: b"COLOR_REP"}
    assert cgats[0]["APPROX_WHITE_POINT"] == b"95.045781 100.000003 108.905751"
    assert cgats[0]["COLOR_REP"] == b"RGB"
    assert cgats[0]["NUMBER_OF_FIELDS"] == 7
    assert cgats[0]["NUMBER_OF_SETS"] == 4

    assert isinstance(cgats[0]["DATA_FORMAT"], CGATS)
    assert isinstance(cgats[0]["DATA"], CGATS)

    keys = ["SAMPLE_ID", "RGB_R", "RGB_G", "RGB_B", "XYZ_X", "XYZ_Y", "XYZ_Z"]

    # TO GENERATE DATA
    # for i in range(cgats[0]['NUMBER_OF_SETS']):
    #     values = ", ".join([str(x) for x in cgats[0]['DATA'][i].values()])
    #     print(f"        {i}: [{values}],")

    values = {
        0: [1, 100.00, 100.00, 100.00, 95.046, 100.00, 108.91],
        1: [2, 100.00, 0.0000, 0.0000, 41.238, 21.260, 1.9306],
        2: [3, 0.0000, 100.00, 0.0000, 35.757, 71.520, 11.921],
        3: [4, 0.0000, 0.0000, 100.00, 18.050, 7.2205, 95.055],
    }

    for i in values:
        for j, k in enumerate(keys):
            assert cgats[0]["DATA"][i][k] == values[i][j]


def test_cgats_with_sample_targ_data(data_files):
    """Test ``DisplayCAL.cgats.CGATS`` class with data coming from the ``Text`` class"""
    from DisplayCAL.icc_profile import Text

    with open(data_files["ccxx.ti1"].absolute(), "rb") as f:
        targ_data = f.read()
    targ_tag = Text(targ_data)
    targ_tag.tagSignature = "targ"
    targ_tag.tagData = targ_data
    cgats = CGATS(cgats=targ_tag)

    assert isinstance(cgats, CGATS)
    assert (
        cgats[0]["DESCRIPTOR"]
        == b"Argyll Calibration Target chart information 1 for creating .ti3 for ccxxmake"
    )
    assert cgats[0]["ORIGINATOR"] == b"Argyll targen"
    assert cgats[0]["KEYWORDS"] == {0: b"APPROX_WHITE_POINT", 1: b"COLOR_REP"}
    assert cgats[0]["APPROX_WHITE_POINT"] == b"95.045781 100.000003 108.905751"
    assert cgats[0]["COLOR_REP"] == b"RGB"
    assert cgats[0]["NUMBER_OF_FIELDS"] == 7
    assert cgats[0]["NUMBER_OF_SETS"] == 4

    assert isinstance(cgats[0]["DATA_FORMAT"], CGATS)
    assert isinstance(cgats[0]["DATA"], CGATS)

    keys = ["SAMPLE_ID", "RGB_R", "RGB_G", "RGB_B", "XYZ_X", "XYZ_Y", "XYZ_Z"]

    # TO GENERATE DATA
    # for i in range(cgats[0]['NUMBER_OF_SETS']):
    #     values = ", ".join([str(x) for x in cgats[0]['DATA'][i].values()])
    #     print(f"        {i}: [{values}],")

    values = {
        0: [1, 100.00, 100.00, 100.00, 95.046, 100.00, 108.91],
        1: [2, 100.00, 0.0000, 0.0000, 41.238, 21.260, 1.9306],
        2: [3, 0.0000, 100.00, 0.0000, 35.757, 71.520, 11.921],
        3: [4, 0.0000, 0.0000, 100.00, 18.050, 7.2205, 95.055],
    }

    for i in values:
        for j, k in enumerate(keys):
            assert cgats[0]["DATA"][i][k] == values[i][j]


def test_cgats_with_sample_ti3_data(data_files):
    """Test ``DisplayCAL.cgats.CGATS`` class with data coming from the ti3 file"""
    cgats = CGATS(cgats=data_files["0_16.ti3"].absolute())

    assert isinstance(cgats, CGATS)
    assert cgats[0]["DESCRIPTOR"] == b"Argyll Calibration Target chart information 3"
    assert cgats[0]["ORIGINATOR"] == b"Argyll dispread"
    assert cgats[0]["DEVICE_CLASS"] == b"DISPLAY"
    assert cgats[0]["COLOR_REP"] == b"RGB_XYZ"
    assert cgats[0]["TARGET_INSTRUMENT"] == b"X-Rite i1 DisplayPro, ColorMunki Display"
    assert cgats[0]["DISPLAY_TYPE_REFRESH"] == b"NO"
    assert cgats[0]["DISPLAY_TYPE_BASE_ID"] == 1
    assert cgats[0]["INSTRUMENT_TYPE_SPECTRAL"] == b"NO"
    assert cgats[0]["LUMINANCE_XYZ_CDM2"] == b"115.999513 125.380126 138.006230"
    assert cgats[0]["NORMALIZED_TO_Y_100"] == b"YES"
    assert cgats[0]["VIDEO_LUT_CALIBRATION_POSSIBLE"] == b"YES"
    assert cgats[0]["NUMBER_OF_FIELDS"] == 7
    assert isinstance(cgats[0]["DATA_FORMAT"], CGATS)
    assert isinstance(cgats[0]["DATA"], CGATS)

    keys = ["SAMPLE_ID", "RGB_R", "RGB_G", "RGB_B", "XYZ_X", "XYZ_Y", "XYZ_Z"]

    # TO GENERATE DATA
    # for i in range(cgats[0]['NUMBER_OF_SETS']):
    #     values = ", ".join([str(x) for x in cgats[0]['DATA'][i].values()])
    #     print(f"        {i}: [{values}],")

    values = {
        0: [1, 100.00, 100.00, 100.00, 92.51826, 100.00, 110.0703],
        1: [2, 0.0000, 0.0000, 0.0000, 0.119951, 0.129559, 0.239291],
        2: [3, 6.25, 6.25, 6.25, 0.321875, 0.348479, 0.479568],
    }

    for i in values:
        for j, k in enumerate(keys):
            assert cgats[0]["DATA"][i][k] == values[i][j]


def test_cgats_from_ti3_back_to_bytes(data_files):
    """Test ``DisplayCAL.cgats.CGATS`` class with data coming from the ti3 file and
    then converted back to bytes
    """
    path = data_files["0_16_proper.ti3"].absolute()
    with open(path, "rb") as f:
        raw_data = f.read()

    # fix the line endings for Windows
    if sys.platform == "win32":
        raw_data = raw_data.replace(b"\r\n", b"\n")
    cgats = CGATS(cgats=path)
    assert bytes(cgats) == raw_data


def test_cgats_get_colorants_method(data_files):
    """Test ``DisplayCAL.cgats.CGATS`` get_colorants() method."""
    path = data_files["default.ti3"].absolute()
    cgats = CGATS(cgats=path)
    result = cgats.get_colorants()
    expected_result = [
        {"RGB_B": 0.0, "RGB_G": 0.0, "RGB_R": 100.0, "SAMPLE_ID": 9, "XYZ_X": 41.83, "XYZ_Y": 22.052, "XYZ_Z": 2.9132,},
        {"RGB_B": 0.0, "RGB_G": 100.0, "RGB_R": 0.0, "SAMPLE_ID": 100, "XYZ_X": 36.405, "XYZ_Y": 71.801, "XYZ_Z": 12.802,},
        {"RGB_B": 100.0, "RGB_G": 0.0, "RGB_R": 0.0, "SAMPLE_ID": 156, "XYZ_X": 18.871, "XYZ_Y": 8.1473, "XYZ_Z": 95.129,},
    ]
    assert result == expected_result


def test_cgats_get_descriptor_method(data_files):
    """Test ``DisplayCAL.cgats.CGATS`` get_descriptor() method."""
    path = data_files["default.ti3"].absolute()
    cgats = CGATS(cgats=path)
    result = cgats.get_descriptor()
    expected_result = b"Argyll Calibration Target chart information 3"
    assert result == expected_result


def test_cgats_get_method(data_files):
    """Test ``DisplayCAL.cgats.CGATS`` get() method."""
    path = data_files["default.ti3"].absolute()
    cgats = CGATS(cgats=path)
    result = cgats.get(0)["DESCRIPTOR"]
    expected_result = b"Argyll Calibration Target chart information 3"
    assert result == expected_result


def test_cgats_getitem_method_1(data_files):
    """Test ``DisplayCAL.cgats.CGATS`` get() method."""
    path = data_files["default.ti3"].absolute()
    cgats = CGATS(cgats=path)
    result = cgats[0]["DESCRIPTOR"]
    expected_result = b"Argyll Calibration Target chart information 3"
    assert result == expected_result


def test_cgats_getitem_method_2(data_files):
    """Test ``DisplayCAL.cgats.CGATS`` get() method."""
    path = data_files["default.ti3"].absolute()
    cgats = CGATS(cgats=path)
    result = cgats[-1]["DESCRIPTOR"]
    expected_result = b"Argyll Device Calibration State"
    assert result == expected_result


def test_cgats_fix_zero_measurements_1(data_files):
    """Test DisplayCAL.cgats.CGATS.fix_zero_measurements() method."""
    path = data_files["0_16.ti1"].absolute()
    cgats = CGATS(cgats=path)
    cgats.fix_zero_measurements()


def test_cgats_fix_zero_measurements_2(data_files):
    """Test DisplayCAL.cgats.CGATS.fix_zero_measurements() method."""
    path = data_files["0_16.ti3"].absolute()
    cgats = CGATS(cgats=path)
    cgats.fix_zero_measurements()


def test_cgats_fix_zero_measurements_3(data_files):
    """Test DisplayCAL.cgats.CGATS.fix_zero_measurements() method."""
    path = data_files["Monitor.cal"].absolute()
    cgats = CGATS(cgats=path)
    cgats.fix_zero_measurements()


def test_cgats_fix_zero_measurements_4(data_files):
    """Test DisplayCAL.cgats.CGATS.fix_zero_measurements() method."""
    path = data_files["Monitor.ti1"].absolute()
    cgats = CGATS(cgats=path)
    cgats.fix_zero_measurements()


def test_cgats_fix_zero_measurements_5(data_files):
    """Test DisplayCAL.cgats.CGATS.fix_zero_measurements() method."""
    path = data_files["Monitor.ti3"].absolute()
    cgats = CGATS(cgats=path)
    cgats.fix_zero_measurements()


def test_cgats_fix_zero_measurements_6(data_files):
    """Test DisplayCAL.cgats.CGATS.fix_zero_measurements() method."""
    path = data_files["Monitor_ZeroValues.ti3"].absolute()
    cgats = CGATS(cgats=path)
    cgats.fix_zero_measurements()


def test_cgats_fix_zero_measurements_7(data_files):
    """Test DisplayCAL.cgats.CGATS.fix_zero_measurements() method."""
    path = data_files["Monitor_AllBlack.ti3"].absolute()
    cgats = CGATS(cgats=path)
    cgats.fix_zero_measurements()


def test_cgats_fix_zero_measurements_8(data_files):
    """Test DisplayCAL.cgats.CGATS.fix_zero_measurements() method. For #68."""
    from DisplayCAL.worker import Worker

    worker = Worker()
    worker.get_logfiles(False)

    path = data_files["Monitor_AllBlack.ti3"].absolute()
    cgats = CGATS(cgats=path)
    cgats.fix_zero_measurements(logfile=worker.get_logfiles(False))


def test_export_3d_1(data_files):
    """Test DisplayCAL.cgats.CGATS.export_3d() method."""
    import pathlib
    import tempfile

    export_path = pathlib.Path(tempfile.gettempdir()) / "ccxx_RGB.x3d.html"
    path = data_files["Monitor.ti1"].absolute()
    cgats = CGATS(cgats=path)
    cgats.export_3d(
        str(export_path.absolute()),
        colorspace="RGB",
        RGB_black_offset=40,
        normalize_RGB_white=False,
        compress=False,
        format="HTML",
    )


@pytest.mark.parametrize(
    "function,result",
    [
        (
            "sort_RGB_gray_to_top",
            [
                [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 50.0, 100.0, 100.0, 100.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [80.0, 80.0, 80.0, 100.0, 100.0, 100.0],
                [50.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                [50.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [25.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 100.0, 0.0, 0.0, 0.0],
            ],
        ),
        (
            "sort_RGB_white_to_top",
            [
                [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 50.0, 100.0, 100.0, 100.0],
                [50.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [50.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [80.0, 80.0, 80.0, 100.0, 100.0, 100.0],
                [25.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 100.0, 0.0, 0.0, 0.0],
            ],
        ),
        (
            "sort_by_HSI",
            [
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 50.0, 100.0, 100.0, 100.0],
                [80.0, 80.0, 80.0, 100.0, 100.0, 100.0],
                [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                [50.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [25.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [50.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                [50.0, 50.0, 100.0, 0.0, 0.0, 0.0],
            ],
        ),
        (
            "sort_by_HSL",
            [
                [50.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 50.0, 100.0, 100.0, 100.0],
                [80.0, 80.0, 80.0, 100.0, 100.0, 100.0],
                [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                [50.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [25.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [50.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                [50.0, 50.0, 100.0, 0.0, 0.0, 0.0],
            ],
        ),
        (
            "sort_by_HSV",
            [
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 50.0, 100.0, 100.0, 100.0],
                [80.0, 80.0, 80.0, 100.0, 100.0, 100.0],
                [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                [50.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [25.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [50.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                [50.0, 50.0, 100.0, 0.0, 0.0, 0.0],
            ],
        ),
        (
            "sort_by_L",
            [
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [50.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [25.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 100.0, 0.0, 0.0, 0.0],
                [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                [50.0, 50.0, 50.0, 100.0, 100.0, 100.0],
                [50.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                [80.0, 80.0, 80.0, 100.0, 100.0, 100.0],
            ],
        ),
        (
            "sort_by_RGB",
            [
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [25.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [50.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 50.0, 100.0, 100.0, 100.0],
                [50.0, 50.0, 100.0, 0.0, 0.0, 0.0],
                [50.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                [80.0, 80.0, 80.0, 100.0, 100.0, 100.0],
                [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            ],
        ),
        (
            "sort_by_BGR",
            [
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [50.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [25.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 50.0, 100.0, 100.0, 100.0],
                [80.0, 80.0, 80.0, 100.0, 100.0, 100.0],
                [50.0, 50.0, 100.0, 0.0, 0.0, 0.0],
                [50.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            ],
        ),
        (
            "sort_by_RGB_pow_sum",
            [
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [50.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [25.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 50.0, 100.0, 100.0, 100.0],
                [50.0, 50.0, 100.0, 0.0, 0.0, 0.0],
                [80.0, 80.0, 80.0, 100.0, 100.0, 100.0],
                [50.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            ],
        ),
        (
            "sort_by_RGB_sum",
            [
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [50.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [25.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 50.0, 100.0, 100.0, 100.0],
                [50.0, 50.0, 100.0, 0.0, 0.0, 0.0],
                [80.0, 80.0, 80.0, 100.0, 100.0, 100.0],
                [50.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            ],
        ),
        (
            "sort_by_rec709_luma",
            [
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [50.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [25.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 50.0, 100.0, 100.0, 100.0],
                [50.0, 50.0, 100.0, 0.0, 0.0, 0.0],
                [80.0, 80.0, 80.0, 100.0, 100.0, 100.0],
                [50.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            ],
        ),
    ],
)
def test_cgats_sorting_1(data_files, function: str, result: List[List[float]]) -> None:
    """Test ``DisplayCAL.cgats.CGATS`` sorting methods except sort_RGB_to_top."""
    path = data_files["0_16_for_sorting.ti1"].absolute()
    cgats = CGATS(cgats=path)
    with check_call(CGATS, "set_RGB_XYZ_values") as calls:
        getattr(cgats, function)()
        assert calls[0][0][1] == result


class ColorCombination(TypedDict):
    """Color combination with sorted result list."""

    red: bool
    green: bool
    blue: bool
    result: List[List[float]]


COLOR_COMBINATIONS = [
    ColorCombination(
        red=False,
        green=False,
        blue=False,
        result=[],
    ),
    ColorCombination(
        red=True,
        green=True,
        blue=True,
        result=[
            [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [50.0, 50.0, 50.0, 100.0, 100.0, 100.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [80.0, 80.0, 80.0, 100.0, 100.0, 100.0],
            [50.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            [50.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [25.0, 50.0, 25.0, 0.0, 0.0, 0.0],
            [50.0, 50.0, 25.0, 0.0, 0.0, 0.0],
            [50.0, 50.0, 100.0, 0.0, 0.0, 0.0],
        ],
    ),
    ColorCombination(
        red=False,
        green=True,
        blue=True,
        result=[
            [50.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [50.0, 50.0, 50.0, 100.0, 100.0, 100.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [50.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [80.0, 80.0, 80.0, 100.0, 100.0, 100.0],
            [25.0, 50.0, 25.0, 0.0, 0.0, 0.0],
            [50.0, 50.0, 25.0, 0.0, 0.0, 0.0],
            [50.0, 50.0, 100.0, 0.0, 0.0, 0.0],
        ],
    ),
    ColorCombination(
        red=False,
        green=False,
        blue=True,
        result=[
            [50.0, 50.0, 100.0, 0.0, 0.0, 0.0],
            [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [50.0, 50.0, 50.0, 100.0, 100.0, 100.0],
            [50.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [50.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [80.0, 80.0, 80.0, 100.0, 100.0, 100.0],
            [25.0, 50.0, 25.0, 0.0, 0.0, 0.0],
            [50.0, 50.0, 25.0, 0.0, 0.0, 0.0],
        ],
    ),
    ColorCombination(
        red=True,
        green=False,
        blue=False,
        result=[
            [50.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [50.0, 50.0, 50.0, 100.0, 100.0, 100.0],
            [50.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [80.0, 80.0, 80.0, 100.0, 100.0, 100.0],
            [25.0, 50.0, 25.0, 0.0, 0.0, 0.0],
            [50.0, 50.0, 25.0, 0.0, 0.0, 0.0],
            [50.0, 50.0, 100.0, 0.0, 0.0, 0.0],
        ],
    ),
    ColorCombination(
        red=False,
        green=True,
        blue=False,
        result=[
            [25.0, 50.0, 25.0, 0.0, 0.0, 0.0],
            [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [50.0, 50.0, 50.0, 100.0, 100.0, 100.0],
            [50.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [50.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [80.0, 80.0, 80.0, 100.0, 100.0, 100.0],
            [50.0, 50.0, 25.0, 0.0, 0.0, 0.0],
            [50.0, 50.0, 100.0, 0.0, 0.0, 0.0],
        ],
    ),
    ColorCombination(
        red=True,
        green=True,
        blue=False,
        result=[
            [50.0, 50.0, 25.0, 0.0, 0.0, 0.0],
            [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [50.0, 50.0, 50.0, 100.0, 100.0, 100.0],
            [50.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [50.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [80.0, 80.0, 80.0, 100.0, 100.0, 100.0],
            [25.0, 50.0, 25.0, 0.0, 0.0, 0.0],
            [50.0, 50.0, 100.0, 0.0, 0.0, 0.0],
        ],
    ),
    ColorCombination(
        red=True,
        green=False,
        blue=True,
        result=[
            [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [50.0, 50.0, 50.0, 100.0, 100.0, 100.0],
            [50.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [50.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [80.0, 80.0, 80.0, 100.0, 100.0, 100.0],
            [25.0, 50.0, 25.0, 0.0, 0.0, 0.0],
            [50.0, 50.0, 25.0, 0.0, 0.0, 0.0],
            [50.0, 50.0, 100.0, 0.0, 0.0, 0.0],
        ],
    ),
]


def get_color_combination() -> ColorCombination:
    """Return color combination from COLOR_COMBINATIONS."""
    yield from COLOR_COMBINATIONS


@pytest.fixture(
    scope="session", name="color_combination", params=get_color_combination()
)
def fixture_color_combination(request: SubRequest) -> ColorCombination:
    """Return color combination."""
    return request.param


def test_cgats_sorting_2(data_files, color_combination: ColorCombination) -> None:
    """Test ``DisplayCAL.cgats.CGATS`` sorting method sort_RGB_to_top."""
    path = data_files["0_16_for_sorting.ti1"].absolute()
    cgats = CGATS(cgats=path)
    if not color_combination["result"]:
        assert not cgats.sort_RGB_to_top(
            color_combination["red"],
            color_combination["green"],
            color_combination["blue"],
        )
    else:
        with check_call(CGATS, "set_RGB_XYZ_values") as calls:
            cgats.sort_RGB_to_top(
                color_combination["red"],
                color_combination["green"],
                color_combination["blue"],
            )
            assert calls[0][0][1] == color_combination["result"]


@pytest.mark.parametrize(
    "split_grays,shift,result",
    [
        (
            True,
            True,
            [
                [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [50.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [25.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 50.0, 100.0, 100.0, 100.0],
                [50.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [50.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                [50.0, 50.0, 100.0, 0.0, 0.0, 0.0],
                [80.0, 80.0, 80.0, 100.0, 100.0, 100.0],
            ],
        ),
        (
            False,
            False,
            [
                [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                [50.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 100.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 50.0, 100.0, 100.0, 100.0],
                [50.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [50.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                [25.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [80.0, 80.0, 80.0, 100.0, 100.0, 100.0],
            ],
        ),
        (
            True,
            False,
            [
                [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [50.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 50.0, 100.0, 100.0, 100.0],
                [25.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [50.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                [50.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [80.0, 80.0, 80.0, 100.0, 100.0, 100.0],
                [50.0, 50.0, 100.0, 0.0, 0.0, 0.0],
            ],
        ),
        (
            False,
            True,
            [
                [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 100.0, 0.0, 0.0, 0.0],
                [50.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 50.0, 100.0, 100.0, 100.0],
                [25.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [50.0, 100.0, 100.0, 100.0, 100.0, 100.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [50.0, 50.0, 25.0, 0.0, 0.0, 0.0],
                [80.0, 80.0, 80.0, 100.0, 100.0, 100.0],
            ],
        ),
    ],
    ids=(
        "split grays - with shift",
        "dont split grays - without shift",
        "split grays - without shift",
        "dont split grays - with shift",
    ),
)
def test_cgats_checkerboard(
    data_files, split_grays: bool, shift: bool, result: List[List[float]]
) -> None:
    """Test ``DisplayCAL.cgats.CGATS`` checkerboard method."""
    path = data_files["0_16_for_sorting.ti1"].absolute()
    cgats = CGATS(cgats=path)
    with check_call(CGATS, "set_RGB_XYZ_values") as calls:
        cgats.checkerboard(split_grays=split_grays, shift=shift)
        assert calls[0][0][1] == result


@pytest.mark.parametrize(
    "name", ["fails_when_unstable", "ok_when_unstable", "large_set"]
)
def test_cgats_maximise_lightness_sort_is_invariant_to_input(data_files, name):
    path = data_files[f"{name}.ti1"].absolute()
    cgats = CGATS(cgats=path)
    results = []

    for i in range(3):
        cgats.checkerboard(sort1=stable_sort_by_L)
        results.append(cgats.get_RGB_XYZ_values()[1])
    assert results
    for i in range(len(results[0])):
        last = None
        for r in results:
            if last is not None:
                assert r[i] == last[i]
            last = r


@pytest.mark.parametrize(
    "weight",
    (True, False),
    ids=(
        "with weight",
        "without weight",
    ),
)
@pytest.mark.parametrize(
    "file",
    ("Monitor.cal", "0_16_proper.ti3"),
)
def test_cgats_apply_bpc(
    data_files,
    weight: bool,
    file: str,
) -> None:
    """Test ``DisplayCAL.cgats.CGATS`` black point compensation method."""
    path = data_files[file].absolute()
    cgats = CGATS(cgats=path)
    assert cgats[0].apply_bpc(weight=weight) == 1


@pytest.mark.parametrize(
    "profile,result",
    (
        (
            "0_16_proper.ti3",
            {
                0: b"SAMPLE_ID",
                1: b"RGB_R",
                2: b"RGB_G",
                3: b"RGB_B",
                4: b"XYZ_X",
                5: b"XYZ_Y",
                6: b"XYZ_Z",
            },
        ),
        ("Monitor.cal", None),
    ),
)
def test_cgats_get_cie_data_format(
    data_files, profile: str, result: Dict[int, bytes] | None
) -> None:
    """Test ``DisplayCAL.cgats.CGATS`` get_cie_data_format."""
    path = data_files[profile].absolute()
    cgats = CGATS(cgats=path)
    assert cgats.get_cie_data_format() == result


@pytest.mark.parametrize(
    "profile,result",
    (
        (
            "0_16_proper.ti3",
            {"XYZ_X": 92.51826162624847, "XYZ_Y": 100.0, "XYZ_Z": 110.07025946041877},
        ),
        (
            "Monitor.ti3",
            {"XYZ_X": 95.28091210097986, "XYZ_Y": 100.0, "XYZ_Z": 108.01177927429806},
        ),
        ("Monitor.cal", None),
    ),
)
def test_cgats_get_white_cie(
    data_files, profile: str, result: Dict[float] | None
) -> None:
    """Test ``DisplayCAL.cgats.CGATS`` get_white_cie."""
    path = data_files[profile].absolute()
    cgats = CGATS(cgats=path)
    assert cgats.get_white_cie() == result


@pytest.mark.parametrize(
    "profile,result",
    (
        ("0_16_proper.ti3", 1),
        ("Monitor.ti3", 1),
        ("multiple_sections.ti1", 3),
        ("Monitor.cal", 0),
    ),
)
def test_cgats_adapt(data_files, profile: str, result: int) -> None:
    """Test ``DisplayCAL.cgats.CGATS`` adapt method."""
    path = data_files[profile].absolute()
    cgats = CGATS(cgats=path)
    assert cgats.adapt() == result


def test_cgats_convert_XYZ_to_Lab(data_files) -> None:
    """Test ``DisplayCAL.cgats.CGATS`` convert_XYZ_to_Lab method."""
    path = data_files["0_16_proper.ti3"].absolute()
    cgats = CGATS(cgats=path)
    cgats.convert_XYZ_to_Lab()
    assert all(key in cgats[0]["DATA"][0] for key in [b"LAB_L", b"LAB_A", b"LAB_B"])


@pytest.mark.parametrize("warn", (True, False), ids=("warn only", "take action"))
@pytest.mark.parametrize(
    "profile,filtered_sets,unfiltered_sets,result",
    (
        (
            "Monitor.ti3",
            175,
            175,
            {
                "SAMPLE_ID": 1,
                "RGB_R": 100.0,
                "RGB_G": 100.0,
                "RGB_B": 100.0,
                "XYZ_X": 95.28091,
                "XYZ_Y": 100.0,
                "XYZ_Z": 108.0118,
            },
        ),
        (
            "Monitor_FixableSet.ti3",
            175,
            175,
            {
                "SAMPLE_ID": 1,
                "RGB_R": 100.0,
                "RGB_G": 100.0,
                "RGB_B": 100.0,
                "XYZ_X": 1e-06,
                "XYZ_Y": 100.0,
                "XYZ_Z": 108.0118,
            },
        ),
        (
            "Monitor_UnfixableSet.ti3",
            174,
            175,
            {
                "SAMPLE_ID": 2,
                "RGB_R": 100.0,
                "RGB_G": 100.0,
                "RGB_B": 75.0,
                "XYZ_X": 86.58697,
                "XYZ_Y": 97.50149,
                "XYZ_Z": 61.68331,
            },
        ),
    ),
)
def test_fix_zero_measurements(
    data_files,
    profile: str,
    filtered_sets: int,
    unfiltered_sets: int,
    result: Dict[str, int | float],
    warn: bool,
) -> None:
    """Test ``DisplayCAL.cgats.CGATS`` fix_zero_measurements method."""
    path = data_files[profile].absolute()
    cgats = CGATS(cgats=path)
    cgats.fix_zero_measurements(warn_only=warn)
    assert len(cgats[0]["DATA"]) == unfiltered_sets if warn else filtered_sets
    if not warn:
        assert cgats[0]["DATA"][0] == result
