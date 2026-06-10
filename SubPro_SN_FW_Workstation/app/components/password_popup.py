"""Password-entry Popup used to protect Settings and Unlock screens."""
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout

from app.components.ui_components import C, BgBox, lbl, btn, inp


class PasswordPopup(Popup):
    """
    Modal password prompt.

    Parameters
    ----------
    db        : Database instance — used to verify the password hash.
    on_success: Callable with no arguments, called when the correct
                password is entered.
    """

    def __init__(self, db, on_success, **kwargs):
        self._db = db
        self._on_success = on_success

        content = BgBox(
            color=C['panel'], orientation='vertical',
            padding=20, spacing=14,
        )

        content.add_widget(lbl('Enter password', size='20sp', bold=True))

        self._pw_inp = inp(hint='Password', password=True)
        self._pw_inp.bind(on_text_validate=self._check)
        content.add_widget(self._pw_inp)

        self._err_lbl = lbl('', color=C['red'], size='15sp',
                            size_hint_y=None, height=24)
        content.add_widget(self._err_lbl)

        btn_row = BoxLayout(
            orientation='horizontal', size_hint_y=None, height=52, spacing=8,
        )
        btn_row.add_widget(btn('Cancel', on_press=lambda _: self.dismiss(),
                               bg=C['panel']))
        btn_row.add_widget(btn('OK', on_press=self._check))
        content.add_widget(btn_row)

        super().__init__(
            title='Authentication required',
            content=content,
            size_hint=(None, None),
            size=(420, 280),
            separator_color=C['accent'],
            background_color=C['panel'],
            **kwargs,
        )

    def on_open(self):
        self._pw_inp.focus = True

    def _check(self, *_):
        if self._db.check_password(self._pw_inp.text):
            self.dismiss()
            self._on_success()
        else:
            self._err_lbl.text = 'Incorrect password.'
            self._pw_inp.text  = ''
            self._pw_inp.focus = True
