"""
First-run screen: shown only when no password has been set yet.
Forces the user to create a password before the app becomes usable.
"""
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget

from app.components.ui_components import BgBox, C, lbl, btn, inp


class FirstRunScreen(Screen):

    def __init__(self, db, **kwargs):
        super().__init__(**kwargs)
        self._db = db
        self._build()

    def _build(self):
        root = BgBox(color=C['bg'], orientation='vertical')
        self.add_widget(root)

        # Centred card
        root.add_widget(Widget())   # top spacer

        card = BgBox(
            color=C['panel'], orientation='vertical',
            size_hint=(None, None), size=(480, 380),
            padding=32, spacing=16,
        )
        # Anchor card horizontally
        anchor = BoxLayout(orientation='horizontal', size_hint_y=None, height=380)
        anchor.add_widget(Widget())
        anchor.add_widget(card)
        anchor.add_widget(Widget())
        root.add_widget(anchor)

        root.add_widget(Widget())   # bottom spacer

        # Card contents
        # Title: slightly smaller and constrained height to avoid clipping
        card.add_widget(lbl('Welcome - Sub-Pro Workstation', bold=True,
                   size='20sp', halign='center', size_hint_y=None, height=44))
        card.add_widget(lbl(
            'No password is set yet.\nCreate a password to continue.',
            size='16sp', color=C['dim'],
        ))

        card.add_widget(lbl('New password', halign='left', size='16sp',
                           size_hint_y=None, height=28))
        self._pw1 = inp(hint='Enter new password', password=True)
        card.add_widget(self._pw1)

        card.add_widget(lbl('Confirm password', halign='left', size='16sp',
                           size_hint_y=None, height=28))
        self._pw2 = inp(hint='Repeat password', password=True)
        self._pw2.bind(on_text_validate=self._on_set)
        card.add_widget(self._pw2)

        self._err = lbl('', color=C['red'], size='15sp',
                        size_hint_y=None, height=28)
        card.add_widget(self._err)

        card.add_widget(btn('Set Password & Continue', on_press=self._on_set,
                           bg=C['green']))

    def _on_set(self, *_):
        pw1 = self._pw1.text
        pw2 = self._pw2.text

        if len(pw1) < 4:
            self._err.text = 'Password must be at least 4 characters.'
            return
        if pw1 != pw2:
            self._err.text = 'Passwords do not match.'
            self._pw2.text = ''
            return

        self._db.set_password(pw1)
        from kivy.app import App
        App.get_running_app().navigate_to('workflow')
