# -----------------------------------------------------------------------------
# Name:        wx.lib.plot.py
# Purpose:     Line, Bar and Scatter Graphs
#
# Author:      Gordon Williams
#
# Created:     2003/11/03
# RCS-ID:      $Id: plot.py 65712 2010-10-01 17:56:32Z RD $
# Copyright:   (c) 2002
# Licence:     Use as you wish.
# -----------------------------------------------------------------------------
# 12/15/2003 - Jeff Grimmett (grimmtooth@softhome.net)
#
# o 2.5 compatability update.
# o Renamed to plot.py in the wx.lib directory.
# o Reworked test frame to work with wx demo framework. This saves a bit
#   of tedious cut and paste, and the test app is excellent.
#
# 12/18/2003 - Jeff Grimmett (grimmtooth@softhome.net)
#
# o wxScrolledMessageDialog -> ScrolledMessageDialog
#
# Oct 6, 2004  Gordon Williams (g_will@cyberus.ca)
#   - Added bar graph demo
#   - Modified line end shape from round to square.
#   - Removed FloatDCWrapper for conversion to ints and ints in arguments
#
# Oct 15, 2004  Gordon Williams (g_will@cyberus.ca)
#   - Imported modules given leading underscore to name.
#   - Added Cursor Line Tracking and User Point Labels.
#   - Demo for Cursor Line Tracking and Point Labels.
#   - Size of plot preview frame adjusted to show page better.
#   - Added helper functions PositionUserToScreen and PositionScreenToUser in PlotCanvas.
#   - Added functions GetClosestPoints (all curves) and GetClosestPoint (only closest curve)
#       can be in either user coords or screen coords.
#
# Jun 22, 2009  Florian Hoech (florian.hoech@gmx.de)
#   - Fixed exception when drawing empty plots on Mac OS X
#   - Fixed exception when trying to draw point labels on Mac OS X (Mac OS X
#     point label drawing code is still slow and only supports wx.COPY)
#   - Moved label positions away from axis lines a bit
#   - Added PolySpline class and modified demo 1 and 2 to use it
#   - Added center and diagonal lines option (Set/GetEnableCenterLines,
#     Set/GetEnableDiagonals)
#   - Added anti-aliasing option with optional high-resolution mode
#     (Set/GetEnableAntiAliasing, Set/GetEnableHiRes) and demo
#   - Added option to specify exact number of tick marks to use for each axis
#     (SetXSpec(<number>, SetYSpec(<number>) -- work like 'min', but with
#     <number> tick marks)
#   - Added support for background and foreground colours (enabled via
#     SetBackgroundColour/SetForegroundColour on a PlotCanvas instance)
#   - Changed PlotCanvas printing initialization from occuring in __init__ to
#     occur on access. This will postpone any IPP and / or CUPS warnings
#     which appear on stderr on some Linux systems until printing functionality
#     is actually used.
#
#

"""
This is a simple light weight plotting module that can be used with
Boa or easily integrated into your own wxPython application.  The
emphasis is on small size and fast plotting for large data sets.  It
has a reasonable number of features to do line and scatter graphs
easily as well as simple bar graphs.  It is not as sophisticated or
as powerful as SciPy Plt or Chaco.  Both of these are great packages
but consume huge amounts of computer resources for simple plots.
They can be found at http://scipy.com

This file contains two parts; first the re-usable library stuff, then,
after a "if __name__=='__main__'" test, a simple frame and a few default
plots for examples and testing.

Based on wxPlotCanvas
Written by K.Hinsen, R. Srinivasan;
Ported to wxPython Harm van der Heijden, feb 1999

Major Additions Gordon Williams Feb. 2003 (g_will@cyberus.ca)
    -More style options
    -Zooming using mouse "rubber band"
    -Scroll left, right
    -Grid(graticule)
    -Printing, preview, and page set up (margins)
    -Axis and title labels
    -Cursor xy axis values
    -Doc strings and lots of comments
    -Optimizations for large number of points
    -Legends

Did a lot of work here to speed markers up. Only a factor of 4
improvement though. Lines are much faster than markers, especially
filled markers.  Stay away from circles and triangles unless you
only have a few thousand points.

Times for 25,000 points
Line - 0.078 sec
Markers
Square -                   0.22 sec
dot -                      0.10
circle -                   0.87
cross,plus -               0.28
triangle, triangle_down -  0.90

Thanks to Chris Barker for getting this version working on Linux.

Zooming controls with mouse (when enabled):
    Left mouse drag - Zoom box.
    Left mouse double click - reset zoom.
    Right mouse click - zoom out centred on click location.
"""

import functools
import string as _string

import numpy as np

import wx

from DisplayCAL.wxfixes import get_dc_font_scale


def convert_to_list_of_tuples(iterable):
    points = []
    for p in iterable:
        points.append(tuple(map(int, p)))
    return points


# ----------------------------------------------------------------------
# From wxPython Phoenix wx/lib/plot/utils.py with __nonzer__ fix
# and Python 2.6 compatibility


class DisplaySide:
    """Generic class for describing which sides of a box are displayed.

    Used for fine-tuning the axis, ticks, and values of a graph.

    This class somewhat mimics a collections.namedtuple factory function in
    that it is an iterable and can have indiviual elements accessible by name.
    It differs from a namedtuple in a few ways:

    - it's mutable
    - it's not a factory function but a full-fledged class
    - it contains type checking, only allowing boolean values
    - it contains name checking, only allowing valid_names as attributes

    :param bottom: Display the bottom side
    :type bottom: bool
    :param left: Display the left side
    :type left: bool
    :param top: Display the top side
    :type top: bool
    :param right: Display the right side
    :type right: bool
    """

    # TODO: Do I want to replace with __slots__?
    #       Not much memory gain because this class is only called a small
    #       number of times, but it would remove the need for part of
    #       __setattr__...
    valid_names = ("bottom", "left", "right", "top")

    def __init__(self, bottom, left, top, right):
        if not all([isinstance(x, bool) for x in [bottom, left, top, right]]):
            raise TypeError("All args must be bools")
        self.bottom = bottom
        self.left = left
        self.top = top
        self.right = right

    def __str__(self):
        s = "{}(bottom={}, left={}, top={}, right={})"
        s = s.format(
            self.__class__.__name__,
            self.bottom,
            self.left,
            self.top,
            self.right,
        )
        return s

    def __repr__(self):
        # for now, just return the str representation
        return self.__str__()

    def __setattr__(self, name, value):
        """Override __setattr__ to implement some type checking and prevent
        other attributes from being created.
        """
        if name not in self.valid_names:
            err_str = "attribute must be one of {}"
            raise NameError(err_str.format(self.valid_names))
        if not isinstance(value, bool):
            raise TypeError("'{}' must be a boolean".format(name))
        self.__dict__[name] = value

    def __len__(self):
        return 4

    def __hash__(self):
        return hash(tuple(self))

    def __getitem__(self, key):
        return (self.bottom, self.left, self.top, self.right)[key]

    def __setitem__(self, key, value):
        if key == 0:
            self.bottom = value
        elif key == 1:
            self.left = value
        elif key == 2:
            self.top = value
        elif key == 3:
            self.right = value
        else:
            raise IndexError("list index out of range")

    def __iter__(self):
        return iter([self.bottom, self.left, self.top, self.right])

    def __bool__(self):
        return bool([_f for _f in self if _f])


# TODO: replace with wx.DCPenChanger/wx.DCBrushChanger, etc.
#       Alternatively, replace those with this function...
class TempStyle:
    """Decorator / Context Manager to revert pen or brush changes.

    Will revert pen, brush, or both to their previous values after a method
    call or block finish.

    :param which: The item to save and revert after execution. Can be
                  one of ``{'both', 'pen', 'brush'}``.
    :type which: str
    :param dc: The DC to get brush/pen info from.
    :type dc: :class:`wx.DC`

    ::

        # Using as a method decorator:
        @TempStyle()                        # same as @TempStyle('both')
        def func(self, dc, a, b, c):        # dc must be 1st arg (beside self)
            # edit pen and brush here

        # Or as a context manager:
        with TempStyle('both', dc):
            # do stuff

    .. Note::

       As of 2016-06-15, this can only be used as a decorator for **class
       methods**, not standard functions. There is a plan to try and remove
       this restriction, but I don't know when that will happen...

    .. epigraph::

       *Combination Decorator and Context Manager! Also makes Julienne fries!
       Will not break! Will not... It broke!*

       -- The Genie
    """

    _valid_types = {"both", "pen", "brush"}
    _err_str = (
        "No DC provided and unable to determine DC from context for function "
        "`{func_name}`. When `{cls_name}` is used as a decorator, the "
        "decorated function must have a wx.DC as a keyword arg 'dc=' or "
        "as the first arg."
    )

    def __init__(self, which="both", dc=None):
        if which not in self._valid_types:
            raise ValueError("`which` must be one of {}".format(self._valid_types))
        self.which = which
        self.dc = dc
        self.prevPen = None
        self.prevBrush = None

    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(instance, dc, *args, **kwargs):
            # fake the 'with' block. This solves:
            # 1.  plots only being shown on 2nd menu selection in demo
            # 2.  self.dc compalaining about not having a super called when
            #     trying to get or set the pen/brush values in __enter__ and
            #     __exit__:
            #         RuntimeError: super-class __init__() of type
            #         BufferedDC was never called
            self._save_items(dc)
            func(instance, dc, *args, **kwargs)
            self._revert_items(dc)

            # import copy                    # copy solves issue #1 above, but
            # self.dc = copy.copy(dc)        # possibly causes issue #2.

            # with self:
            #     print('in with')
            #     func(instance, dc, *args, **kwargs)

        return wrapper

    def __enter__(self):
        self._save_items(self.dc)
        return self

    def __exit__(self, *exc):
        self._revert_items(self.dc)
        return False  # True means exceptions *are* suppressed.

    def _save_items(self, dc):
        if self.which == "both":
            self._save_pen(dc)
            self._save_brush(dc)
        elif self.which == "pen":
            self._save_pen(dc)
        elif self.which == "brush":
            self._save_brush(dc)
        else:
            err_str = (
                "How did you even get here?? This class forces "
                "correct values for `which` at instancing..."
            )
            raise ValueError(err_str)

    def _revert_items(self, dc):
        if self.which == "both":
            self._revert_pen(dc)
            self._revert_brush(dc)
        elif self.which == "pen":
            self._revert_pen(dc)
        elif self.which == "brush":
            self._revert_brush(dc)
        else:
            err_str = (
                "How did you even get here?? This class forces "
                "correct values for `which` at instancing..."
            )
            raise ValueError(err_str)

    def _save_pen(self, dc):
        self.prevPen = dc.GetPen()

    def _save_brush(self, dc):
        self.prevBrush = dc.GetBrush()

    def _revert_pen(self, dc):
        dc.SetPen(self.prevPen)

    def _revert_brush(self, dc):
        dc.SetBrush(self.prevBrush)


def scale_and_shift_point(x, y, scale=1, shift=0):
    """Creates a scaled and shifted 2x1 numpy array of [x, y] values.

    The shift value must be in the scaled units.

    :param float `x`:        The x value of the unscaled, unshifted point
    :param float `y`:        The y valye of the unscaled, unshifted point
    :param np.array `scale`: The scale factor to use ``[x_sacle, y_scale]``
    :param np.array `shift`: The offset to apply ``[x_shift, y_shift]``.
                             Must be in scaled units

    :returns: a numpy array of 2 elements
    :rtype: np.array

    .. note::

       :math:`new = (scale * old) + shift`
    """
    point = scale * np.array([x, y]) + shift
    return point


def set_displayside(value):
    """Wrapper around :class:`~wx.lib.plot._DisplaySide` that allows for "overloaded" calls.

    If ``value`` is a boolean: all 4 sides are set to ``value``

    If ``value`` is a 2-tuple: the bottom and left sides are set to ``value``
    and the other sides are set to False.

    If ``value`` is a 4-tuple, then each item is set individually: ``(bottom,
    left, top, right)``

    :param value: Which sides to display.
    :type value:   bool, 2-tuple of bool, or 4-tuple of bool
    :raises: `TypeError` if setting an invalid value.
    :raises: `ValueError` if the tuple has incorrect length.
    :rtype: :class:`~wx.lib.plot._DisplaySide`
    """
    err_txt = "value must be a bool or a 2- or 4-tuple of bool"

    # TODO: for 2-tuple, do not change other sides? rather than set to False.
    if isinstance(value, bool):
        # turns on or off all axes
        _value = (value, value, value, value)
    elif isinstance(value, tuple):
        if len(value) == 2:
            _value = (value[0], value[1], False, False)
        elif len(value) == 4:
            _value = value
        else:
            raise ValueError(err_txt)
    else:
        raise TypeError(err_txt)
    return DisplaySide(*_value)


# ----------------------------------------------------------------------
#
# Plotting classes...
#
class PolyPoints:
    """Base Class for lines and markers
    - All methods are private.
    """

    def __init__(self, points, attr):
        self._points = np.array(points).astype(np.float64)
        self._logscale = (False, False)
        self._pointSize = (1.0, 1.0)
        self.currentScale = (1, 1)
        self.currentShift = (0, 0)
        self.scaled = self.points
        self.attributes = {}
        self.attributes.update(self._attributes)
        for name, value in list(attr.items()):
            if name not in list(self._attributes.keys()):
                raise KeyError(
                    "Style attribute incorrect. Should be one of %s"
                    % list(self._attributes.keys())
                )
            self.attributes[name] = value

    def setLogScale(self, logscale):
        self._logscale = logscale

    def __getattr__(self, name):
        if name == "points":
            if len(self._points) > 0:
                data = np.array(self._points, copy=True)
                if self._logscale[0]:
                    data = self.log10(data, 0)
                if self._logscale[1]:
                    data = self.log10(data, 1)
                return data
            else:
                return self._points
        else:
            raise AttributeError(name)

    def log10(self, data, ind):
        data = np.compress(data[:, ind] > 0, data, 0)
        data[:, ind] = np.log10(data[:, ind])
        return data

    def boundingBox(self):
        if len(self.points) == 0:
            # no curves to draw
            # defaults to (-1,-1) and (1,1) but axis can be set in Draw
            minXY = np.array([-1.0, -1.0])
            maxXY = np.array([1.0, 1.0])
        else:
            minXY = np.minimum.reduce(self.points)
            maxXY = np.maximum.reduce(self.points)
        return minXY, maxXY

    def scaleAndShift(self, scale=(1, 1), shift=(0, 0)):
        if len(self.points) == 0:
            # no curves to draw
            return
        if (scale is not self.currentScale) or (shift is not self.currentShift):
            # update point scaling
            self.scaled = scale * self.points + shift
            self.currentScale = scale
            self.currentShift = shift
        # else unchanged use the current scaling

    def getLegend(self):
        return self.attributes["legend"]

    def getClosestPoint(self, pntXY, pointScaled=True):
        """Returns the index of closest point on the curve, pointXY, scaledXY, distance
        x, y in user coords
        if pointScaled == True based on screen coords
        if pointScaled == False based on user coords
        """
        if pointScaled is True:
            # Using screen coords
            p = self.scaled
            pxy = self.currentScale * np.array(pntXY) + self.currentShift
        else:
            # Using user coords
            p = self.points
            pxy = np.array(pntXY)
        # determine distance for each point
        d = np.sqrt(np.add.reduce((p - pxy) ** 2, 1))  # sqrt(dx^2+dy^2)
        pntIndex = np.argmin(d)
        dist = d[pntIndex]
        return [
            pntIndex,
            self.points[pntIndex],
            self.scaled[pntIndex] / self._pointSize,
            dist,
        ]


