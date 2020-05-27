from qgis.PyQt.Qt import QTextDocument
from qgis.PyQt.QtGui import QFont, QPainter
from qgis.PyQt.QtCore import QPoint
from qgis.gui import QgsMapCanvas


class CopyrightDecorator:

    def __init__(self, canvas: QgsMapCanvas, text: str,
                 position='bottom-right',
                 font='Sans Serif',
                 fontsize=13,
                 color='#444444'):
        self._canvas = canvas
        self._text = text
        self._position = position
        self._font = font
        self._fontsize = fontsize
        self._color = color
        self._lambda_function = None

    def add_to_canvas(self):
        self._lambda_function = lambda p: self._on_render_complete(p)
        self._canvas.renderComplete.connect(self._lambda_function)
        self._canvas.refresh()

    def remove_from_canvas(self):
        self._canvas.renderComplete.disconnect(self._lambda_function)
        self._canvas.refresh()

    def _make_copyright_textdocument(self) -> QTextDocument:
        text = QTextDocument()
        font = QFont()
        font.setFamily(self._font)
        font.setPointSize(self._fontsize)
        text.setDefaultFont(font)
        style = "<style type=\"text/css\"> p {color: " + \
            self._color + "}</style>"
        text.setHtml(style + "<p>" + self._text + "</p>")
        return text

    def _on_render_complete(self, p: QPainter):
        pos_x, pos_y = self._calc_positon(p)
        p.translate(pos_x, pos_y)
        text = self._make_copyright_textdocument()
        text.drawContents(p)

    def _calc_positon(self, p: QPainter):
        display_zoom_ratio = self._canvas.mapSettings().devicePixelRatio()
        canvas_width = p.device().width() / display_zoom_ratio
        canvas_height = p.device().height() / display_zoom_ratio

        text_size = self._make_copyright_textdocument().size()

        if self._position == 'top-left':
            return (0, 0)
        elif self._position == 'top-right':
            return (canvas_width - text_size.width(), 0)
        elif self._position == 'bottom-left':
            return (0, canvas_height - text_size.height())
        elif self._position == 'bottom-right':
            return (canvas_width - text_size.width(),
                    canvas_height - text_size.height())
        else:
            print('selected position', + self._position + 'is invalid.')
            return (0, 0)
