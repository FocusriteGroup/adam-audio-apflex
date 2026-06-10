"""
History screen — view past units, filter, expand detail, export CSV.
"""
import logging
from datetime import datetime
from pathlib import Path

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from app.components.ui_components import BgBox, C, NavBar, btn, inp, lbl
from app.db.database import Database

logger = logging.getLogger(__name__)

_RESULT_COLOR = {
    'PASS':       C['green'],
    'FAIL':       C['red'],
    'INCOMPLETE': C['dim'],
}

# Column (header_text, size_hint_x)
_COLS = [
    ('Timestamp',  0.17),
    ('Product SN', 0.13),
    ('Variant',    0.07),
    ('FW Found',   0.10),
    ('Flashed',    0.07),
    ('FW Final',   0.10),
    ('Parts',      0.07),
    ('Result',     0.09),
    ('',           0.06),   # detail button
]


class HistoryScreen(Screen):

    def __init__(self, db: Database, **kwargs):
        super().__init__(**kwargs)
        self.db = db
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        root = BgBox(color=C['bg'], orientation='vertical')
        self.add_widget(root)

        root.add_widget(NavBar(current='history'))

        # Filter bar
        fbar = BgBox(
            color=C['nav'], orientation='horizontal',
            size_hint_y=None, height=54, padding=(12, 4), spacing=8,
        )
        fbar.add_widget(lbl('From:', size='15sp', size_hint_x=None, width=46))
        self._from_inp = inp(hint='YYYY-MM-DD',
                            size_hint=(None, None), size=(120, 40))
        fbar.add_widget(self._from_inp)

        fbar.add_widget(lbl('To:', size='15sp', size_hint_x=None, width=28))
        self._to_inp = inp(hint='YYYY-MM-DD',
                          size_hint=(None, None), size=(120, 40))
        fbar.add_widget(self._to_inp)

        fbar.add_widget(lbl('SN:', size='15sp', size_hint_x=None, width=28))
        self._sn_inp = inp(hint='Search...', size_hint=(None, None), size=(150, 40))
        fbar.add_widget(self._sn_inp)

        fbar.add_widget(btn('Apply', on_press=self._load_data,
                           size_hint=(None, None), size=(80, 40)))
        fbar.add_widget(Widget())   # spacer
        fbar.add_widget(btn('Export CSV', on_press=self._export,
                           bg=C['panel'], size_hint=(None, None), size=(120, 40)))
        root.add_widget(fbar)

        # Table area
        table_root = BgBox(color=C['bg'], orientation='vertical',
                          padding=(8, 4), spacing=2)
        root.add_widget(table_root)

        # Header row (fixed, outside scroll)
        table_root.add_widget(self._make_header_row())

        # Scrollable data rows
        self._scroll = ScrollView()
        self._data_box = BgBox(
            color=C['bg'], orientation='vertical',
            size_hint_y=None, spacing=2,
        )
        self._data_box.bind(minimum_height=self._data_box.setter('height'))
        self._scroll.add_widget(self._data_box)
        table_root.add_widget(self._scroll)

        # Status bar
        self._status_lbl = lbl('', size='14sp', color=C['dim'],
                               size_hint_y=None, height=28)
        root.add_widget(self._status_lbl)

    def _make_header_row(self) -> BoxLayout:
        row = BgBox(color=C['panel'], orientation='horizontal',
                   size_hint_y=None, height=36, padding=(4, 0))
        for text, hint in _COLS:
            row.add_widget(lbl(
                text, size='14sp', bold=True, color=C['dim'],
                halign='center', size_hint_x=hint,
            ))
        return row

    def _make_data_row(self, unit: dict, parts_count: int,
                       req_count: int) -> BoxLayout:
        result = unit['result']
        row_color = C['panel'] if unit['id'] % 2 == 0 else C['bg']
        row = BgBox(color=row_color, orientation='horizontal',
                   size_hint_y=None, height=42, padding=(4, 0))

        values = [
            unit['timestamp'][:16],
            unit['product_sn'],
            unit['variant'],
            unit['fw_version_found'] or '-',
            'Yes' if unit['fw_flashed'] else 'No',
            unit['fw_version_final'] or '-',
            f'{parts_count}/{req_count}',
            result,
        ]
        for (_, hint), val in zip(_COLS[:-1], values):
            color = _RESULT_COLOR.get(val, C['text']) if val in _RESULT_COLOR else C['text']
            row.add_widget(lbl(
                val, size='14sp', color=color,
                halign='center', size_hint_x=hint,
            ))

        # Detail button
        _, hint = _COLS[-1]
        detail_btn = btn(
            '>', bg=C['panel'],
            size_hint_x=hint,
            on_press=lambda _, u=unit: self._show_detail(u),
        )
        row.add_widget(detail_btn)
        return row

    # ── Data loading ──────────────────────────────────────────────────────────

    def on_enter(self, *_):
        self._load_data()

    def _load_data(self, *_):
        self._data_box.clear_widgets()
        units = self.db.get_units(
            product_sn_filter=self._sn_inp.text.strip(),
            date_from=self._from_inp.text.strip(),
            date_to=self._to_inp.text.strip(),
        )
        req_count = len([p for p in self.db.get_parts_config() if p['required']])
        for unit in units:
            parts_count = len(self.db.get_parts_for_unit(unit['id']))
            self._data_box.add_widget(
                self._make_data_row(unit, parts_count, req_count))
        self._status_lbl.text = f'{len(units)} record(s) found.'

    # ── Detail popup ──────────────────────────────────────────────────────────

    def _show_detail(self, unit: dict):
        parts = self.db.get_parts_for_unit(unit['id'])
        content = BgBox(color=C['panel'], orientation='vertical',
                       padding=16, spacing=8)
        content.add_widget(lbl(
            f"Product SN: {unit['product_sn']}  -  {unit['variant']}",
            bold=True, size='18sp', size_hint_y=None, height=32,
        ))
        content.add_widget(lbl(
            f"Timestamp: {unit['timestamp']}",
            size='14sp', color=C['dim'], size_hint_y=None, height=24,
        ))
        content.add_widget(lbl(
            f"FW: {unit['fw_version_found']} → {unit['fw_version_final']}"
            f"  {'(flashed)' if unit['fw_flashed'] else '(no change)'}",
            size='15sp', size_hint_y=None, height=28,
        ))
        result_color = _RESULT_COLOR.get(unit['result'], C['text'])
        content.add_widget(lbl(
            f"Result: {unit['result']}",
            bold=True, color=result_color,
            size='17sp', size_hint_y=None, height=30,
        ))

        if parts:
            content.add_widget(lbl(
                'Parts scanned:', halign='left', bold=True,
                size='15sp', size_hint_y=None, height=28,
            ))
            scroll = ScrollView(size_hint_y=None, height=140)
            pbox = BgBox(color=C['bg'], orientation='vertical',
                        size_hint_y=None, spacing=3)
            pbox.bind(minimum_height=pbox.setter('height'))
            for p in parts:
                note = (f'  <- re-assigned from unit #{p["previous_unit_id"]}'
                        if p['previous_unit_id'] else '')
                pbox.add_widget(lbl(
                    f"  {p['part_name']}: {p['part_sn']}{note}",
                    halign='left', size='14sp',
                    size_hint_y=None, height=28,
                ))
            scroll.add_widget(pbox)
            content.add_widget(scroll)

        content.add_widget(btn('Close', on_press=lambda _: popup.dismiss(),
                              bg=C['panel'], size_hint_y=None, height=48))

        popup = Popup(
            title=f"Detail - {unit['product_sn']}",
            content=content,
            size_hint=(None, None), size=(580, 460),
            separator_color=C['accent'],
        )
        popup.open()

    # ── CSV export ────────────────────────────────────────────────────────────

    def _export(self, *_):
        folder = self._ask_folder()
        if not folder:
            self._status_lbl.text  = 'Export cancelled.'
            self._status_lbl.color = C['dim']
            return

        ts  = datetime.now().strftime('%Y%m%d_%H%M%S')
        out = Path(folder) / f'subpro_export_{ts}.csv'
        try:
            self.db.export_csv(
                out,
                product_sn_filter=self._sn_inp.text.strip(),
                date_from=self._from_inp.text.strip(),
                date_to=self._to_inp.text.strip(),
            )
            self._status_lbl.text  = f'Exported -> {out}'
            self._status_lbl.color = C['green']
        except Exception as exc:
            self._status_lbl.text  = f'Export failed: {exc}'
            self._status_lbl.color = C['red']

    @staticmethod
    def _ask_folder() -> str:
        """Open a native Windows folder-picker dialog. Returns '' if cancelled."""
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            folder = filedialog.askdirectory(
                title='Select folder for CSV export')
            root.destroy()
            return folder or ''
        except Exception:
            # tkinter unavailable — fall back to Desktop
            return str(Path.home() / 'Desktop')