class PolyLine(PolyPoints):
    """Class to define line type and style
    - All methods except __init__ are private.
    """

    _attributes = {"colour": "black", "width": 1, "style": wx.SOLID, "legend": ""}

    def __init__(self, points, **attr):
        """Creates PolyLine object
        points - sequence (array, tuple or list) of (x,y) points making up line
        **attr - key word attributes
            Defaults:
                'colour'= 'black',          - wx.Pen Colour any wx.NamedColour
                'width'= 1,                 - Pen width
                'style'= wx.SOLID,          - wx.Pen style
                'legend'= ''                - Line Legend to display
        """
        PolyPoints.__init__(self, points, attr)

    def draw(self, dc, printerScale, coord=None):
        colour = self.attributes["colour"]
        width = self.attributes["width"] * printerScale * self._pointSize[0]
        style = self.attributes["style"]
        if not isinstance(colour, wx.Colour):
            colour = wx.NamedColour(colour)
        pen = wx.Pen(colour, int(width), style)
        pen.SetCap(wx.CAP_BUTT)
        dc.SetPen(pen)
        if coord is None:
            if len(self.scaled):  # bugfix for Mac OS X
                if wx.VERSION >= (4,) and isinstance(self.scaled, np.ndarray):
                    # Need to convert to list of tuples
                    scaled = convert_to_list_of_tuples(self.scaled)
                    dc.DrawLines(scaled)
                else:
                    dc.DrawLines(self.scaled)
        else:
            dc.DrawLines(coord)  # draw legend line

    def getSymExtent(self, printerScale):
        """Width and Height of Marker"""
        h = self.attributes["width"] * printerScale * self._pointSize[0]
        w = 7 * h
        return (w, h)


class PolySpline(PolyLine):
    """Class to define line type and style
    - All methods except __init__ are private.
    """

    _attributes = {"colour": "black", "width": 1, "style": wx.SOLID, "legend": ""}

    def __init__(self, points, **attr):
        """Creates PolyLine object
        points - sequence (array, tuple or list) of (x,y) points making up line
        **attr - key word attributes
            Defaults:
                'colour'= 'black',          - wx.Pen Colour any wx.NamedColour
                'width'= 1,                 - Pen width
                'style'= wx.SOLID,          - wx.Pen style
                'legend'= ''                - Line Legend to display
        """
        PolyLine.__init__(self, points, **attr)

    def draw(self, dc, printerScale, coord=None):
        colour = self.attributes["colour"]
        width = self.attributes["width"] * printerScale * self._pointSize[0]
        style = self.attributes["style"]
        if not isinstance(colour, wx.Colour):
            colour = wx.NamedColour(colour)
        pen = wx.Pen(colour, int(width), style)
        pen.SetCap(wx.CAP_ROUND)
        dc.SetPen(pen)
        if coord is None:
            if len(self.scaled):  # bugfix for Mac OS X
                if wx.VERSION >= (4,) and isinstance(self.scaled, np.ndarray):
                    # Need to convert to list of tuples
                    scaled = convert_to_list_of_tuples(self.scaled)
                    dc.DrawSpline(scaled)
                else:
                    dc.DrawSpline(self.scaled)
        else:
            dc.DrawLines(coord)  # draw legend line


class PolyMarker(PolyPoints):
    """Class to define marker type and style
    - All methods except __init__ are private.
    """

    _attributes = {
        "colour": "black",
        "width": 1,
        "size": 2,
        "fillcolour": None,
        "fillstyle": wx.SOLID,
        "marker": "circle",
        "legend": "",
    }

    def __init__(self, points, **attr):
        """Creates PolyMarker object
        points - sequence (array, tuple or list) of (x,y) points
        **attr - key word attributes
            Defaults:
                'colour'= 'black',          - wx.Pen Colour any wx.NamedColour
                'width'= 1,                 - Pen width
                'size'= 2,                  - Marker size
                'fillcolour'= same as colour,      - wx.Brush Colour any wx.NamedColour
                'fillstyle'= wx.SOLID,      - wx.Brush fill style (use wx.TRANSPARENT for no fill)
                'marker'= 'circle'          - Marker shape
                'legend'= ''                - Marker Legend to display

            Marker Shapes:
                - 'circle'
                - 'dot'
                - 'square'
                - 'triangle'
                - 'triangle_down'
                - 'cross'
                - 'plus'
        """

        PolyPoints.__init__(self, points, attr)

    def draw(self, dc, printerScale, coord=None):
        colour = self.attributes["colour"]
        width = self.attributes["width"] * printerScale * self._pointSize[0]
        size = self.attributes["size"] * printerScale * self._pointSize[0]
        fillcolour = self.attributes["fillcolour"]
        fillstyle = self.attributes["fillstyle"]
        marker = self.attributes["marker"]

        if colour and not isinstance(colour, wx.Colour):
            colour = wx.NamedColour(colour)
        if fillcolour and not isinstance(fillcolour, wx.Colour):
            fillcolour = wx.NamedColour(fillcolour)

        dc.SetPen(wx.Pen(colour, int(width)))
        if fillcolour:
            dc.SetBrush(wx.Brush(fillcolour, fillstyle))
        else:
            dc.SetBrush(wx.Brush(colour, fillstyle))
        if coord is None:
            if len(self.scaled):  # bugfix for Mac OS X
                self._drawmarkers(dc, self.scaled, marker, size)
        else:
            self._drawmarkers(dc, coord, marker, size)  # draw legend marker

    def getSymExtent(self, printerScale):
        """Width and Height of Marker"""
        s = 7 * self.attributes["size"] * printerScale * self._pointSize[0]
        return (s, s)

    def _drawmarkers(self, dc, coords, marker, size=1):
        f = eval("self._" + marker)
        f(dc, coords, size)

    def _circle(self, dc, coords, size=1):
        fact = 2.5 * size
        wh = 5.0 * size
        rect = np.zeros((len(coords), 4), float) + [0.0, 0.0, wh, wh]
        rect[:, 0:2] = coords - [fact, fact]
        dc.DrawEllipseList(rect.astype(np.int32))

    def _dot(self, dc, coords, size=1):
        dc.DrawPointList(coords)

    def _square(self, dc, coords, size=1):
        fact = 2.5 * size
        wh = 5.0 * size
        rect = np.zeros((len(coords), 4), float) + [0.0, 0.0, wh, wh]
        rect[:, 0:2] = coords - [fact, fact]
        dc.DrawRectangleList(rect.astype(np.int32))

    def _triangle(self, dc, coords, size=1):
        shape = [
            (-2.5 * size, 1.44 * size),
            (2.5 * size, 1.44 * size),
            (0.0, -2.88 * size),
        ]
        poly = np.repeat(coords, 3, 0)
        poly.shape = (len(coords), 3, 2)
        poly += shape
        dc.DrawPolygonList(poly.astype(np.int32))

    def _triangle_down(self, dc, coords, size=1):
        shape = [
            (-2.5 * size, -1.44 * size),
            (2.5 * size, -1.44 * size),
            (0.0, 2.88 * size),
        ]
        poly = np.repeat(coords, 3, 0)
        poly.shape = (len(coords), 3, 2)
        poly += shape
        dc.DrawPolygonList(poly.astype(np.int32))

    def _cross(self, dc, coords, size=1):
        fact = 2.5 * size
        for f in [[-fact, -fact, fact, fact], [-fact, fact, fact, -fact]]:
            lines = np.concatenate((coords, coords), axis=1) + f
            dc.DrawLineList(lines.astype(np.int32))

    def _plus(self, dc, coords, size=1):
        fact = 2.5 * size
        for f in [[-fact, 0, fact, 0], [0, -fact, 0, fact]]:
            lines = np.concatenate((coords, coords), axis=1) + f
            dc.DrawLineList(lines.astype(np.int32))


class PlotGraphics:
    """Container to hold PolyXXX objects and graph labels
    - All methods except __init__ are private.
    """

    def __init__(self, objects, title="", xLabel="", yLabel=""):
        """Creates PlotGraphics object
        objects - list of PolyXXX objects to make graph
        title - title shown at top of graph
        xLabel - label shown on x-axis
        yLabel - label shown on y-axis
        """
        if not isinstance(objects, (list, tuple)):
            raise TypeError("objects argument should be list or tuple")
        self.objects = objects
        self.title = title
        self.xLabel = xLabel
        self.yLabel = yLabel
        self._pointSize = (1.0, 1.0)

    def setLogScale(self, logscale):
        if not isinstance(logscale, tuple):
            raise TypeError("logscale must be a tuple of bools, e.g. (False, False)")
        if len(self.objects) == 0:
            return
        for o in self.objects:
            o.setLogScale(logscale)

    def boundingBox(self):
        p1, p2 = self.objects[0].boundingBox()
        for o in self.objects[1:]:
            p1o, p2o = o.boundingBox()
            p1 = np.minimum(p1, p1o)
            p2 = np.maximum(p2, p2o)
        return p1, p2

    def scaleAndShift(self, scale=(1, 1), shift=(0, 0)):
        for o in self.objects:
            o.scaleAndShift(scale, shift)

    def setPrinterScale(self, scale):
        """Thickens up lines and markers only for printing"""
        self.printerScale = scale

    def setXLabel(self, xLabel=""):
        """Set the X axis label on the graph"""
        self.xLabel = xLabel

    def setYLabel(self, yLabel=""):
        """Set the Y axis label on the graph"""
        self.yLabel = yLabel

    def setTitle(self, title=""):
        """Set the title at the top of graph"""
        self.title = title

    def getXLabel(self):
        """Get x axis label string"""
        return self.xLabel

    def getYLabel(self):
        """Get y axis label string"""
        return self.yLabel

    def getTitle(self, title=""):
        """Get the title at the top of graph"""
        return self.title

    def draw(self, dc):
        for o in self.objects:
            # t=_time.time()          # profile info
            o._pointSize = self._pointSize
            o.draw(dc, self.printerScale)
            # dt= _time.time() - t
            # print o, "time=", dt

    def getSymExtent(self, printerScale):
        """Get max width and height of lines and markers symbols for legend"""
        self.objects[0]._pointSize = self._pointSize
        symExt = self.objects[0].getSymExtent(printerScale)
        for o in self.objects[1:]:
            o._pointSize = self._pointSize
            oSymExt = o.getSymExtent(printerScale)
            symExt = np.maximum(symExt, oSymExt)
        return symExt

    def getLegendNames(self):
        """Returns list of legend names"""
        lst = []
        for obj in self.objects:
            legend = obj.getLegend()
            if legend:
                lst.append(legend)
        return lst

    def __len__(self):
        return len(self.objects)

    def __getitem__(self, item):
        return self.objects[item]


# -------------------------------------------------------------------------------
# Main window that you will want to import into your application.


