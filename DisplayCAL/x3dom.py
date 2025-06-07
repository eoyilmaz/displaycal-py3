"""Convert VRML files to X3D and HTML using X3DOM.

It includes utilities for parsing VRML, updating color spaces, managing
resources, and handling 3D transformations. The module also supports caching
and embedding resources for efficient processing.
"""

from __future__ import annotations

import http.client
import os
import re
import string
import urllib.error
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING

from DisplayCAL import colormath
from DisplayCAL import localization as lang
from DisplayCAL.config import get_data_path
from DisplayCAL.defaultpaths import CACHE as CACHEPATH
from DisplayCAL.log import safe_print as _safe_print
from DisplayCAL.meta import DOMAIN
from DisplayCAL.options import DEBUG
from DisplayCAL.util_io import GzipFileProper
from DisplayCAL.util_str import StrList, create_replace_function

if TYPE_CHECKING:
    from DisplayCAL.worker import Worker


class VRMLParseError(Exception):
    """Exception raised for errors in the VRML parsing process."""


class Tag:
    """X3D Tag.

    Args:
        tagname (str): The name of the tag.
        **attributes: Optional attributes for the tag.
    """

    def __init__(self, tagname: str, **attributes) -> None:
        self.parent = None
        self.tagname = tagname
        self.children = []
        self.attributes = attributes

    def __str__(self) -> str:
        """Return a string representation of the tag."""
        return self.markup()

    def markup(self, allow_empty_element_tag: bool = False, x3dom: bool = False) -> str:
        """Return the X3D markup for this tag.

        Args:
            allow_empty_element_tag (bool): If True, allows the tag to be
                self-closing. Defaults to False.
            x3dom (bool): If True, generates X3DOM compatible markup.
                Defaults to False.

        Returns:
            str: The X3D markup for this tag.
        """
        markup = [f"<{self.tagname}"]
        attrs = []
        for key in self.attributes:
            value = self.attributes[key]
            value = (
                value.strip()
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("&", "&amp;")
                .replace("'", "&#39;")
            )
            if value in ("FALSE", "TRUE"):
                value = value.lower()
            attrs.append(f"{key}='{value}'")
        if attrs:
            markup.append(" " + " ".join(attrs))
        if not allow_empty_element_tag:
            markup.append(">")
        if self.children:
            if allow_empty_element_tag:
                markup.append(">")
            markup.append("\n")
            for child in self.children:
                markup.extend(
                    f"\t{line}\n"
                    for line in child.markup(
                        allow_empty_element_tag, x3dom
                    ).splitlines()
                )
        if not allow_empty_element_tag or self.children:
            # Not XML, or XML with children
            markup.append(f"</{self.tagname}>\n")
        else:
            # XML, no children
            markup.append("/>")
        if (
            self.tagname == "Material"
            and float(self.attributes.get("transparency", "0").strip())
            not in (0.0, 1.0)
            and x3dom
        ):
            # Fix z-fighting in X3DOM renderer
            markup.append("<DepthMode readOnly='true'></DepthMode>")
        return "".join(markup)

    def append_child(self, child: Tag) -> None:
        """Append a child tag to this tag.

        Args:
            child (Tag): The child tag to append.
        """
        child.parent = self
        self.children.append(child)

    @classmethod
    def ensure_cache_directory(cls, cache_dir: str) -> None:
        """Ensure the cache directory exists.

        Args:
            cache_dir (str): The path to the cache directory.
        """
        if not os.path.isdir(cache_dir):
            _safe_print("Creating cache directory:", cache_dir)
            os.makedirs(cache_dir)

    @classmethod
    def get_resource_from_cache(cls, force: bool, cachefilename: str) -> str:
        """Get resource from cache if available.

        Args:
            force (bool): If True, forces re-download of the resource.
            cachefilename (str): The path to the cached file.

        Returns:
            str: The content of the cached file if it exists, otherwise an
                empty string.
        """
        body = ""
        if not force and os.path.isfile(cachefilename):
            _safe_print("Using cached file:", cachefilename)
            with open(cachefilename, "rb") as cachefile:
                body = cachefile.read()
        return body

    @classmethod
    def request_url_content(cls, url: str) -> bytes:
        """Request content from a URL.

        Args:
            url (str): The URL to fetch content from.

        Returns:
            bytes: The content of the URL if successful, otherwise an empty
                byte string.
        """
        body = b""
        for url_ in [url, url.replace("https://", "http://")]:
            _safe_print("Requesting:", url_)
            try:
                response = urllib.request.urlopen(url_)  # noqa: S310
            except (
                OSError,
                urllib.error.URLError,
                http.client.HTTPException,
            ) as exception:
                _safe_print(exception)
            else:
                body = response.read()
                response.close()
                break
        return body

    @classmethod
    def get_local_resources(cls, basename: str) -> None | bytes:
        """Get local resources.

        Args:
            basename (str): The name of the resource file to fetch.

        Returns:
            None | bytes: The content of the resource file if found,
                otherwise None.
        """
        url = get_data_path(f"x3d-viewer/{basename}")
        if not url:
            _safe_print("Error: Resource not found:", basename)
            return None
        with open(url, "rb") as resource_file:
            return resource_file.read()

    @classmethod
    def get_resource(
        cls, url: str, source: bool = True, force: bool = False, cache: bool = True
    ) -> None | str:
        """Collect resources.

        Args:
            url (str): The URL of the resource to fetch.
            source (bool): If True, returns the resource content,
                otherwise returns the file path.
            force (bool): If True, forces fetching the resource even if
                it is already cached.
            cache (bool): If True, caches the resource locally.

        Returns:
            None | str: The content of the resource if source is True,
                or the file path if source is False. Returns None if the
                resource could not be fetched or is empty.
        """
        baseurl, basename = os.path.split(url)
        # Strip protocol
        cache_uri = re.sub(r"^\w+://", "", baseurl)
        # Strip www
        cache_uri = re.sub(r"^(?:www\.)?", "", cache_uri)
        # domain.com -> com.domain
        domain, path = cache_uri.split("/", 1)
        cache_uri = "/".join([".".join(reversed(domain.split("."))), path])
        # com.domain/path -> com.domain.path
        cache_uri = re.sub(r"^([^/]+)/", "\\1.", cache_uri)
        cache_dir = os.path.join(CACHEPATH, os.path.join(*cache_uri.split("/")))
        cls.ensure_cache_directory(cache_dir)
        cachefilename = os.path.join(cache_dir, basename)
        body = cls.get_resource_from_cache(force, cachefilename)
        if not body.strip():
            body = cls.request_url_content(url)
        if not body.strip():
            # Fallback to local copy
            body = cls.get_local_resources(basename)
        if body.strip():
            if cache and (force or not os.path.isfile(cachefilename)):
                with open(cachefilename, "wb") as cachefile:
                    cachefile.write(body)
            if source and not basename.endswith(".swf"):
                if basename.endswith(".css"):
                    return f"<style>{body}</style>"
                if basename.endswith(".js"):
                    return f"<script>{body}"
                return body
            return "file:///" + str(cachefilename).lstrip("/").replace(os.path.sep, "/")
        _safe_print("Error: Empty document:", url)
        if os.path.isfile(cachefilename):
            _safe_print("Removing", cachefilename)
            os.remove(cachefilename)
        return None

    def html(
        self,
        title: str = "Untitled",
        xhtml: bool = False,
        embed: bool = False,
        force: bool = False,
        cache: bool = True,
    ) -> str:
        """Convert X3D to HTML.

        This will generate HTML5 by default unless you set xhtml=True.

        If embed is True, the X3DOM runtime and X3D viewer will be embedded in
        the HTML (increases filesize considerably).

        Args:
            title (str): The title of the HTML document.
            xhtml (bool): If True, generates XHTML output. Defaults to False.
            embed (bool): If True, embeds the X3DOM runtime in the HTML.
                Defaults to False.
            force (bool): If True, forces re-download of resources. Defaults
                to False.
            cache (bool): If True, caches resources. Defaults to True.

        Returns:
            str: The HTML representation of the tag, including the X3D content
                and necessary resources.
        """
        # Get children of X3D document
        x3d_html = re.sub(r"\s*</?X3D(?:\s+[^>]*)?>\s*", "", self.markup(xhtml, True))
        if not xhtml:
            # Convert uppercase letters at start of tag name to lowercase
            x3d_html = re.sub(
                r"(</?[0-9A-Z]+)", lambda match: match.groups()[0].lower(), x3d_html
            )
        # Indent
        x3d_html = "\n".join(
            ["\t" * 2 + line for line in x3d_html.splitlines()]
        ).lstrip()

        # Get HTML template from cache or online
        html = self.get_resource(
            f"https://{DOMAIN}/x3d-viewer/release/x3d-viewer.html", True, force, cache
        ).decode("utf-8")
        if cache or embed:
            # Update resources in HTML
            restags = re.findall(r"<[^>]+\s+data-fallback-\w+=[^>]*>", html)
            for restag in restags:
                attrname = re.search(r"\s+data-fallback-(\w+)=", restag).groups()[0]
                url = re.search(rf"\s+{attrname}=([\"'])(.+?)\1", restag).groups()[1]
                if url.endswith(".swf") and not cache:
                    continue
                resource = self.get_resource(url, embed, force, cache)
                if not resource:
                    continue
                if embed and not url.endswith(".swf"):
                    html = html.replace(restag, resource)
                else:
                    updated_restag = re.sub(
                        rf"(\s+data-fallback-{attrname}=)([\"']).+?\2",
                        create_replace_function(r"\1\2%s\2", resource),
                        restag,
                    )
                    html = html.replace(restag, updated_restag)
        # Update title
        html = re.sub(
            r"(<title>)[^<]*(</title>)",
            create_replace_function(r"\1%s\2", str(title)),
            html,
        )
        # Insert X3D
        html = html.replace("</x3d>", "\t" + x3d_html + "\n\t\t</x3d>")
        # Finish
        if xhtml:
            html = "<?xml version='1.0' encoding='UTF-8'?>\n" + html
            html = re.sub(r"\s*/>", " />", html)
        else:
            html = re.sub(r"\s*/>", ">", html)
        return html

    def xhtml(self, *args, **kwargs) -> str:
        """Return XHTML representation of the tag.

        Args:
            *args: Positional arguments to pass to the html method.
            **kwargs: Keyword arguments to pass to the html method.
                If `xhtml` is not set, it will be set to True.

        Returns:
            str: The XHTML representation of the tag.
        """
        kwargs["xhtml"] = True
        return self.html(*args, **kwargs)

    def x3d(self) -> str:
        """Return X3D representation of the tag.

        Returns:
            str: The X3D representation of the tag, including the XML
                declaration and DOCTYPE.
        """
        return "\n".join(
            [
                "<?xml version='1.0' encoding='UTF-8'?>",
                '<!DOCTYPE X3D PUBLIC "ISO//Web3D//DTD X3D 3.0//EN" '
                '"http://www.web3d.org/specifications/x3d-3.0.dtd">',
                self.markup(allow_empty_element_tag=True),
            ]
        )


