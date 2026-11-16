import sys
import os
import shutil
import random
import ctypes
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QListWidget, QFileDialog, QSlider, QLabel, QLineEdit, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QShortcut, QKeySequence
import vlc
from send2trash import send2trash

# Professional Dark Media Player Style Sheet
MEDIA_PLAYER_STYLE = """
QMainWindow {
    background-color: #18181c;
}
QWidget {
    color: #d0d0d5;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 11pt;
}
QListWidget {
    background-color: #121215;
    border: 1px solid #282830;
    border-radius: 4px;
    padding: 4px;
    selection-background-color: #3b3b4f;
    selection-color: #ffffff;
}
QLineEdit {
    background-color: #121215;
    border: 1px solid #282830;
    border-radius: 4px;
    padding: 5px;
    color: #e0e0e5;
}
QPushButton {
    background-color: #26262d;
    border: 1px solid #383842;
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: bold;
    color: #e0e0e5;
}
QPushButton:hover {
    background-color: #32323b;
    border: 1px solid #484856;
}
QPushButton:pressed {
    background-color: #1d1d22;
    border: 1px solid #202026;
}
QPushButton:disabled {
    background-color: #1e1e23;
    color: #555560;
    border: 1px solid #2a2a32;
}
QPushButton#AccentButton1 {
    background-color: #2b3a4a;
    border: 1px solid #3a5068;
}
QPushButton#AccentButton1:hover {
    background-color: #354a60;
}
QPushButton#AccentButton2 {
    background-color: #3d2b4a;
    border: 1px solid #553a68;
}
QPushButton#AccentButton2:hover {
    background-color: #4a355d;
}
QPushButton#PurgeButton {
    background-color: #4a2b2b;
    border: 1px solid #683a3a;
}
QPushButton#PurgeButton:hover {
    background-color: #5d3535;
}
QSlider::groove:horizontal {
    border: 1px solid #282830;
    height: 6px;
    background: #121215;
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: #4a6fa5;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #d0d0d5;
    border: 1px solid #ffffff;
    width: 14px;
    margin: -4px 0;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #ffffff;
}
QLabel {
    color: #a0a0ab;
    font-weight: 600;
}
"""

class MediaUtilityApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DannyMediaScrubber v2.3")
        self.setGeometry(100, 100, 950, 720)

        self.vlc_instance = vlc.Instance()
        self.media_player = self.vlc_instance.media_player_new()

        self.playlist = []
        self.current_index = -1
        self.is_seeking = False
        
        self.target_dir_1 = ""
        self.target_dir_2 = ""
        self.target_dir_purge = ""
        
        self.is_muted = False
        self.previous_volume = 100
        
        # Undo last move — stores ('move', original_path, dest_path)
        self.last_move = None

        self.hold_direction = 0
        self.hold_timer = QTimer(self)
        self.hold_timer.setInterval(150)
        self.hold_timer.timeout.connect(self.execute_hold_step)

        self.init_ui()
        self.init_shortcuts()

        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.update_ui)
        self.timer.start()

    def init_ui(self):
        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # --- LEFT PANEL ---
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.video_frame = QWidget()
        self.video_frame.setStyleSheet("background-color: #0a0a0c; border: 1px solid #222228; border-radius: 6px;")
        left_layout.addWidget(self.video_frame, stretch=5)

        scrub_layout = QHBoxLayout()
        self.time_label = QLabel("00:00")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.sliderPressed.connect(lambda: setattr(self, 'is_seeking', True))
        self.slider.sliderReleased.connect(self.apply_seek)
        self.duration_label = QLabel("00:00")
        scrub_layout.addWidget(self.time_label)
        scrub_layout.addWidget(self.slider)
        scrub_layout.addWidget(self.duration_label)
        left_layout.addLayout(scrub_layout)

        skip_layout = QHBoxLayout()
        self.btn_rewind = QPushButton("<< 3s (Hold)")
        self.btn_rewind.pressed.connect(lambda: self.start_holding(-3))
        self.btn_rewind.released.connect(self.stop_holding)
        self.btn_ffwd = QPushButton("3s >> (Hold)")
        self.btn_ffwd.pressed.connect(lambda: self.start_holding(3))
        self.btn_ffwd.released.connect(self.stop_holding)
        skip_layout.addWidget(self.btn_rewind)
        skip_layout.addWidget(self.btn_ffwd)
        left_layout.addLayout(skip_layout)

        vol_layout = QHBoxLayout()
        self.mute_btn = QPushButton("🔊 Mute")
        self.mute_btn.setFixedWidth(90)
        self.mute_btn.clicked.connect(self.toggle_mute)
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(100)
        self.vol_slider.valueChanged.connect(self.change_volume)
        vol_layout.addWidget(self.mute_btn)
        vol_layout.addWidget(self.vol_slider)
        left_layout.addLayout(vol_layout)

        control_layout = QHBoxLayout()
        self.btn_open = QPushButton("Add Files")
        self.btn_open.clicked.connect(self.add_files)
        self.btn_prev = QPushButton("◀ Prev")
        self.btn_prev.clicked.connect(self.prev_file)
        self.btn_play = QPushButton("Play / Pause")
        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_next = QPushButton("Next ▶")
        self.btn_next.clicked.connect(self.next_file)
        control_layout.addWidget(self.btn_open)
        control_layout.addWidget(self.btn_prev)
        control_layout.addWidget(self.btn_play)
        control_layout.addWidget(self.btn_next)
        left_layout.addLayout(control_layout)

        main_layout.addWidget(left_container, stretch=3)

        # --- RIGHT PANEL ---
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        playlist_label = QLabel("Playlist Queue")
        right_layout.addWidget(playlist_label)

        self.playlist_widget = QListWidget()
        self.playlist_widget.itemDoubleClicked.connect(self.play_selected_item)
        right_layout.addWidget(self.playlist_widget, stretch=3)

        self.btn_shuffle = QPushButton("🔀 Shuffle Playlist")
        self.btn_shuffle.clicked.connect(self.shuffle_playlist)
        right_layout.addWidget(self.btn_shuffle)

        # --- DESTINATION 1 ---
        self.btn_move_1 = QPushButton("Move to Dir 1")
        self.btn_move_1.setObjectName("AccentButton1")
        self.btn_move_1.clicked.connect(lambda: self.move_file(1))
        right_layout.addWidget(self.btn_move_1)

        dir_layout_1 = QHBoxLayout()
        self.target_path_edit_1 = QLineEdit()
        self.target_path_edit_1.setPlaceholderText("Target 1 path...")
        self.target_path_edit_1.setReadOnly(True)
        self.btn_set_dir_1 = QPushButton("Set Dir 1")
        self.btn_set_dir_1.setObjectName("AccentButton1")
        self.btn_set_dir_1.clicked.connect(lambda: self.select_target_directory(1))
        dir_layout_1.addWidget(self.target_path_edit_1)
        dir_layout_1.addWidget(self.btn_set_dir_1)
        right_layout.addLayout(dir_layout_1)

        # --- DESTINATION 2 ---
        self.btn_move_2 = QPushButton("Move to Dir 2")
        self.btn_move_2.setObjectName("AccentButton2")
        self.btn_move_2.clicked.connect(lambda: self.move_file(2))
        right_layout.addWidget(self.btn_move_2)

        dir_layout_2 = QHBoxLayout()
        self.target_path_edit_2 = QLineEdit()
        self.target_path_edit_2.setPlaceholderText("Target 2 path...")
        self.target_path_edit_2.setReadOnly(True)
        self.btn_set_dir_2 = QPushButton("Set Dir 2")
        self.btn_set_dir_2.setObjectName("AccentButton2")
        self.btn_set_dir_2.clicked.connect(lambda: self.select_target_directory(2))
        dir_layout_2.addWidget(self.target_path_edit_2)
        dir_layout_2.addWidget(self.btn_set_dir_2)
        right_layout.addLayout(dir_layout_2)

        # --- PURGE FOLDER ---
        self.btn_move_purge = QPushButton("Move to Purge Folder")
        self.btn_move_purge.clicked.connect(lambda: self.move_file(3))
        right_layout.addWidget(self.btn_move_purge)

        dir_layout_purge = QHBoxLayout()
        self.btn_purge_folder = QPushButton("🗑 Purge Folder")
        self.btn_purge_folder.setObjectName("PurgeButton")
        self.btn_purge_folder.clicked.connect(self.purge_folder)
        self.target_path_edit_purge = QLineEdit()
        self.target_path_edit_purge.setPlaceholderText("Purge folder path...")
        self.target_path_edit_purge.setReadOnly(True)
        self.btn_set_dir_purge = QPushButton("Set Purge Dir")
        self.btn_set_dir_purge.clicked.connect(lambda: self.select_target_directory(3))
        dir_layout_purge.addWidget(self.btn_purge_folder)
        dir_layout_purge.addWidget(self.target_path_edit_purge)
        dir_layout_purge.addWidget(self.btn_set_dir_purge)
        right_layout.addLayout(dir_layout_purge)

        # --- UNDO ---
        right_layout.addSpacing(10)
        self.btn_undo = QPushButton("↩ Undo Last Move")
        self.btn_undo.clicked.connect(self.undo_move)
        self.btn_undo.setEnabled(False)
        right_layout.addWidget(self.btn_undo)

        main_layout.addWidget(right_container, stretch=2)

    def init_shortcuts(self):
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self.toggle_play)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, self.prev_file)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, self.next_file)

    def start_holding(self, seconds):
        self.hold_direction = seconds
        self.execute_hold_step()
        self.hold_timer.start()

    def stop_holding(self):
        self.hold_timer.stop()
        self.hold_direction = 0

    def execute_hold_step(self):
        if self.media_player.get_media():
            current_time = self.media_player.get_time()
            new_time = max(0, current_time + (self.hold_direction * 1000))
            self.media_player.set_time(new_time)

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Open Media Files", "", "Video Files (*.mp4 *.mkv *.avi *.mov)")
        if files:
            for f in files:
                self.playlist.append(f)
                self.playlist_widget.addItem(os.path.basename(f))
            if self.current_index == -1:
                self.current_index = 0
                self.load_media(self.current_index)

    def load_media(self, index):
        if 0 <= index < len(self.playlist):
            file_path = self.playlist[index]
            media = self.vlc_instance.media_new(file_path)
            self.media_player.set_media(media)
            if sys.platform.startswith('win'):
                self.media_player.set_hwnd(int(self.video_frame.winId()))
            elif sys.platform.startswith('darwin'):
                self.media_player.set_nsobject(int(self.video_frame.winId()))
            else:
                self.media_player.set_xwindow(int(self.video_frame.winId()))
            self.media_player.play()
            self.media_player.audio_set_volume(self.vol_slider.value())
            self.playlist_widget.setCurrentRow(index)

    def toggle_play(self):
        if self.media_player.is_playing():
            self.media_player.pause()
        else:
            self.media_player.play()

    def prev_file(self):
        if self.playlist and self.current_index > 0:
            self.current_index -= 1
            self.load_media(self.current_index)

    def next_file(self):
        if self.playlist:
            self.current_index = (self.current_index + 1) % len(self.playlist)
            self.load_media(self.current_index)

    def play_selected_item(self, item):
        index = self.playlist_widget.row(item)
        self.current_index = index
        self.load_media(self.current_index)

    def apply_seek(self):
        pos = self.slider.value() / 1000.0
        self.media_player.set_position(pos)
        self.is_seeking = False

    def change_volume(self, value):
        self.media_player.audio_set_volume(value)
        if value > 0 and self.is_muted:
            self.is_muted = False
            self.mute_btn.setText("🔊 Mute")

    def toggle_mute(self):
        if not self.is_muted:
            self.previous_volume = self.vol_slider.value()
            self.vol_slider.setValue(0)
            self.is_muted = True
            self.mute_btn.setText("🔇 Unmute")
        else:
            self.vol_slider.setValue(self.previous_volume if self.previous_volume > 0 else 50)
            self.is_muted = False
            self.mute_btn.setText("🔊 Mute")

    def shuffle_playlist(self):
        if len(self.playlist) <= 1:
            return
        current_file = self.playlist[self.current_index] if 0 <= self.current_index < len(self.playlist) else None
        paired = list(zip(self.playlist, [self.playlist_widget.item(i).text() for i in range(self.playlist_widget.count())]))
        random.shuffle(paired)
        self.playlist, names = zip(*paired)
        self.playlist = list(self.playlist)
        names = list(names)
        self.playlist_widget.clear()
        for name in names:
            self.playlist_widget.addItem(name)
        if current_file in self.playlist:
            self.current_index = self.playlist.index(current_file)
            self.playlist_widget.setCurrentRow(self.current_index)

    def update_ui(self):
        if self.media_player.get_state() == vlc.State.Ended:
            if self.current_index < len(self.playlist) - 1:
                self.next_file()
            return
        if self.media_player.is_playing() and not self.is_seeking:
            length = self.media_player.get_length()
            if length > 0:
                pos = self.media_player.get_position()
                self.slider.setValue(int(pos * 1000))
                current_time = int(self.media_player.get_time() / 1000)
                total_time = int(length / 1000)
                self.time_label.setText(f"{current_time // 60:02d}:{current_time % 60:02d}")
                self.duration_label.setText(f"{total_time // 60:02d}:{total_time % 60:02d}")

    def select_target_directory(self, target_num):
        dir_path = QFileDialog.getExistingDirectory(self, f"Select Directory {target_num}")
        if dir_path:
            if target_num == 1:
                self.target_dir_1 = dir_path
                self.target_path_edit_1.setText(dir_path)
            elif target_num == 2:
                self.target_dir_2 = dir_path
                self.target_path_edit_2.setText(dir_path)
            else:
                self.target_dir_purge = dir_path
                self.target_path_edit_purge.setText(dir_path)

    def resolve_destination(self, target_dir, filename):
        dest_path = os.path.join(target_dir, filename)
        if not os.path.exists(dest_path):
            return dest_path
        base, ext = os.path.splitext(filename)
        counter = 1
        while True:
            new_name = f"{base}_{counter}{ext}"
            dest_path = os.path.join(target_dir, new_name)
            if not os.path.exists(dest_path):
                return dest_path
            counter += 1

    def move_file(self, target_num):
        if target_num == 1:
            target_dir = self.target_dir_1
        elif target_num == 2:
            target_dir = self.target_dir_2
        else:
            target_dir = self.target_dir_purge

        if not target_dir or not os.path.exists(target_dir):
            label = "Purge" if target_num == 3 else str(target_num)
            QMessageBox.warning(self, f"Target Directory Required", f"No destination folder is set for Dir {label} yet!\n\nPlease click the Set button first.")
            return

        if 0 <= self.current_index < len(self.playlist):
            file_path = self.playlist[self.current_index]
            try:
                self.media_player.stop()
                self.media_player.set_media(None)
                QApplication.processEvents()
                normalized_path = os.path.normpath(file_path)
                filename = os.path.basename(normalized_path)
                dest_path = self.resolve_destination(target_dir, filename)
                shutil.move(normalized_path, dest_path)
                self.last_move = (normalized_path, dest_path)
                self.btn_undo.setEnabled(True)
                self.playlist.pop(self.current_index)
                self.playlist_widget.takeItem(self.current_index)
                if self.playlist:
                    self.current_index = min(self.current_index, len(self.playlist) - 1)
                    self.load_media(self.current_index)
                else:
                    self.current_index = -1
            except Exception as e:
                print(f"Move Error Encountered: {e}")

    def purge_folder(self):
        if not self.target_dir_purge or not os.path.exists(self.target_dir_purge):
            QMessageBox.warning(self, "Purge Folder Not Set", "No purge folder is set yet.\n\nPlease click 'Set Purge Dir' first.")
            return
        files = [f for f in os.listdir(self.target_dir_purge) if os.path.isfile(os.path.join(self.target_dir_purge, f))]
        if not files:
            QMessageBox.information(self, "Purge Folder Empty", "The purge folder is already empty.")
            return
        confirm = QMessageBox.question(self, "Confirm Purge", f"Send {len(files)} file(s) to the Recycle Bin?\n\nThis cannot be undone.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            errors = 0
            for f in files:
                try:
                    send2trash(os.path.normpath(os.path.join(self.target_dir_purge, f)))
                except Exception as e:
                    errors += 1
                    print(f"Purge error on {f}: {e}")
            if errors:
                QMessageBox.warning(self, "Purge Complete", f"Done. {errors} file(s) could not be deleted.")
            else:
                QMessageBox.information(self, "Purge Complete", f"{len(files)} file(s) sent to Recycle Bin.")

    def undo_move(self):
        if not self.last_move:
            return
        original_path, dest_path = self.last_move
        try:
            if not os.path.exists(dest_path):
                QMessageBox.warning(self, "Undo Failed", "The moved file no longer exists at its destination.")
                self.last_move = None
                self.btn_undo.setEnabled(False)
                return
            original_dir = os.path.dirname(original_path)
            filename = os.path.basename(original_path)
            restore_path = self.resolve_destination(original_dir, filename)
            shutil.move(dest_path, restore_path)
            self.playlist.append(restore_path)
            self.playlist_widget.addItem(os.path.basename(restore_path))
            self.current_index = len(self.playlist) - 1
            self.playlist_widget.setCurrentRow(self.current_index)
            self.load_media(self.current_index)
            self.last_move = None
            self.btn_undo.setEnabled(False)
        except Exception as e:
            print(f"Undo Error Encountered: {e}")

if __name__ == "__main__":
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('DannyMediaScrubber')
    app = QApplication(sys.argv)
    app.setStyleSheet(MEDIA_PLAYER_STYLE)
    player = MediaUtilityApp()
    player.show()
    sys.exit(app.exec())
