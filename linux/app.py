#!/usr/bin/env python3
"""Native Qt/Wayland Culvert dashboard. The interface never runs as root."""
from __future__ import annotations
import json, os, subprocess, sys, time, uuid
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'wayland' if os.environ.get('WAYLAND_DISPLAY') else 'xcb')
from PySide6.QtCore import Qt, QTimer, QThreadPool, QRunnable, QObject, Signal, QUrl, QRectF
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap, QPainter, QPainterPath, QPen, QAction, QKeySequence, QShortcut, QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QLabel, QPushButton, QStackedWidget, QFrame, QPlainTextEdit, QLineEdit, QFormLayout, QSpinBox, QCheckBox, QFileDialog, QMessageBox, QInputDialog, QTableWidget, QTableWidgetItem, QHeaderView, QSystemTrayIcon, QMenu, QComboBox, QScrollArea, QBoxLayout, QSizePolicy)
from common import ROOT, CONFIG, STATE, SYSTEM_ROOT, create_link, device_request, load_profile, parse_link, preferences, private_write, privileged, read_status, save_preferences, save_profile, ssh_command, validate_profile

STYLE = '''
QWidget { background:#080709; color:#f6ebee; font-family:"DejaVu Sans"; font-size:14px; }
QMainWindow { background:#080709; }
QFrame#sidebar { background:#100b0e; border-right:1px solid #411e26; }
QFrame#card, QFrame#hero { background:#130e11; border:1px solid #411e26; border-radius:12px; }
QFrame#hero { border-top:2px solid #ff4158; }
QLabel { background:transparent; }
QLabel#brand { color:#ff4158; font-family:"DejaVu Sans Mono"; font-weight:800; font-size:28px; letter-spacing:3px; }
QLabel#eyebrow { color:#b89ba3; font-family:"DejaVu Sans Mono"; font-size:11px; letter-spacing:2px; }
QLabel#title { font-size:30px; font-weight:700; }
QLabel#metric { font-family:"DejaVu Sans Mono"; font-size:25px; font-weight:700; }
QLabel#muted { color:#b89ba3; }
QPushButton { background:#211117; border:1px solid #4b2631; border-radius:7px; padding:11px 14px; text-align:left; }
QPushButton:hover { background:#391521; border-color:#ff4158; }
QPushButton:focus { border:2px solid #ff919c; }
QPushButton:disabled { color:#775d66; border-color:#291b20; }
QPushButton[primary="true"] { background:#ff4158; color:#080709; font-weight:800; text-align:center; min-height:27px; }
QPushButton[nav="true"] { background:transparent; border:none; color:#b89ba3; padding:14px; }
QPushButton[active="true"] { background:#2b0f17; border-left:3px solid #ff4158; color:#ff919c; }
QLineEdit,QPlainTextEdit,QSpinBox,QComboBox { background:#130e11; border:1px solid #411e26; border-radius:6px; padding:8px; selection-background-color:#ad203d; }
QTableWidget { background:#130e11; alternate-background-color:#1d1117; border:1px solid #411e26; gridline-color:#291b20; selection-background-color:#4a1627; }
QHeaderView::section { background:#211117; color:#b89ba3; border:none; padding:12px; }
QCheckBox { spacing:10px; padding:6px; }
QCheckBox::indicator { width:17px; height:17px; border:1px solid #775d66; border-radius:3px; background:#130e11; }
QCheckBox::indicator:checked { background:#ff4158; }
QMenu { background:#130e11; border:1px solid #411e26; } QMenu::item { padding:8px 22px; } QMenu::item:selected { background:#411e26; }
'''


def label(text, kind=None, wrap=False):
    result = QLabel(text)
    if kind: result.setObjectName(kind)
    result.setWordWrap(wrap)
    result.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
    return result


def button(text, action, primary=False):
    result = QPushButton(text); result.clicked.connect(action)
    if primary: result.setProperty('primary', True)
    return result


def bytes_text(value):
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB'):
        if abs(value) < 1024: return f'{value:.1f} {unit}' if unit != 'B' else f'{int(value)} B'
        value /= 1024
    return f'{value:.1f} PiB'


class Signals(QObject):
    done = Signal(object)
    error = Signal(str)
    finished = Signal()