class PlotCanvas(wx.Panel):
    """Subclass of a wx.Panel which holds two scrollbars and the actual
    plotting canvas (self.canvas). It allows for simple general plotting
    of data with zoom, labels, and automatic axis scaling."""

    def __init__(
        self,
        parent,
        id=wx.ID_ANY,
        pos=wx.DefaultPosition,
        size=wx.DefaultSize,
        style=0,
        name="plotCanvas",
    ):
        """Constructs a panel, which can be a child of a frame or
        any other non-control window"""

        wx.Panel.__init__(self, parent, id, pos, size, style, name)

        sizer = wx.FlexGridSizer(2, 2, 0, 0)
        self.canvas = wx.Window(self, -1)
        self.sb_vert = wx.ScrollBar(self, -1, style=wx.SB_VERTICAL)
        self.sb_vert.SetScrollbar(0, 1000, 1000, 1000)
        self.sb_hor = wx.ScrollBar(self, -1, style=wx.SB_HORIZONTAL)
        self.sb_hor.SetScrollbar(0, 1000, 1000, 1000)

        sizer.Add(self.canvas, 1, wx.EXPAND)
        sizer.Add(self.sb_vert, 0, wx.EXPAND)
        sizer.Add(self.sb_hor, 0, wx.EXPAND)
        sizer.Add((0, 0))

        sizer.AddGrowableRow(0, 1)
        sizer.AddGrowableCol(0, 1)

        self.sb_vert.Show(False)
        self.sb_hor.Show(False)

        self.SetSizer(sizer)
        self.Fit()

        self.border = (1, 1)

        self.SetBackgroundColour("white")

        # Create some mouse events for zooming
        self.canvas.Bind(wx.EVT_LEFT_DOWN, self.OnMouseLeftDown)
        self.canvas.Bind(wx.EVT_LEFT_UP, self.OnMouseLeftUp)
        self.canvas.Bind(wx.EVT_MOTION, self.OnMotion)
        self.canvas.Bind(wx.EVT_LEFT_DCLICK, self.OnMouseDoubleClick)
        self.canvas.Bind(wx.EVT_RIGHT_DOWN, self.OnMouseRightDown)

        # scrollbar events
        self.Bind(wx.EVT_SCROLL_THUMBTRACK, self.OnScroll)
        self.Bind(wx.EVT_SCROLL_PAGEUP, self.OnScroll)
        self.Bind(wx.EVT_SCROLL_PAGEDOWN, self.OnScroll)
        self.Bind(wx.EVT_SCROLL_LINEUP, self.OnScroll)
        self.Bind(wx.EVT_SCROLL_LINEDOWN, self.OnScroll)

        # set curser as cross-hairs
        self.canvas.SetCursor(wx.CROSS_CURSOR)
        self.HandCursor = wx.CursorFromImage(Hand.GetImage())
        self.GrabHandCursor = wx.CursorFromImage(GrabHand.GetImage())
        self.MagCursor = wx.CursorFromImage(MagPlus.GetImage())

        # Things for printing
        self._print_data = None
        self._pageSetupData = None
        self.printerScale = 1
        self.parent = parent

        # scrollbar variables
        self._sb_ignore = False
        self._adjustingSB = False
        self._sb_xfullrange = 0
        self._sb_yfullrange = 0
        self._sb_xunit = 0
        self._sb_yunit = 0

        self._dragEnabled = False
        self._screenCoordinates = np.array([0.0, 0.0])

        self._logscale = (False, False)

        # Zooming variables
        self._zoomInFactor = 0.5
        self._zoomOutFactor = 2
        self._zoomCorner1 = np.array([0.0, 0.0])  # left mouse down corner
        self._zoomCorner2 = np.array([0.0, 0.0])  # left mouse up corner
        self._zoomEnabled = False
        self._hasDragged = False

        # Drawing Variables
        self.last_draw = None
        self._pointScale = 1
        self._pointShift = 0
        self._xSpec = "auto"
        self._ySpec = "auto"
        self._gridEnabled = False
        self._legendEnabled = False
        self._titleEnabled = True
        self._centerLinesEnabled = False
        self._diagonalsEnabled = False
        self._ticksEnabled = DisplaySide(False, False, False, False)

        # Fonts
        self._fontCache = {}
        self._fontSizeAxis = 10
        self._fontSizeTitle = 15
        self._fontSizeLegend = 7

        # pointLabels
        self._pointLabelEnabled = False
        self.last_PointLabel = None
        self._pointLabelFunc = None
        self.canvas.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeave)
        self._logicalFunction = wx.COPY  # wx.EQUIV not supported on Mac OS X

        self._useScientificNotation = False

        self._antiAliasingEnabled = False
        self._hiResEnabled = False
        self._pointSize = (1.0, 1.0)
        self._fontScale = 1.0

        self.canvas.Bind(wx.EVT_PAINT, self.OnPaint)
        self.canvas.Bind(wx.EVT_SIZE, self.OnSize)
        # OnSize called to make sure the buffer is initialized.
        # This might result in OnSize getting called twice on some
        # platforms at initialization, but little harm done.
        self.OnSize(None)  # sets the initial size based on client size

        self._gridColour = wx.NamedColour("black")

        # Default Pens
        self._tickPen = wx.Pen(wx.BLACK, int(self._pointSize[0]))
        self._tickLength = tuple(-x * 2 for x in self._pointSize)

    def SetCursor(self, cursor):
        self.canvas.SetCursor(cursor)

    def GetGridColour(self):
        return self._gridColour

    def SetGridColour(self, colour):
        if isinstance(colour, wx.Colour):
            self._gridColour = colour
        else:
            self._gridColour = wx.NamedColour(colour)

    @property
    def tickPen(self):
        """The :class:`wx.Pen` used to draw the tick marks on the plot.

        :getter: Returns the :class:`wx.Pen` used for drawing the tick marks.
        :setter: Sets the :class:`wx.Pen` use for drawging the tick marks.
        :type:   :class:`wx.Pen`
        :raise:  `TypeError` when setting a value that is not a
                 :class:`wx.Pen`.
        """
        return self._tickPen

    @tickPen.setter
    def tickPen(self, pen):
        if not isinstance(pen, wx.Pen):
            raise TypeError("pen must be an instance of wx.Pen")
        self._tickPen = pen

    @property
    def tickLength(self):
        """The length of the tick marks on an axis.

        :getter: Returns the length of the tick marks.
        :setter: Sets the length of the tick marks.
        :type:   tuple of (xlength, ylength): int or float
        :raise:  `TypeError` when setting a value that is not an int or float.
        """
        return self._tickLength

    @tickLength.setter
    def tickLength(self, length):
        if not isinstance(length, (tuple, list)):
            raise TypeError("`length` must be a 2-tuple of ints or floats")
        self._tickLength = length

    @property
    def tickLengthScale(self):
        """Scale tick length for hires antialiased mode and printing"""
        return (
            3 * self.printerScale * self._tickLength[0] * self._pointSize[0],
            3 * self.printerScale * self._tickLength[1] * self._pointSize[1],
        )

    # SaveFile
    def SaveFile(self, fileName=""):
        """Saves the file to the type specified in the extension. If no file
        name is specified a dialog box is provided.  Returns True if sucessful,
        otherwise False.

        .bmp  Save a Windows bitmap file.
        .xbm  Save an X bitmap file.
        .xpm  Save an XPM bitmap file.
        .png  Save a Portable Network Graphics file.
        .jpg  Save a Joint Photographic Experts Group file.
        """
        extensions = {
            "bmp": wx.BITMAP_TYPE_BMP,  # Save a Windows bitmap file.
            "xbm": wx.BITMAP_TYPE_XBM,  # Save an X bitmap file.
            "xpm": wx.BITMAP_TYPE_XPM,  # Save an XPM bitmap file.
            "jpg": wx.BITMAP_TYPE_JPEG,  # Save a JPG file.
            "png": wx.BITMAP_TYPE_PNG,  # Save a PNG file.
        }

        fType = _string.lower(fileName[-3:])
        dlg1 = None
        while fType not in extensions:
            if dlg1:  # FileDialog exists: Check for extension
                dlg2 = wx.MessageDialog(
                    self,
                    "File name extension\nmust be one of\nbmp, xbm, xpm, png, or jpg",
                    "File Name Error",
                    wx.OK | wx.ICON_ERROR,
                )
                try:
                    dlg2.ShowModal()
                finally:
                    dlg2.Destroy()
            else:  # FileDialog doesn't exist: just check one
                dlg1 = wx.FileDialog(
                    self,
                    "Choose a file with extension bmp, gif, xbm, xpm, png, or jpg",
                    ".",
                    "",
                    "BMP files (*.bmp)|*.bmp|XBM files (*.xbm)|*.xbm|XPM file (*.xpm)|*.xpm|PNG files (*.png)|*.png|JPG files (*.jpg)|*.jpg",
                    wx.SAVE | wx.OVERWRITE_PROMPT,
                )

            if dlg1.ShowModal() == wx.ID_OK:
                fileName = dlg1.GetPath()
                fType = _string.lower(fileName[-3:])
            else:  # exit without saving
                dlg1.Destroy()
                return False

        if dlg1:
            dlg1.Destroy()

        # Save Bitmap
        res = self._Buffer.SaveFile(fileName, extensions[fType])
        return res

    @property
    def print_data(self):
        if not self._print_data:
            self._print_data = wx.PrintData()
            self._print_data.SetPaperId(wx.PAPER_LETTER)
            self._print_data.SetOrientation(wx.LANDSCAPE)
        return self._print_data

    @property
    def pageSetupData(self):
        if not self._pageSetupData:
            self._pageSetupData = wx.PageSetupDialogData()
            self._pageSetupData.SetMarginBottomRight((25, 25))
            self._pageSetupData.SetMarginTopLeft((25, 25))
            self._pageSetupData.SetPrintData(self.print_data)
        return self._pageSetupData

    def PageSetup(self):
        """Brings up the page setup dialog"""
        data = self.pageSetupData
        data.SetPrintData(self.print_data)
        dlg = wx.PageSetupDialog(self.parent, data)
        try:
            if dlg.ShowModal() == wx.ID_OK:
                data = dlg.GetPageSetupData()  # returns wx.PageSetupDialogData
                # updates page parameters from dialog
                self.pageSetupData.SetMarginBottomRight(data.GetMarginBottomRight())
                self.pageSetupData.SetMarginTopLeft(data.GetMarginTopLeft())
                self.pageSetupData.SetPrintData(data.GetPrintData())
                self._print_data = wx.PrintData(
                    data.GetPrintData()
                )  # updates print_data
        finally:
            dlg.Destroy()

    def Printout(self, paper=None):
        """Print current plot."""
        if paper is not None:
            self.print_data.SetPaperId(paper)
        pdd = wx.PrintDialogData(self.print_data)
        printer = wx.Printer(pdd)
        out = PlotPrintout(self)
        print_ok = printer.Print(self.parent, out)
        if print_ok:
            self._print_data = wx.PrintData(printer.GetPrintDialogData().GetPrintData())
        out.Destroy()

    def PrintPreview(self):
        """Print-preview current plot."""
        printout = PlotPrintout(self)
        printout2 = PlotPrintout(self)
        self.preview = wx.PrintPreview(printout, printout2, self.print_data)
        if not self.preview.Ok():
            wx.MessageDialog(
                self,
                "Print Preview failed.\nCheck that default printer is configured\n",
                "Print error",
                wx.OK | wx.CENTRE,
            ).ShowModal()
        self.preview.SetZoom(40)
        # search up tree to find frame instance
        frameInst = self
        while not isinstance(frameInst, wx.Frame):
            frameInst = frameInst.GetParent()
        frame = wx.PreviewFrame(self.preview, frameInst, "Preview")
        frame.Initialize()
        frame.SetPosition(self.GetPosition())
        frame.SetSize((600, 550))
        frame.Centre(wx.BOTH)
        frame.Show(True)

    def setLogScale(self, logscale):
        if not isinstance(logscale, tuple):
            raise TypeError("logscale must be a tuple of bools, e.g. (False, False)")
        if self.last_draw is not None:
            graphics, xAxis, yAxis = self.last_draw
            graphics.setLogScale(logscale)
            self.last_draw = (graphics, None, None)
        self.SetXSpec("min")
        self.SetYSpec("min")
        self._logscale = logscale

    def getLogScale(self):
        return self._logscale

    def SetFontSizeAxis(self, point=10):
        """Set the tick and axis label font size (default is 10 point)"""
        self._fontSizeAxis = point

    def GetFontSizeAxis(self):
        """Get current tick and axis label font size in points"""
        return self._fontSizeAxis

    def SetFontSizeTitle(self, point=15):
        """Set Title font size (default is 15 point)"""
        self._fontSizeTitle = point

    def GetFontSizeTitle(self):
        """Get current Title font size in points"""
        return self._fontSizeTitle

    def SetFontSizeLegend(self, point=7):
        """Set Legend font size (default is 7 point)"""
        self._fontSizeLegend = point

    def GetFontSizeLegend(self):
        """Get current Legend font size in points"""
        return self._fontSizeLegend

    def SetShowScrollbars(self, value):
        """Set True to show scrollbars"""
        if value not in [True, False]:
            raise TypeError("Value should be True or False")
        if value == self.GetShowScrollbars():
            return
        self.sb_vert.Show(value)
        self.sb_hor.Show(value)
        wx.CallAfter(self.Layout)

    def GetShowScrollbars(self):
        """Set True to show scrollbars"""
        return self.sb_vert.IsShown()

    def SetUseScientificNotation(self, useScientificNotation):
        self._useScientificNotation = useScientificNotation

    def GetUseScientificNotation(self):
        return self._useScientificNotation

    def SetEnableAntiAliasing(self, enableAntiAliasing):
        """Set True to enable anti-aliasing."""
        self._antiAliasingEnabled = enableAntiAliasing
        self.Redraw()

    def GetEnableAntiAliasing(self):
        return self._antiAliasingEnabled

    def SetEnableHiRes(self, enableHiRes):
        """Set True to enable high-resolution mode when using anti-aliasing."""
        self._hiResEnabled = enableHiRes
        self.Redraw()

    def GetEnableHiRes(self):
        return self._hiResEnabled

    def SetEnableDrag(self, value):
        """Set True to enable drag."""
        if value not in [True, False]:
            raise TypeError("Value should be True or False")
        if value:
            if self.GetEnableZoom():
                self.SetEnableZoom(False)
            self.SetCursor(self.HandCursor)
        else:
            self.SetCursor(wx.CROSS_CURSOR)
        self._dragEnabled = value

    def GetEnableDrag(self):
        return self._dragEnabled

    def SetEnableZoom(self, value):
        """Set True to enable zooming."""
        if value not in [True, False]:
            raise TypeError("Value should be True or False")
        if value:
            if self.GetEnableDrag():
                self.SetEnableDrag(False)
            self.SetCursor(self.MagCursor)
        else:
            self.SetCursor(wx.CROSS_CURSOR)
        self._zoomEnabled = value

    def GetEnableZoom(self):
        """True if zooming enabled."""
        return self._zoomEnabled

    def SetEnableGrid(self, value):
        """Set True, 'Horizontal' or 'Vertical' to enable grid."""
        if value not in [True, False, "Horizontal", "Vertical"]:
            raise TypeError("Value should be True, False, Horizontal or Vertical")
        self._gridEnabled = value
        self.Redraw()

    def GetEnableGrid(self):
        """True if grid enabled."""
        return self._gridEnabled

    def SetEnableCenterLines(self, value):
        """Set True, 'Horizontal' or 'Vertical' to enable center line(s)."""
        if value not in [True, False, "Horizontal", "Vertical"]:
            raise TypeError("Value should be True, False, Horizontal or Vertical")
        self._centerLinesEnabled = value
        self.Redraw()

    def GetEnableCenterLines(self):
        """True if grid enabled."""
        return self._centerLinesEnabled

    def SetEnableDiagonals(self, value):
        """Set True, 'Bottomleft-Topright' or 'Bottomright-Topleft' to enable
        center line(s)."""
        if value not in [True, False, "Bottomleft-Topright", "Bottomright-Topleft"]:
            raise TypeError(
                "Value should be True, False, Bottomleft-Topright or Bottomright-Topleft"
            )
        self._diagonalsEnabled = value
        self.Redraw()

    def GetEnableDiagonals(self):
        """True if grid enabled."""
        return self._diagonalsEnabled

    def SetEnableLegend(self, value):
        """Set True to enable legend."""
        if value not in [True, False]:
            raise TypeError("Value should be True or False")
        self._legendEnabled = value
        self.Redraw()

    def GetEnableLegend(self):
        """True if Legend enabled."""
        return self._legendEnabled

    def SetEnableTitle(self, value):
        """Set True to enable title."""
        if value not in [True, False]:
            raise TypeError("Value should be True or False")
        self._titleEnabled = value
        self.Redraw()

    def GetEnableTitle(self):
        """True if title enabled."""
        return self._titleEnabled

    def SetEnablePointLabel(self, value):
        """Set True to enable pointLabel."""
        if value not in [True, False]:
            raise TypeError("Value should be True or False")
        self._pointLabelEnabled = value
        self.Redraw()  # will erase existing pointLabel if present
        self.last_PointLabel = None

    def GetEnablePointLabel(self):
        """True if pointLabel enabled."""
        return self._pointLabelEnabled

    @property
    def enableTicks(self):
        """The current enableTicks value.

        :getter: Returns the value of enableTicks.
        :setter: Sets the value of enableTicks.
        :type:   bool, 2-tuple of bool, or 4-tuple of bool
        :raises: `TypeError` if setting an invalid value.
        :raises: `ValueError` if the tuple has incorrect length.

        If bool, enable or disable all ticks

        If 2-tuple, enable or disable the bottom or left ticks:
        ``(bottom, left)``

        If 4-tuple, enable or disable each tick side individually:
        ``(bottom, left, top, right)``
        """
        return self._ticksEnabled

    @enableTicks.setter
    def enableTicks(self, value):
        self._ticksEnabled = set_displayside(value)
        self.Redraw()

    def SetPointLabelFunc(self, func):
        """Sets the function with custom code for pointLabel drawing
        ******** more info needed ***************
        """
        self._pointLabelFunc = func

    def GetPointLabelFunc(self):
        """Returns pointLabel Drawing Function"""
        return self._pointLabelFunc

    def Reset(self):
        """Unzoom the plot."""
        self.last_PointLabel = None  # reset pointLabel
        if self.last_draw is not None:
            self._Draw(self.last_draw[0])

    def ScrollRight(self, units):
        """Move view right number of axis units."""
        self.last_PointLabel = None  # reset pointLabel
        if self.last_draw is not None:
            graphics, xAxis, yAxis = self.last_draw
            xAxis = (xAxis[0] + units, xAxis[1] + units)
            self._Draw(graphics, xAxis, yAxis)

    def ScrollUp(self, units):
        """Move view up number of axis units."""
        self.last_PointLabel = None  # reset pointLabel
        if self.last_draw is not None:
            graphics, xAxis, yAxis = self.last_draw
            yAxis = (yAxis[0] + units, yAxis[1] + units)
            self._Draw(graphics, xAxis, yAxis)

    def GetXY(self, event):
        """Wrapper around _getXY, which handles log scales"""
        x, y = self._getXY(event)
        if self.getLogScale()[0]:
            x = np.power(10, x)
        if self.getLogScale()[1]:
            y = np.power(10, y)
        return x, y

    def _getXY(self, event):
        """Takes a mouse event and returns the XY user axis values."""
        x, y = self.PositionScreenToUser(event.GetPosition())
        return x, y

    def PositionUserToScreen(self, pntXY):
        """Converts User position to Screen Coordinates"""
        userPos = np.array(pntXY)
        x, y = userPos * self._pointScale + self._pointShift
        return x, y

    def PositionScreenToUser(self, pntXY):
        """Converts Screen position to User Coordinates"""
        screenPos = np.array(pntXY)
        x, y = (screenPos - self._pointShift) / self._pointScale
        return x, y

    def SetXSpec(self, type="auto"):
        """xSpec- defines x axis type. Can be 'none', 'min' or 'auto'
        where:
            'none' - shows no axis or tick mark values
            'min' - shows min bounding box values
            'auto' - rounds axis range to sensible values
            <number> - like 'min', but with <number> tick marks
        """
        self._xSpec = type

    def SetYSpec(self, type="auto"):
        """ySpec- defines x axis type. Can be 'none', 'min' or 'auto'
        where:
            'none' - shows no axis or tick mark values
            'min' - shows min bounding box values
            'auto' - rounds axis range to sensible values
            <number> - like 'min', but with <number> tick marks
        """
        self._ySpec = type

    def GetXSpec(self):
        """Returns current XSpec for axis"""
        return self._xSpec

    def GetYSpec(self):
        """Returns current YSpec for axis"""
        return self._ySpec

    @property
    def xSpec(self):
        """Defines the X axis type.

        Default is 'auto'.

        :getter: Returns the value of xSpec.
        :setter: Sets the value of xSpec.
        :type:   str, int, or length-2 sequence of floats
        :raises: `TypeError` if setting an invalid value.

        Valid strings:
        + 'none' - shows no axis or tick mark values
        + 'min' - shows min bounding box values
        + 'auto' - rounds axis range to sensible values

        Other valid values:
        + <number> - like 'min', but with <number> tick marks
        + list or tuple: a list of (min, max) values. Must be length 2.

        .. seealso::
           :attr:`~wx.lib.plot.plotcanvas.PlotCanvas.ySpec`
        """
        return self._xSpec

    @xSpec.setter
    def xSpec(self, value):
        ok_values = ("none", "min", "auto")
        if value not in ok_values and not isinstance(value, (int, float)):
            if not isinstance(value, (list, tuple)) and len(value != 2):
                err_str = (
                    "xSpec must be 'none', 'min', 'auto', "
                    "a number, or sequence of numbers (length 2)"
                )
                raise TypeError(err_str)
        self._xSpec = value

    @property
    def ySpec(self):
        """Defines the Y axis type.

        Default is 'auto'.

        :getter: Returns the value of xSpec.
        :setter: Sets the value of xSpec.
        :type:   str, int, or length-2 sequence of floats
        :raises: `TypeError` if setting an invalid value.

        Valid strings:
        + 'none' - shows no axis or tick mark values
        + 'min' - shows min bounding box values
        + 'auto' - rounds axis range to sensible values

        Other valid values:
        + <number> - like 'min', but with <number> tick marks
        + list or tuple: a list of (min, max) values. Must be length 2.

        .. seealso::
           :attr:`~wx.lib.plot.plotcanvas.PlotCanvas.xSpec`
        """
        return self._ySpec

    @ySpec.setter
    def ySpec(self, value):
        ok_values = ("none", "min", "auto")
        if value not in ok_values and not isinstance(value, (int, float)):
            if not isinstance(value, (list, tuple)) and len(value != 2):
                err_str = (
                    "ySpec must be 'none', 'min', 'auto', "
                    "a number, or sequence of numbers (length 2)"
                )
                raise TypeError(err_str)
        self._ySpec = value

    def GetXMaxRange(self):
        xAxis = self._getXMaxRange()
        if self.getLogScale()[0]:
            xAxis = np.power(10, xAxis)
        return xAxis

    def _getXMaxRange(self):
        """Returns (minX, maxX) x-axis range for displayed graph"""
        graphics = self.last_draw[0]
        p1, p2 = graphics.boundingBox()  # min, max points of graphics
        xAxis = self._axisInterval(self._xSpec, p1[0], p2[0])  # in user units
        return xAxis

    def GetYMaxRange(self):
        yAxis = self._getYMaxRange()
        if self.getLogScale()[1]:
            yAxis = np.power(10, yAxis)
        return yAxis

    def _getYMaxRange(self):
        """Returns (minY, maxY) y-axis range for displayed graph"""
        graphics = self.last_draw[0]
        p1, p2 = graphics.boundingBox()  # min, max points of graphics
        yAxis = self._axisInterval(self._ySpec, p1[1], p2[1])
        return yAxis

    def GetXCurrentRange(self):
        xAxis = self._getXCurrentRange()
        if self.getLogScale()[0]:
            xAxis = np.power(10, xAxis)
        return xAxis

    def _getXCurrentRange(self):
        """Returns (minX, maxX) x-axis for currently displayed portion of graph"""
        return self.last_draw[1]

    def GetYCurrentRange(self):
        yAxis = self._getYCurrentRange()
        if self.getLogScale()[1]:
            yAxis = np.power(10, yAxis)
        return yAxis

    def _getYCurrentRange(self):
        """Returns (minY, maxY) y-axis for currently displayed portion of graph"""
        return self.last_draw[2]

    def Draw(self, graphics, xAxis=None, yAxis=None, dc=None):
        """Wrapper around _Draw, which handles log axes"""

        graphics.setLogScale(self.getLogScale())

        # check Axis is either tuple or none
        if xAxis is not None and not isinstance(xAxis, tuple):
            raise TypeError("xAxis should be None or (minX,maxX)" + str(type(xAxis)))

        if yAxis is not None and not isinstance(yAxis, tuple):
            raise TypeError("yAxis should be None or (minY,maxY)" + str(type(xAxis)))

        # check case for axis = (a,b) where a==b caused by improper zooms
        if xAxis is not None:
            if xAxis[0] == xAxis[1]:
                return
            if self.getLogScale()[0]:
                xAxis = np.log10(xAxis)
        if yAxis is not None:
            if yAxis[0] == yAxis[1]:
                return
            if self.getLogScale()[1]:
                yAxis = np.log10(yAxis)
        self._Draw(graphics, xAxis, yAxis, dc)

    def _Draw(self, graphics, xAxis=None, yAxis=None, dc=None):
        """\
        Draw objects in graphics with specified x and y axis.
        graphics- instance of PlotGraphics with list of PolyXXX objects
        xAxis - tuple with (min, max) axis range to view
        yAxis - same as xAxis
        dc - drawing context - doesn't have to be specified.
        If it's not, the offscreen buffer is used
        """

        if dc is None:
            # sets new dc and clears it
            dc = wx.BufferedDC(wx.ClientDC(self.canvas), self._Buffer)
            bbr = wx.Brush(self.GetBackgroundColour(), wx.SOLID)
            dc.SetBackground(bbr)
            dc.SetBackgroundMode(wx.SOLID)
            dc.Clear()
        if self._antiAliasingEnabled:
            if not isinstance(dc, wx.GCDC):
                try:
                    dc = wx.GCDC(dc)
                except Exception:
                    pass
                else:
                    if self._hiResEnabled:
                        dc.SetMapMode(
                            wx.MM_TWIPS
                        )  # high precision - each logical unit is 1/20 of a point
                    self._pointSize = tuple(
                        1.0 / lscale for lscale in dc.GetLogicalScale()
                    )
                    self._setSize()
        elif self._pointSize != (1.0, 1.0):
            self._pointSize = (1.0, 1.0)
            self._setSize()
        self._fontScale = get_dc_font_scale(dc)
        graphics._pointSize = self._pointSize

        dc.SetTextForeground(self.GetForegroundColour())
        dc.SetTextBackground(self.GetBackgroundColour())

        # dc.Clear()

        # set font size for every thing but title and legend
        dc.SetFont(self._getFont(self._fontSizeAxis))

        # sizes axis to axis type, create lower left and upper right corners of plot
        if xAxis is None or yAxis is None:
            # One or both axis not specified in Draw
            p1, p2 = graphics.boundingBox()  # min, max points of graphics
            if xAxis is None:
                xAxis = self._axisInterval(self._xSpec, p1[0], p2[0])  # in user units
            if yAxis is None:
                yAxis = self._axisInterval(self._ySpec, p1[1], p2[1])
            # Adjust bounding box for axis spec
            p1[0], p1[1] = (
                xAxis[0],
                yAxis[0],
            )  # lower left corner user scale (xmin,ymin)
            p2[0], p2[1] = (
                xAxis[1],
                yAxis[1],
            )  # upper right corner user scale (xmax,ymax)
        else:
            # Both axis specified in Draw
            p1 = np.array(
                [xAxis[0], yAxis[0]]
            )  # lower left corner user scale (xmin,ymin)
            p2 = np.array(
                [xAxis[1], yAxis[1]]
            )  # upper right corner user scale (xmax,ymax)

        self.last_draw = (
            graphics,
            np.array(xAxis),
            np.array(yAxis),
        )  # saves most recient values

        # Get ticks and textExtents for axis if required
        if self._xSpec != "none":
            xticks = self._xticks(xAxis[0], xAxis[1])
        else:
            xticks = None
        if xticks:
            xTextExtent = dc.GetTextExtent(
                xticks[-1][1]
            )  # w h of x axis text last number on axis
        else:
            xTextExtent = (0, 0)  # No text for ticks
        if self._ySpec != "none":
            yticks = self._yticks(yAxis[0], yAxis[1])
        else:
            yticks = None
        if yticks:
            if self.getLogScale()[1]:
                yTextExtent = dc.GetTextExtent("-2e-2")
            else:
                yTextExtentBottom = dc.GetTextExtent(yticks[0][1])
                yTextExtentTop = dc.GetTextExtent(yticks[-1][1])
                yTextExtent = (
                    max(yTextExtentBottom[0], yTextExtentTop[0]),
                    max(yTextExtentBottom[1], yTextExtentTop[1]),
                )
        else:
            yTextExtent = (0, 0)  # No text for ticks

        # TextExtents for Title and Axis Labels
        titleWH, xLabelWH, yLabelWH = self._titleLablesWH(dc, graphics)

        # TextExtents for Legend
        legendBoxWH, legendSymExt, legendTextExt = self._legendWH(dc, graphics)

        # room around graph area
        legend_inside = True
        if legend_inside:
            # Legend inside graph
            x_offset = xTextExtent[0]
        else:
            # Legend outside graph
            x_offset = max(xTextExtent[0], legendBoxWH[0])
        rhsW = (
            x_offset + 5 * self._pointSize[0]
        )  # use larger of number width or legend width
        lhsW = yTextExtent[0] + yLabelWH[1] + 5 * self._pointSize[0]
        bottomH = (
            max(xTextExtent[1], yTextExtent[1] / 2.0)
            + xLabelWH[1]
            + 2 * self._pointSize[1]
        )
        topH = yTextExtent[1] / 2.0 + titleWH[1]
        textSize_scale = np.array(
            [rhsW + lhsW, bottomH + topH]
        )  # make plot area smaller by text size
        textSize_shift = np.array([lhsW, bottomH])  # shift plot area by this amount

        # draw title if requested
        if self._titleEnabled:
            dc.SetFont(self._getFont(self._fontSizeTitle))
            titlePos = (
                self.plotbox_origin[0]
                + lhsW
                + (self.plotbox_size[0] - lhsW - rhsW) / 2.0
                - titleWH[0] / 2.0,
                self.plotbox_origin[1] - self.plotbox_size[1],
            )
            dc.DrawText(graphics.getTitle(), int(titlePos[0]), int(titlePos[1]))

        # draw label text
        self._drawAxesLabels(
            dc, graphics, lhsW, rhsW, bottomH, topH, xLabelWH, yLabelWH
        )

        # allow for scaling and shifting plotted points
        scale = (self.plotbox_size - textSize_scale) / (p2 - p1) * np.array((1, -1))
        shift = -p1 * scale + self.plotbox_origin + textSize_shift * np.array((1, -1))
        self._pointScale = scale / self._pointSize  # make available for mouse events
        self._pointShift = shift / self._pointSize

        # Draw ticks
        if self._ticksEnabled:
            self._drawTicks(dc, p1, p2, scale, shift, xticks, yticks)

        self._drawAxes(dc, p1, p2, scale, shift, xticks, yticks)

        # draw legend makers and text (if outside)
        if self._legendEnabled and not legend_inside:
            self._drawLegend(
                dc, graphics, rhsW, topH, legendBoxWH, legendSymExt, legendTextExt
            )

        graphics.scaleAndShift(scale, shift)
        graphics.setPrinterScale(
            self.printerScale
        )  # thicken up lines and markers if printing

        # set clipping area so drawing does not occur outside axis box
        ptx, pty, rectWidth, rectHeight = self._point2ClientCoord(p1, p2)
        # allow graph to overlap axis lines by adding units to width and height
        dc.SetClippingRegion(
            int(ptx * self._pointSize[0]),
            int(pty * self._pointSize[1]),
            int(rectWidth * self._pointSize[0] + 2),
            int(rectHeight * self._pointSize[1] + 1),
        )
        # Draw extras
        self._drawExtras(dc, p1, p2, scale, shift)
        # Draw the lines and markers
        # start = _time.time()
        graphics.draw(dc)

        # draw legend makers and text (if inside) so that it overlaps graphics
        if self._legendEnabled and legend_inside:
            rhsW += legendBoxWH[0]
            self._drawLegend(
                dc, graphics, rhsW, topH, legendBoxWH, legendSymExt, legendTextExt
            )

        # print "entire graphics drawing took: %f second"%(_time.time() - start)
        # remove the clipping region
        dc.DestroyClippingRegion()

        self._adjustScrollbars()
        if "gtk3" in wx.PlatformInfo:
            self.Refresh()

    def Redraw(self, dc=None):
        """Redraw the existing plot."""
        if self.last_draw is not None:
            graphics, xAxis, yAxis = self.last_draw
            self._Draw(graphics, xAxis, yAxis, dc)

    def Clear(self):
        """Erase the window."""
        self.last_PointLabel = None  # reset pointLabel
        dc = wx.BufferedDC(wx.ClientDC(self.canvas), self._Buffer)
        bbr = wx.Brush(self.GetBackgroundColour(), wx.SOLID)
        dc.SetBackground(bbr)
        dc.SetBackgroundMode(wx.SOLID)
        dc.Clear()
        if self._antiAliasingEnabled:
            try:
                dc = wx.GCDC(dc)
            except Exception:
                pass
        dc.SetTextForeground(self.GetForegroundColour())
        dc.SetTextBackground(self.GetBackgroundColour())
        self.last_draw = None
        if "gtk3" in wx.PlatformInfo:
            self.Refresh()
            self.Update()

    def Zoom(self, Center, Ratio):
        """Zoom on the plot
        Centers on the X,Y coords given in Center
        Zooms by the Ratio = (Xratio, Yratio) given
        """
        self.last_PointLabel = None  # reset maker
        x, y = Center
        if self.last_draw is not None:
            (graphics, xAxis, yAxis) = self.last_draw
            w = (xAxis[1] - xAxis[0]) * Ratio[0]
            h = (yAxis[1] - yAxis[0]) * Ratio[1]
            xAxis = (x - w / 2, x + w / 2)
            yAxis = (y - h / 2, y + h / 2)
            self._Draw(graphics, xAxis, yAxis)

    def GetClosestPoints(self, pntXY, pointScaled=True):
        """Returns list with
        [curveNumber, legend, index of closest point, pointXY, scaledXY, distance]
        list for each curve.
        Returns [] if no curves are being plotted.

        x, y in user coords
        if pointScaled == True based on screen coords
        if pointScaled == False based on user coords
        """
        if self.last_draw is None:
            # no graph available
            return []
        graphics, xAxis, yAxis = self.last_draw
        closest_points = []
        for curveNum, obj in enumerate(graphics):
            # check there are points in the curve
            if len(obj.points) == 0:
                continue  # go to next obj
            # [curveNumber, legend, index of closest point, pointXY, scaledXY, distance]
            cn = (
                [curveNum] + [obj.getLegend()] + obj.getClosestPoint(pntXY, pointScaled)
            )
            closest_points.append(cn)
        return closest_points

    def GetClosestPoint(self, pntXY, pointScaled=True):
        """Returns list with
        [curveNumber, legend, index of closest point, pointXY, scaledXY, distance]
        list for only the closest curve.
        Returns [] if no curves are being plotted.

        x, y in user coords
        if pointScaled == True based on screen coords
        if pointScaled == False based on user coords
        """
        # closest points on screen based on screen scaling (pointScaled= True)
        # list [curveNumber, index, pointXY, scaledXY, distance] for each curve
        closestPts = self.GetClosestPoints(pntXY, pointScaled)
        if not closestPts:
            return []  # no graph present
        # find one with least distance
        dists = [c[-1] for c in closestPts]
        mdist = min(dists)  # Min dist
        i = dists.index(mdist)  # index for min dist
        return closestPts[i]  # this is the closest point on closest curve

    GetClosetPoint = GetClosestPoint

    def UpdatePointLabel(self, mDataDict):
        """Updates the pointLabel point on screen with data contained in
        mDataDict.

        mDataDict will be passed to your function set by
        SetPointLabelFunc.  It can contain anything you
        want to display on the screen at the scaledXY point
        you specify.

        This function can be called from parent window with onClick,
        onMotion events etc.
        """
        if self.last_PointLabel is not None:
            # compare pointXY
            if np.any(mDataDict["pointXY"] != self.last_PointLabel["pointXY"]):
                # closest changed
                self._drawPointLabel(self.last_PointLabel)  # erase old
                self._drawPointLabel(mDataDict)  # plot new
        else:
            # just plot new with no erase
            self._drawPointLabel(mDataDict)  # plot new
        # save for next erase
        self.last_PointLabel = mDataDict

    # event handlers **********************************
    def OnMotion(self, event):
        if self._zoomEnabled and event.LeftIsDown():
            if self._hasDragged:
                self._drawRubberBand(self._zoomCorner1, self._zoomCorner2)  # remove old
            else:
                self._hasDragged = True
            self._zoomCorner2[0], self._zoomCorner2[1] = self._getXY(event)
            self._drawRubberBand(self._zoomCorner1, self._zoomCorner2)  # add new
        elif self._dragEnabled and event.LeftIsDown():
            coordinates = event.GetPosition()
            newpos, oldpos = list(
                map(
                    np.array,
                    list(
                        map(
                            self.PositionScreenToUser,
                            [coordinates, self._screenCoordinates],
                        )
                    ),
                )
            )
            dist = newpos - oldpos
            self._screenCoordinates = coordinates

            if self.last_draw is not None:
                graphics, xAxis, yAxis = self.last_draw
                yAxis -= dist[1]
                xAxis -= dist[0]
                self._Draw(graphics, xAxis, yAxis)

    def OnMouseLeftDown(self, event):
        self._zoomCorner1[0], self._zoomCorner1[1] = self._getXY(event)
        self._screenCoordinates = np.array(event.GetPosition())
        if self._dragEnabled:
            self.SetCursor(self.GrabHandCursor)
            self.canvas.CaptureMouse()

    def OnMouseLeftUp(self, event):
        if self._zoomEnabled:
            if self._hasDragged:
                self._drawRubberBand(self._zoomCorner1, self._zoomCorner2)  # remove old
                self._zoomCorner2[0], self._zoomCorner2[1] = self._getXY(event)
                self._hasDragged = False  # reset flag
                minX, minY = np.minimum(self._zoomCorner1, self._zoomCorner2)
                maxX, maxY = np.maximum(self._zoomCorner1, self._zoomCorner2)
                self.last_PointLabel = None  # reset pointLabel
                if self.last_draw is not None:
                    self._Draw(
                        self.last_draw[0],
                        xAxis=(minX, maxX),
                        yAxis=(minY, maxY),
                        dc=None,
                    )
            # else: # A box has not been drawn, zoom in on a point
            # # this interfered with the double click, so I've disables it.
            #    X,Y = self._getXY(event)
            #    self.Zoom( (X,Y), (self._zoomInFactor,self._zoomInFactor) )
        if self._dragEnabled:
            self.SetCursor(self.HandCursor)
            if self.canvas.HasCapture():
                self.canvas.ReleaseMouse()

    def OnMouseDoubleClick(self, event):
        if self._zoomEnabled:
            # Give a little time for the click to be totally finished
            # before (possibly) removing the scrollbars and trigering
            # size events, etc.
            wx.FutureCall(200, self.Reset)

    def OnMouseRightDown(self, event):
        if self._zoomEnabled:
            X, Y = self._getXY(event)
            self.Zoom((X, Y), (self._zoomOutFactor, self._zoomOutFactor))

    def OnPaint(self, event):
        # All that is needed here is to draw the buffer to screen
        if self.last_PointLabel is not None:
            self._drawPointLabel(self.last_PointLabel)  # erase old
            self.last_PointLabel = None
        dc = wx.BufferedPaintDC(self.canvas, self._Buffer)
        if self._antiAliasingEnabled:
            try:
                dc = wx.GCDC(dc)
            except Exception:
                pass

    def OnSize(self, event):
        # The Buffer init is done here, to make sure the buffer is always
        # the same size as the Window
        Size = self.canvas.GetClientSize()
        Size.width = max(1, Size.width)
        Size.height = max(1, Size.height)

        # Make new offscreen bitmap: this bitmap will always have the
        # current drawing in it, so it can be used to save the image to
        # a file, or whatever.
        self._Buffer = wx.EmptyBitmap(Size.width, Size.height)
        self._setSize()

        self.last_PointLabel = None  # reset pointLabel

        if self.last_draw is None:
            self.Clear()
        else:
            graphics, xSpec, ySpec = self.last_draw
            self._Draw(graphics, xSpec, ySpec)

    def OnLeave(self, event):
        """Used to erase pointLabel when mouse outside window"""
        if self.last_PointLabel is not None:
            self._drawPointLabel(self.last_PointLabel)  # erase old
            self.last_PointLabel = None

    def OnScroll(self, evt):
        if not self._adjustingSB:
            self._sb_ignore = True
            sbpos = evt.GetPosition()

            if evt.GetOrientation() == wx.VERTICAL:
                fullrange, pagesize = (
                    self.sb_vert.GetRange(),
                    self.sb_vert.GetPageSize(),
                )
                sbpos = fullrange - pagesize - sbpos
                dist = sbpos * self._sb_yunit - (
                    self._getYCurrentRange()[0] - self._sb_yfullrange
                )
                self.ScrollUp(dist)

            if evt.GetOrientation() == wx.HORIZONTAL:
                dist = sbpos * self._sb_xunit - (
                    self._getXCurrentRange()[0] - self._sb_xfullrange
                )
                self.ScrollRight(dist)

    # Private Methods **************************************************
    def _setSize(self, width=None, height=None):
        """DC width and height."""
        if width is None:
            (self.width, self.height) = self.canvas.GetClientSize()
        else:
            self.width, self.height = width, height
        self.width *= self._pointSize[0]  # high precision
        self.height *= self._pointSize[1]  # high precision
        self.plotbox_size = 0.97 * np.array([self.width, self.height])
        xo = 0.5 * (self.width - self.plotbox_size[0])
        yo = self.height - 0.5 * (self.height - self.plotbox_size[1])
        self.plotbox_origin = np.array([xo, yo])

    def _setPrinterScale(self, scale):
        """Used to thicken lines and increase marker size for print out."""
        # line thickness on printer is very thin at 600 dot/in. Markers small
        self.printerScale = scale

    def _printDraw(self, printDC):
        """Used for printing."""
        if self.last_draw is not None:
            graphics, xSpec, ySpec = self.last_draw
            self._Draw(graphics, xSpec, ySpec, printDC)

    def _drawPointLabel(self, mDataDict):
        """Draws and erases pointLabels"""
        width = self._Buffer.GetWidth()
        height = self._Buffer.GetHeight()
        tmp_Buffer = self._Buffer.GetSubBitmap((0, 0, width, height))
        dcs = wx.MemoryDC(self._Buffer)
        self._pointLabelFunc(dcs, mDataDict)  # custom user pointLabel function

        dc = wx.ClientDC(self.canvas)
        dc = wx.BufferedDC(dc, self._Buffer)
        # this will erase if called twice
        dc.Blit(0, 0, width, height, dcs, 0, 0, self._logicalFunction)
        self._Buffer = tmp_Buffer
        if "gtk3" in wx.PlatformInfo:
            self.Refresh()
            self.Update()

    def _drawLegend(
        self, dc, graphics, rhsW, topH, legendBoxWH, legendSymExt, legendTextExt
    ):
        """Draws legend symbols and text"""
        # top right hand corner of graph box is ref corner
        trhc = self.plotbox_origin + (
            self.plotbox_size - [rhsW + self._pointSize[0], topH + self._pointSize[1]]
        ) * [1, -1]
        # Draw a 20% transparent box behind legend so that if legend is inside
        # graph it looks nicer on overlap
        dc.SetPen(wx.TRANSPARENT_PEN)
        c = wx.Colour()
        c.Set(
            self.BackgroundColour.red,
            self.BackgroundColour.green,
            self.BackgroundColour.blue,
            204,
        )
        dc.SetBrush(wx.Brush(c))
        spacing = 0.0455 * legendBoxWH[0]
        dc.DrawRectangle(
            int(trhc[0] - spacing),
            int(trhc[1]),
            int(legendBoxWH[0] + spacing),
            int(legendBoxWH[1] + self._pointSize[1] * 2),
        )
        legend_inside = True
        if legend_inside:
            legendLHS = 0
        else:
            legendLHS = (
                0.091 * legendBoxWH[0]
            )  # border space between legend sym and graph box
        lineHeight = (
            max(legendSymExt[1], legendTextExt[1]) * 1.1
        )  # 1.1 used as space between lines
        dc.SetFont(self._getFont(self._fontSizeLegend))
        n = 0
        for o in graphics:
            legend = o.getLegend()
            if not legend:
                continue
            s = n * lineHeight
            n += 1
            if isinstance(o, PolyMarker):
                # draw marker with legend
                pnt = (
                    trhc[0] + legendLHS + legendSymExt[0] / 2.0,
                    trhc[1] + s + lineHeight / 2.0,
                )
                o.draw(dc, self.printerScale, coord=np.array([pnt]))
            elif isinstance(o, PolyLine):
                # draw line with legend
                pnt1 = (trhc[0] + legendLHS, trhc[1] + s + lineHeight / 2.0)
                pnt2 = (
                    trhc[0] + legendLHS + legendSymExt[0],
                    trhc[1] + s + lineHeight / 2.0,
                )
                o.draw(dc, self.printerScale, coord=np.array([pnt1, pnt2]))
            else:
                raise TypeError("object is neither PolyMarker or PolyLine instance")
            # draw legend txt
            pnt = (
                trhc[0] + legendLHS + legendSymExt[0] + 5 * self._pointSize[0],
                trhc[1] + s + lineHeight / 2.0 - legendTextExt[1] / 2,
            )
            dc.DrawText(legend, int(pnt[0]), int(pnt[1]))
        dc.SetFont(self._getFont(self._fontSizeAxis))  # reset

    def _titleLablesWH(self, dc, graphics):
        """Draws Title and labels and returns width and height for each"""
        # TextExtents for Title and Axis Labels
        dc.SetFont(self._getFont(self._fontSizeTitle))
        if self._titleEnabled:
            title = graphics.getTitle()
            titleWH = dc.GetTextExtent(title)
        else:
            titleWH = (0, 0)
        dc.SetFont(self._getFont(self._fontSizeAxis))
        xLabel, yLabel = graphics.getXLabel(), graphics.getYLabel()
        xLabelWH = dc.GetTextExtent(xLabel)
        yLabelWH = dc.GetTextExtent(yLabel)
        return titleWH, xLabelWH, yLabelWH

    def _legendWH(self, dc, graphics):
        """Returns the size in screen units for legend box"""
        txtExt = (0, 0)
        if not self._legendEnabled:
            legendBoxWH = symExt = txtExt
        else:
            # find max symbol size
            symExt = graphics.getSymExtent(self.printerScale)
            # find max legend text extent
            dc.SetFont(self._getFont(self._fontSizeLegend))
            txtList = graphics.getLegendNames()
            for txt in txtList:
                txtExt = np.maximum(txtExt, dc.GetTextExtent(txt))
            maxW = symExt[0] + txtExt[0]
            maxH = max(symExt[1], txtExt[1])
            # padding .1 for lhs of legend box and space between lines
            maxW = maxW * 1.1
            maxH = maxH * 1.1 * len(txtList)
            dc.SetFont(self._getFont(self._fontSizeAxis))
            legendBoxWH = (maxW, maxH)
        return (legendBoxWH, symExt, txtExt)

    def _drawRubberBand(self, corner1, corner2):
        """Draws/erases rect box from corner1 to corner2"""
        ptx, pty, rectWidth, rectHeight = self._point2ClientCoord(corner1, corner2)
        # draw rectangle
        dc = wx.ClientDC(self.canvas)
        dc.SetPen(wx.Pen(wx.BLACK))
        dc.SetBrush(wx.Brush(wx.WHITE, wx.TRANSPARENT))
        dc.SetLogicalFunction(wx.INVERT)
        dc.DrawRectangle(ptx, pty, rectWidth, rectHeight)
        dc.SetLogicalFunction(wx.COPY)
        if "gtk3" in wx.PlatformInfo:
            self.Refresh()
            self.Update()

    def _getFont(self, size):
        """Take font size, adjusts if printing and returns wx.Font"""
        s = size * self.printerScale * self._fontScale
        of = self.GetFont()
        # Linux speed up to get font from cache rather than X font server
        key = (int(s), of.GetFamily(), of.GetStyle(), of.GetWeight(), of.GetFaceName())
        font = self._fontCache.get(key, None)
        if font:
            return font  # yeah! cache hit
        else:
            if "phoenix" in wx.PlatformInfo:
                kwarg = "faceName"
            else:
                kwarg = "face"
            font = wx.Font(
                int(s),
                of.GetFamily(),
                of.GetStyle(),
                of.GetWeight(),
                **{kwarg: of.GetFaceName()},
            )
            self._fontCache[key] = font
            return font

    def _point2ClientCoord(self, corner1, corner2):
        """Converts user point coords to client screen int coords x,y,width,height"""
        c1 = np.array(corner1)
        c2 = np.array(corner2)
        # convert to screen coords
        pt1 = c1 * self._pointScale + self._pointShift
        pt2 = c2 * self._pointScale + self._pointShift
        # make height and width positive
        pul = np.minimum(pt1, pt2)  # Upper left corner
        plr = np.maximum(pt1, pt2)  # Lower right corner
        rectWidth, rectHeight = plr - pul
        ptx, pty = pul
        return ptx, pty, rectWidth, rectHeight

    def _axisInterval(self, spec, lower, upper):
        """Returns sensible axis range for given spec"""
        if spec == "none" or spec == "min" or isinstance(spec, (float, int)):
            if lower == upper:
                return lower - 0.5, upper + 0.5
            else:
                return lower, upper
        elif spec == "auto":
            range = upper - lower
            if range == 0.0:
                return lower - 0.5, upper + 0.5
            log = np.log10(range)
            power = np.floor(log)
            fraction = log - power
            if fraction <= 0.05:
                power = power - 1
            grid = 10.0**power
            lower = lower - lower % grid
            mod = upper % grid
            if mod != 0:
                upper = upper - mod + grid
            return lower, upper
        elif isinstance(spec, tuple):
            lower, upper = spec
            if lower <= upper:
                return lower, upper
            else:
                return upper, lower
        else:
            raise ValueError(str(spec) + ": illegal axis specification")

    def _drawAxes(self, dc, p1, p2, scale, shift, xticks, yticks):
        penWidth = (
            self.printerScale * self._pointSize[0]
        )  # increases thickness for printing only
        dc.SetPen(wx.Pen(self._gridColour, int(penWidth)))

        # set length of tick marks--long ones make grid
        if self._gridEnabled:
            x, y, width, height = self._point2ClientCoord(p1, p2)
            if self._gridEnabled == "Horizontal":
                yTickLength = (width / 2.0 + 1) * self._pointSize[1]
                xTickLength = 3 * self.printerScale * self._pointSize[0]
            elif self._gridEnabled == "Vertical":
                yTickLength = 3 * self.printerScale * self._pointSize[1]
                xTickLength = (height / 2.0 + 1) * self._pointSize[0]
            else:
                yTickLength = (width / 2.0 + 1) * self._pointSize[1]
                xTickLength = (height / 2.0 + 1) * self._pointSize[0]
        else:
            yTickLength = (
                3 * self.printerScale * self._pointSize[1]
            )  # lengthens lines for printing
            xTickLength = 3 * self.printerScale * self._pointSize[0]

        if self._ticksEnabled:
            # get the tick lengths so that labels don't overlap
            xoffset = self.tickLengthScale[0]
            yoffset = self.tickLengthScale[1]
            # only care about negative (out of plot area) tick lengths.
            xoffset = xoffset if xoffset < 0 else 0
            yoffset = yoffset if yoffset < 0 else 0
        else:
            xoffset = yoffset = 0

        if self._xSpec != "none":
            lower, upper = p1[0], p2[0]
            text = 1
            for y, d in [
                (p1[1], -xTickLength),
                (p2[1], xTickLength),
            ]:  # miny, maxy and tick lengths
                for x, label in xticks:
                    w = dc.GetTextExtent(label)[0]
                    pt = scale * np.array([x, y]) + shift
                    dc.DrawLine(
                        int(pt[0]), int(pt[1]), int(pt[0]), int(pt[1] + d)
                    )  # draws tick mark d units
                    if text:
                        dc.DrawText(
                            label,
                            int(pt[0] - w / 2.0),
                            int(pt[1] + 2 * self._pointSize[1] - xoffset),
                        )
                a1 = scale * np.array([lower, y]) + shift
                a2 = scale * np.array([upper, y]) + shift
                dc.DrawLine(
                    int(a1[0]), int(a1[1]), int(a2[0]), int(a2[1])
                )  # draws upper and lower axis line
                text = 0  # axis values not drawn on top side

        if self._ySpec != "none":
            lower, upper = p1[1], p2[1]
            text = 1
            h = dc.GetCharHeight()
            for x, d in [(p1[0], -yTickLength), (p2[0], yTickLength)]:
                for y, label in yticks:
                    w = dc.GetTextExtent(label)[0]
                    pt = scale * np.array([x, y]) + shift
                    dc.DrawLine(int(pt[0]), int(pt[1]), int(pt[0] - d), int(pt[1]))
                    if text:
                        dc.DrawText(
                            label,
                            int(pt[0] - w - 3 * self._pointSize[0] + yoffset),
                            int(pt[1] - 0.5 * h),
                        )
                a1 = scale * np.array([x, lower]) + shift
                a2 = scale * np.array([x, upper]) + shift
                dc.DrawLine(int(a1[0]), int(a1[1]), int(a2[0]), int(a2[1]))
                text = 0  # axis values not drawn on right side

    @TempStyle("pen")
    def _drawTicks(self, dc, p1, p2, scale, shift, xticks, yticks):
        """Draw the tick marks

        :param :class:`wx.DC` `dc`: The :class:`wx.DC` to draw on.
        :type `dc`: :class:`wx.DC`
        :param p1: The lower-left hand corner of the plot in plot coords. So,
                   if the plot ranges from x=-10 to 10 and y=-5 to 5, then
                   p1 = (-10, -5)
        :type p1: :class:`np.array`, length 2
        :param p2: The upper-right hand corner of the plot in plot coords. So,
                   if the plot ranges from x=-10 to 10 and y=-5 to 5, then
                   p2 = (10, 5)
        :type p2: :class:`np.array`, length 2
        :param scale: The [X, Y] scaling factor to convert plot coords to
                      DC coords
        :type scale: :class:`np.array`, length 2
        :param shift: The [X, Y] shift values to convert plot coords to
                      DC coords. Must be in plot units, not DC units.
        :type shift: :class:`np.array`, length 2
        :param xticks: The X tick definition
        :type xticks: list of length-2 lists
        :param yticks: The Y tick definition
        :type yticks: list of length-2 lists
        """
        # TODO: add option for ticks to extend outside of graph
        #       - done via negative ticklength values?
        #           + works but the axes values cut off the ticks.
        # increases thickness for printing only
        pen = self.tickPen
        penWidth = self.printerScale * pen.GetWidth()
        pen.SetWidth(penWidth)
        dc.SetPen(pen)

        # lengthen lines for printing
        xTickLength = self.tickLengthScale[0]
        yTickLength = self.tickLengthScale[1]

        ticks = self.enableTicks
        if self.xSpec != "none":  # I don't like this :-/
            if ticks.bottom:
                lines = []
                for x, _label in xticks:
                    pt = scale_and_shift_point(x, p1[1], scale, shift)
                    lines.append(
                        (int(pt[0]), int(pt[1]), int(pt[0]), int(pt[1] - xTickLength))
                    )
                dc.DrawLineList(lines)
            if ticks.top:
                lines = []
                for x, _label in xticks:
                    pt = scale_and_shift_point(x, p2[1], scale, shift)
                    lines.append(
                        (int(pt[0]), int(pt[1]), int(pt[0]), int(pt[1] + xTickLength))
                    )
                dc.DrawLineList(lines)

        if self.ySpec != "none":
            if ticks.left:
                lines = []
                for y, _label in yticks:
                    pt = scale_and_shift_point(p1[0], y, scale, shift)
                    lines.append(
                        (int(pt[0]), int(pt[1]), int(pt[0] + yTickLength), int(pt[1]))
                    )
                dc.DrawLineList(lines)
            if ticks.right:
                lines = []
                for y, _label in yticks:
                    pt = scale_and_shift_point(p2[0], y, scale, shift)
                    lines.append(
                        (int(pt[0]), int(pt[1]), int(pt[0] - yTickLength), int(pt[1]))
                    )
                dc.DrawLineList(lines)

    def _drawExtras(self, dc, p1, p2, scale, shift):
        b1, b2 = self.last_draw[0].boundingBox()

        if self._centerLinesEnabled:
            x, y = [b1[i] + (b2[i] - b1[i]) / 2.0 for i in range(2)]
            x, y = self.PositionUserToScreen((x, y))
            x, y = x * self._pointSize[0], y * self._pointSize[1]
            if self._centerLinesEnabled in ("Horizontal", True):
                dc.DrawLine(
                    int(scale[0] * p1[0] + shift[0]),
                    int(y),
                    int(scale[0] * p2[0] + shift[0]),
                    int(y),
                )
            if self._centerLinesEnabled in ("Vertical", True):
                dc.DrawLine(
                    int(x),
                    int(scale[1] * p1[1] + shift[1]),
                    int(x),
                    int(scale[1] * p2[1] + shift[1]),
                )

        if self._diagonalsEnabled:
            x1, y1 = self.PositionUserToScreen(b1)
            x1, y1 = x1 * self._pointSize[0], y1 * self._pointSize[1]
            x2, y2 = self.PositionUserToScreen(b2)
            x2, y2 = x2 * self._pointSize[0], y2 * self._pointSize[1]
            if self._diagonalsEnabled in ("Bottomleft-Topright", True):
                dc.DrawLine(int(x1), int(y1), int(x2), int(y2))
            if self._diagonalsEnabled in ("Bottomright-Topleft", True):
                dc.DrawLine(int(x1), int(y2), int(x2), int(y1))

    def _drawAxesLabels(
        self, dc, graphics, lhsW, rhsW, bottomH, topH, xLabelWH, yLabelWH
    ):
        """Draws the axes labels"""
        if self._ticksEnabled:
            # get the tick lengths so that labels don't overlap
            xTickLength = self.tickLengthScale[0]
            yTickLength = self.tickLengthScale[1]
            # only care about negative (out of plot area) tick lengths.
            xTickLength = xTickLength if xTickLength < 0 else 0
            yTickLength = yTickLength if yTickLength < 0 else 0
        else:
            xTickLength = yTickLength = 0

        # TODO: axes values get big when this is turned off
        dc.SetFont(self._getFont(self._fontSizeAxis))
        xLabelPos = (
            self.plotbox_origin[0]
            + lhsW
            + (self.plotbox_size[0] - lhsW - rhsW) / 2.0
            - xLabelWH[0] / 2.0,
            self.plotbox_origin[1] - xLabelWH[1] - yTickLength,
        )
        dc.DrawText(graphics.xLabel, int(xLabelPos[0]), int(xLabelPos[1]))
        yLabelPos = (
            self.plotbox_origin[0] - 1 * self._pointSize[0] + xTickLength,
            self.plotbox_origin[1]
            - bottomH
            - (self.plotbox_size[1] - bottomH - topH) / 2.0
            + yLabelWH[0] / 2.0,
        )
        if graphics.yLabel:  # bug fix for Linux
            dc.DrawRotatedText(
                graphics.yLabel, int(yLabelPos[0]), int(yLabelPos[1]), 90
            )

    def _xticks(self, *args):
        if self._logscale[0]:
            return self._logticks(*args)
        else:
            attr = {"numticks": self._xSpec}
            return self._ticks(*args, **attr)

    def _yticks(self, *args):
        if self._logscale[1]:
            return self._logticks(*args)
        else:
            attr = {"numticks": self._ySpec}
            return self._ticks(*args, **attr)

    def _logticks(self, lower, upper):
        # lower,upper = map(np.log10,[lower,upper])
        # print 'logticks',lower,upper
        ticks = []
        mag = np.power(10, np.floor(lower))
        if upper - lower > 6:
            t = np.power(10, np.ceil(lower))
            base = np.power(10, np.floor((upper - lower) / 6))

            def inc(t):
                return t * base - t

        else:
            t = np.ceil(np.power(10, lower) / mag) * mag

            def inc(t):
                return 10 ** int(np.floor(np.log10(t) + 1e-16))

        majortick = int(np.log10(mag))
        while t <= pow(10, upper):
            if majortick != int(np.floor(np.log10(t) + 1e-16)):
                majortick = int(np.floor(np.log10(t) + 1e-16))
                ticklabel = "1e%d" % majortick
            else:
                if upper - lower < 2:
                    minortick = int(t / pow(10, majortick) + 0.5)
                    ticklabel = "%de%d" % (minortick, majortick)
                else:
                    ticklabel = ""
            ticks.append((np.log10(t), ticklabel))
            t += inc(t)
        if len(ticks) == 0:
            ticks = [(0, "")]
        return ticks

    def _ticks(self, lower, upper, numticks=None):
        if isinstance(numticks, (float, int)):
            ideal = (upper - lower) / float(numticks)
        else:
            ideal = (upper - lower) / 7.0
        log = np.log10(ideal)
        power = np.floor(log)
        if isinstance(numticks, (float, int)):
            grid = ideal
        else:
            fraction = log - power
            factor = 1.0
            error = fraction
            for f, lf in self._multiples:
                e = np.fabs(fraction - lf)
                if e < error:
                    error = e
                    factor = f
            grid = factor * 10.0**power
        if self._useScientificNotation and (power > 4 or power < -4):
            format = "%+7.1e"
        else:
            if ideal > int(ideal):
                fdigits = len(str(round(ideal, 4)).split(".")[-1][:4].rstrip("0"))
            else:
                fdigits = 0
            if power >= 0:
                digits = max(1, int(power))
                format = "%" + repr(digits) + "." + repr(fdigits) + "f"
            else:
                digits = -int(power)
                format = "%" + repr(digits + 2) + "." + repr(fdigits) + "f"
        ticks = []
        t = -grid * np.floor(-lower / grid)
        while t <= upper:
            if t == -0:
                t = 0
            ticks.append((t, format % (t,)))
            t = t + grid
        return ticks

    _multiples = [(2.0, np.log10(2.0)), (5.0, np.log10(5.0))]

    def _adjustScrollbars(self):
        if self._sb_ignore:
            self._sb_ignore = False
            return

        if not self.GetShowScrollbars():
            return

        self._adjustingSB = True
        needScrollbars = False

        # horizontal scrollbar
        r_current = self._getXCurrentRange()
        r_max = list(self._getXMaxRange())
        sbfullrange = float(self.sb_hor.GetRange())

        r_max[0] = min(r_max[0], r_current[0])
        r_max[1] = max(r_max[1], r_current[1])

        self._sb_xfullrange = r_max

        unit = (r_max[1] - r_max[0]) / float(self.sb_hor.GetRange())
        pos = int((r_current[0] - r_max[0]) / unit)

        if pos >= 0:
            pagesize = int((r_current[1] - r_current[0]) / unit)

            self.sb_hor.SetScrollbar(pos, pagesize, sbfullrange, pagesize)
            self._sb_xunit = unit
            needScrollbars = needScrollbars or (pagesize != sbfullrange)
        else:
            self.sb_hor.SetScrollbar(0, 1000, 1000, 1000)

        # vertical scrollbar
        r_current = self._getYCurrentRange()
        r_max = list(self._getYMaxRange())
        sbfullrange = float(self.sb_vert.GetRange())

        r_max[0] = min(r_max[0], r_current[0])
        r_max[1] = max(r_max[1], r_current[1])

        self._sb_yfullrange = r_max

        unit = (r_max[1] - r_max[0]) / sbfullrange
        pos = int((r_current[0] - r_max[0]) / unit)

        if pos >= 0:
            pagesize = int((r_current[1] - r_current[0]) / unit)
            pos = sbfullrange - 1 - pos - pagesize
            self.sb_vert.SetScrollbar(pos, pagesize, sbfullrange, pagesize)
            self._sb_yunit = unit
            needScrollbars = needScrollbars or (pagesize != sbfullrange)
        else:
            self.sb_vert.SetScrollbar(0, 1000, 1000, 1000)

        self.SetShowScrollbars(needScrollbars)
        self._adjustingSB = False