def _attrchk(attribute: bool, token: str, tag: Tag, indent: str) -> bool:
    """Check if the current token is an attribute and update the tag accordingly.

    Args:
        attribute (bool): Whether the current token is an attribute.
        token (str): The current token being processed.
        tag (Tag): The current tag being processed.
        indent (str): The current indentation level for debug output.

    Returns:
        bool: Updated attribute status.
    """
    if attribute:
        if DEBUG and tag.attributes.get(token):
            safe_print(indent, f"attribute {token!r} {tag.attributes[token]!r}")
        attribute = False
    return attribute


def get_vrml_axes(
    xlabel: str = "X",
    ylabel: str = "Y",
    zlabel: str = "Z",
    offsetx: float = 0,
    offsety: float = 0,
    offsetz: float = 0,
    maxx: float = 100,
    maxy: float = 100,
    maxz: float = 100,
    zero: bool = True,
) -> str:
    """Generate VRML axes.

    Args:
        xlabel (str): Label for the X axis.
        ylabel (str): Label for the Y axis.
        zlabel (str): Label for the Z axis.
        offsetx (float): Offset for the X axis.
        offsety (float): Offset for the Y axis.
        offsetz (float): Offset for the Z axis.
        maxx (float): Maximum value for the X axis.
        maxy (float): Maximum value for the Y axis.
        maxz (float): Maximum value for the Z axis.
        zero (bool): If True, adds a label at the origin.

    Returns:
        str: VRML string representing the axes and labels.
    """
    return """# Z axis
        Transform {{
            translation {offsetx:.1f} {offsety:.1f} {offsetz:.1f}
            children [
                Shape {{
                    geometry Box {{ size 2.0 2.0 {maxz:.1f} }}
                    appearance Appearance {{
                        material Material {{ diffuseColor 0.7 0.7 0.7 }}
                    }}
                }}
            ]
        }}
        # Z axis label
        Transform {{
            translation {zlabelx:.1f} {zlabely:.1f} {zlabelz:.1f}
            children [
                Shape {{
                    geometry Text {{
                        string ["{zlabel}"]
                        fontStyle FontStyle {{ family "SANS" style "BOLD" size 10.0 }}
                    }}
                    appearance Appearance {{
                        material Material {{ diffuseColor 0.7 0.7 0.7 }}
                    }}
                }}
            ]
        }}
        # X axis
        Transform {{
            translation {xaxisx:.1f} {offsety:.1f} {xyaxisz:.1f}
            children [
                Shape {{
                    geometry Box {{ size {maxx:.1f} 2.0 2.0 }}
                    appearance Appearance {{
                        material Material {{ diffuseColor 0.7 0.7 0.7 }}
                    }}
                }}
            ]
        }}
        # X axis label
        Transform {{
            translation {xlabelx:.1f} {xlabely:.1f} {xyaxisz:.1f}
            children [
                Shape {{
                    geometry Text {{
                        string ["{xlabel}"]
                        fontStyle FontStyle {{ family "SANS" style "BOLD" size 10.0 }}
                    }}
                    appearance Appearance {{
                        material Material {{ diffuseColor 0.7 0.7 0.7 }}
                    }}
                }}
            ]
        }}
        # Y axis
        Transform {{
            translation {offsetx:.1f} {yaxisy:.1f} {xyaxisz:.1f}
            children [
                Shape {{
                    geometry Box {{ size 2.0 {maxy:.1f} 2.0 }}
                    appearance Appearance {{
                        material Material {{ diffuseColor 0.7 0.7 0.7 }}
                    }}
                }}
            ]
        }}
        # Y axis label
        Transform {{
            translation {ylabelx:.1f} {ylabely:.1f} {xyaxisz:.1f}
            children [
                Shape {{
                    geometry Text {{
                        string ["{ylabel}"]
                        fontStyle FontStyle {{ family "SANS" style "BOLD" size 10.0 }}
                    }}
                    appearance Appearance {{
                        material Material {{ diffuseColor 0.7 0.7 0.7 }}
                    }}
                }}
            ]
        }}
        # Zero
        Transform {{
            translation {zerox:.1f} {zeroy:.1f} {zeroz:.1f}
            children [
                Shape {{
                    geometry Text {{
                        string ["{zerolabel}"]
                        fontStyle FontStyle {{ family "SANS" style "BOLD" size 10.0 }}
                    }}
                    appearance Appearance {{
                        material Material {{ diffuseColor 0.7 0.7 0.7 }}
                    }}
                }}
            ]
        }}""".format(
        **dict(
            list(locals().items())
            + list(
                {
                    "xaxisx": maxx / 2.0 + offsetx,
                    "yaxisy": maxy / 2.0 + offsety,
                    "xyaxisz": offsetz - maxz / 2.0,
                    "zlabelx": offsetx - 10,
                    "zlabely": offsety - 10,
                    "zlabelz": maxz / 2.0 + offsetz + 5,
                    "xlabelx": maxx + offsetx + 5,
                    "xlabely": offsety - 5,
                    "ylabelx": offsetx - 5,
                    "ylabely": maxy + offsety + 5,
                    "zerolabel": "0" if zero else "",
                    "zerox": offsetx - 10,
                    "zeroy": offsety - 10,
                    "zeroz": offsetz - maxz / 2.0 - 5,
                }.items()
            )
        )
    )