class Job(QRunnable):
    def __init__(self, action):
        super().__init__(); self.action = action; self.signals = Signals()
    def run(self):
        try: self.signals.done.emit(self.action())
        except Exception as error: self.signals.error.emit(str(error))
        finally: self.signals.finished.emit()


class Chart(QWidget):
    def __init__(self):
        super().__init__(); self.samples = []; self.setMinimumHeight(180); self.setAccessibleName('Recent measured tunnel receive speed')
    def add(self, value): self.samples = (self.samples + [max(0, value)])[-90:]; self.update()
    def paintEvent(self, _):
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = self.rect().adjusted(12, 15, -12, -25); top = max([1024, *self.samples])
        painter.setPen(QPen(QColor('#291b20'), 1))
        for i in range(4):
            y = bounds.top() + bounds.height() * i / 3
            painter.drawLine(bounds.left(), int(y), bounds.right(), int(y))
        painter.setPen(QColor('#b89ba3')); painter.drawText(12, self.height() - 5, 'LAST 90 SAMPLES  /  ' + bytes_text(top) + '/s peak')
        if len(self.samples) < 2:
            painter.drawText(bounds, Qt.AlignmentFlag.AlignCenter, 'Connect to see measured traffic'); return
        path = QPainterPath()
        for i, value in enumerate(self.samples):
            x = bounds.left() + bounds.width() * i / max(89, len(self.samples) - 1)
            y = bounds.bottom() - bounds.height() * value / top
            if i == 0: path.moveTo(x, y)
            else: path.lineTo(x, y)
        painter.setPen(QPen(QColor('#ff4158'), 2)); painter.drawPath(path)
        fill = QPainterPath(path); fill.lineTo(x, bounds.bottom()); fill.lineTo(bounds.left(), bounds.bottom()); fill.closeSubpath()
        painter.fillPath(fill, QColor(255, 65, 88, 28))