# -------------------------------------------------------------------------------
# Used to layout the printer page


class PlotPrintout(wx.Printout):
    """Controls how the plot is made in printing and previewing"""

    # Do not change method names in this class,
    # we have to override wx.Printout methods here!
    def __init__(self, graph):
        """graph is instance of plotCanvas to be printed or previewed"""
        wx.Printout.__init__(self)
        self.graph = graph

    def HasPage(self, page):
        if page == 1:
            return True
        else:
            return False

    def GetPageInfo(self):
        return (1, 1, 1, 1)  # disable page numbers

    def OnPrintPage(self, page):
        dc = self.GetDC()  # allows using floats for certain functions
        # print "PPI Printer",self.GetPPIPrinter()
        # print "PPI Screen", self.GetPPIScreen()
        # print "DC GetSize", dc.GetSize()
        # print "GetPageSizePixels", self.GetPageSizePixels()
        # Note PPIScreen does not give the correct number
        # Calulate everything for printer and then scale for preview
        PPIPrinter = self.GetPPIPrinter()  # printer dots/inch (w,h)
        # PPIScreen= self.GetPPIScreen()          # screen dots/inch (w,h)
        dcSize = dc.GetSize()  # DC size
        if self.graph._antiAliasingEnabled and not isinstance(dc, wx.GCDC):
            try:
                dc = wx.GCDC(dc)
            except Exception:
                pass
            else:
                if self.graph._hiResEnabled:
                    dc.SetMapMode(
                        wx.MM_TWIPS
                    )  # high precision - each logical unit is 1/20 of a point
        pageSize = self.GetPageSizePixels()  # page size in terms of pixcels
        clientDcSize = self.graph.GetClientSize()

        # find what the margins are (mm)
        margLeftSize, margTopSize = self.graph.pageSetupData.GetMarginTopLeft()
        margRightSize, margBottomSize = self.graph.pageSetupData.GetMarginBottomRight()

        # calculate offset and scale for dc
        pixLeft = margLeftSize * PPIPrinter[0] / 25.4  # mm*(dots/in)/(mm/in)
        pixRight = margRightSize * PPIPrinter[0] / 25.4
        pixTop = margTopSize * PPIPrinter[1] / 25.4
        pixBottom = margBottomSize * PPIPrinter[1] / 25.4

        plotAreaW = pageSize[0] - (pixLeft + pixRight)
        plotAreaH = pageSize[1] - (pixTop + pixBottom)

        # ratio offset and scale to screen size if preview
        if self.IsPreview():
            ratioW = float(dcSize[0]) / pageSize[0]
            ratioH = float(dcSize[1]) / pageSize[1]
            pixLeft *= ratioW
            pixTop *= ratioH
            plotAreaW *= ratioW
            plotAreaH *= ratioH

        # rescale plot to page or preview plot area
        self.graph._setSize(plotAreaW, plotAreaH)

        # Set offset and scale
        dc.SetDeviceOrigin(pixLeft, pixTop)

        # Thicken up pens and increase marker size for printing
        ratioW = float(plotAreaW) / clientDcSize[0]
        ratioH = float(plotAreaH) / clientDcSize[1]
        aveScale = (ratioW + ratioH) / 2
        if self.graph._antiAliasingEnabled and not self.IsPreview():
            scale = dc.GetUserScale()
            dc.SetUserScale(
                scale[0] / self.graph._pointSize[0], scale[1] / self.graph._pointSize[1]
            )
        self.graph._setPrinterScale(aveScale)  # tickens up pens for printing

        self.graph._printDraw(dc)
        # rescale back to original
        self.graph._setSize()
        self.graph._setPrinterScale(1)
        self.graph.Redraw()  # to get point label scale and shift correct

        return True