def safe_print(*args, **kwargs) -> None:
    """Print to stdout if DEBUG is enabled."""
    if DEBUG:
        _safe_print(*args, **kwargs)


def update_xyz(
    xyz: str,
    colorspace: str = "Luv",
    offsetx: float = 0,
    offsety: float = 0,
    scale: float = 100,
    maxz: float = 100,
) -> str:
    """Update XYZ coordinates to the specified colorspace.

    Args:
        xyz (str): The XYZ coordinates as a string, e.g. "x y z".
        colorspace (str): The target colorspace, e.g. "Luv", "DIN99", etc.
        offsetx (float): Offset for x coordinate.
        offsety (float): Offset for y coordinate.
        scale (float): Scale factor for the coordinates.
        maxz (float): Maximum z value.

    Returns:
        str: The updated coordinates as a string in the specified colorspace.
    """
    x, y, z = [float(v) for v in xyz.split()]
    a, b, L = x, y, z + 50  # noqa: N806
    X, Y, Z = colormath.Lab2XYZ(L, a, b, scale=100)  # noqa: N806
    if colorspace.startswith("DIN99"):
        if colorspace == "DIN99":
            z, x, y = colormath.Lab2DIN99(L, a, b)
        elif colorspace == "DIN99b":
            z, x, y = colormath.Lab2DIN99b(L, a, b)
        elif colorspace == "DIN99c":
            z, x, y = colormath.XYZ2DIN99c(X, Y, Z)
        else:
            z, x, y = colormath.XYZ2DIN99d(X, Y, Z)
        x, y, z = x * scale, y * scale, z / 100.0 * maxz
    elif colorspace == "Luv":
        z, x, y = colormath.XYZ2Luv(X, Y, Z)
    elif colorspace == "Lu'v'":
        L, u_, v_ = colormath.XYZ2Lu_v_(X, Y, Z)  # noqa: N806
        x, y, z = ((u_ + offsetx) * scale, (v_ + offsety) * scale, L / 100.0 * maxz)
    elif colorspace == "xyY":
        x, y, Y = colormath.XYZ2xyY(X, Y, Z)  # noqa: N806
        x, y, z = ((x + offsetx) * scale, (y + offsety) * scale, Y / 100.0 * maxz)
    elif colorspace == "ICtCp":
        I, Ct, Cp = colormath.XYZ2ICtCp(  # noqa: N806
            X / 100.0, Y / 100.0, Z / 100.0, clamp=False
        )
        z, x, y = I * 100, Ct * 100, Cp * 100
    elif colorspace == "IPT":
        I, P, T = colormath.XYZ2IPT(X / 100.0, Y / 100.0, Z / 100.0)  # noqa: N806
        z, x, y = I * 100, P * 100, T * 100
    elif colorspace == "Lpt":
        z, x, y = colormath.XYZ2Lpt(X, Y, Z)
    z -= maxz / 2.0
    return " ".join([f"{v:.6f}" for v in (x, y, z)])


