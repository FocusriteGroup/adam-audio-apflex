"""
Main workflow screen.

State machine
─────────────
IDLE          → user presses Start
SCAN_PRODUCT  → waiting for product SN barcode
PROCESSING    → backend steps running (FW check / flash, write SN)  [TODO: real device]
SCAN_PARTS    → scanning component barcodes (any order)
DONE          → all required parts scanned, unit written to DB
FAIL          → something went wrong; shows reason; user presses Restart
"""
import logging
from typing import Optional

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget

from app.components.ui_components import BgBox, C, NavBar, btn, inp, lbl
from app.db.database import Database
from app.services.device_service import DeviceService
from app.services import sn_validator as snv

logger = logging.getLogger(__name__)

# Workflow states
_IDLE         = 'idle'
_SCAN_PRODUCT = 'scan_product'
_PROCESSING   = 'processing'
_SCAN_PARTS   = 'scan_parts'
_DONE         = 'done'
_FAIL         = 'fail'


class WorkflowScreen(Screen):

    def __init__(self, db: Database, device_service: DeviceService, **kwargs):
        super().__init__(**kwargs)
        self.db = db
        self.device_service = device_service

        self._state  = _IDLE
        self._session: dict = {}
        self._nav_bar: Optional[NavBar] = None

        self._build()

    # ── Build UI ───────────────────────────────────────────────────────────────

    def _build(self):
        root = BgBox(color=C['bg'], orientation='vertical')
        self.add_widget(root)

        self._nav_bar = NavBar(current='workflow', session_active=False)
        root.add_widget(self._nav_bar)

        # ── Two-column content ─────────────────────────────────────────────────
        content = BoxLayout(orientation='horizontal', padding=16, spacing=12)
        root.add_widget(content)

        # Left: main workflow column
        main_col = BoxLayout(orientation='vertical', spacing=10, size_hint_x=0.63)
        content.add_widget(main_col)

        # Step indicator
        self._step_lbl = lbl(
            'Ready', size='26sp', bold=True,
            size_hint_y=None, height=64,
        )
        main_col.add_widget(self._step_lbl)

        # Instruction
        self._instr_lbl = lbl(
            'Press Start to begin.',
            size='18sp', color=C['dim'],
        )
        main_col.add_widget(self._instr_lbl)

        # Scan input (hidden initially)
        self._scan_inp = inp(hint='Scan barcode...', size_hint_y=None, height=60,
                             font_size='22sp')
        self._scan_inp.bind(on_text_validate=self._on_scan)
        self._scan_inp.bind(focus=self._on_scan_focus)
        self._scan_inp.opacity = 0
        self._scan_inp.disabled = True
        main_col.add_widget(self._scan_inp)

        # Status / result
        self._status_lbl = lbl('', size='16sp', color=C['dim'],
                               size_hint_y=None, height=40)
        main_col.add_widget(self._status_lbl)

        self._result_lbl = lbl('', size='52sp', bold=True,
                               size_hint_y=None, height=90)
        main_col.add_widget(self._result_lbl)

        main_col.add_widget(Widget())   # vertical spacer

        # Buttons
        btn_row = BoxLayout(size_hint_y=None, height=68, spacing=12)
        main_col.add_widget(btn_row)

        self._action_btn = btn('Start', on_press=self._on_action,
                               bg=C['accent'], size_hint_x=0.5)
        btn_row.add_widget(self._action_btn)

        self._cancel_btn = btn('Cancel', on_press=self._on_cancel,
                               bg=C['red'], size_hint_x=0.5)
        self._cancel_btn.opacity  = 0
        self._cancel_btn.disabled = True
        btn_row.add_widget(self._cancel_btn)

        # Right: parts checklist panel
        parts_panel = BgBox(
            color=C['panel'], orientation='vertical',
            size_hint_x=0.37, padding=12, spacing=6,
        )
        content.add_widget(parts_panel)

        parts_panel.add_widget(lbl(
            'Required Parts', bold=True, size='17sp',
            size_hint_y=None, height=36,
        ))

        # Divider
        divider = Widget(size_hint_y=None, height=1)
        with divider.canvas:
            from kivy.graphics import Color as KColor, Rectangle as KRect
            KColor(*C['dim'])
            KRect(pos=divider.pos, size=divider.size)
        parts_panel.add_widget(divider)

        self._parts_scroll = ScrollView()
        self._parts_layout = BoxLayout(
            orientation='vertical', size_hint_y=None, spacing=2,
        )
        self._parts_layout.bind(
            minimum_height=self._parts_layout.setter('height'))
        self._parts_scroll.add_widget(self._parts_layout)
        parts_panel.add_widget(self._parts_scroll)

        # Variant badge (shows A8S or A10S after product SN is scanned)
        self._variant_lbl = lbl('', size='15sp', color=C['dim'],
                                size_hint_y=None, height=32)
        parts_panel.add_widget(self._variant_lbl)

        self._rebuild_parts_list()

    # ── Parts checklist ────────────────────────────────────────────────────────

    def _rebuild_parts_list(self, variant: Optional[str] = None):
        self._parts_layout.clear_widgets()
        parts = [p for p in self.db.get_parts_config() if p['required']]
        for part in parts:
            scanned_sn = self._session.get('parts_scanned', {}).get(part['name'])
            done = bool(scanned_sn)

            row = BgBox(
                color=C['panel2'] if done else C['panel'],
                orientation='horizontal',
                size_hint_y=None, height=46, padding=(6, 0), spacing=6,
            )

            # Status dot
            indicator = lbl(
                '*' if done else '-',
                color=C['green'] if done else C['dim'],
                size='20sp', bold=True, size_hint_x=None, width=22,
            )
            row.add_widget(indicator)

            # Part name (green when scanned)
            row.add_widget(lbl(
                part['name'], halign='left', size='16sp',
                bold=done,
                color=C['green'] if done else C['text'],
            ))

            # Prefix hint (variant-aware once variant is known)
            if variant == 'A8S':
                pfx = part['prefix_a8s']
            elif variant == 'A10S':
                pfx = part['prefix_a10s']
            else:
                a = part['prefix_a8s']
                b_ = part['prefix_a10s']
                pfx = a if a == b_ else f'{a}/{b_}'

            row.add_widget(lbl(
                f'({pfx}...)',
                color=C['green'] if done else C['dim'],
                size='14sp', size_hint_x=None, width=70,
                halign='right',
            ))

            self._parts_layout.add_widget(row)

    # ── State helpers ──────────────────────────────────────────────────────────

    def _set_nav_session(self, active: bool):
        """Toggle nav-bar button availability during an active session."""
        idx = list(self.children[0].children).index(self._nav_bar) \
              if self._nav_bar in self.children[0].children else -1
        parent = self.children[0]
        parent.remove_widget(self._nav_bar)
        self._nav_bar = NavBar(current='workflow', session_active=active)
        # Re-insert at the top (BoxLayout stores children reversed)
        parent.add_widget(self._nav_bar, index=len(parent.children))

    def _show_scan_input(self):
        self._scan_inp.opacity  = 1
        self._scan_inp.disabled = False
        Clock.schedule_once(lambda _: setattr(self._scan_inp, 'focus', True), 0.15)

    def _hide_scan_input(self):
        self._scan_inp.opacity  = 0
        self._scan_inp.disabled = True
        self._scan_inp.text     = ''

    def _show_cancel(self):
        self._cancel_btn.opacity  = 1
        self._cancel_btn.disabled = False

    def _hide_cancel(self):
        self._cancel_btn.opacity  = 0
        self._cancel_btn.disabled = True

    # ── Transitions ────────────────────────────────────────────────────────────

    def _go_idle(self):
        self._state   = _IDLE
        self._session = {}
        self._step_lbl.text   = 'Ready'
        self._instr_lbl.text  = 'Press Start to begin.'
        self._status_lbl.text = ''
        self._result_lbl.text = ''
        self._result_lbl.color = C['text']
        self._variant_lbl.text = ''
        self._action_btn.text     = 'Start'
        self._action_btn.opacity  = 1
        self._action_btn.disabled = False
        self._action_btn.background_color = C['accent']
        self._hide_cancel()
        self._hide_scan_input()
        self._set_nav_session(False)
        self._rebuild_parts_list()

    def _go_scan_product(self):
        self._state = _SCAN_PRODUCT
        self._step_lbl.text  = 'Step 1 - Scan Product SN'
        self._instr_lbl.text = 'Scan the barcode of the complete unit.\n(CI... = A8S   |   CJ... = A10S)'
        self._status_lbl.text = ''
        self._result_lbl.text = ''
        self._action_btn.opacity  = 0
        self._action_btn.disabled = True
        self._show_cancel()
        self._show_scan_input()
        self._set_nav_session(True)

    def _go_processing(self):
        self._state = _PROCESSING
        self._step_lbl.text   = 'Processing...'
        self._instr_lbl.text  = 'Checking firmware and writing serial number.'
        self._status_lbl.text = ''
        self._hide_scan_input()
        Clock.schedule_once(self._run_backend, 0.3)

    def _go_scan_parts(self):
        self._state = _SCAN_PARTS
        self._step_lbl.text  = 'Step 2 - Scan Component Parts'
        self._instr_lbl.text = 'Scan each part barcode in any order.'
        self._show_scan_input()

    def _go_done(self):
        self._state = _DONE
        variant = self._session.get('variant', '')
        self._step_lbl.text   = f'DONE  -  Sub-Pro {variant}'
        self._instr_lbl.text  = 'Unit complete. Press Start Next Unit to continue.'
        self._result_lbl.text  = 'PASS'
        self._result_lbl.color = C['green']
        self._status_lbl.text  = f"FW {self._session.get('fw_final', '?')}  -  all parts recorded"
        self._hide_scan_input()
        self._action_btn.text    = 'Start Next Unit'
        self._action_btn.opacity  = 1
        self._action_btn.disabled = False
        self._action_btn.background_color = C['green']
        self._hide_cancel()
        self._set_nav_session(False)

    def _go_fail(self, reason: str):
        self._state = _FAIL
        # Write FAIL to DB if a unit was started
        unit_id = self._session.get('unit_id')
        if unit_id:
            self.db.complete_unit(unit_id, 'FAIL')
        self._step_lbl.text    = 'FAIL'
        self._result_lbl.text  = 'FAIL'
        self._result_lbl.color = C['red']
        self._instr_lbl.text   = reason
        self._status_lbl.text  = ''
        self._hide_scan_input()
        self._action_btn.text    = 'Restart'
        self._action_btn.opacity  = 1
        self._action_btn.disabled = False
        self._action_btn.background_color = C['red']
        self._hide_cancel()
        self._set_nav_session(False)

    # ── Event handlers ─────────────────────────────────────────────────────────

    def _on_action(self, *_):
        if self._state == _IDLE:
            self._session = {'parts_scanned': {}}
            self._rebuild_parts_list()
            self._go_scan_product()
        elif self._state in (_DONE, _FAIL):
            self._go_idle()

    def _on_cancel(self, *_):
        unit_id = self._session.get('unit_id')
        if unit_id:
            self.db.complete_unit(unit_id, 'FAIL')
        self._go_idle()

    def _on_scan(self, instance):
        raw = instance.text.strip().upper()
        instance.text = ''

        if self._state == _SCAN_PRODUCT:
            self._handle_product_scan(raw)
        elif self._state == _SCAN_PARTS:
            self._handle_part_scan(raw)

    # ── Product SN handling ───────────────────────────────────────────────────

    def _handle_product_scan(self, sn: str):
        ok, err = snv.validate_sn(sn)
        if not ok:
            self._status_lbl.text = f'X  {err}'
            self._show_scan_input()
            return

        variant = snv.get_product_variant(sn)
        if variant is None:
            self._status_lbl.text = (
                f'X  Unknown product prefix "{sn[:2]}". '
                f'Expected CI (A8S) or CJ (A10S).'
            )
            self._show_scan_input()
            return

        if self.db.is_golden_sample(sn):
            self._go_fail(
                f'Golden Sample detected: {sn}\n'
                f'This unit must NOT be programmed.'
            )
            return

        self._session['product_sn'] = sn
        self._session['variant']    = variant
        self._variant_lbl.text = f'Variant: Sub-Pro {variant}'

        # Create a preliminary DB record so the unit is tracked even on crash
        unit_id = self.db.create_unit(sn, variant)
        self._session['unit_id'] = unit_id

        self._rebuild_parts_list(variant)
        self._go_processing()

    # ── Real backend ──────────────────────────────────────────────────────────

    def _run_backend(self, *_):
        """
        Execute the device-side provisioning steps:
          1. Read current firmware version from device.
          2. If it does not match the configured target, flash the correct firmware.
          3. Verify firmware version after flash.
          4. Write the scanned product SN to the device.
          5. Read back the SN from the device and confirm it matches.
        On any failure, transition to FAIL with a descriptive reason.
        """
        sn      = self._session['product_sn']
        unit_id = self._session['unit_id']

        target_fw = self.db.get_config('target_fw_version', '').strip()
        fw_bin    = self.db.get_config('fw_bin_path', '').strip()

        # ── Step 1: Read current firmware version ─────────────────────────────
        self._set_status('Reading firmware version...')
        ok, fw_found, err = self.device_service.get_firmware_version()
        if not ok:
            self._go_fail(f'Could not read firmware version.\n{err}')
            return

        fw_flashed = False

        # ── Step 2: Flash if outdated ─────────────────────────────────────────
        if target_fw and fw_found != target_fw:
            if not fw_bin:
                self._go_fail(
                    f'Device has FW {fw_found}, target is {target_fw}.\n'
                    f'No firmware .bin path configured in Settings.'
                )
                return

            from pathlib import Path
            bin_path = Path(fw_bin)
            if not bin_path.is_absolute():
                # Resolve relative to the repo root (parent of this project folder)
                bin_path = (
                    Path(__file__).resolve().parent.parent.parent / fw_bin
                )
            if not bin_path.exists():
                self._go_fail(
                    f'Firmware file not found:\n{bin_path}'
                )
                return

            self._set_status(f'Flashing firmware {target_fw}...')
            ok, _, err = self.device_service.flash_firmware(bin_path)
            if not ok:
                self._go_fail(f'Firmware flash failed.\n{err}')
                return

            fw_flashed = True

            # ── Step 3: Verify FW version after flash ─────────────────────────
            self._set_status('Verifying firmware version after flash...')
            ok, fw_after, err = self.device_service.get_firmware_version()
            if not ok:
                self._go_fail(f'Could not read FW version after flash.\n{err}')
                return
            if target_fw and fw_after != target_fw:
                self._go_fail(
                    f'FW version mismatch after flash.\n'
                    f'Expected {target_fw}, got {fw_after}.'
                )
                return
            fw_found_after = fw_after
        else:
            fw_found_after = fw_found

        fw_final = fw_found_after

        # ── Step 4: Write serial number to device ─────────────────────────────
        self._set_status(f'Writing SN {sn} to device...')
        ok, _, err = self.device_service.set_serial_number(sn)
        if not ok:
            self._go_fail(f'Failed to write serial number to device.\n{err}')
            return

        # ── Step 5: Read back and verify serial number ─────────────────────────
        self._set_status('Verifying SN readback...')
        ok, sn_readback, err = self.device_service.get_serial_number()
        if not ok:
            self._go_fail(f'Failed to read back serial number.\n{err}')
            return
        if sn_readback.strip().upper() != sn.strip().upper():
            self._go_fail(
                f'SN readback mismatch.\n'
                f'Written: {sn}  |  Read back: {sn_readback}'
            )
            return

        # ── All steps passed — update DB and move to parts scan ───────────────
        self._session['fw_found']   = fw_found
        self._session['fw_flashed'] = fw_flashed
        self._session['fw_final']   = fw_final

        self.db.update_unit_fw(unit_id, fw_found, fw_flashed, fw_final)

        flash_note = f' (flashed from {fw_found})' if fw_flashed else ''
        self._status_lbl.text = (
            f'FW {fw_final}{flash_note}  -  SN {sn} written and verified.'
        )
        self._go_scan_parts()

    def _set_status(self, msg: str):
        """Update the status label mid-step (visible during processing)."""
        self._status_lbl.text = msg

    # ── Part SN handling ──────────────────────────────────────────────────────

    def _handle_part_scan(self, sn: str):
        variant  = self._session.get('variant')
        parts    = self.db.get_parts_config()
        required = [p for p in parts if p['required']]
        already  = self._session['parts_scanned']

        # Full SN validation
        ok, err = snv.validate_sn(sn)
        if not ok:
            self._status_lbl.text = f'X  {err}'
            self._show_scan_input()
            return

        prefix = snv.get_prefix(sn)

        # Find which part this prefix belongs to
        matched_part = None
        for part in required:
            exp = part['prefix_a8s'] if variant == 'A8S' else part['prefix_a10s']
            if prefix == exp.upper():
                matched_part = part
                break

        if matched_part is None:
            self._status_lbl.text = (
                f'X  Unknown prefix "{prefix}" for variant {variant}. '
                f'Check the parts configuration.'
            )
            self._show_scan_input()
            return

        part_name = matched_part['name']

        # Detect re-assignment (part previously on another unit)
        prev_unit_id = self.db.get_latest_unit_for_part_sn(sn)
        cur_unit_id  = self._session['unit_id']
        reassignment = (prev_unit_id is not None and prev_unit_id != cur_unit_id)

        # Record in session + DB
        already[part_name] = sn
        self.db.add_part_scan(
            cur_unit_id, part_name, sn,
            previous_unit_id=prev_unit_id if reassignment else None,
        )

        note = f'  [re-assigned from unit #{prev_unit_id}]' if reassignment else ''
        self._status_lbl.text = f'OK  {part_name}: {sn}{note}'

        self._rebuild_parts_list(variant)

        # Check if all required parts are done
        done_names = set(already.keys())
        req_names  = {p['name'] for p in required}
        if req_names.issubset(done_names):
            self.db.complete_unit(cur_unit_id, 'PASS')
            self._go_done()
        else:
            remaining = req_names - done_names
            self._instr_lbl.text = (
                'Scan next part.\n'
                f"Still needed: {', '.join(sorted(remaining))}"
            )
            self._show_scan_input()

    # ── on_enter ──────────────────────────────────────────────────────────────

    def on_enter(self, *_):
        """Refresh parts checklist and restore scan focus when returning."""
        if self._state == _IDLE:
            self._rebuild_parts_list()
        # If a scan input is currently visible, re-focus it so the operator
        # can scan immediately without clicking into the field.
        if not self._scan_inp.disabled:
            Clock.schedule_once(
                lambda _: setattr(self._scan_inp, 'focus', True), 0.2)

    def _on_scan_focus(self, _instance, focused: bool):
        """Keep focus pinned to the scan field while it is active.

        Barcode scanners type fast then send Enter; if focus is ever lost
        (e.g. a stray click elsewhere) we immediately grab it back so the
        operator never has to click into the field.
        """
        if not focused and not self._scan_inp.disabled:
            Clock.schedule_once(
                lambda _: setattr(self._scan_inp, 'focus', True), 0.1)