# ----------------------------------------------------------------------
try:
    from DisplayCAL.embeddedimage import PyEmbeddedImage
except ImportError:
    from wx.lib.embeddedimage import PyEmbeddedImage

MagPlus = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAABHNCSVQICAgIfAhkiAAAAOFJ"
    "REFUeJy1VdEOxCAIo27//8XbuKfuPASGZ0Zisoi2FJABbZM3bY8c13lo5GvbjioBPAUEB0Yc"
    "VZ0iGRRc56Ee8DcikEgrJD8EFpzRegQASiRtBtzuA0hrdRPYQxaEKyJPG6IHyiK3xnNZvUSS"
    "NvUuzgYh0il4y14nCFPk5XgmNbRbQbVotGo9msj47G3UXJ7fuz8Q8FAGEu0/PbZh2D3NoshU"
    "1VUydBGVZKMimlGeErdNGUmf/x7YpjMjcf8HVYvS2adr6aFVlCy/5Ijk9q8SeCR9isJR8SeJ"
    "8pv7S0Wu2Acr0qdj3w7DRAAAAABJRU5ErkJggg=="
)

GrabHand = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAABHNCSVQICAgIfAhkiAAAARFJ"
    "REFUeJy1VdESgzAIS2j//4s3s5fRQ6Rad5M7H0oxCZhWSpK1TjwUBCBJAIBItL1fijlfe1yJ"
    "8noCGC9KgrXO7f0SyZEDAF/H2opsAHv9V/548nplT5Jo7YAFQKQ1RMWzmHUS96suqdBrHkuV"
    "uxpdJjCS8CfGXWdJ2glzcquKSR5c46QOtCpgNyIHj6oieAXg3282QvMX45hy8a8H0VonJZUO"
    "clesjOPg/dhBTq64o1Kacz4Ri2x5RKsf8+wcWQaJJL+A+xRcZHeQeBKjK+5EFiVJ4xy4x2Mn"
    "1Vk4U5/DWmfPieiqbye7a3tV/cCsWKu76K76KUFFchVnhigJ/hmktelm/m3e3b8k+Ec8PqLH"
    "CT4JRfyK9o1xYwAAAABJRU5ErkJggg=="
)