def get_offset_and_scale_from_colorspace(
    colorspace: str, maxxy: float
) -> tuple[float, float, float]:
    """Get offset and scale based on the colorspace.

    Args:
        colorspace (str): The colorspace to determine the offset and scale for.
        maxxy (float): The maximum value for x and y coordinates.

    Returns:
        tuple[float, float, float]: A tuple containing the offset for x, offset
            for y, and scale.
    """
    if colorspace.startswith("DIN99"):
        scale = 1.0
    elif colorspace == "Lu'v'":
        offsetx, offsety = -0.3, -0.3
        scale = maxxy / 0.6
    elif colorspace == "xyY":
        offsetx, offsety = -0.4, -0.4
        scale = maxxy / 0.8
    return offsetx, offsety, scale


def update_point_lists(
    vrml: str,
    colorspace: str,
    offsetx: float,
    offsety: float,
    scale: float,
    maxz: float,
) -> str:
    """Update point lists in VRML.

    Args:
        vrml (str): The VRML content as a string.
        colorspace (str): The target colorspace, e.g. "Luv", "DIN99", etc.
        offsetx (float): Offset for x coordinate.
        offsety (float): Offset for y coordinate.
        scale (float): Scale factor for the coordinates.
        maxz (float): Maximum z value.

    Returns:
        str: The updated VRML content with modified point lists.
    """
    for item in re.findall(r"point\s*\[[^\]]+\]", vrml):
        item = item[:-1].rstrip()
        # Remove comments
        points = re.sub(r"#[^\n\r]*", "", item)
        # Get actual points
        points = re.match(r"point\s*\[(.+)", points, re.S).groups()[0]
        points = points.strip().split(",")
        for i, xyz in enumerate(points):
            xyz = xyz.strip()
            if xyz:
                points[i] = update_xyz(xyz, colorspace, offsetx, offsety, scale, maxz)
        vrml = vrml.replace(
            item,
            "point [{}{}".format(os.linesep, ("," + os.linesep).join(points).rstrip()),
        )
    return vrml


def update_spheres(
    vrml: str,
    colorspace: str = "Luv",
    offsetx: float = 0,
    offsety: float = 0,
    scale: float = 100,
    maxz: float = 100,
) -> str:
    """Update sphere coordinates in VRML.

    Args:
        vrml (str): The VRML content as a string.
        colorspace (str): The target colorspace, e.g. "Luv", "DIN99", etc.
        offsetx (float): Offset for x coordinate.
        offsety (float): Offset for y coordinate.
        scale (float): Scale factor for the coordinates.
        maxz (float): Maximum z value.

    Returns:
        str: The updated VRML content with modified sphere coordinates.
    """
    spheres = re.findall(
        r"Transform\s*\{\s*translation\s+[+\-0-9.]+\s*[+\-0-9.]+\s*[+\-0-9.]+\s+"
        r"children\s*\[\s*Shape\s*\{\s*geometry\s+Sphere\s*\{[^}]*\}\s*"
        r"appearance\s+Appearance\s*\{\s*material\s+"
        r"Material\s*\{[^}]*\}\s*\}\s*\}\s*\]\s*\}",
        vrml,
    )
    for sphere in spheres:
        coords = re.search(
            r"translation\s+([+\-0-9.]+\s+[+\-0-9.]+\s+[+\-0-9.]+)", sphere
        )
        if not coords:
            continue
        vrml = vrml.replace(
            sphere,
            sphere.replace(
                coords.group(),
                "translation {}".format(
                    update_xyz(
                        coords.groups()[0],
                        colorspace,
                        offsetx,
                        offsety,
                        scale,
                        maxz,
                    )
                ),
            ),
        )
    return vrml


