# -*- coding: utf-8 -*-
from DisplayCAL.wxwindows import fancytext_RenderToRenderer


def test_fancytext_render_to_renderer():
    """Testing DisplayCAL.wxwindows.fancytext_RenderToRenderer()"""

    class FakeRenderer:
        def __init__(self):
            self.startElement = None
            self.endElement = None
            self.characterData = None

    renderer = FakeRenderer()
    some_test_str = "some_str_"
    fancytext_RenderToRenderer(some_test_str, renderer, enclose=True)