Hand = PyEmbeddedImage(
    "iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAABHNCSVQICAgIfAhkiAAAARBJ"
    "REFUeJytluECwiAIhDn1/Z942/UnjCGoq+6XNeWDC1xAqbKr6zyo61Ibds60J8GBT0yS3IEM"
    "ABuIpJTa4IOLiAAQksuKyixLH1ShHgTgZl8KiALxOsODPoEMkgJ25Su6zoO3ZrjRnI96OLIq"
    "k7dsqOCboDa4XV/nwQEQVeFtmMnvbSJja+oagKBUaLn9hzd7VipRa9ostIv0O1uhzzaqNJxk"
    "hViwDVxqg51kksMg9r2rDDIFwHCap130FBhdMzeAfWg//6Ki5WWQrHSv6EIUeVs0g3wT3J7r"
    "FmWQp/JJDXeRh2TXcJa91zAH2uN2mvXFsrIrsjS8rnftWmWfAiLIStuD9m9h9belvzgS/1fP"
    "X7075IwDENteAAAAAElFTkSuQmCC"
)

# ---------------------------------------------------------------------------
# if running standalone...
#
#     ...a sample implementation using the above
#


def _draw1Objects():
    # 100 points sin function, plotted as green circles
    data1 = 2.0 * np.pi * np.arange(200) / 200.0
    data1.shape = (100, 2)
    data1[:, 1] = np.sin(data1[:, 0])
    markers1 = PolyMarker(
        data1, legend="Green Markers", colour="green", marker="circle", size=1
    )

    # 50 points cos function, plotted as red line
    data1 = 2.0 * np.pi * np.arange(100) / 100.0
    data1.shape = (50, 2)
    data1[:, 1] = np.cos(data1[:, 0])
    lines = PolySpline(data1, legend="Red Line", colour="red")

    # A few more points...
    pi = np.pi
    markers2 = PolyMarker(
        [(0.0, 0.0), (pi / 4.0, 1.0), (pi / 2, 0.0), (3.0 * pi / 4.0, -1)],
        legend="Cross Legend",
        colour="blue",
        marker="cross",
    )

    return PlotGraphics([markers1, lines, markers2], "Graph Title", "X Axis", "Y Axis")