def update_vrml_for_din99(
    vrml: str,
    colorspace: str,
    offsetx: float,
    offsety: float,
    scale: float,
    maxz: float
) -> str:
    """Update VRML for DIN99 colorspace.

    Args:
        vrml (str): The VRML content as a string.
        colorspace (str): The target colorspace, e.g. "DIN99", "DIN99b", etc.
        offsetx (float): Offset for x coordinate.
        offsety (float): Offset for y coordinate.
        scale (float): Scale factor for the coordinates.
        maxz (float): Maximum z value.

    Returns:
        str: The modified VRML content with DIN99 specific adjustments.
    """
    # Remove * from L*a*b* and add range

    # Pristine Argyll CMS VRML
    vrml = re.sub(r'(string\s*\[")(\+?)(L)\*("\])', r'\1\3", "\2\0$\4', vrml)
    vrml = vrml.replace("\0$", "100")
    vrml = re.sub(r'(string\s*\[")([+\-]?)(a)\*("\])', r'\1\3", "\2\0$\4', vrml)
    vrml = re.sub(r'(string\s*\[")([+\-]?)(b)\*("\])', r"\1\3 \2\0$\4", vrml)

    # DisplayCAL tweaked VRML created by worker.Worker.calculate_gamut()
    vrml = re.sub(
        r'(string\s*\["a)\*",\s*"([+\-]?)\d+("\])', r'\1", "\2\0$\3', vrml
    )
    vrml = re.sub(r'(string\s*\["b)\*\s+([+\-]?)\d+("\])', r"\1 \2\0$\3", vrml)

    vrml = vrml.replace("\0$", f"{round(100.0 / scale)}")

    # Add colorspace information
    return re.sub(
        r"(Viewpoint\s*\{[^}]+\})",
        rf"""\1
Transform {{
translation {maxz + offsetx:.6f} {maxz + offsety:.6f} {-maxz / 2.0:.6f}
children [
    Shape {{
        geometry Text {{
            string ["{colorspace}"]
            fontStyle FontStyle {{ family "SANS" style "BOLD" size 10.0 }}
        }}
        appearance Appearance {{
            material Material {{ diffuseColor 0.7 0.7 0.7 }}
        }}
    }}
]
}}""",
        vrml,
    )


def update_vrml_for_luv(vrml: str) -> str:
    """Update VRML for Luv colorspace.

    Args:
        vrml (str): The VRML content as a string.

    Returns:
        str: The modified VRML content with Luv specific adjustments.
    """
    # Replace a* b* labels with u* v*
    vrml = re.sub(r'(string\s*\["[+\-]?)a(\*)', r"\1u\2", vrml)
    vrml = re.sub(r'(string\s*\["[+\-]?)b(\*)', r"\1v\2", vrml)


def update_vrml_for_luv_and_xyy(
    vrml: str,
    colorspace: str,
    offsetx: float,
    offsety: float,
    scale: float,
    maxxy: float,
    maxz: float
) -> str:
    """Update VRML for Luv and xyY colorspaces.

    Args:
        vrml (str): The VRML content as a string.
        colorspace (str): The target colorspace, e.g. "Luv", "xyY".
        offsetx (float): Offset for x coordinate.
        offsety (float): Offset for y coordinate.
        scale (float): Scale factor for the coordinates.
        maxxy (float): Maximum value for x and y coordinates.
        maxz (float): Maximum z value.

    Returns:
        str: The modified VRML content with Luv and xyY specific adjustments.
    """
    # Remove axes
    vrml = re.sub(
        r"Transform\s*\{\s*translation\s+[+\-0-9.]+\s*[+\-0-9.]+\s*[+\-0-9.]+\s+"
        r"children\s*\[\s*Shape\s*\{\s*geometry\s+Box\s*\{[^}]*\}\s*appearance\s+"
        r"Appearance\s*\{\s*material\s+Material\s*\{[^}]*\}\s*\}\s*\}\s*\]\s*\}",
        "",
        vrml,
    )
    # Remove axis labels
    vrml = re.sub(
        r"Transform\s*\{\s*translation\s+[+\-0-9.]+\s*[+\-0-9.]+\s*[+\-0-9.]+\s+"
        r"children\s*\[\s*Shape\s*\{\s*geometry\s+Text\s*\{\s*"
        r"string\s*\[[^\]]*\]\s*fontStyle\s+FontStyle\s*\{[^}]*\}\s*\}\s*"
        r"appearance\s+Appearance\s*\{\s*material\s+"
        r"Material\s*{[^}]*\}\s*\}\s*\}\s*\]\s*\}",
        "",
        vrml,
    )
    # Add new axes + labels
    if colorspace == "Lu'v'":
        xlabel, ylabel, zlabel = "u' 0.6", "v' 0.6", "L* 100"
    else:
        xlabel, ylabel, zlabel = "x 0.8", "y 0.8", "Y 100"
    return re.sub(
        r"(Viewpoint\s*\{[^}]+\})",
        r"\1\n"
        + get_vrml_axes(
            xlabel,
            ylabel,
            zlabel,
            offsetx * scale,
            offsety * scale,
            0,
            maxxy,
            maxxy,
            maxz,
        ),
        vrml,
    )


