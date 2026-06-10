"""
Settings screen — password-protected, three tabs:

  1. Device & Firmware  — device name, golden samples, FW config
  2. Parts              — configure the parts list + prefixes + required flag
  3. Change Password    — update the app password
"""
import logging

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.checkbox import CheckBox
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.widget import Widget

from app.components.ui_components import BgBox, C, NavBar, btn, inp, lbl, section_hdr, spacer
from app.db.database import Database
from app.services.device_service import DeviceService

logger = logging.getLogger(__name__)


class SettingsScreen(Screen):

    def __init__(self, db: Database, device_service: DeviceService, **kwargs):
        super().__init__(**kwargs)
        self.db = db
        self.device_service = device_service
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        root = BgBox(color=C['bg'], orientation='vertical')
        self.add_widget(root)

        root.add_widget(NavBar(current='settings'))

        tabs = TabbedPanel(do_default_tab=False, tab_width=220, tab_height=44)
        tabs.background_color = C['panel']

        self._tab1 = TabbedPanelItem(text='Device & Firmware')
        self._tab2 = TabbedPanelItem(text='Parts')
        self._tab3 = TabbedPanelItem(text='Change Password')

        tabs.add_widget(self._tab1)
        tabs.add_widget(self._tab2)
        tabs.add_widget(self._tab3)

        # Build tab contents (populated in on_enter to pick up latest DB values)
        self._tab1.add_widget(self._build_device_tab())
        self._tab2.add_widget(self._build_parts_tab())
        self._tab3.add_widget(self._build_password_tab())

        Clock.schedule_once(lambda _: setattr(tabs, 'default_tab', self._tab1))
        root.add_widget(tabs)

    # ── Tab 1: Device & Firmware ───────────────────────────────────────────────

    def _build_device_tab(self) -> ScrollView:
        scroll = ScrollView()
        layout = BgBox(
            color=C['bg'], orientation='vertical',
            size_hint_y=None, padding=20, spacing=10,
        )
        layout.bind(minimum_height=layout.setter('height'))

        # Device name
        layout.add_widget(section_hdr('Device'))
        layout.add_widget(spacer(4))
        row, self._device_name_inp = self._field_row('Device Name:', '')
        layout.add_widget(row)
        layout.add_widget(lbl(
            'Used for all OCA/mDNS calls (e.g. "SubPro")',
            size='13sp', color=C['dim'], halign='left', size_hint_y=None, height=22,
        ))

        # Golden samples — A8S
        layout.add_widget(spacer(8))
        layout.add_widget(section_hdr('Golden Samples - A8S  (CI prefix)'))
        self._gs_a8s_layout = BgBox(
            color=C['bg'], orientation='vertical',
            size_hint_y=None, spacing=3,
        )
        self._gs_a8s_layout.bind(minimum_height=self._gs_a8s_layout.setter('height'))
        layout.add_widget(self._gs_a8s_layout)
        # Add-new row
        add_a8s = BoxLayout(size_hint_y=None, height=50, spacing=8)
        self._new_a8s_sn   = inp(hint='CI... serial number')
        self._new_a8s_note = inp(hint='Note (optional)')
        add_a8s.add_widget(self._new_a8s_sn)
        add_a8s.add_widget(self._new_a8s_note)
        add_a8s.add_widget(btn(
            '+ Add', bg=C['green'],
            size_hint_x=None, width=90,
            on_press=lambda _: self._add_gs(
                'A8S', self._new_a8s_sn, self._new_a8s_note),
        ))
        layout.add_widget(add_a8s)

        # Golden samples — A10S
        layout.add_widget(spacer(8))
        layout.add_widget(section_hdr('Golden Samples - A10S  (CJ prefix)'))
        self._gs_a10s_layout = BgBox(
            color=C['bg'], orientation='vertical',
            size_hint_y=None, spacing=3,
        )
        self._gs_a10s_layout.bind(minimum_height=self._gs_a10s_layout.setter('height'))
        layout.add_widget(self._gs_a10s_layout)
        add_a10s = BoxLayout(size_hint_y=None, height=50, spacing=8)
        self._new_a10s_sn   = inp(hint='CJ... serial number')
        self._new_a10s_note = inp(hint='Note (optional)')
        add_a10s.add_widget(self._new_a10s_sn)
        add_a10s.add_widget(self._new_a10s_note)
        add_a10s.add_widget(btn(
            '+ Add', bg=C['green'],
            size_hint_x=None, width=90,
            on_press=lambda _: self._add_gs(
                'A10S', self._new_a10s_sn, self._new_a10s_note),
        ))
        layout.add_widget(add_a10s)

        # Firmware
        layout.add_widget(spacer(8))
        layout.add_widget(section_hdr('Firmware'))
        layout.add_widget(spacer(4))
        row_fw, self._target_fw_inp = self._field_row('Target Version:', '')
        layout.add_widget(row_fw)
        row_bin, self._fw_bin_inp = self._field_row('Firmware .bin path:', '')
        layout.add_widget(row_bin)
        layout.add_widget(lbl(
            'Relative to the Audio-Precision repo root, e.g. '
            '"SubsProFirmware/subpro-firmware-for-updating.bin"',
            size='13sp', color=C['dim'], halign='left', size_hint_y=None, height=22,
        ))

        # Save
        layout.add_widget(spacer(12))
        self._dev_save_lbl = lbl('', size='15sp', color=C['green'],
                                 size_hint_y=None, height=28)
        layout.add_widget(self._dev_save_lbl)
        layout.add_widget(btn('Save', on_press=self._save_device_tab, bg=C['green'],
                              size_hint_y=None, height=52))
        layout.add_widget(spacer(20))

        scroll.add_widget(layout)
        return scroll

    def _field_row(self, label_text: str, value: str):
        row = BoxLayout(size_hint_y=None, height=52, spacing=10)
        row.add_widget(lbl(
            label_text, halign='left', valign='middle',
            size_hint_x=None, width=180,
        ))
        text_inp = inp(hint=label_text)
        text_inp.text = value
        row.add_widget(text_inp)
        return row, text_inp

    def _gs_row(self, gs: dict, variant: str) -> BoxLayout:
        row = BgBox(
            color=C['panel'], orientation='horizontal',
            size_hint_y=None, height=46, padding=(6, 0), spacing=8,
        )
        row.add_widget(lbl(gs['serial_number'], halign='left', size='15sp',
                          size_hint_x=None, width=120))
        row.add_widget(lbl(gs['note'] or '-', halign='left', size='14sp',
                          color=C['dim']))
        row.add_widget(btn(
            'Remove', bg=C['red'],
            size_hint_x=None, width=90,
            on_press=lambda _, gid=gs['id']: self._remove_gs(gid, variant),
        ))
        return row

    # ── Tab 2: Parts ──────────────────────────────────────────────────────────

    def _build_parts_tab(self) -> BgBox:
        root = BgBox(color=C['bg'], orientation='vertical', padding=16, spacing=8)

        # Column header — must mirror the column layout of _make_part_row()
        hdr = BoxLayout(size_hint_y=None, height=36, padding=(4, 0), spacing=6)
        hdr.add_widget(lbl('Name', size='15sp', color=C['dim'],
                          halign='left', size_hint_x=0.28))
        hdr.add_widget(lbl('Prefix A8S', size='15sp', color=C['dim'],
                          halign='left', size_hint_x=0.15))
        hdr.add_widget(lbl('Prefix A10S', size='15sp', color=C['dim'],
                          halign='left', size_hint_x=0.15))
        hdr.add_widget(lbl('Req?', size='15sp', color=C['dim'],
                          halign='center', size_hint_x=None, width=40))
        hdr.add_widget(lbl('', size_hint_x=None, width=90))
        root.add_widget(hdr)

        # Scrollable rows
        scroll = ScrollView()
        self._parts_rows_layout = BgBox(
            color=C['bg'], orientation='vertical',
            size_hint_y=None, spacing=3,
        )
        self._parts_rows_layout.bind(
            minimum_height=self._parts_rows_layout.setter('height'))
        scroll.add_widget(self._parts_rows_layout)
        root.add_widget(scroll)

        # Add-new row
        root.add_widget(section_hdr('Add New Part'))
        add_row = BoxLayout(size_hint_y=None, height=52, spacing=6)
        self._new_part_name   = inp(hint='Part name')
        self._new_part_pa8s   = inp(hint='A8S prefix', size_hint_x=None, width=110)
        self._new_part_pa10s  = inp(hint='A10S prefix', size_hint_x=None, width=110)
        self._new_part_req    = CheckBox(active=True, size_hint_x=None, width=40)
        add_row.add_widget(self._new_part_name)
        add_row.add_widget(self._new_part_pa8s)
        add_row.add_widget(self._new_part_pa10s)
        add_row.add_widget(lbl('Req?', size='14sp', size_hint_x=None, width=36))
        add_row.add_widget(self._new_part_req)
        add_row.add_widget(btn('+ Add Part', bg=C['green'],
                               on_press=self._add_part,
                               size_hint_x=None, width=110))
        root.add_widget(add_row)

        # Status + Save
        self._parts_save_lbl = lbl('', size='15sp', color=C['green'],
                                   size_hint_y=None, height=28)
        root.add_widget(self._parts_save_lbl)
        root.add_widget(btn('Save All Changes', on_press=self._save_parts,
                           bg=C['green'], size_hint_y=None, height=52))

        return root

    def _make_part_row(self, part: dict) -> tuple:
        """Return (row_widget, dict of input refs) for one part."""
        row = BgBox(color=C['panel'], orientation='horizontal',
                   size_hint_y=None, height=50, padding=(4, 0), spacing=6)
        name_inp  = inp(hint='Name')
        name_inp.text = part['name']
        name_inp.size_hint_x = 0.28
        pa8s_inp  = inp(hint='A8S prefix')
        pa8s_inp.text = part['prefix_a8s']
        pa8s_inp.size_hint_x = 0.15
        pa10s_inp = inp(hint='A10S prefix')
        pa10s_inp.text = part['prefix_a10s']
        pa10s_inp.size_hint_x = 0.15
        req_cb = CheckBox(active=bool(part['required']),
                         size_hint_x=None, width=40)
        rm_btn = btn('Remove', bg=C['red'],
                    size_hint_x=None, width=90,
                    on_press=lambda _, pid=part['id']: self._remove_part(pid))
        row.add_widget(name_inp)
        row.add_widget(pa8s_inp)
        row.add_widget(pa10s_inp)
        row.add_widget(req_cb)
        row.add_widget(rm_btn)
        return row, {'id': part['id'], 'name': name_inp,
                     'prefix_a8s': pa8s_inp, 'prefix_a10s': pa10s_inp,
                     'required': req_cb}

    # ── Tab 3: Change Password ────────────────────────────────────────────────

    def _build_password_tab(self) -> BgBox:
        root = BgBox(color=C['bg'], orientation='vertical', padding=40, spacing=14)
        root.add_widget(Widget())

        card = BgBox(
            color=C['panel'], orientation='vertical',
            size_hint=(None, None), size=(460, 340),
            padding=28, spacing=14,
        )
        anchor = BoxLayout(orientation='horizontal', size_hint_y=None, height=340)
        anchor.add_widget(Widget())
        anchor.add_widget(card)
        anchor.add_widget(Widget())
        root.add_widget(anchor)
        root.add_widget(Widget())

        card.add_widget(lbl('Change Password', bold=True, size='20sp'))
        card.add_widget(lbl('Current password', halign='left', size='15sp',
                           size_hint_y=None, height=26))
        self._cur_pw   = inp(hint='Current password', password=True)
        card.add_widget(self._cur_pw)
        card.add_widget(lbl('New password', halign='left', size='15sp',
                           size_hint_y=None, height=26))
        self._new_pw   = inp(hint='New password', password=True)
        card.add_widget(self._new_pw)
        card.add_widget(lbl('Confirm new password', halign='left', size='15sp',
                           size_hint_y=None, height=26))
        self._conf_pw  = inp(hint='Repeat new password', password=True)
        self._conf_pw.bind(on_text_validate=self._change_password)
        card.add_widget(self._conf_pw)

        self._pw_msg = lbl('', size='15sp', size_hint_y=None, height=28)
        card.add_widget(self._pw_msg)
        card.add_widget(btn('Update Password', on_press=self._change_password,
                           bg=C['accent']))
        return root

    # ── Data helpers ──────────────────────────────────────────────────────────

    def _refresh_device_tab(self):
        self._device_name_inp.text = self.db.get_config('device_name', '')
        self._target_fw_inp.text   = self.db.get_config('target_fw_version', '')
        self._fw_bin_inp.text      = self.db.get_config('fw_bin_path', '')
        self._refresh_gs_list('A8S',  self._gs_a8s_layout)
        self._refresh_gs_list('A10S', self._gs_a10s_layout)

    def _refresh_gs_list(self, variant: str, container):
        container.clear_widgets()
        for gs in self.db.get_golden_samples(variant):
            container.add_widget(self._gs_row(gs, variant))
        if not container.children:
            container.add_widget(lbl('No golden samples configured yet.',
                                    size='14sp', color=C['dim'],
                                    size_hint_y=None, height=36))

    def _refresh_parts_tab(self):
        self._parts_rows_layout.clear_widgets()
        self._part_refs = []
        for part in self.db.get_parts_config():
            row, refs = self._make_part_row(part)
            self._parts_rows_layout.add_widget(row)
            self._part_refs.append(refs)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _field_error(self, text_inp, message: str):
        """Show a validation error inside an input field's hint area."""
        text_inp.text = ''
        text_inp.hint_text = message
        text_inp.hint_text_color = C['red']
        text_inp.focus = True

    def _add_gs(self, variant: str, sn_inp, note_inp):
        sn   = sn_inp.text.strip().upper()
        note = note_inp.text.strip()
        if not sn:
            return

        from app.services import sn_validator as snv

        # Full SN format check
        ok, err = snv.validate_sn(sn)
        if not ok:
            self._field_error(sn_inp, err)
            return

        # Variant / prefix consistency: A8S -> CI, A10S -> CJ
        sn_variant = snv.get_product_variant(sn)
        if sn_variant != variant:
            expected_prefix = 'CI' if variant == 'A8S' else 'CJ'
            self._field_error(
                sn_inp,
                f'{sn[:2]} is not a {variant} serial '
                f'(expected {expected_prefix} prefix).'
            )
            return

        try:
            self.db.add_golden_sample(variant, sn, note)
            logger.info('Golden sample added: variant=%s SN=%s note=%r', variant, sn, note)
            sn_inp.text   = ''
            sn_inp.hint_text = 'CI... serial number' if variant == 'A8S' else 'CJ... serial number'
            note_inp.text = ''
            layout = self._gs_a8s_layout if variant == 'A8S' else self._gs_a10s_layout
            self._refresh_gs_list(variant, layout)
            self._dev_save_lbl.text = f'Golden sample {sn} added.'
            self._dev_save_lbl.color = C['green']
        except Exception as e:
            logger.error('Failed to add golden sample %s: %s', sn, e)
            self._dev_save_lbl.text = f'Error: {e}'
            self._dev_save_lbl.color = C['red']

    def _remove_gs(self, gs_id: int, variant: str):
        self.db.remove_golden_sample(gs_id)
        logger.info('Golden sample removed: id=%s variant=%s', gs_id, variant)
        layout = self._gs_a8s_layout if variant == 'A8S' else self._gs_a10s_layout
        self._refresh_gs_list(variant, layout)
        self._dev_save_lbl.text = 'Golden sample removed.'

    def _save_device_tab(self, *_):
        self.db.set_config('device_name',       self._device_name_inp.text.strip())
        self.db.set_config('target_fw_version', self._target_fw_inp.text.strip())
        self.db.set_config('fw_bin_path',       self._fw_bin_inp.text.strip())
        # Update device service immediately
        App.get_running_app().device_service.update_device_name(
            self._device_name_inp.text.strip())
        logger.info(
            'Device config saved: name=%r target_fw=%r fw_bin=%r',
            self._device_name_inp.text.strip(),
            self._target_fw_inp.text.strip(),
            self._fw_bin_inp.text.strip(),
        )
        self._dev_save_lbl.text  = 'Saved.'
        self._dev_save_lbl.color = C['green']

    def _add_part(self, *_):
        name  = self._new_part_name.text.strip()
        pa8s  = self._new_part_pa8s.text.strip().upper()
        pa10s = self._new_part_pa10s.text.strip().upper()
        req   = self._new_part_req.active
        if not name or not pa8s or not pa10s:
            self._parts_save_lbl.text  = 'Fill in all fields before adding.'
            self._parts_save_lbl.color = C['red']
            return
        try:
            self.db.add_part_config(name, pa8s, pa10s, req)
            logger.info('Part added: name=%r prefix_a8s=%s prefix_a10s=%s required=%s', name, pa8s, pa10s, req)
            self._new_part_name.text  = ''
            self._new_part_pa8s.text  = ''
            self._new_part_pa10s.text = ''
            self._new_part_req.active = True
            self._refresh_parts_tab()
            self._parts_save_lbl.text  = f'Part "{name}" added.'
            self._parts_save_lbl.color = C['green']
        except Exception as e:
            logger.error('Failed to add part %r: %s', name, e)
            self._parts_save_lbl.text  = f'Error: {e}'
            self._parts_save_lbl.color = C['red']

    def _remove_part(self, part_id: int):
        self.db.remove_part_config(part_id)
        logger.info('Part removed: id=%s', part_id)
        self._refresh_parts_tab()
        self._parts_save_lbl.text  = 'Part removed.'
        self._parts_save_lbl.color = C['green']

    def _save_parts(self, *_):
        for refs in self._part_refs:
            self.db.update_part_config(
                refs['id'],
                refs['name'].text.strip(),
                refs['prefix_a8s'].text.strip().upper(),
                refs['prefix_a10s'].text.strip().upper(),
                refs['required'].active,
            )
        self._parts_save_lbl.text  = 'Parts configuration saved.'
        self._parts_save_lbl.color = C['green']
        logger.info('Parts configuration saved (%d rows)', len(self._part_refs))

    def _change_password(self, *_):
        cur  = self._cur_pw.text
        new  = self._new_pw.text
        conf = self._conf_pw.text

        if not self.db.check_password(cur):
            self._pw_msg.text  = 'Current password is incorrect.'
            self._pw_msg.color = C['red']
            self._cur_pw.text  = ''
            return
        if len(new) < 4:
            self._pw_msg.text  = 'New password must be at least 4 characters.'
            self._pw_msg.color = C['red']
            return
        if new != conf:
            self._pw_msg.text  = 'Passwords do not match.'
            self._pw_msg.color = C['red']
            self._conf_pw.text = ''
            return

        self.db.set_password(new)
        self._cur_pw.text  = ''
        self._new_pw.text  = ''
        self._conf_pw.text = ''
        self._pw_msg.text  = 'Password updated successfully.'
        self._pw_msg.color = C['green']

    # ── Kivy lifecycle ────────────────────────────────────────────────────────

    def on_enter(self, *_):
        self._refresh_device_tab()
        self._refresh_parts_tab()
        self._dev_save_lbl.text   = ''
        self._parts_save_lbl.text = ''
        self._pw_msg.text         = ''