def _draw2Objects():
    # 100 points sin function, plotted as green dots
    data1 = 2.0 * np.pi * np.arange(200) / 200.0
    data1.shape = (100, 2)
    data1[:, 1] = np.sin(data1[:, 0])
    line1 = PolySpline(
        data1, legend="Green Line", colour="green", width=6, style=wx.DOT
    )

    # 50 points cos function, plotted as red dot-dash
    data1 = 2.0 * np.pi * np.arange(100) / 100.0
    data1.shape = (50, 2)
    data1[:, 1] = np.cos(data1[:, 0])
    line2 = PolySpline(
        data1, legend="Red Line", colour="red", width=3, style=wx.DOT_DASH
    )

    # A few more points...
    pi = np.pi
    markers1 = PolyMarker(
        [(0.0, 0.0), (pi / 4.0, 1.0), (pi / 2, 0.0), (3.0 * pi / 4.0, -1)],
        legend="Cross Hatch Square",
        colour="blue",
        width=3,
        size=6,
        fillcolour="red",
        fillstyle=wx.CROSSDIAG_HATCH,
        marker="square",
    )

    return PlotGraphics(
        [markers1, line1, line2], "Big Markers with Different Line Styles"
    )


def _draw3Objects():
    markerList = [
        "circle",
        "dot",
        "square",
        "triangle",
        "triangle_down",
        "cross",
        "plus",
        "circle",
    ]
    m = []
    for i in range(len(markerList)):
        m.append(
            PolyMarker(
                [(2 * i + 0.5, i + 0.5)],
                legend=markerList[i],
                colour="blue",
                marker=markerList[i],
            )
        )
    return PlotGraphics(m, "Selection of Markers", "Minimal Axis", "No Axis")


def _draw4Objects():
    # 25,000 point line
    data1 = np.arange(5e5, 1e6, 10)
    data1.shape = (25000, 2)
    line1 = PolyLine(data1, legend="Wide Line", colour="green", width=5)

    # A few more points...
    markers2 = PolyMarker(data1, legend="Square", colour="blue", marker="square")
    return PlotGraphics([line1, markers2], "25,000 Points", "Value X", "")


def _draw5Objects():
    # Empty graph with axis defined but no points/lines
    points = []
    line1 = PolyLine(points, legend="Wide Line", colour="green", width=5)
    return PlotGraphics([line1], "Empty Plot With Just Axes", "Value X", "Value Y")