def update_vrml_for_ictcp(vrml: str) -> str:
    """Update VRML for ICtCp colorspace.

    Args:
        vrml (str): The VRML content as a string.

    Returns:
        str: The modified VRML content with ICtCp specific adjustments.
    """
    # Replace L* a* b* labels with I Ct Cp
    vrml = re.sub(r'(string\s*\["[+\-]?)L\*?', r"\1I", vrml)
    vrml = re.sub(r'(string\s*\["[+\-]?)a\*?', r"\1Ct", vrml)
    vrml = re.sub(r'(string\s*\["[+\-]?)b\*?', r"\1Cp", vrml)
    # Change axis colors
    axes = re.findall(
        r"Shape\s*\{\s*geometry\s*(?:Box|Text)\s*\{\s*(?:"
        r'size\s+\d+\.0+\s+\d+\.0+\s+\d+\.0+|string\s+\["[^"]*"\]\s*'
        r"fontStyle\s+FontStyle\s*\{[^}]+\})\s*\}\s*appearance\s+"
        r"Appearance\s*\{\s*material\s*Material\s*\{[^}]+}\s*\}\s*\}",
        vrml,
    )
    for axis in axes:
        # Red -> purpleish blue
        vrml = vrml.replace(
            axis,
            re.sub(
                r"diffuseColor\s+1\.0+\s+0\.0+\s+0\.0+",
                "diffuseColor 0.5 0.0 1.0",
                axis,
            ),
        )
        # Green -> yellowish green
        vrml = vrml.replace(
            axis,
            re.sub(
                r"diffuseColor\s+0\.0+\s+1\.0+\s+0\.0+",
                "diffuseColor 0.8 1.0 0.0",
                axis,
            ),
        )
        # Yellow -> magentaish red
        vrml = vrml.replace(
            axis,
            re.sub(
                r"diffuseColor\s+1\.0+\s+1\.0+\s+0\.0+",
                "diffuseColor 1.0 0.0 0.25",
                axis,
            ),
        )
        # Blue -> cyan
        vrml = vrml.replace(
            axis,
            re.sub(
                r"diffuseColor\s+0\.0+\s+0\.0+\s+1\.0+",
                "diffuseColor 0.0 1.0 1.0",
                axis,
            ),
        )


def update_vrml_for_ipt(vrml: str) -> str:
    """Update VRML for IPT colorspace.

    Args:
        vrml (str): The VRML content as a string.

    Returns:
        str: The modified VRML content with IPT specific adjustments.
    """
    # Replace L* a* b* labels with I P T
    vrml = re.sub(r'(string\s*\["[+\-]?)L\*?', r"\1I", vrml)
    vrml = re.sub(r'(string\s*\["[+\-]?)a\*?', r"\1P", vrml)
    return re.sub(r'(string\s*\["[+\-]?)b\*?', r"\1T", vrml)


def update_vrml_for_lpt(vrml: str) -> str:
    """Update VRML for Lpt colorspace.

    Args:
        vrml (str): The VRML content as a string.

    Returns:
        str: The modified VRML content with Lpt specific adjustments.
    """
    # Replace a* b* labels with p* t*
    vrml = re.sub(r'(string\s*\["[+\-]?)a\*?', r"\1p", vrml)
    return re.sub(r'(string\s*\["[+\-]?)b\*?', r"\1t", vrml)



def update_vrml(vrml: str, colorspace: str) -> str:
    """Update color and axes in VRML.

    Args:
        vrml (str): The VRML content as a string.
        colorspace (str): The target colorspace, e.g. "Luv", "DIN99", etc.

    Returns:
        str: The updated VRML content as a string.
    """
    offsetx, offsety = 0, 0
    maxz = scale = 100
    maxxy = 200
    offsetx, offsety, scale = get_offset_and_scale_from_colorspace(colorspace, maxxy)

    # Update point lists
    vrml = update_point_lists(vrml, colorspace, offsetx, offsety, scale, maxz)

    # Update spheres
    vrml = update_spheres(vrml, colorspace, offsetx, offsety, scale, maxz)

    if colorspace.startswith("DIN99"):
        vrml = update_vrml_for_din99(vrml, colorspace, offsetx, offsety, scale, maxz)
    elif colorspace == "Luv":
        vrml = update_vrml_for_luv(vrml)
    elif colorspace in ("Lu'v'", "xyY"):
        vrml = update_vrml_for_luv_and_xyy(
            vrml, colorspace, offsetx, offsety, scale, maxxy, maxz
        )
    elif colorspace == "ICtCp":
        vrml = update_vrml_for_ictcp(vrml)
    elif colorspace == "IPT":
        vrml = update_vrml_for_ipt(vrml)
    elif colorspace == "Lpt":
        vrml = update_vrml_for_lpt(vrml)
    return vrml