class Logo(QWidget):
    """Trans-colored tactical star, counter-rotating inside a decorative orbit."""
    def __init__(self):
        super().__init__(); self.setFixedHeight(146); self.phase = 0.; self.animated = bool(preferences()['animations'])
        self.emblem = QPixmap(str(ROOT / 'assets/Culvert-mark.png'))
        self.setAccessibleName('Culvert trans-colored Star of David with decorative rotation and glitch')
        self.timer = QTimer(self); self.timer.timeout.connect(self.advance); self.timer.start(50)
    def advance(self):
        if self.animated and self.isVisible() and self.window().isActiveWindow() and not self.window().isMinimized():
            self.phase = (self.phase + 1.5) % 720; self.update()
    def set_animated(self, enabled): self.animated = enabled; self.update()
    def paintEvent(self, _):
        import math
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing); painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        size = min(self.width(), self.height()) - 4; left = (self.width() - size) / 2; top = (self.height() - size) / 2
        ring = QRectF(left + size*.055, top + size*.055, size*.89, size*.89)
        painter.setPen(QPen(QColor('#4c232f'), max(1, size*.008))); painter.drawEllipse(ring)
        for i, color in enumerate(('#ff4158', '#ff919c')):
            angle = self.phase + i*180; painter.setPen(QPen(QColor(color), max(1.4, size*.023), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawArc(ring, int(-angle*16), -88*16)
            x = ring.center().x() + math.cos(math.radians(angle))*ring.width()/2
            y = ring.center().y() + math.sin(math.radians(angle))*ring.height()/2
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QColor(color)); painter.drawEllipse(QRectF(x-size*.032, y-size*.032, size*.064, size*.064))
        def star(offset=0):
            painter.save(); painter.translate(left+size/2+offset, top+size/2); painter.rotate(-self.phase*.5)
            painter.drawPixmap(QRectF(-size*.40, -size*.40, size*.80, size*.80), self.emblem, QRectF(self.emblem.rect())); painter.restore()
        star()
        phase = self.phase % 360
        if self.animated and self.window().isActiveWindow() and (56 <= phase < 59 or 61 <= phase < 64):
            painter.save(); painter.setClipRect(QRectF(left, top+size*.43, size, size*.12)); star(size*(.025 if phase < 60 else -.025)); painter.restore()
            painter.setPen(QPen(QColor('#5bcefa'), max(1, size*.012))); painter.drawLine(int(left+size*.14), int(top+size*.45), int(left+size*.31), int(top+size*.45))
            painter.setPen(QPen(QColor('#f5a9b8'), max(1, size*.012))); painter.drawLine(int(left+size*.69), int(top+size*.54), int(left+size*.86), int(top+size*.54))


class Window(QMainWindow):
    def __init__(self, demo=False):
        super().__init__(); self.demo = demo; self.busy = False; self.jobs = set(); self.status = {}; self.previous = None; self.last_state = None; self.device_data = {}; self.device_ids = []
        self.setWindowTitle('Culvert'); self.setWindowIcon(QIcon(str(ROOT / 'assets/Culvert.ico'))); self.resize(1180, 780); self.setMinimumSize(900, 650)
        self.profile = load_profile() if not demo else None
        shell = QWidget(); outer = QHBoxLayout(shell); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0); self.setCentralWidget(shell)
        sidebar = self.sidebar = QFrame(); sidebar.setObjectName('sidebar'); sidebar.setFixedWidth(225); nav = QVBoxLayout(sidebar); nav.setContentsMargins(24, 30, 18, 20)
        self.logo = Logo(); nav.addWidget(self.logo)
        self.brand_label = label('CULVERT', 'brand'); nav.addWidget(self.brand_label); self.brand_subtitle = label('YOUR DATA.\nOURS NOW.', 'eyebrow'); nav.addWidget(self.brand_subtitle); nav.addSpacing(10)
        self.stack = QStackedWidget(); self.nav_buttons = []
        for title in ('Overview', 'Connections', 'Diagnostics', 'Your devices', 'Settings'):
            item = button(title, lambda checked=False, name=title: self.navigate(name)); item.setToolTip(title); item.setProperty('nav', True); nav.addWidget(item); self.nav_buttons.append(item)
        nav.addStretch(); self.session_label = label('WAYLAND / ' + (os.environ.get('XDG_CURRENT_DESKTOP') or 'DESKTOP').upper(), 'eyebrow', True); nav.addWidget(self.session_label)
        self.footer_label = label('CULVERT 2.4.5\nConnected on your terms.', 'muted', True); nav.addWidget(self.footer_label); outer.addWidget(sidebar)
        body = QWidget(); layout = QVBoxLayout(body); layout.setContentsMargins(26, 24, 26, 24); layout.setSpacing(18)
        self.notice = label('', 'muted', True); self.notice.setVisible(False); layout.addWidget(self.notice); layout.addWidget(self.stack); outer.addWidget(body, 1)
        self.overview(); self.connections(); self.diagnostics(); self.devices(); self.settings(); self.navigate('Overview')
        QShortcut(QKeySequence('Ctrl+Return'), self, self.toggle)
        self.tray = QSystemTrayIcon(self.windowIcon(), self); menu = QMenu(); menu.addAction('Open Culvert', self.show_window); menu.addAction('Connect / disconnect', self.toggle); menu.addAction('Restore normal internet', self.disconnect); menu.addSeparator(); menu.addAction('Quit interface (keep tunnel)', QApplication.quit); self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.show_window() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        if QSystemTrayIcon.isSystemTrayAvailable() and not demo: self.tray.show()
        self.timer = QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(1000); self.refresh()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, 'metric_cards'): return
        compact = self.width() < 1000
        self.sidebar.setFixedWidth(76 if compact else 225)
        self.brand_label.setVisible(not compact)
        self.logo.setFixedHeight(46 if compact else 146)
        self.sidebar.layout().setContentsMargins(10 if compact else 24, 22, 10 if compact else 18, 20)
        self.brand_subtitle.setVisible(not compact)
        self.session_label.setVisible(not compact and self.height() > 570)
        self.footer_label.setVisible(not compact and self.height() > 570)
        for item in self.nav_buttons: item.setText(item.toolTip()[:1] if compact else item.toolTip())
        columns = 2 if compact else 4
        for index, card in enumerate(self.metric_cards): self.metric_layout.addWidget(card, index // columns, index % columns)
        self.hero_layout.setDirection(QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight)
        self.overview_actions.setDirection(QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight)

    def show_window(self): self.show(); self.raise_(); self.activateWindow()
    def closeEvent(self, event):
        if self.tray.isVisible() and not self.demo: event.ignore(); self.hide()
        else: event.accept()
    def page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(18); layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinimumSize); scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame); scroll.setWidget(page); self.stack.addWidget(scroll); return layout
    def navigate(self, name):
        for i, item in enumerate(self.nav_buttons):
            item.setProperty('active', item.toolTip() == name); item.style().unpolish(item); item.style().polish(item)
            if item.toolTip() == name: self.stack.setCurrentIndex(i)
    def say(self, text): self.notice.setText(text); self.notice.setVisible(bool(text))
    def work(self, action, done=None):
        if self.demo or self.busy: return
        self.busy = True; self.connect_button.setEnabled(False)
        job = Job(action); self.jobs.add(job)
        job.signals.done.connect(done or (lambda result: self.say(str(result) if result else 'Done.')))
        job.signals.error.connect(self.say)
        def finished(): self.busy = False; self.jobs.discard(job); self.refresh()
        job.signals.finished.connect(finished); QThreadPool.globalInstance().start(job)
    def overview(self):
        layout = self.page(); hero = QFrame(); hero.setObjectName('hero'); hero_layout = self.hero_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, hero); hero_layout.setContentsMargins(24, 24, 24, 24)
        words = QVBoxLayout(); words.addWidget(label('YOUR CONNECTION', 'eyebrow')); self.headline = label('Ready when you are.', 'title', True); words.addWidget(self.headline)
        self.evidence = label('Import your device link to connect to Culvert’s VM.', 'muted', True); words.addWidget(self.evidence); hero_layout.addLayout(words, 1)
        self.connect_button = button('Connect', self.toggle, True); self.connect_button.setMinimumWidth(155); hero_layout.addWidget(self.connect_button); layout.addWidget(hero)
        row = self.metric_layout = QGridLayout(); self.metric_cards = []; self.metrics = {}
        for key, title in [('exit', 'EXIT ADDRESS'), ('latency', 'UDP ROUND TRIP'), ('download', 'RECEIVING'), ('upload', 'SENDING')]:
            card = QFrame(); card.setObjectName('card'); card_layout = QVBoxLayout(card); card_layout.setContentsMargins(18, 18, 18, 18); card_layout.addWidget(label(title, 'eyebrow'))
            metric = label('—', 'metric'); self.metrics[key] = metric; card_layout.addWidget(metric); self.metric_cards.append(card); row.addWidget(card, 0, len(self.metric_cards)-1)
        layout.addLayout(row)
        card = QFrame(); card.setObjectName('card'); contents = QVBoxLayout(card); contents.setContentsMargins(20, 20, 20, 20); contents.addWidget(label('TUNNEL TRAFFIC', 'eyebrow')); self.chart = Chart(); contents.addWidget(self.chart); layout.addWidget(card, 1)
        self.checks = label('EXIT  —     DNS  —     UDP  —     IPv4 / IPv6  —', 'muted'); layout.addWidget(self.checks)
        actions = self.overview_actions = QBoxLayout(QBoxLayout.Direction.LeftToRight); actions.addWidget(button('Import device link', self.import_link)); actions.addWidget(button('Restore normal internet', self.disconnect)); actions.addStretch(); layout.addLayout(actions)
        self.identity = label('No device identity saved.', 'muted'); layout.addWidget(self.identity)
    def connections(self):
        layout = self.page(); layout.addWidget(label('Live connections', 'title')); layout.addWidget(label('Destination activity stays on this PC. No destination lookup service is used.', 'muted', True))
        self.connection_table = QTableWidget(0, 5); self.connection_table.setHorizontalHeaderLabels(['Destination', 'Port', 'Protocol', 'Received', 'Sent']); self.connection_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch); self.connection_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.connection_table.setAlternatingRowColors(True); layout.addWidget(self.connection_table)
    def diagnostics(self):
        layout = self.page(); layout.addWidget(label('Connection evidence', 'title')); self.details = QPlainTextEdit(); self.details.setReadOnly(True); layout.addWidget(self.details)
        row = QHBoxLayout(); row.addWidget(button('Measure UDP latency', self.measure)); row.addWidget(button('Save diagnostics', self.export_diagnostics)); row.addWidget(button('Restore normal internet', self.disconnect)); layout.addLayout(row)
    def devices(self):
        layout = self.page(); layout.addWidget(label('Your devices', 'title')); layout.addWidget(label('Each device gets a separate connection. Adding or revoking can briefly reconnect this VM’s users.', 'muted', True))
        self.device_table = QTableWidget(0, 2); self.device_table.setHorizontalHeaderLabels(['Device', 'Access']); self.device_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch); self.device_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.device_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); layout.addWidget(self.device_table)
        row = QHBoxLayout(); row.addWidget(button('Refresh', self.refresh_devices)); row.addWidget(button('Add device', self.add_device)); row.addWidget(button('Copy selected link', self.copy_device)); row.addWidget(button('Revoke selected', self.revoke_device)); layout.addLayout(row)
        self.device_note = label('Configure your VM’s SSH key in Settings, then refresh.', 'muted', True); layout.addWidget(self.device_note)
    def settings(self):
        layout = self.page(); layout.addWidget(label('Settings', 'title')); form = QFormLayout(); options = preferences()
        self.ssh_user = QLineEdit(options['ssh_user']); self.ssh_port = QSpinBox(); self.ssh_port.setRange(1, 65535); self.ssh_port.setValue(options['ssh_port']); self.ssh_key = QLineEdit(options['ssh_key'])
        key_row = QWidget(); key_layout = QHBoxLayout(key_row); key_layout.setContentsMargins(0, 0, 0, 0); key_layout.addWidget(self.ssh_key); key_layout.addWidget(button('Browse…', self.browse_key))
        self.network_lock = QCheckBox('Block ordinary internet if the tunnel fails (whole PC)'); self.network_lock.setChecked(bool(options['network_lock']))
        self.autoheal = QCheckBox('Recover automatically after network changes'); self.autoheal.setChecked(bool(options['autoheal']))
        self.autostart = QCheckBox('Open Culvert when I sign in'); self.autostart.setChecked(bool(options['autostart']))
        self.animations = QCheckBox('Animate the star, orbit and subtle glitch while Culvert is active'); self.animations.setChecked(bool(options['animations']))
        self.animations.toggled.connect(self.logo.set_animated)
        form.addRow('SSH username', self.ssh_user); form.addRow('SSH port', self.ssh_port); form.addRow('Private key file', key_row); form.addRow(self.network_lock); form.addRow(self.autoheal); form.addRow(self.autostart); form.addRow(self.animations); layout.addLayout(form)
        layout.addWidget(label('The key stays on this PC. The optional network lock affects every application. Restore normal internet clears Culvert’s lock.', 'muted', True))
        actions = QHBoxLayout(); actions.addWidget(button('Save settings', self.save_settings)); actions.addWidget(button('Import previous profile', self.import_profile)); actions.addWidget(button('VM usage', self.usage)); layout.addLayout(actions)
        cover_row = QHBoxLayout(); self.cover = QComboBox(); self.cover.addItems(['Apple / www.apple.com', 'BAMWX / bamwx.com']); cover_row.addWidget(self.cover); cover_row.addWidget(button('Switch cover site', self.switch_cover)); layout.addLayout(cover_row)
        layout.addStretch(); self.helper_label = label('System tunnel helper: installed' if (SYSTEM_ROOT / 'linux/helper.py').is_file() else 'Finish system setup to enable full-device tunneling.', 'muted', True); layout.addWidget(self.helper_label)
        lower = QHBoxLayout(); lower.addWidget(button('Finish system setup', self.install_system)); lower.addWidget(button('Open Culvert releases', lambda: QDesktopServices.openUrl(QUrl('https://github.com/Zykoraa/culvert/releases')))); layout.addLayout(lower)
    def import_link(self):
        text, accepted = QInputDialog.getMultiLineText(self, 'Culvert device connection', 'Paste the personal vless:// link issued for this device:')
        if accepted and text.strip():
            try: profile = parse_link(text); self.work(lambda: save_profile(profile), lambda result: self.import_done(profile, result))
            except Exception as error: self.say(str(error))
    def import_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Choose your Culvert VM profile', str(Path.home()), 'Device profile (*.json)')
        if path:
            try:
                if Path(path).stat().st_size > 8192: raise ValueError('Profile is too large.')
                profile = validate_profile(json.loads(Path(path).read_text())); self.work(lambda: save_profile(profile), lambda result: self.import_done(profile, result))
            except Exception as error: self.say(str(error))
    def import_done(self, profile, result): self.profile = profile; self.say(result); self.refresh()
    def toggle(self):
        if self.status.get('state') != 'disconnected': self.disconnect(); return
        if not self.profile: self.import_link(); return
        self.say('Approve the system prompt to start Culvert’s tunnel.'); self.work(lambda: privileged('connect', self.profile))
    def disconnect(self): self.work(lambda: privileged('disconnect'))
    def browse_key(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Choose your VM SSH private key', str(Path.home()), 'All files (*)')
        if path: self.ssh_key.setText(path)
    def save_settings(self):
        if self.status.get('state') != 'disconnected': self.say('Disconnect before changing connection settings.'); return
        try:
            value = preferences(); value.update(ssh_user=self.ssh_user.text().strip(), ssh_port=self.ssh_port.value(), ssh_key=self.ssh_key.text().strip(), network_lock=self.network_lock.isChecked(), autoheal=self.autoheal.isChecked(), autostart=self.autostart.isChecked(), animations=self.animations.isChecked()); save_preferences(value)
            autostart = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'autostart/culvert.desktop'
            if value['autostart']:
                autostart.parent.mkdir(parents=True, exist_ok=True); autostart.write_text('[Desktop Entry]\nType=Application\nName=Culvert\nExec=' + str(Path.home() / '.local/bin/culvert') + '\nIcon=culvert\nTerminal=false\n')
            else: autostart.unlink(missing_ok=True)
            self.say('Culvert settings saved.')
        except Exception as error: self.say(str(error))
    def install_system(self):
        script = ROOT / 'linux/install-system.sh'
        def install():
            result = subprocess.run(['pkexec', '/usr/bin/bash', str(script)], capture_output=True, text=True, timeout=120)
            if result.returncode: raise RuntimeError('System setup was canceled or could not finish. Run linux/install-system.sh with sudo from a terminal.')
            return 'System tunnel helper installed. You can connect now.'
        self.work(install, lambda result: (self.helper_label.setText('System tunnel helper: installed'), self.say(result)))
    def export_diagnostics(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Save redacted diagnostics', 'Culvert-diagnostics.json', 'JSON (*.json)')
        if path:
            safe = {k: v for k, v in self.status.items() if k not in ('connections',)}
            safe.update(version='2.4.5', platform=QGuiApplication.platformName(), desktop=os.environ.get('XDG_CURRENT_DESKTOP', ''))
            private_write(Path(path), safe); self.say('Saved locally. No credentials or destination history included.')
    def measure(self):
        if not self.status.get('verified'): self.say('Wait for a verified tunnel first.'); return
        from host import udp_probe
        def measure():
            samples = []
            for _ in range(12):
                if not read_status().get('verified'): raise RuntimeError('Connection changed; measurement canceled.')
                try: samples.append(udp_probe())
                except Exception: pass
                time.sleep(.3)
            if not samples: return 'No valid UDP probe responses.'
            samples.sort(); return f'UDP test: median {samples[len(samples)//2]:.1f} ms, maximum {max(samples):.1f} ms; {12-len(samples)}/12 failed. This is the STUN test path, not application ping.'
        self.work(measure)
    def usage(self): self.work(lambda: ssh_command('bash ~/usage.sh'), lambda result: QMessageBox.information(self, 'Shared VM usage', result))
    def refresh_devices(self):
        def refresh():
            pending = CONFIG / 'pending-device-operation.json'
            if pending.exists():
                job = json.loads(pending.read_text())
                if job['server'] != self.profile['server']: raise ValueError('A device change is pending on another VM.')
                state = device_request({'action': 'status', 'job': job['request']['job']})
                if state['state'] in ('done', 'failed'): pending.unlink()
                else: raise ValueError('A device change is still running. Refresh again shortly.')
            return device_request({'action': 'list'})
        self.work(refresh, self.devices_loaded)
    def devices_loaded(self, data):
        self.device_data = data; self.device_ids = data.get('devices', []); self.device_table.setRowCount(len(self.device_ids))
        for i, device in enumerate(self.device_ids):
            own = self.profile and device['id'] == self.profile['uuid']
            for col, text in enumerate([device['name'] + (' (this PC)' if own else ''), 'Managed' if device['managed'] else 'Protected owner']): self.device_table.setItem(i, col, QTableWidgetItem(text))
        self.device_note.setText(f'{len(self.device_ids)} devices on this VM. Keep personal links private.')
    def change_device(self, operation, identity, name=''):
        if not self.profile: self.say('Import a device connection first.'); return
        def change():
            pending = CONFIG / 'pending-device-operation.json'
            if pending.exists(): raise ValueError('Refresh the pending change first.')
            request = {'action': 'submit', 'operation': operation, 'id': identity, 'name': name, 'requester': self.profile['uuid'], 'job': str(uuid.uuid4())}
            private_write(pending, {'server': self.profile['server'], 'request': request})
            try: device_request(request)
            except RuntimeError: pass  # Restarting Xray can drop the submitting SSH connection.
            except Exception: pending.unlink(missing_ok=True); raise
            for _ in range(40):
                time.sleep(2)
                try: status = device_request({'action': 'status', 'job': request['job']})
                except RuntimeError: continue
                if status['state'] in ('done', 'failed'):
                    pending.unlink(missing_ok=True)
                    if status['state'] == 'failed': raise ValueError(status['message'])
                    return device_request({'action': 'list'})
            raise ValueError('The VM change is still pending. Refresh to check its result.')
        self.work(change, self.devices_loaded)
    def add_device(self):
        name, accepted = QInputDialog.getText(self, 'Add device', 'Device name:')
        if accepted and name.strip(): self.change_device('add', str(uuid.uuid4()), name.strip())
    def selected_device(self):
        row = self.device_table.currentRow()
        if row < 0 or row >= len(self.device_ids): raise ValueError('Select a device first.')
        return self.device_ids[row]
    def copy_device(self):
        try:
            device = self.selected_device(); profile = dict(self.profile); profile.update(uuid=device['id'], user=device['name'], sni=self.device_data['sni'], shortId=self.device_data['shortId'], port=self.device_data['port']); QApplication.clipboard().setText(create_link(profile)); self.say('Personal connection link copied. Treat it like a password.')
        except Exception as error: self.say(str(error))
    def revoke_device(self):
        try:
            device = self.selected_device()
            if not device['managed'] or device['id'] == self.profile['uuid']: raise ValueError('The owner and this PC are protected.')
            if QMessageBox.question(self, 'Revoke device', 'Revoke ' + device['name'] + '? Its saved connection will stop working.') == QMessageBox.StandardButton.Yes: self.change_device('revoke', device['id'])
        except Exception as error: self.say(str(error))
    def switch_cover(self):
        if not self.profile: self.say('Import a device connection first.'); return
        key, sni = [('apple', 'www.apple.com'), ('bamwx', 'bamwx.com')][self.cover.currentIndex()]
        if self.profile['sni'] == sni: self.say('This cover is already active.'); return
        if QMessageBox.question(self, 'Switch VM cover', 'This briefly reconnects devices on the VM. The server will revert after 90 seconds unless the new connection is confirmed.') != QMessageBox.StandardButton.Yes: return
        old = dict(self.profile)
        def change():
            try: ssh_command('set-cover.sh ' + key + ' --revert 90')
            except RuntimeError: pass
            updated = dict(old, sni=sni); save_profile(updated); time.sleep(2); privileged('connect', updated)
            for _ in range(30):
                time.sleep(2)
                if read_status().get('verified'):
                    ssh_command('confirm-cover.sh', profile=updated); return updated
            save_profile(old)
            try: privileged('connect', old)
            except Exception: pass
            raise RuntimeError('The new cover was not verified. The server auto-revert remains armed and the previous profile is restored.')
        self.work(change, lambda updated: self.import_done(updated, 'New cover verified and confirmed.'))
    def refresh(self):
        if self.demo:
            value = {'state': 'connected', 'verified': True, 'message': 'DESIGN PREVIEW · no live connection', 'health': {'exit': '203.0.113.7', 'latency': 24.8, 'dns': True, 'udp': True, 'route4': True, 'route6': True}, 'received': 12582912, 'sent': 1048576, 'connections': []}
        else: value = read_status()
        self.status = value; state = value.get('state', 'disconnected'); health = value.get('health', {}); verified = value.get('verified', False)
        self.headline.setText('Connection verified.' if verified else {'disconnected': 'Ready when you are.', 'connecting': 'Establishing connection…', 'recovering': 'Recovering your connection…', 'faulted': 'Connection needs attention.'}.get(state, 'Checking your connection…'))
        self.evidence.setText(value.get('message', '')); self.headline.setStyleSheet('color:#bfe4cb;' if verified else '')
        self.connect_button.setText('Connect' if state == 'disconnected' else 'Disconnect'); self.connect_button.setEnabled(not self.busy and not self.demo)
        self.metrics['exit'].setText(health.get('exit') or '—'); self.metrics['exit'].setStyleSheet('font-size:19px;')
        self.metrics['latency'].setText(str(health['latency']) + ' ms' if health.get('latency') is not None else '—')
        now = time.monotonic(); rx = value.get('received', 0); tx = value.get('sent', 0); download = upload = 0
        if self.previous and state in ('connected', 'unverified'):
            elapsed = now - self.previous[0]
            if 0 < elapsed < 5: download = max(0, rx-self.previous[1]) / elapsed; upload = max(0, tx-self.previous[2]) / elapsed
        self.previous = (now, rx, tx); self.metrics['download'].setText(bytes_text(download) + '/s'); self.metrics['upload'].setText(bytes_text(upload) + '/s')
        if self.demo: download = [24, 48, 32, 85, 66, 110, 73, 41][int(now) % 8] * 1024
        if state in ('connected', 'unverified'): self.chart.add(download)
        self.checks.setText('     '.join(name + ('  ✓' if health.get(key) else '  —') for name, key in [('DNS', 'dns'), ('UDP', 'udp'), ('IPv4', 'route4'), ('IPv6', 'route6')]))
        self.identity.setText((self.profile['user'] + '  /  ' + self.profile['server'] + '  ·  ' + self.profile['sni']) if self.profile else 'Import a personal connection to enroll this PC.')
        connections = value.get('connections', []); self.connection_table.setRowCount(len(connections))
        for i, record in enumerate(connections):
            for j, text in enumerate([record.get('host', ''), str(record.get('port', '')), record.get('network', '').upper(), bytes_text(record.get('download', 0)), bytes_text(record.get('upload', 0))]): self.connection_table.setItem(i, j, QTableWidgetItem(text))
        explanation = {'state': state, 'verified': verified, 'network_lock': value.get('network_lock', False), 'checks': health, 'restarts': value.get('restarts', 0), 'last_evidence': value.get('updated')}
        self.details.setPlainText(json.dumps(explanation, indent=2) + '\n\nChecks sample specific paths; they do not establish every app or route.\nUDP timing measures a STUN path, not your voice app.\n\nCulvert keeps profiles, history and destinations on this PC.\nNo telemetry or diagnostics are uploaded automatically.')
        if state != self.last_state and not self.demo:
            self.last_state = state; STATE.mkdir(parents=True, exist_ok=True, mode=0o700); path = STATE / 'history.json'
            try: history = json.loads(path.read_text())
            except (OSError, ValueError): history = []
            private_write(path, (history + [{'at': time.time(), 'state': state, 'message': value.get('message', '')}])[-2000:])
        self.tray.setToolTip('Culvert · ' + state)


def main():
    if os.geteuid() == 0: raise SystemExit('Run the Culvert interface as your desktop user, not root.')
    app = QApplication(sys.argv); app.setApplicationName('Culvert'); app.setDesktopFileName('culvert'); app.setStyle('Fusion'); app.setStyleSheet(STYLE)
    window = Window(demo='--demo' in sys.argv); window.show()
    if '--snapshot' in sys.argv:
        target = sys.argv[sys.argv.index('--snapshot') + 1]
        def snapshot():
            for i in range(75): window.chart.add((35 + ((i*17) % 90))*1024)
            window.logo.phase = 0
            window.grab().save(target); print('Qt platform:', QGuiApplication.platformName()); app.quit()
        QTimer.singleShot(1200, snapshot)
    return app.exec()

if __name__ == '__main__': sys.exit(main())