def _draw6Objects():
    # Bar graph
    points1 = [(1, 0), (1, 10)]
    line1 = PolyLine(points1, colour="green", legend="Feb.", width=10)
    points1g = [(2, 0), (2, 4)]
    line1g = PolyLine(points1g, colour="red", legend="Mar.", width=10)
    points1b = [(3, 0), (3, 6)]
    line1b = PolyLine(points1b, colour="blue", legend="Apr.", width=10)

    points2 = [(4, 0), (4, 12)]
    line2 = PolyLine(points2, colour="Yellow", legend="May", width=10)
    points2g = [(5, 0), (5, 8)]
    line2g = PolyLine(points2g, colour="orange", legend="June", width=10)
    points2b = [(6, 0), (6, 4)]
    line2b = PolyLine(points2b, colour="brown", legend="July", width=10)

    return PlotGraphics(
        [line1, line1g, line1b, line2, line2g, line2b],
        "Bar Graph - (Turn on Grid, Legend)",
        "Months",
        "Number of Students",
    )


def _draw7Objects():
    # Empty graph with axis defined but no points/lines
    x = np.arange(1, 1000, 1)
    y1 = 4.5 * x**2
    y2 = 2.2 * x**3
    points1 = np.transpose([x, y1])
    points2 = np.transpose([x, y2])
    line1 = PolyLine(points1, legend="quadratic", colour="blue", width=1)
    line2 = PolyLine(points2, legend="cubic", colour="red", width=1)
    return PlotGraphics([line1, line2], "double log plot", "Value X", "Value Y")


class TestFrame(wx.Frame):
    def __init__(self, parent, id, title):
        wx.Frame.__init__(self, parent, id, title, wx.DefaultPosition, (600, 400))

        # Now Create the menu bar and items
        self.mainmenu = wx.MenuBar()

        menu = wx.Menu()
        menu.Append(200, "Page Setup...", "Setup the printer page")
        self.Bind(wx.EVT_MENU, self.OnFilePageSetup, id=200)

        menu.Append(201, "Print Preview...", "Show the current plot on page")
        self.Bind(wx.EVT_MENU, self.OnFilePrintPreview, id=201)

        menu.Append(202, "Print...", "Print the current plot")
        self.Bind(wx.EVT_MENU, self.OnFilePrint, id=202)

        menu.Append(203, "Save Plot...", "Save current plot")
        self.Bind(wx.EVT_MENU, self.OnSaveFile, id=203)

        menu.Append(205, "E&xit", "Enough of this already!")
        self.Bind(wx.EVT_MENU, self.OnFileExit, id=205)
        self.mainmenu.Append(menu, "&File")

        menu = wx.Menu()
        menu.Append(206, "Draw1", "Draw plots1")
        self.Bind(wx.EVT_MENU, self.OnPlotDraw1, id=206)
        menu.Append(207, "Draw2", "Draw plots2")
        self.Bind(wx.EVT_MENU, self.OnPlotDraw2, id=207)
        menu.Append(208, "Draw3", "Draw plots3")
        self.Bind(wx.EVT_MENU, self.OnPlotDraw3, id=208)
        menu.Append(209, "Draw4", "Draw plots4")
        self.Bind(wx.EVT_MENU, self.OnPlotDraw4, id=209)
        menu.Append(210, "Draw5", "Draw plots5")
        self.Bind(wx.EVT_MENU, self.OnPlotDraw5, id=210)
        menu.Append(260, "Draw6", "Draw plots6")
        self.Bind(wx.EVT_MENU, self.OnPlotDraw6, id=260)
        menu.Append(261, "Draw7", "Draw plots7")
        self.Bind(wx.EVT_MENU, self.OnPlotDraw7, id=261)

        menu.Append(211, "&Redraw", "Redraw plots")
        self.Bind(wx.EVT_MENU, self.OnPlotRedraw, id=211)
        menu.Append(212, "&Clear", "Clear canvas")
        self.Bind(wx.EVT_MENU, self.OnPlotClear, id=212)
        menu.Append(213, "&Scale", "Scale canvas")
        self.Bind(wx.EVT_MENU, self.OnPlotScale, id=213)
        menu.Append(214, "Enable &Zoom", "Enable Mouse Zoom", kind=wx.ITEM_CHECK)
        self.Bind(wx.EVT_MENU, self.OnEnableZoom, id=214)
        menu.Append(215, "Enable &Grid", "Turn on Grid", kind=wx.ITEM_CHECK)
        self.Bind(wx.EVT_MENU, self.OnEnableGrid, id=215)
        menu.Append(217, "Enable &Drag", "Activates dragging mode", kind=wx.ITEM_CHECK)
        self.Bind(wx.EVT_MENU, self.OnEnableDrag, id=217)
        menu.Append(220, "Enable &Legend", "Turn on Legend", kind=wx.ITEM_CHECK)
        self.Bind(wx.EVT_MENU, self.OnEnableLegend, id=220)
        menu.Append(
            222, "Enable &Point Label", "Show Closest Point", kind=wx.ITEM_CHECK
        )
        self.Bind(wx.EVT_MENU, self.OnEnablePointLabel, id=222)

        menu.Append(223, "Enable &Anti-Aliasing", "Smooth output", kind=wx.ITEM_CHECK)
        self.Bind(wx.EVT_MENU, self.OnEnableAntiAliasing, id=223)
        menu.Append(
            224,
            "Enable &High-Resolution AA",
            "Draw in higher resolution",
            kind=wx.ITEM_CHECK,
        )
        self.Bind(wx.EVT_MENU, self.OnEnableHiRes, id=224)

        menu.Append(226, "Enable Center Lines", "Draw center lines", kind=wx.ITEM_CHECK)
        self.Bind(wx.EVT_MENU, self.OnEnableCenterLines, id=226)
        menu.Append(
            227, "Enable Diagonal Lines", "Draw diagonal lines", kind=wx.ITEM_CHECK
        )
        self.Bind(wx.EVT_MENU, self.OnEnableDiagonals, id=227)

        menu.Append(231, "Set Gray Background", "Change background colour to gray")
        self.Bind(wx.EVT_MENU, self.OnBackgroundGray, id=231)
        menu.Append(232, "Set &White Background", "Change background colour to white")
        self.Bind(wx.EVT_MENU, self.OnBackgroundWhite, id=232)
        menu.Append(233, "Set Red Label Text", "Change label text colour to red")
        self.Bind(wx.EVT_MENU, self.OnForegroundRed, id=233)
        menu.Append(234, "Set &Black Label Text", "Change label text colour to black")
        self.Bind(wx.EVT_MENU, self.OnForegroundBlack, id=234)

        menu.Append(225, "Scroll Up 1", "Move View Up 1 Unit")
        self.Bind(wx.EVT_MENU, self.OnScrUp, id=225)
        menu.Append(230, "Scroll Rt 2", "Move View Right 2 Units")
        self.Bind(wx.EVT_MENU, self.OnScrRt, id=230)
        menu.Append(235, "&Plot Reset", "Reset to original plot")
        self.Bind(wx.EVT_MENU, self.OnReset, id=235)

        self.mainmenu.Append(menu, "&Plot")

        menu = wx.Menu()
        menu.Append(300, "&About", "About this thing...")
        self.Bind(wx.EVT_MENU, self.OnHelpAbout, id=300)
        self.mainmenu.Append(menu, "&Help")

        self.SetMenuBar(self.mainmenu)

        # A status bar to tell people what's happening
        self.CreateStatusBar(1)

        self.client = PlotCanvas(self)
        # define the function for drawing pointLabels
        self.client.SetPointLabelFunc(self.DrawPointLabel)
        # Create mouse event for showing cursor coords in status bar
        self.client.canvas.Bind(wx.EVT_LEFT_DOWN, self.OnMouseLeftDown)
        # Show closest point when enabled
        self.client.canvas.Bind(wx.EVT_MOTION, self.OnMotion)

        self.Show(True)

    def DrawPointLabel(self, dc, mDataDict):
        """This is the fuction that defines how the pointLabels are plotted
        dc - DC that will be passed
        mDataDict - Dictionary of data that you want to use for the pointLabel

        As an example I have decided I want a box at the curve point
        with some text information about the curve plotted below.
        Any wxDC method can be used.
        """
        # ----------
        dc.SetPen(wx.Pen(wx.BLACK))
        dc.SetBrush(wx.Brush(wx.BLACK, wx.SOLID))

        sx, sy = mDataDict["scaledXY"]  # scaled x,y of closest point
        dc.DrawRectangle(sx - 5, sy - 5, 10, 10)  # 10by10 square centered on point
        px, py = mDataDict["pointXY"]
        cNum = mDataDict["curveNum"]
        pntIn = mDataDict["pIndex"]
        legend = mDataDict["legend"]
        # make a string to display
        s = "Crv# %i, '%s', Pt. (%.2f,%.2f), PtInd %i" % (cNum, legend, px, py, pntIn)
        dc.DrawText(s, int(sx), int(sy + 1))
        # -----------

    def OnMouseLeftDown(self, event):
        s = "Left Mouse Down at Point: (%.4f, %.4f)" % self.client._getXY(event)
        self.SetStatusText(s)
        event.Skip()  # allows plotCanvas OnMouseLeftDown to be called

    def OnMotion(self, event):
        # show closest point (when enbled)
        if self.client.GetEnablePointLabel():
            # make up dict with info for the pointLabel
            # I've decided to mark the closest point on the closest curve
            dlst = self.client.GetClosestPoint(
                self.client._getXY(event), pointScaled=True
            )
            if dlst:  # returns [] if none
                curveNum, legend, pIndex, pointXY, scaledXY, distance = dlst
                # make up dictionary to pass to my user function (see DrawPointLabel)
                mDataDict = {
                    "curveNum": curveNum,
                    "legend": legend,
                    "pIndex": pIndex,
                    "pointXY": pointXY,
                    "scaledXY": scaledXY,
                }
                # pass dict to update the pointLabel
                self.client.UpdatePointLabel(mDataDict)
        event.Skip()  # go to next handler

    def OnFilePageSetup(self, event):
        self.client.PageSetup()

    def OnFilePrintPreview(self, event):
        self.client.PrintPreview()

    def OnFilePrint(self, event):
        self.client.Printout()

    def OnSaveFile(self, event):
        self.client.SaveFile()

    def OnFileExit(self, event):
        self.Close()

    def OnPlotDraw1(self, event):
        self.resetDefaults()
        self.client.Draw(_draw1Objects())

    def OnPlotDraw2(self, event):
        self.resetDefaults()
        self.client.Draw(_draw2Objects())

    def OnPlotDraw3(self, event):
        self.resetDefaults()
        self.client.SetFont(wx.Font(10, wx.SCRIPT, wx.NORMAL, wx.NORMAL))
        self.client.SetFontSizeAxis(20)
        self.client.SetFontSizeLegend(12)
        self.client.SetXSpec("min")
        self.client.SetYSpec("none")
        self.client.Draw(_draw3Objects())

    def OnPlotDraw4(self, event):
        self.resetDefaults()
        drawObj = _draw4Objects()
        self.client.Draw(drawObj)

        # # profile
        # start = _time.time()
        # for x in range(10):
        #    self.client.Draw(drawObj)
        # print "10 plots of Draw4 took: %f sec."%(_time.time() - start)
        # # profile end

    def OnPlotDraw5(self, event):
        # Empty plot with just axes
        self.resetDefaults()
        drawObj = _draw5Objects()
        # make the axis X= (0,5), Y=(0,10)
        # (default with None is X= (-1,1), Y= (-1,1))
        self.client.Draw(drawObj, xAxis=(0, 5), yAxis=(0, 10))

    def OnPlotDraw6(self, event):
        # Bar Graph Example
        self.resetDefaults()
        # self.client.SetEnableLegend(True)   #turn on Legend
        # self.client.SetEnableGrid(True)     #turn on Grid
        self.client.SetXSpec("none")  # turns off x-axis scale
        self.client.SetYSpec("auto")
        self.client.Draw(_draw6Objects(), xAxis=(0, 7))

    def OnPlotDraw7(self, event):
        # log scale example
        self.resetDefaults()
        self.client.setLogScale((True, True))
        self.client.Draw(_draw7Objects())

    def OnPlotRedraw(self, event):
        self.client.Redraw()

    def OnPlotClear(self, event):
        self.client.Clear()

    def OnPlotScale(self, event):
        if self.client.last_draw is not None:
            graphics, xAxis, yAxis = self.client.last_draw
            self.client.Draw(graphics, (1, 3.05), (0, 1))

    def OnEnableZoom(self, event):
        self.client.SetEnableZoom(event.IsChecked())
        self.mainmenu.Check(217, not event.IsChecked())

    def OnEnableGrid(self, event):
        self.client.SetEnableGrid(event.IsChecked())

    def OnEnableDrag(self, event):
        self.client.SetEnableDrag(event.IsChecked())
        self.mainmenu.Check(214, not event.IsChecked())

    def OnEnableLegend(self, event):
        self.client.SetEnableLegend(event.IsChecked())

    def OnEnablePointLabel(self, event):
        self.client.SetEnablePointLabel(event.IsChecked())

    def OnEnableAntiAliasing(self, event):
        self.client.SetEnableAntiAliasing(event.IsChecked())

    def OnEnableHiRes(self, event):
        self.client.SetEnableHiRes(event.IsChecked())

    def OnEnableCenterLines(self, event):
        self.client.SetEnableCenterLines(event.IsChecked())

    def OnEnableDiagonals(self, event):
        self.client.SetEnableDiagonals(event.IsChecked())

    def OnBackgroundGray(self, event):
        self.client.SetBackgroundColour("#CCCCCC")
        self.client.Redraw()

    def OnBackgroundWhite(self, event):
        self.client.SetBackgroundColour("white")
        self.client.Redraw()

    def OnForegroundRed(self, event):
        self.client.SetForegroundColour("red")
        self.client.Redraw()

    def OnForegroundBlack(self, event):
        self.client.SetForegroundColour("black")
        self.client.Redraw()

    def OnScrUp(self, event):
        self.client.ScrollUp(1)

    def OnScrRt(self, event):
        self.client.ScrollRight(2)

    def OnReset(self, event):
        self.client.Reset()

    def OnHelpAbout(self, event):
        from wx.lib.dialogs import ScrolledMessageDialog

        about = ScrolledMessageDialog(self, __doc__, "About...")
        about.ShowModal()

    def resetDefaults(self):
        """Just to reset the fonts back to the PlotCanvas defaults"""
        self.client.SetFont(wx.Font(10, wx.SWISS, wx.NORMAL, wx.NORMAL))
        self.client.SetFontSizeAxis(10)
        self.client.SetFontSizeLegend(7)
        self.client.setLogScale((False, False))
        self.client.SetXSpec("auto")
        self.client.SetYSpec("auto")


def __test():
    class MyApp(wx.App):
        def OnInit(self):
            wx.InitAllImageHandlers()
            frame = TestFrame(None, -1, "PlotCanvas")
            # frame.Show(True)
            self.SetTopWindow(frame)
            return True

    app = MyApp(0)
    app.MainLoop()


if __name__ == "__main__":
    __test()