def vrml2x3dom(vrml: str, worker: None | Worker = None) -> Tag:
    """Convert VRML to X3D.

    Args:
        vrml (str): The VRML content as a string.
        worker (None | Worker): Optional worker instance for progress updates.

    Raises:
        VRMLParseError: If there is an error in the VRML parsing process.

    Returns:
        Tag: The root X3D tag containing the converted VRML content.
    """
    x3d = Tag(
        "X3D",
        **{
            "xmlns:xsd": "http://www.w3.org/2001/XMLSchema-instance",
            "profile": "Immersive",
            "version": "3.0",
            "xsd:noNamespaceSchemaLocation": "http://www.web3d.org/specifications/x3d-3.0.xsd",
        },
    )
    tag = Tag("Scene")
    x3d.append_child(tag)
    token = ""
    attribute = False
    quote = 0
    listing = False
    # Remove comments
    vrml = re.sub(r"#[^\n\r]*", "", vrml)
    # <class> <Token> { -> <Token> {
    vrml = re.sub(r"\w+[ \t]+(\w+\s*\{)", "\\1", vrml)
    # Remove commas
    vrml = re.sub(r",\s*", " ", vrml)
    indent = ""
    maxi = len(vrml) - 1.0
    lastprogress = 0
    for i, c in enumerate(vrml):
        curprogress = int(i / maxi * 100)
        if worker:
            if curprogress > lastprogress:
                worker.lastmsg.write(f"{curprogress}%\n")
            if getattr(worker, "thread_abort", False):
                return False
        if curprogress > lastprogress:
            lastprogress = curprogress
            end = None if curprogress < 100 else "\n"
            _safe_print.write(f"\r{curprogress}%", end=end)
        validate_character(c)
        tag, token, attribute, quote, listing, indent = parse_vrml_character(
            c, tag, token, attribute, quote, listing, indent
        )
    return x3d


def validate_character(c: str) -> None:
    """Validate a character in the VRML content.

    Args:
        c (str): The character to validate.

    Raises:
        VRMLParseError: If the character is invalid.
    """
    if ord(c) < 32 and c not in "\n\r\t":
        raise VRMLParseError(f"Parse error: Got invalid character {c!r}")


def parse_vrml_character(
    c: str,
    tag: Tag,
    token: str,
    attribute: bool,
    quote: int,
    listing: bool,
    indent: str,
) -> tuple[Tag, str, bool, int, bool, str]:
    """Parse a character in the VRML content.

    Args:
        c (str): The character to parse.
        tag (Tag): The current tag being processed.
        token (str): The current token being built.
        attribute (bool): Whether the current token is an attribute.
        quote (int): The number of quotes encountered.
        listing (bool): Whether we are currently in a listing context.
        indent (str): The current indentation level for debug output.

    Raises:
        VRMLParseError: If there is an error in the parsing process.

    Returns:
        tuple[Tag, str, bool, int, bool, str]: Updated tag, token, attribute,
            quote count, listing status, and indentation.
    """
    valid_token_chars = string.ascii_letters + string.digits + "_"
    if c == "{":
        tag, token, attribute, indent = start_new_tag(tag, token, indent)
    elif c == "}":
        tag, token, attribute, indent = end_new_tag(tag, token, attribute, indent)
    elif c == "[":
        listing = True if log_listing_token(token, indent) else listing
    elif c == "]":
        token, attribute, listing = reset_token_and_attribute(
            tag, token, attribute, indent
        )
    elif attribute:
        tag, token, attribute, quote, listing, indent = parse_attribute_value(
            c, tag, token, attribute, quote, listing, indent
        )
    elif c not in " \n\r\t":
        if c in valid_token_chars:
            token += c
        else:
            raise VRMLParseError(f"Parse error: Got invalid character {c!r}")
    elif token:
        tag, token, attribute = handle_token(c, tag, token, attribute)
    return tag, token, attribute, quote, listing, indent


def start_new_tag(tag: Tag, token: str, indent: str) -> tuple[Tag, str, bool, str]:
    """Start a new tag in the VRML content.

    Args:
        tag (Tag): The current tag being processed.
        token (str): The current token being built.
        indent (str): The current indentation level for debug output.

    Returns:
        tuple[Tag, str, bool, str]: Updated tag, token, attribute status,
            and indentation.
    """
    safe_print(indent, f"start tag {token!r}")
    indent += "  "
    attribute = False
    validate_token(token)
    child = Tag(token)
    tag.append_child(child)
    tag = child
    token = ""
    return tag, token, attribute, indent


def end_new_tag(
    tag: Tag, token: str, attribute: bool, indent: str
) -> tuple[Tag, str, bool, str]:
    """End the current tag in the VRML content.

    Args:
        tag (Tag): The current tag being processed.
        token (str): The current token being built.
        attribute (bool): Whether the current token is an attribute.
        indent (str): The current indentation level for debug output.

    Returns:
        tuple[Tag, str, bool, str]: Updated tag, token, attribute status,
            and indentation.
    """
    attribute = _attrchk(attribute, token, tag, indent)
    indent = indent[:-2]
    safe_print(indent, f"end tag {tag.tagname!r}")
    if tag.parent:
        tag = tag.parent
    else:
        raise VRMLParseError("Parse error: Stray '}'")
    token = ""
    return tag, token, attribute, indent


def log_listing_token(token: str, indent: str) -> bool:
    """Log the listing token if it is not empty.

    Args:
        token (str): The current token being processed.
        indent (str): The current indentation level for debug output.

    Returns:
        bool: True if the token is not empty, False otherwise.
    """
    if token:
        safe_print(indent, f"listing {token!r}")
        return True
    return False


def reset_token_and_attribute(
    tag: Tag, token: str, attribute: bool, indent: str
) -> tuple[str, bool, bool]:
    """Reset the token and attribute status after a listing.

    Args:
        tag (Tag): The current tag being processed.
        token (str): The current token being built.
        attribute (bool): Whether the current token is an attribute.
        indent (str): The current indentation level for debug output.

    Returns:
        tuple[str, bool, bool]: Updated token, attribute status, and listing status.
    """
    attribute = _attrchk(attribute, token, tag, indent)
    token = ""
    listing = False
    return token, attribute, listing


