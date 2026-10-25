"""ICC CurveType and ParametricCurveType tags."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Callable, TextIO

from DisplayCAL import colormath
from DisplayCAL.icc_profile.codecs import (
    s15Fixed16Number,
    u8Fixed8Number,
    u8Fixed8Number_tohex,
    uInt16Number,
    uInt16Number_tohex,
    uInt32Number,
    uInt32Number_tohex,
)
from DisplayCAL.icc_profile.tags.base import ICCProfileTag, XYZType

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Self

    from DisplayCAL.icc_profile import ICCProfile


class CurveType(ICCProfileTag, list):
    """ICC CurveType tag.

    Args:
        tagData (bytes, optional): Raw tag data. Defaults to None.
        tagSignature (str, optional): Tag signature. Defaults to None.
        profile (ICCProfile, optional): ICC profile instance. Defaults to None.
    """

    def __init__(
        self,
        tagData: None | bytes = None,  # noqa: N803
        tagSignature: None | str = None,  # noqa: N803
        profile: None | ICCProfile = None,
    ) -> None:
        ICCProfileTag.__init__(self, tagData, tagSignature)
        self.profile = profile
        self._reset()
        if not tagData:
            return
        curve_entries_count = uInt32Number(tagData[8:12])
        curve_entries = tagData[12:]
        if curve_entries_count == 1:
            # Gamma
            self.append(u8Fixed8Number(curve_entries[:2]))
        elif curve_entries_count:
            # Curve
            for _count in range(curve_entries_count):
                self.append(uInt16Number(curve_entries[:2]))
                curve_entries = curve_entries[2:]
        else:
            # Identity
            self.append(1.0)

    def __delitem__(self, value: int) -> None:
        """Delete an item from the list.

        Args:
            value (int): Index of the item to delete.
        """
        list.__delitem__(self, value)
        self._reset()

    def __iadd__(self, value: Any) -> Self:  # noqa: ANN401
        """Add a value to the list.

        Args:
            value (Any): The value to add to the list.

        Returns:
            Self: The updated list.
        """
        list.__iadd__(self, value)
        self._reset()
        return self

    def __imul__(self, value: int) -> Self:
        """Multiply the list by a scalar.

        Args:
            value (int): The scalar to multiply the list by.

        Returns:
            Self: The updated list.
        """
        list.__imul__(self, value)
        self._reset()
        return self

    def __setitem__(self, key: int, value: Any) -> None:  # noqa: ANN401
        """Set an item in the list.

        Args:
            key (int): Index of the item to set.
            value (Any): The new value to set at the index.
        """
        list.__setitem__(self, key, value)
        self._reset()

    def _reset(self) -> None:
        """Reset internal state."""
        self._transfer_function = {}
        self._bt1886 = {}

    def append(self, object_: Any) -> None:  # noqa: ANN401
        """Append an object to the list.

        Args:
            object_ (Any): The object to append to the list.
        """
        list.append(self, object_)
        self._reset()

    def apply_bpc(self, black_Y_out: float = 0, weight: bool = False) -> None:  # noqa: N803
        """Apply black point compensation to the curve.

        Args:
            black_Y_out (float, optional): The output black point Y value to
                apply. Defaults to 0.
            weight (bool, optional): If True, apply weighted black point
                compensation. Defaults to False.
        """
        if len(self) < 2:
            return
        D50_xyY = colormath.XYZ2xyY(*colormath.get_whitepoint("D50"))  # noqa: N806
        bp_in = colormath.xyY2XYZ(D50_xyY[0], D50_xyY[1], self[0] / 65535.0)
        bp_out = colormath.xyY2XYZ(D50_xyY[0], D50_xyY[1], black_Y_out)
        wp_out = colormath.xyY2XYZ(D50_xyY[0], D50_xyY[1], self[-1] / 65535.0)
        for i, v in enumerate(self):
            X, Y, Z = colormath.xyY2XYZ(D50_xyY[0], D50_xyY[1], v / 65535.0)  # noqa: N806
            self[i] = (
                colormath.apply_bpc(X, Y, Z, bp_in, bp_out, wp_out, weight)[1] * 65535.0
            )

    def extend(self, iterable: Iterable) -> None:
        """Extend the list with elements from an iterable.

        Args:
            iterable (iterable): An iterable whose elements will be added to
                the list.
        """
        list.extend(self, iterable)
        self._reset()

    def get_gamma(
        self,
        use_vmin_vmax: bool = False,
        average: bool = True,
        least_squares: bool = False,
        slice_: tuple[float, float] = (0.01, 0.99),
        lstar_slice: bool = True,
    ) -> float | list:
        """Return average or least squares gamma or a list of gamma values.

        Args:
            use_vmin_vmax (bool, optional): If True, use the first and last
                values as vmin and vmax for gamma calculation. Default is
                False.
            average (bool, optional): If True, return the average gamma value.
                Default is True.
            least_squares (bool, optional): If True, return the least squares
                gamma value. Default is False.
            slice_ (tuple[float, float], optional): The range of the curve to
                consider for the gamma calculation. Defaults to (0.01, 0.99).
            lstar_slice (bool, optional): If True, use L* values for the slice.
                Defaults to True.

        Returns:
            float | list: If average or least_squares is True, return a single
                gamma value. Otherwise, return a list of gamma values for the
                specified slice.
        """
        if len(self) <= 1:
            values = self if len(self) else [1.0]  # Identity
            if average or least_squares:
                return values[0]
            return [values[0]]
        if lstar_slice:
            start = slice_[0] * 100
            end = slice_[1] * 100
            values = []
            for i, y in enumerate(self):
                n = colormath.XYZ2Lab(0, y / 65535.0 * 100, 0)[0]
                if start <= n <= end:
                    values.append((i / (len(self) - 1.0) * 65535.0, y))
        else:
            maxv = len(self) - 1.0
            maxi = int(maxv)
            starti = round(slice_[0] * maxi)
            endi = round(slice_[1] * maxi) + 1
            values = list(
                zip(
                    [(v / maxv) * 65535 for v in range(starti, endi)], self[starti:endi]
                )
            )
        vmin = 0
        vmax = 65535.0
        if use_vmin_vmax and len(self) > 2:
            vmin = self[0]
            vmax = self[-1]
        return colormath.get_gamma(values, 65535.0, vmin, vmax, average, least_squares)

    def get_transfer_function(
        self,
        best: bool = True,
        slice_: tuple[float, float] = (0.05, 0.95),
        black_Y: None | float = None,  # noqa: N803
        outoffset: None | float = None,
    ) -> tuple[tuple[str, float, float], float] | float:
        """Return transfer function name, exponent and match percentage.

        Args:
            best (bool): If True, return the best matching transfer function.
            slice_ (tuple[float, float]): The range of the curve to consider for
                the transfer function.
            black_Y (None | float): The black Y value to use for the transfer
                function calculation. If None, it will be calculated from the
                curve.
            outoffset (None | float): The output offset to apply. If None, it
                will be set to 1.0.

        Returns:
            tuple: A tuple containing the transfer function name, exponent,
                output offset, and the match percentage.
            float: The match percentage of the transfer function.
        """
        if len(self) == 1:
            # Gamma
            return (f"Gamma {round(self[0], 2):.2f}", self[0], 1.0), 1.0
        if not len(self):
            # Identity
            return ("Gamma 1.0", 1.0, 1.0), 1.0
        transfer_function = self._transfer_function.get((best, slice_))
        if transfer_function:
            return transfer_function
        trc = CurveType()
        match = {}
        otrc = CurveType()
        otrc[:] = self
        if otrc[0]:
            otrc.apply_bpc()
        vmin = otrc[0]
        vmax = otrc[-1]
        if self.profile and isinstance(self.profile.tags.get("lumi"), XYZType):
            white_cdm2 = self.profile.tags.lumi.Y
        else:
            white_cdm2 = 100.0
        if black_Y is None:
            black_Y = self[0] / 65535.0  # noqa: N806
        black_cdm2 = black_Y * white_cdm2
        maxv = len(otrc) - 1.0
        maxi = int(maxv)
        _starti = round(0.4 * maxi)
        _endi = round(0.6 * maxi)
        gamma = otrc.get_gamma(True, slice_=(0.4, 0.6), lstar_slice=False)
        egamma = colormath.get_gamma([(0.5, 0.5**gamma)], vmin=-black_Y)
        outoffset_unspecified = outoffset is None
        if outoffset_unspecified:
            outoffset = 1.0
        tfs = [
            ("Rec. 709", -709, outoffset),
            ("Rec. 1886", -1886, 0),
            ("SMPTE 240M", -240, outoffset),
            ("SMPTE 2084", -2084, outoffset),
            ("DICOM", -1023, outoffset),
            ("HLG", -2, outoffset),
            ("L*", -3.0, outoffset),
            ("sRGB", -2.4, outoffset),
            (
                f"Gamma {gamma:.2f} {outoffset:.0%}",
                gamma,
                outoffset,
            ),
        ]
        if outoffset_unspecified and black_Y:
            tfs.extend(
                (
                    f"Gamma {gamma:.2f} {i:d}%",
                    gamma,
                    i / 100.0,
                )
                for i in range(100)
            )
        for name, exp, outoffset in tfs:
            if name in ("DICOM", "Rec. 1886", "SMPTE 2084", "HLG"):
                try:
                    if name == "DICOM":
                        trc.set_dicom_trc(black_cdm2, white_cdm2, size=len(self))
                    elif name == "Rec. 1886":
                        trc.set_bt1886_trc(black_Y, size=len(self))
                    elif name == "SMPTE 2084":
                        trc.set_smpte2084_trc(black_cdm2, white_cdm2, size=len(self))
                    elif name == "HLG":
                        trc.set_hlg_trc(black_cdm2, white_cdm2, size=len(self))
                except ValueError:
                    continue
            elif exp > 0 and black_Y:
                trc.set_bt1886_trc(black_Y, outoffset, egamma, "b")
            else:
                trc.set_trc(exp, len(self), vmin, vmax)
            if trc[0] and trc[-1] - trc[0]:
                trc.apply_bpc()
            if otrc == trc:
                match[(name, exp, outoffset)] = 1.0
            else:
                match[(name, exp, outoffset)] = 0.0
                count = 0
                start = slice_[0] * len(self)
                end = slice_[1] * len(self)
                for i, n in enumerate(otrc):
                    # n = colormath.XYZ2Lab(0, n / 65535.0 * 100, 0)[0]
                    if start > i or i > end:
                        continue
                    n = colormath.get_gamma(
                        [(i / (len(self) - 1.0) * 65535.0, n)],
                        65535.0,
                        vmin,
                        vmax,
                        False,
                    )
                    if n:
                        n = n[0]
                        # n2 = colormath.XYZ2Lab(0, trc[i] / 65535.0 * 100, 0)[0]
                        n2 = colormath.get_gamma(
                            [(i / (len(self) - 1.0) * 65535.0, trc[i])],
                            65535.0,
                            vmin,
                            vmax,
                            False,
                        )
                        if n2 and n2[0]:
                            n2 = n2[0]
                            match[(name, exp, outoffset)] += 1 - (
                                max(n, n2) - min(n, n2)
                            ) / ((n + n2) / 2.0)
                            count += 1
                if count:
                    match[(name, exp, outoffset)] /= count
        if not best:
            self._transfer_function[(best, slice_)] = match
            return match
        match, (name, exp, outoffset) = sorted(
            zip(list(match.values()), list(match.keys()))
        )[-1]
        self._transfer_function[(best, slice_)] = (name, exp, outoffset), match
        return (name, exp, outoffset), match

    def insert(self, object_: Any) -> None:  # noqa: ANN401
        """Insert an item at a given position in the list.

        Args:
            object_ (Any): The item to insert into the list.
        """
        list.insert(self, object_)
        self._reset()

    def pop(self, index: int) -> None:
        """Remove and return an item at the given index.

        Args:
            index (int): The index of the item to remove and return.
        """
        list.pop(self, index)
        self._reset()

    def remove(self, value: Any) -> None:  # noqa: ANN401
        """Remove the first occurrence of a value from the list.

        Args:
            value (Any): The value to remove from the list.
        """
        list.remove(self, value)
        self._reset()

    def reverse(self) -> None:
        """Reverse the order of the list."""
        list.reverse(self)
        self._reset()

    def set_bt1886_trc(
        self,
        black_Y: float = 0,  # noqa: N803
        outoffset: float = 0.0,
        gamma: float = 2.4,
        gamma_type: str = "B",
        size: None | int = None,
    ) -> None | colormath.BT1886:
        """Set the response to the BT. 1886 curve.

        This response is special in that it depends on the actual black
        level of the display.

        Args:
            black_Y (float, optional): Black point in absolute Y, range 0..100.
                Defaults to 0.
            outoffset (float, optional): Output offset, range 0.0..1. Defaults to 0.0.
            gamma (float, optional): Gamma value, range 1.0..3.0.
                Defaults to 2.4.
            gamma_type (str, optional): Type of gamma to use, either "b" for
                BT.1886 or "g" for technical gamma. Defaults to "B".
            size (None | int, optional): Number of steps. Recommended >= 1024.

        Returns:
            None | BT1886: None if the response was set successfully, or BT1886
                instance if it was already set for the given parameters.
        """
        bt1886 = self._bt1886.get((gamma, black_Y, outoffset))
        if bt1886:
            return bt1886
        if gamma_type in ("b", "g"):
            # Get technical gamma needed to achieve effective gamma
            gamma = colormath.xicc_tech_gamma(gamma, black_Y, outoffset)
        rXYZ = colormath.RGB2XYZ(1.0, 0, 0)  # noqa: N806
        gXYZ = colormath.RGB2XYZ(0, 1.0, 0)  # noqa: N806
        bXYZ = colormath.RGB2XYZ(0, 0, 1.0)  # noqa: N806
        mtx = colormath.Matrix3x3(
            [
                [rXYZ[0], gXYZ[0], bXYZ[0]],
                [rXYZ[1], gXYZ[1], bXYZ[1]],
                [rXYZ[2], gXYZ[2], bXYZ[2]],
            ]
        )
        wXYZ = colormath.RGB2XYZ(1.0, 1.0, 1.0)  # noqa: N806
        x, y = colormath.XYZ2xyY(*wXYZ)[:2]
        XYZbp = colormath.xyY2XYZ(x, y, black_Y)  # noqa: N806
        bt1886 = colormath.BT1886(mtx, XYZbp, outoffset, gamma)
        self._bt1886[(gamma, black_Y, outoffset)] = bt1886
        self.set_trc(-709, size)
        for i, v in enumerate(self):
            X, Y, Z = colormath.xyY2XYZ(x, y, v / 65535.0)  # noqa: N806
            self[i] = bt1886.apply(X, Y, Z)[1] * 65535.0
        return None

    def set_dicom_trc(
        self, black_cdm2: float = 0.05, white_cdm2: float = 100, size: None | int = None
    ) -> None:
        """Set the response to the DICOM Grayscale Standard Display Function.

        This response is special in that it depends on the actual black
        and white level of the display.

        Args:
            black_cdm2 (float, optional): Black point in absolute Y,
                range 0.05..white_cdm2. Defaults to 0.05.
            white_cdm2 (float, optional): White point in absolute Y,
                range black_cdm2..4000. Defaults to 100.
            size (None | int, optional): Number of steps. Recommended >= 1024.
        """
        # See http://medical.nema.org/Dicom/2011/11_14pu.pdf
        # Luminance levels depend on the start level of 0.05 cd/m2
        # and end level of 4000 cd/m2
        black_cdm2 = round(black_cdm2, 6)
        if black_cdm2 < 0.05 or black_cdm2 >= white_cdm2:
            raise ValueError(
                f"The black level of {black_cdm2} cd/m2 is out of range "
                "for DICOM. Valid range begins at 0.05 cd/m2."
            )
        if white_cdm2 > 4000 or white_cdm2 <= black_cdm2:
            raise ValueError(
                f"The white level of {white_cdm2} cd/m2 is out of range "
                "for DICOM. Valid range is up to 4000 cd/m2."
            )
        black_jndi = colormath.DICOM(black_cdm2, True)
        white_jndi = colormath.DICOM(white_cdm2, True)
        white_dicom_y = math.pow(10, colormath.DICOM(white_jndi))
        if not size:
            size = len(self)
        if size < 2:
            size = 1024
        self[:] = []
        for i in range(size):
            v = (
                math.pow(
                    10,
                    colormath.DICOM(
                        black_jndi + (float(i) / (size - 1)) * (white_jndi - black_jndi)
                    ),
                )
                / white_dicom_y
            )
            self.append(v * 65535)

    def set_hlg_trc(
        self,
        black_cdm2: float = 0,
        white_cdm2: float = 100,
        system_gamma: float = 1.2,
        ambient_cdm2: float = 5,
        maxsignal: float = 1.0,
        size: None | int = None,
        logfile: None | TextIO = None,
    ) -> None:
        """Set the response to the Hybrid Log-Gamma (HLG) function.

        This response is special in that it depends on the actual black
        and white level of the display, system gamma and ambient.

        Args:
            black_cdm2 (float, optional): Black point in absolute XYZ, range
                0..white_cdm2. Defaults to 0.
            white_cdm2 (float, optional): White point in absolute Y,
                range 0..10000. Defaults to 100.
            system_gamma (float, optional): System gamma, typically 1.2.
                Defaults to 1.2.
            ambient_cdm2 (float, optional): Ambient light in cd/m2. Defaults to
                5.
            maxsignal (float, optional): Set clipping point. Defaults to 1.0.
            size (None | int, optional): Number of steps. Recommended >= 1024.
            logfile (None | TextIO, optional): Log file to write diagnostic
                information to. Defaults to None.

        Raises:
            ValueError: If the black or white levels are out of range for
                HLG.
            ValueError: If the white level exceeds 10000 cd/m2.
            ValueError: If the black level is negative or greater than or equal
                to the white level.
            ValueError: If the white level is less than or equal to the black
                level.
        """
        if black_cdm2 < 0 or black_cdm2 >= white_cdm2:
            raise ValueError(
                f"The black level of {black_cdm2:f} cd/m2 is out of range "
                "for HLG. Valid range begins at 0 cd/m2."
            )
        values = []

        hlg = colormath.HLG(black_cdm2, white_cdm2, system_gamma, ambient_cdm2)

        if maxsignal < 1:
            # Adjust EOTF so that EOTF[maxsignal] gives (approx) white_cdm2
            while hlg.eotf(maxsignal) * hlg.white_cdm2 < white_cdm2:
                hlg.white_cdm2 += 1

        lscale = 1.0 / hlg.oetf(1.0, True)
        hlg.white_cdm2 *= lscale
        if lscale < 1 and logfile:
            logfile.write(
                f"Nominal peak luminance after scaling = {hlg.white_cdm2:.2f}\n"
            )

        maxv = hlg.eotf(maxsignal)
        if not size:
            size = len(self)
        if size < 2:
            size = 1024
        for i in range(size):
            n = i / (size - 1.0)
            v = hlg.eotf(min(n, maxsignal))
            values.append(min(v / maxv, 1.0))
        self[:] = [min(v * 65535, 65535) for v in values]

    def set_smpte2084_trc(
        self,
        black_cdm2: float = 0,
        white_cdm2: float = 100,
        master_black_cdm2: float = 0,
        master_white_cdm2: float = 0,
        use_alternate_master_white_clip: bool = True,
        rolloff: bool = False,
        size: None | int = None,
    ) -> None:
        """Set the response to the SMPTE 2084 perceptual quantizer (PQ) function.

        This response is special in that it depends on the actual black
        and white level of the display.

        Args:
            black_cdm2 (float, optinoal): Black point in absolute Y, range
                0..white_cdm2. Defaults to 0.
            white_cdm2 (float, optional): White point in absolute Y, range
                0..10000. Defaults to 100.
            master_black_cdm2 (float, optional): Used to normalize PQ values.
            master_white_cdm2 (float, optional): Used to normalize PQ values.
            use_alternate_master_white_clip (bool, optional): If True,
                use the alternate master white clip as defined in ITU-R
                BT.2390. Defaults to True.
            rolloff (bool, optional): BT.2390.
            size (None | int, optional): Number of steps. Recommended >= 1024.

        Raises:
            ValueError: If the black or white levels are out of range for
                SMPTE 2084.
            ValueError: If the white level exceeds 10000 cd/m2.
            ValueError: If the black level is negative or greater than or equal
                to the white level.
            ValueError: If the white level is less than or equal to the black
                level.
            ValueError: If the master white level exceeds 10000 cd/m2.
        """
        # See https://www.smpte.org/sites/default/files/2014-05-06-EOTF-Miller-1-2-handout.pdf
        # Luminance levels depend on the end level of 10000 cd/m2
        if black_cdm2 < 0 or black_cdm2 >= white_cdm2:
            raise ValueError(
                f"The black level of {black_cdm2:f} cd/m2 is out of range "
                "for SMPTE 2084. Valid range begins at 0 cd/m2."
            )
        if max(white_cdm2, master_white_cdm2) > 10000:
            raise ValueError(
                f"The white level of {max(white_cdm2, master_white_cdm2):f} "
                "cd/m2 is out of range for SMPTE 2084. "
                "Valid range is up to 10000 cd/m2."
            )
        values = []
        maxv = white_cdm2 / 10000.0
        maxi = colormath.special_pow(maxv, 1.0 / -2084)
        if rolloff:
            # Rolloff as defined in ITU-R BT.2390
            if not master_white_cdm2:
                master_white_cdm2 = 10000
            bt2390 = colormath.BT2390(
                black_cdm2,
                white_cdm2,
                master_black_cdm2,
                master_white_cdm2,
                use_alternate_master_white_clip,
            )
            maxi_out = maxi
        else:
            if not master_white_cdm2:
                master_white_cdm2 = white_cdm2
            maxi_out = colormath.special_pow(master_white_cdm2 / 10000.0, 1.0 / -2084)
        if not size:
            size = len(self)
        if size < 2:
            size = 1024
        for i in range(size):
            n = i / (size - 1.0)
            if rolloff:
                n = bt2390.apply(n)
            v = colormath.special_pow(n * (maxi / maxi_out), -2084)
            values.append(min(v / maxv, 1.0))
        self[:] = [min(v * 65535, 65535) for v in values]
        if black_cdm2 and not rolloff:
            self.apply_bpc(black_cdm2 / white_cdm2)

    def set_trc(
        self,
        power: float | Callable = 2.2,
        size: None | int = None,
        vmin: float = 0,
        vmax: float = 65535,
    ) -> None:
        """Set the response to a certain function.

        Args:
            power (float | Callable, optional): The power to raise the input
                value to. If a callable, it should take a single float argument
                and return a float. Defaults to 2.2. Positive power, or
                -2.4 = sRGB, -3.0 = L*, -240 = SMPTE 240M, -601 = Rec. 601,
                -709 = Rec. 709 (Rec. 601 and 709 transfer functions are
                identical).
            size (int, optional): The number of entries in the curve. Defaults
                to None.
            vmin (float, optional): The minimum value of the curve. Defaults to
                0.
            vmax (float, optional): The maximum value of the curve. Defaults to
                65535.
        """
        if not size:
            size = len(self) or 1024
        if size == 1:
            if callable(power):
                power = colormath.get_gamma([(0.5, power(0.5))])
            if power >= 0.0 and not vmin:
                self[:] = [power]
                return
            size = 1024
        self[:] = []
        if not callable(power):
            exp = power

            def power(a: float) -> float:
                """Power function for non-callable power.

                Args:
                    a (float): The input value to raise to the power.

                Returns:
                    float: The result of raising the input value to the power.
                """
                return colormath.special_pow(a, exp)

        for i in range(size):
            self.append(vmin + power(float(i) / (size - 1)) * (vmax - vmin))

    def smooth_cr(self, length: int = 64) -> None:
        """Smooth curves (Catmull-Rom).

        Args:
            length (int, optional): Number of points to use for smoothing.
                Defaults to 64.
        """
        raise NotImplementedError

    def smooth_avg(
        self,
        passes: int = 1,
        window: None | tuple[float, float, float] = None,
    ) -> None:
        """Smooth curves (moving average).

        Args:
            passes (int, optional): Number of passes. Defaults to 1.
            window (None | tuple[float, float, float], optional): Tuple or list
                containing weighting factors. Its length determines the size of
                the window to use. Defaults to (1.0, 1.0, 1.0).
        """
        self[:] = colormath.smooth_avg(self, passes, window)

    def sort(
        self,
        cmp: None | Callable = None,
        key: None | Callable = None,
        reverse: bool = False,
    ) -> None:
        """Sort the curve entries.

        Args:
            cmp (callable, optional): A comparison function that defines the
                sort order. Not used in Python 3.
            key (callable, optional): A function that extracts a comparison
                key from each list element. Defaults to None.
            reverse (bool, optional): If True, the list elements are sorted in
                descending order. Defaults to False.
        """
        list.sort(self, key=key, reverse=reverse)
        self._reset()

    @property
    def tagData(self) -> bytes:  # noqa: N802
        """Return raw tag data.

        Returns:
            bytes: The raw tag data representing the curve.
        """
        # Identity
        curve_entries_count = 0 if len(self) == 1 and self[0] == 1.0 else len(self)
        tag_data = [b"curv", b"\0" * 4, uInt32Number_tohex(curve_entries_count)]
        if curve_entries_count == 1:
            # Gamma
            tag_data.append(u8Fixed8Number_tohex(self[0]))
        elif curve_entries_count:
            # Curve
            tag_data.extend(uInt16Number_tohex(curveEntry) for curveEntry in self)
        return b"".join(tag_data)

    @tagData.setter
    def tagData(self, tagData: bytes) -> None:  # noqa: N802, N803
        """Set the tag data from raw bytes.

        Does nothing, as this tag is read-only.

        Args:
            tagData (bytes): Raw tag data to set.
        """


class ParametricCurveType(ICCProfileTag):
    """ICC ParametricCurveType tag.

    Args:
        tagData (bytes, optional): Raw tag data. Defaults to None.
        tagSignature (str, optional): Tag signature. Defaults to None.
        profile (ICCProfile, optional): ICC profile instance. Defaults to None.
    """

    def __init__(
        self,
        tagData: None | bytes = None,  # noqa: N803
        tagSignature: None | str = None,  # noqa: N803
        profile: None | ICCProfile = None,
    ) -> None:
        ICCProfileTag.__init__(self, tagData, tagSignature)
        self.profile = profile
        self.params = {}
        if not tagData:
            return
        fntype = uInt16Number(tagData[8:10])
        numparams = {0: 1, 1: 3, 2: 4, 3: 5, 4: 7}.get(fntype)
        for i, param in enumerate("gabcdef"[:numparams]):
            self.params[param] = s15Fixed16Number(tagData[12 + i * 4 : 12 + i * 4 + 4])

    def __apply(self, v: float) -> float:
        """Apply the transfer function to a value.

        Args:
            v (float): The input value to apply the transfer function to.

        Returns:
            float: The output value after applying the transfer function.
        """
        if len(self.params) == 1:
            return v ** self.params["g"]
        if len(self.params) == 3:
            # CIE 122-1966
            if v >= -self.params["b"] / self.params["a"]:
                return (self.params["a"] * v + self.params["b"]) ** self.params["g"]
            return 0
        if len(self.params) == 4:
            # IEC 61966-3
            if v >= -self.params["b"] / self.params["a"]:
                return (self.params["a"] * v + self.params["b"]) ** self.params[
                    "g"
                ] + self.params["c"]
            return self.params["c"]
        if len(self.params) == 5:
            # IEC 61966-2.1 (sRGB)
            if v >= self.params["d"]:
                return (self.params["a"] * v + self.params["b"]) ** self.params["g"]
            return self.params["c"] * v
        if len(self.params) == 7:
            if v >= self.params["d"]:
                return (self.params["a"] * v + self.params["b"]) ** self.params[
                    "g"
                ] + self.params["e"]
            return self.params["c"] * v + self.params["f"]
        raise NotImplementedError(f"Invalid number of parameters: {len(self.params):d}")

    def apply(self, v: float) -> float:
        """Apply the transfer function to a value.

        Args:
            v (float): The input value to apply the transfer function to.

        Returns:
            float: The output value after applying the transfer function,
                clipped to [0, 1].
        """
        # clip result to [0, 1]
        return max(0, min(self.__apply(v), 1))

    def get_trc(self, size: int = 1024) -> CurveType:
        """Return a CurveType object with the transfer function.

        Args:
            size (int): Number of points in the curve. Defaults to 1024.

        Returns:
            CurveType: A CurveType object representing the transfer function.
        """
        curv = CurveType(profile=self.profile)
        for i in range(size):
            curv.append(self.apply(i / (size - 1.0)) * 65535)
        return curv
