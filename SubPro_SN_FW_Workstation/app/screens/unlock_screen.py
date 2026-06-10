"""
Unlock screen — placeholder for future firmware-side unlock support.

Provides a UI panel for sending an unlock signature to a locked device.
The actual CLI/OCA command is not yet implemented in the firmware; the
button is visible but disabled with a clear explanation.
"""
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget

from app.components.ui_components import BgBox, C, NavBar, btn, inp, lbl, section_hdr


class UnlockScreen(Screen):

    def __init__(self, db, device_service, **kwargs):
        super().__init__(**kwargs)
        self.db = db
        self.device_service = device_service
        self._build()

    def _build(self):
        root = BgBox(color=C['bg'], orientation='vertical')
        self.add_widget(root)

        root.add_widget(NavBar(current='unlock'))

        # Centred card
        root.add_widget(Widget())

        card = BgBox(
            color=C['panel'], orientation='vertical',
            size_hint=(None, None), size=(560, 400),
            padding=32, spacing=16,
        )
        anchor = BoxLayout(orientation='horizontal', size_hint_y=None, height=400)
        anchor.add_widget(Widget())
        anchor.add_widget(card)
        anchor.add_widget(Widget())
        root.add_widget(anchor)

        root.add_widget(Widget())

        # Card contents
        card.add_widget(lbl('Unlock Device', bold=True, size='22sp'))

        card.add_widget(lbl(
            '!  For rework / service use only.\n'
            'Connect the device, enter the unlock signature from Settings,\n'
            'then press Unlock Device.',
            size='15sp', color=C['dim'],
        ))

        card.add_widget(section_hdr('Unlock Signature'))

        sig_row = BoxLayout(size_hint_y=None, height=52, spacing=8)
        self._sig_inp = inp(hint='Unlock signature (configured in Settings)')
        sig_row.add_widget(self._sig_inp)
        card.add_widget(sig_row)

        self._result_lbl = lbl('', size='16sp', size_hint_y=None, height=36)
        card.add_widget(self._result_lbl)

        self._unlock_btn = btn(
            'Unlock Device  [not yet implemented in firmware]',
            bg=C['disabled'],
            disabled=True,
            size_hint_y=None, height=56,
        )
        card.add_widget(self._unlock_btn)

        card.add_widget(lbl(
            'The firmware-side unlock command is pending implementation.\n'
            'This screen will become functional in a future firmware release.',
            size='13sp', color=C['dim'],
        ))

    def on_enter(self, *_):
        self._result_lbl.text = ''
        self._sig_inp.text    = ''
