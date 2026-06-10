"""
Shared Kivy styling constants and helper widgets.

Import everything from here rather than duplicating color/font values
across screen files.
"""
from kivy.graphics import Color, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

# ── Color palette ─────────────────────────────────────────────────────────────
C = {
    'bg':       (0.12, 0.12, 0.12, 1),
    'nav':      (0.07, 0.07, 0.07, 1),
    'panel':    (0.19, 0.19, 0.19, 1),
    'panel2':   (0.23, 0.23, 0.23, 1),
    'input':    (0.27, 0.27, 0.27, 1),
    'accent':   (0.18, 0.52, 0.92, 1),
    'green':    (0.06, 0.72, 0.20, 1),
    'red':      (0.85, 0.12, 0.12, 1),
    'text':     (0.95, 0.95, 0.95, 1),
    'dim':      (0.52, 0.52, 0.52, 1),
    'disabled': (0.30, 0.30, 0.30, 1),
}


# ── BgBox ─────────────────────────────────────────────────────────────────────

class BgBox(BoxLayout):
    """BoxLayout with a solid background colour drawn on canvas.before."""

    def __init__(self, color=None, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*(color or C['bg']))
            self._rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        self._rect.pos  = self.pos
        self._rect.size = self.size


# ── Helper factory functions ───────────────────────────────────────────────────

def lbl(text: str, size: str = '18sp', color=None, bold: bool = False,
        halign: str = 'center', valign: str = 'middle', **kw) -> Label:
    w = Label(
        text=text, font_size=size,
        color=color or C['text'],
        bold=bold, halign=halign, valign=valign,
        **kw,
    )
    w.bind(size=lambda i, v: setattr(i, 'text_size', v))
    return w


def btn(text: str, on_press=None, bg=None, disabled: bool = False,
        **kw) -> Button:
    b = Button(
        text=text,
        background_normal='',
        background_color=bg or C['accent'],
        color=C['text'],
        font_size='18sp',
        disabled=disabled,
        **kw,
    )
    if on_press:
        b.bind(on_press=on_press)
    return b


def inp(hint: str = '', password: bool = False, on_submit=None,
        **kw) -> TextInput:
    defaults = dict(
        hint_text=hint,
        multiline=False,
        password=password,
        background_color=C['input'],
        foreground_color=C['text'],
        hint_text_color=C['dim'],
        cursor_color=C['text'],
        font_size='20sp',
        size_hint_y=None,
        height=48,
    )
    defaults.update(kw)
    t = TextInput(**defaults)
    if on_submit:
        t.bind(on_text_validate=on_submit)
    return t


def section_hdr(text: str) -> BgBox:
    """Darker bar used as a section header inside settings panels."""
    box = BgBox(
        color=C['panel2'], orientation='horizontal',
        size_hint_y=None, height=36, padding=(10, 0),
    )
    box.add_widget(lbl(text, bold=True, halign='left', size='16sp'))
    return box


def spacer(h: int = 12) -> Widget:
    return Widget(size_hint_y=None, height=h)


# ── NavBar ────────────────────────────────────────────────────────────────────

class NavBar(BgBox):
    """
    Persistent top navigation bar.

    Parameters
    ----------
    current : str
        Name of the currently active screen ('workflow' | 'settings' |
        'unlock' | 'history'). The matching button is highlighted and
        disabled.
    session_active : bool
        When True, Settings and Unlock buttons are grayed out to prevent
        accidental navigation during an active scan session.
    """

    _NAV_ITEMS = [
        ('Home',     'workflow', False),
        ('History',  'history',  False),
        ('Unlock',   'unlock',   True),
        ('Settings', 'settings', True),
    ]

    def __init__(self, current: str = 'workflow',
                 session_active: bool = False, **kwargs):
        super().__init__(
            color=C['nav'], orientation='horizontal',
            size_hint_y=None, height=56,
            padding=(16, 6), spacing=8,
            **kwargs,
        )
        self._current = current
        self._session_active = session_active
        self._build()

    def _build(self):
        title = lbl(
            '[b]ADAM AUDIO[/b]   Sub-Pro Workstation',
            markup=True, size='17sp', halign='left', size_hint_x=0.45,
        )
        self.add_widget(title)
        self.add_widget(Widget())   # flexible spacer

        for label, screen_name, needs_pw in self._NAV_ITEMS:
            is_current  = (self._current == screen_name)
            is_disabled = is_current or (self._session_active and needs_pw)
            b = Button(
                text=label,
                size_hint=(None, 1), width=110,
                background_normal='',
                background_color=C['accent'] if is_current else C['disabled'] if is_disabled else C['panel'],
                color=C['text'],
                font_size='15sp',
                disabled=is_disabled,
            )
            if not is_disabled:
                b.bind(on_press=lambda _, s=screen_name, p=needs_pw:
                       self._navigate(s, p))
            self.add_widget(b)

    @staticmethod
    def _navigate(screen_name: str, needs_pw: bool):
        from kivy.app import App
        App.get_running_app().navigate_to(screen_name, require_password=needs_pw)