def parse_attribute_value(
    c: str,
    tag: Tag,
    token: str,
    attribute: bool,
    quote: int,
    listing: bool,
    indent: str,
) -> tuple[Tag, str, bool, int, bool, str]:
    """Parse a character as part of an attribute value.

    Notes:
        - Handles special cases for whitespace, newlines, and quoted values.
        - Specifically checks for the "style" attribute in "FontStyle" tags to
          handle quotes differently.
        - Uses a helper function '_attrchk' to finalize attribute values when
          appropriate.
        - Assumes 'StrList' is a custom list-like class for attribute value
          storage.

    Args:
        c (str): The current character being parsed.
        tag (Tag): A Tag instange whose attributes are being updated.
        token (str): The current attribute name being processed.
        attribute (bool): The current attribute state.
        quote (int): Counter for quote characters to determine quoted attribute
            values.
        listing (bool): Flag indicating if the parser is in a listing mode
            (affects whitespace handling).
        indent (str): Current indentation as str.

    Returns:
        tuple[Tag, str, bool, int, bool, str]: Updated (tag, token, attribute,
            quote, listing, indent) after processing the character.
    """
    if c in "\n\r":
        if listing:
            if tag.attributes.get(token) and tag.attributes[token][-1] != " ":
                tag.attributes[token] += " "
        else:
            attribute = _attrchk(attribute, token, tag, indent)
            token = ""
    else:
        if token not in tag.attributes:
            tag.attributes[token] = StrList()
        if not (c.strip() or tag.attributes[token]):
            return tag, token, attribute, quote, listing, indent
        if c == '"':
            quote += 1
        if (c != '"' or tag.tagname != "FontStyle" or token != "style") and (
            c != " " or (tag.attributes[token] and tag.attributes[token][-1] != " ")
        ):
            tag.attributes[token] += c
        if quote == 2:
            if not listing:
                attribute = _attrchk(attribute, token, tag, indent)
                token = ""
            quote = 0
    return tag, token, attribute, quote, listing, indent


def validate_token(token: str) -> None:
    """Validate a token in the VRML content.

    Args:
        token (str): The token to validate.

    Raises:
        VRMLParseError: If the token is invalid.
    """
    if token:
        if token[0] not in string.ascii_letters:
            raise VRMLParseError("Invalid token", token)
    else:
        raise VRMLParseError("Parse error: Empty token")


def handle_token(
    c: str, tag: Tag, token: str, attribute: bool
) -> tuple[Tag, str, bool]:
    """Handle a token in the VRML content.

    Args:
        c (str): The current character being processed.
        tag (Tag): The current tag being processed.
        token (str): The current token being built.
        attribute (bool): Whether the current token is an attribute.

    Returns:
        tuple[Tag, str, bool]: Updated tag, token, and attribute status.
    """
    validate_token(token)
    if token == "children":
        token = ""
    elif c in " \t" and not attribute:
        attribute = True
        if token in tag.attributes:
            # Overwrite existing attribute
            tag.attributes[token] = StrList()
    return tag, token, attribute


def vrmlfile2x3dfile(
    vrmlpath: str,
    x3dpath: str,
    html: bool = True,
    embed: bool = False,
    force: bool = False,
    cache: bool = True,
    worker: None | Worker = None,
) -> bool:
    """Convert VRML file located at vrmlpath to HTML and write to x3dpath.

    Args:
        vrmlpath (str): Path to the VRML file.
        x3dpath (str): Path where the X3D file will be written.
        html (bool): If True, generates HTML output. Defaults to True.
        embed (bool): If True, embeds the X3DOM runtime in the HTML. Defaults
            to False.
        force (bool): If True, forces re-download of resources. Defaults to
            False.
        cache (bool): If True, caches resources. Defaults to True.
        worker (None | Worker): Optional worker instance for progress updates.

    Returns:
        bool: True if conversion was successful, False if aborted or an error
            occurred.
    """
    filename, ext = os.path.splitext(vrmlpath)
    reader = open
    if ext.lower() in (".gz", ".wrz"):
        reader = GzipFileProper

    with reader(vrmlpath, "rb") as vrmlfile:
        vrml = vrmlfile.read()

    if isinstance(vrml, bytes):
        vrml = vrml.decode("utf-8")

    if worker:
        worker.recent.write(
            "{} {}\n".format(lang.getstr("converting"), os.path.basename(vrmlpath))
        )
    _safe_print(lang.getstr("converting"), vrmlpath)
    filename, ext = os.path.splitext(x3dpath)
    try:
        x3d = vrml2x3dom(vrml, worker)
        if not x3d:
            _safe_print(lang.getstr("aborted"))
            return False
        if not html:
            _safe_print("Writing", x3dpath)
            with open(x3dpath, "w") as x3dfile:
                x3dfile.write(x3d.x3d())
        else:
            html = x3d.html(
                title=os.path.basename(filename), embed=embed, force=force, cache=cache
            )
            _safe_print("Writing", f"{x3dpath}.html")
            with open(f"{x3dpath}.html", "w") as htmlfile:
                htmlfile.write(html)
    except KeyboardInterrupt:
        x3d = False
    except VRMLParseError as exception:
        return exception
    except OSError as exception:
        return exception
    except Exception as exception:
        import traceback

        _safe_print(traceback.format_exc())
        return exception
    return True
