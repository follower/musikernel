#!/usr/bin/python3
"""
This file is part of the MusiKernel project, Copyright MusiKernel Team

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

"""

from PyQt4 import QtGui, QtCore

from libpydaw import liblo, pydaw_util, pydaw_widgets, pydaw_device_dialog
from libpydaw.pydaw_util import *
from libpydaw.translate import _
import libmk
from libmk import mk_project
import libpydaw.strings
from mkplugins import mk_plugin_ui_dict

import time
import gc
import sys
import subprocess


class MkIpc(libmk.AbstractIPC):
    def __init__(self):
        libmk.AbstractIPC.__init__(self, True, "/musikernel/master")

    def stop_server(self):
        print("stop_server called")
        if self.with_osc:
            self.send_configure("exit", "")

    def pydaw_kill_engine(self):
        self.send_configure("abort", "")

    def pydaw_master_vol(self, a_vol):
        self.send_configure("mvol", str(round(a_vol, 8)))

    def pydaw_update_plugin_control(self, a_plugin_uid, a_port, a_val):
        self.send_configure(
            "pc", "|".join(str(x) for x in (a_plugin_uid, a_port, a_val)))

    def pydaw_configure_plugin(self, a_plugin_uid, a_key, a_message):
        self.send_configure(
            "co", "|".join(str(x) for x in (a_plugin_uid, a_key, a_message)))

    def pydaw_midi_learn(self):
        self.send_configure("ml", "")

    def pydaw_load_cc_map(self, a_plugin_uid, a_str):
        self.send_configure(
            "cm", "|".join(str(x) for x in (a_plugin_uid, a_str)))

    def pydaw_add_to_wav_pool(self, a_file, a_uid):
        self.send_configure("wp", "|".join(str(x) for x in (a_uid, a_file)))

    def pydaw_rate_env(self, a_in_file, a_out_file, a_start, a_end):
        f_wait_file = pydaw_get_wait_file_path(a_out_file)
        self.send_configure(
            "renv", "{}\n{}\n{}|{}".format(a_in_file, a_out_file,
            a_start, a_end))
        pydaw_wait_for_finished_file(f_wait_file)

    def pydaw_pitch_env(self, a_in_file, a_out_file, a_start, a_end):
        f_wait_file = pydaw_get_wait_file_path(a_out_file)
        self.send_configure(
            "penv", "{}\n{}\n{}|{}".format(a_in_file, a_out_file,
            a_start, a_end))
        pydaw_wait_for_finished_file(f_wait_file)

    def pydaw_preview_audio(self, a_file):
        self.send_configure("preview", str(a_file))

    def pydaw_stop_preview(self):
        self.send_configure("spr", "")

    def pydaw_set_host(self, a_index):
        self.send_configure("abs", str(a_index))

    def pydaw_reload_wavpool_item(self, a_uid):
        self.send_configure("wr", str(a_uid))


class transport_widget:
    def __init__(self):
        self.suppress_osc = True
        self.start_region = 0
        self.last_bar = 0
        self.last_open_dir = pydaw_util.global_home
        self.group_box = QtGui.QGroupBox()
        self.group_box.setObjectName("transport_panel")
        self.vlayout = QtGui.QVBoxLayout()
        self.group_box.setLayout(self.vlayout)
        self.hlayout1 = QtGui.QHBoxLayout()
        self.vlayout.addLayout(self.hlayout1)
        self.play_button = QtGui.QRadioButton()
        self.play_button.setObjectName("play_button")
        self.play_button.clicked.connect(self.on_play)
        self.hlayout1.addWidget(self.play_button)
        self.stop_button = QtGui.QRadioButton()
        self.stop_button.setChecked(True)
        self.stop_button.setObjectName("stop_button")
        self.stop_button.clicked.connect(self.on_stop)
        self.hlayout1.addWidget(self.stop_button)
        self.rec_button = QtGui.QRadioButton()
        self.rec_button.setObjectName("rec_button")
        self.rec_button.clicked.connect(self.on_rec)
        self.hlayout1.addWidget(self.rec_button)
        self.grid_layout1 = QtGui.QGridLayout()
        self.hlayout1.addLayout(self.grid_layout1)

        f_time_label = QtGui.QLabel(_("Time"))
        f_time_label.setAlignment(QtCore.Qt.AlignCenter)
        self.grid_layout1.addWidget(f_time_label, 0, 27)
        self.time_label = QtGui.QLabel(_("0:00"))
        self.time_label.setMinimumWidth(90)
        self.time_label.setAlignment(QtCore.Qt.AlignCenter)
        self.grid_layout1.addWidget(self.time_label, 1, 27)

        self.menu_button = QtGui.QPushButton(_("Menu"))
        self.grid_layout1.addWidget(self.menu_button, 1, 50)
        self.panic_button = QtGui.QPushButton(_("Panic"))
        self.panic_button.pressed.connect(self.on_panic)
        self.grid_layout1.addWidget(self.panic_button, 0, 50)

        self.grid_layout1.addWidget(QtGui.QLabel(_("Host")), 0, 55)
        self.host_combobox = QtGui.QComboBox()
        self.host_combobox.setMinimumWidth(120)
        self.host_combobox.addItems(["EDM-Next", "Wave-Next"])
        self.host_combobox.currentIndexChanged.connect(
            libmk.MAIN_WINDOW.set_host)
        self.grid_layout1.addWidget(self.host_combobox, 1, 55)

        self.master_vol_knob = pydaw_widgets.pydaw_pixmap_knob(60, -480, 0)
        self.hlayout1.addWidget(self.master_vol_knob)
        self.master_vol_knob.valueChanged.connect(self.master_vol_changed)
        self.master_vol_knob.sliderReleased.connect(self.master_vol_released)
        self.last_region_num = -99
        self.suppress_osc = False

        self.controls_to_disable = (self.menu_button, self.host_combobox)

    def enable_controls(self, a_enabled):
        for f_control in self.controls_to_disable:
            f_control.setEnabled(a_enabled)

    def master_vol_released(self):
        pydaw_util.set_file_setting(
            "master_vol", self.master_vol_knob.value())

    def load_master_vol(self):
        self.master_vol_knob.setValue(
            pydaw_util.get_file_setting("master_vol", int, 0))

    def master_vol_changed(self, a_val):
        if a_val == 0:
            f_result = 1.0
        else:
            f_result = pydaw_util.pydaw_db_to_lin(float(a_val) * 0.1)
        libmk.IPC.pydaw_master_vol(f_result)

    def set_time(self, a_text):
        self.time_label.setText(a_text)

    def on_spacebar(self):
        if libmk.IS_PLAYING:
            self.stop_button.click()
        else:
            self.play_button.click()

    def on_play(self):
        if libmk.IS_RECORDING:
            self.rec_button.setChecked(True)
            return
        if MAIN_WINDOW.current_module.TRANSPORT.on_play():
            libmk.IS_PLAYING = True
            self.enable_controls(False)
        else:
            self.stop_button.setChecked(True)

    def on_ready(self):
        self.load_master_vol()

    def on_stop(self):
        if not libmk.IS_PLAYING and not libmk.IS_RECORDING:
            return
        MAIN_WINDOW.current_module.TRANSPORT.on_stop()
        libmk.IS_PLAYING = False
        libmk.IS_RECORDING = False
        self.enable_controls(True)
        time.sleep(0.1)

    def on_rec(self):
        if libmk.IS_RECORDING:
            return
        if libmk.IS_PLAYING:
            self.play_button.setChecked(True)
            return
        if MAIN_WINDOW.current_module.TRANSPORT.on_rec():
            libmk.IS_PLAYING = True
            libmk.IS_RECORDING = True
            self.enable_controls(False)
        else:
            self.stop_button.setChecked(True)

    def on_panic(self):
        MAIN_WINDOW.current_module.TRANSPORT.on_panic()

    def set_tooltips(self, a_enabled):
        if a_enabled:
            self.panic_button.setToolTip(
                _("Panic button:   Sends a note-off signal on every "
                "note to every instrument\nYou can also use CTRL+P"))
            self.group_box.setToolTip(libpydaw.strings.transport)
        else:
            self.panic_button.setToolTip("")
            self.group_box.setToolTip("")


class MkMainWindow(QtGui.QMainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        libmk.MAIN_WINDOW = self
        try:
            libmk.OSC = liblo.Address(19271)
        except liblo.AddressError as err:
            print((str(err)))
            sys.exit()
        except:
            print("Unable to start OSC with {}".format(19271))
            libmk.OSC = None
        libmk.IPC = MkIpc()
        libmk.TRANSPORT = transport_widget()
        self.setObjectName("mainwindow")
        self.setObjectName("plugin_ui")
        self.setMinimumSize(500, 500)
        self.last_ac_dir = pydaw_util.global_home
        self.widget = QtGui.QWidget()
        self.widget.setObjectName("plugin_ui")
        self.setCentralWidget(self.widget)
        self.main_layout = QtGui.QVBoxLayout(self.widget)
        self.main_layout.setMargin(0)
        self.transport_splitter = QtGui.QSplitter(QtCore.Qt.Vertical)
        self.main_layout.addWidget(self.transport_splitter)

        self.transport_widget = QtGui.QWidget()
        self.transport_hlayout = QtGui.QHBoxLayout(self.transport_widget)
        self.transport_hlayout.setMargin(2)
        self.transport_splitter.addWidget(self.transport_widget)
        self.transport_widget.setSizePolicy(
            QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Minimum)

        self.transport_hlayout.addWidget(
            libmk.TRANSPORT.group_box, alignment=QtCore.Qt.AlignLeft)
        self.transport_stack = QtGui.QStackedWidget()
        self.transport_hlayout.addWidget(
            self.transport_stack, alignment=QtCore.Qt.AlignLeft)
        self.transport_hlayout.addItem(QtGui.QSpacerItem(
            1, 1, QtGui.QSizePolicy.Expanding))

        self.main_stack = QtGui.QStackedWidget()
        self.transport_splitter.addWidget(self.main_stack)

        import edmnext
        import wavenext

        self.wave_editor_module = wavenext

        self.host_modules = (edmnext, wavenext)
        self.host_windows = tuple(x.MAIN_WINDOW for x in self.host_modules)

        self.current_module = edmnext
        self.current_window = edmnext.MAIN_WINDOW

        for f_module in self.host_modules:
            self.transport_stack.addWidget(f_module.TRANSPORT.group_box)

        for f_window in self.host_windows:
            self.main_stack.addWidget(f_window)

        self.ignore_close_event = True

        self.menu_bar = QtGui.QMenu(self)

        libmk.TRANSPORT.menu_button.setMenu(self.menu_bar)
        self.menu_file = self.menu_bar.addMenu(_("File"))

        self.new_action = self.menu_file.addAction(_("New..."))
        self.new_action.triggered.connect(self.on_new)
        self.new_action.setShortcut(QtGui.QKeySequence.New)

        self.open_action = self.menu_file.addAction(_("Open..."))
        self.open_action.triggered.connect(self.on_open)
        self.open_action.setShortcut(QtGui.QKeySequence.Open)

        self.save_action = self.menu_file.addAction(
            _("Save (projects are automatically saved, "
            "this creates a timestamped backup)"))
        self.save_action.triggered.connect(self.on_save)
        self.save_action.setShortcut(QtGui.QKeySequence.Save)

        self.save_as_action = self.menu_file.addAction(
            _("Save As...(this creates a named backup)"))
        self.save_as_action.triggered.connect(self.on_save_as)
        self.save_as_action.setShortcut(QtGui.QKeySequence.SaveAs)

        self.save_copy_action = self.menu_file.addAction(
            _("Save Copy...("
            "This creates a full copy of the project directory)"))
        self.save_copy_action.triggered.connect(self.on_save_copy)

        self.menu_file.addSeparator()

        self.project_history_action = self.menu_file.addAction(
            _("Project History...("
            "This shows a tree of all backups)"))
        self.project_history_action.triggered.connect(self.on_project_history)

        self.menu_file.addSeparator()

        self.offline_render_action = self.menu_file.addAction(
            _("Offline Render..."))
        self.offline_render_action.triggered.connect(self.on_offline_render)

        self.audio_device_action = self.menu_file.addAction(
            _("Hardware Settings..."))
        self.audio_device_action.triggered.connect(
            self.on_change_audio_settings)
        self.menu_file.addSeparator()

        self.kill_engine_action = self.menu_file.addAction(
            _("Kill Audio Engine"))
        self.kill_engine_action.triggered.connect(self.on_kill_engine)
        self.menu_file.addSeparator()

        self.quit_action = self.menu_file.addAction(_("Quit"))
        self.quit_action.triggered.connect(self.close)
        self.quit_action.setShortcut(QtGui.QKeySequence.Quit)

        self.menu_edit = self.menu_bar.addMenu(_("Edit"))

        self.undo_action = self.menu_edit.addAction(_("Undo"))
        self.undo_action.triggered.connect(self.on_undo)
        self.undo_action.setShortcut(QtGui.QKeySequence.Undo)

        self.redo_action = self.menu_edit.addAction(_("Redo"))
        self.redo_action.triggered.connect(self.on_redo)
        self.redo_action.setShortcut(QtGui.QKeySequence.Redo)

        self.menu_appearance = self.menu_bar.addMenu(_("Appearance"))

        self.collapse_splitters_action = self.menu_appearance.addAction(
            _("Collapse Transport and Song Editor"))
        self.collapse_splitters_action.triggered.connect(
            self.on_collapse_splitters)
        self.collapse_splitters_action.setShortcut(
            QtGui.QKeySequence("CTRL+Up"))

        self.restore_splitters_action = self.menu_appearance.addAction(
            _("Restore Transport and Song Editor"))
        self.restore_splitters_action.triggered.connect(
            self.on_restore_splitters)
        self.restore_splitters_action.setShortcut(
            QtGui.QKeySequence("CTRL+Down"))

        self.menu_appearance.addSeparator()

        self.open_theme_action = self.menu_appearance.addAction(
            _("Open Theme..."))
        self.open_theme_action.triggered.connect(self.on_open_theme)

        self.menu_tools = self.menu_bar.addMenu(_("Tools"))

        self.ac_action = self.menu_tools.addAction(_("MP3 Converter..."))
        self.ac_action.triggered.connect(self.mp3_converter_dialog)

        self.ac_action = self.menu_tools.addAction(_("Ogg Converter..."))
        self.ac_action.triggered.connect(self.ogg_converter_dialog)

        self.menu_help = self.menu_bar.addMenu(_("Help"))

        self.troubleshoot_action = self.menu_help.addAction(
            _("Troubleshooting..."))
        self.troubleshoot_action.triggered.connect(self.on_troubleshoot)

        self.version_action = self.menu_help.addAction(_("Version Info..."))
        self.version_action.triggered.connect(self.on_version)

        self.menu_bar.addSeparator()

        self.tooltips_action = self.menu_bar.addAction(_("Show Tooltips"))
        self.tooltips_action.setCheckable(True)
        self.tooltips_action.setChecked(libmk.TOOLTIPS_ENABLED)
        self.tooltips_action.triggered.connect(self.set_tooltips_enabled)

        self.panic_action = QtGui.QAction(self)
        self.addAction(self.panic_action)
        self.panic_action.setShortcut(QtGui.QKeySequence.fromString("CTRL+P"))
        self.panic_action.triggered.connect(libmk.TRANSPORT.on_panic)

        self.spacebar_action = QtGui.QAction(self)
        self.addAction(self.spacebar_action)
        self.spacebar_action.triggered.connect(self.on_spacebar)
        self.spacebar_action.setShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key_Space))

        try:
            self.osc_server = liblo.Server(30321)
        except liblo.ServerError as err:
            print("Error creating OSC server: {}".format(err))
            self.osc_server = None
        if self.osc_server is not None:
            print(self.osc_server.get_url())
            self.osc_server.add_method(
                "musikernel/edmnext", 's',
                edmnext.MAIN_WINDOW.configure_callback)
            self.osc_server.add_method(
                "musikernel/wavenext", 's',
                wavenext.MAIN_WINDOW.configure_callback)
            self.osc_server.add_method(None, None, self.osc_fallback)
            self.osc_timer = QtCore.QTimer(self)
            self.osc_timer.setSingleShot(False)
            self.osc_timer.timeout.connect(self.osc_time_callback)
            self.osc_timer.start(0)

        if pydaw_util.global_pydaw_with_audio:
            self.subprocess_timer = QtCore.QTimer(self)
            self.subprocess_timer.timeout.connect(self.subprocess_monitor)
            self.subprocess_timer.setSingleShot(False)
            self.subprocess_timer.start(1000)

        self.on_restore_splitters()
        self.show()

    def open_in_wave_editor(self, a_file):
        libmk.TRANSPORT.host_combobox.setCurrentIndex(1)
        self.main_stack.repaint()
        self.wave_editor_module.WAVE_EDITOR.open_file(a_file)
        #self.wave_editor_module.WAVE_EDITOR.sample_graph.repaint()

    def set_host(self, a_index):
        self.transport_stack.setCurrentIndex(a_index)
        self.main_stack.setCurrentIndex(a_index)
        self.current_module = self.host_modules[a_index]
        self.current_window = self.host_windows[a_index]
        libmk.IPC.pydaw_set_host(a_index)

    def show_offline_rendering_wait_window(self, a_file_name):
        f_file_name = "{}.finished".format(a_file_name)
        def ok_handler():
            f_window.close()

        def cancel_handler():
            f_window.close()

        def timeout_handler():
            if os.path.isfile(f_file_name):
                f_ok.setEnabled(True)
                f_timer.stop()
                f_time_label.setText(
                    _("Finished in {}").format(f_time_label.text()))
                os.remove(f_file_name)
            else:
                f_elapsed_time = time.time() - f_start_time
                f_time_label.setText(str(round(f_elapsed_time, 1)))

        f_start_time = time.time()
        f_window = QtGui.QDialog(MAIN_WINDOW)
        f_window.setWindowTitle(_("Rendering to .wav, please wait"))
        f_layout = QtGui.QGridLayout()
        f_window.setLayout(f_layout)
        f_time_label = QtGui.QLabel("")
        f_time_label.setMinimumWidth(360)
        f_layout.addWidget(f_time_label, 1, 1)
        f_timer = QtCore.QTimer()
        f_timer.timeout.connect(timeout_handler)

        f_ok = QtGui.QPushButton(_("OK"))
        f_ok.pressed.connect(ok_handler)
        f_ok.setEnabled(False)
        f_layout.addWidget(f_ok)
        f_layout.addWidget(f_ok, 2, 2)
        #f_cancel = QtGui.QPushButton("Cancel")
        #f_cancel.pressed.connect(cancel_handler)
        #f_layout.addWidget(f_cancel, 9, 2)
        f_timer.start(100)
        f_window.exec_()

    def show_offline_rendering_wait_window_v2(self, a_cmd_list, a_file_name):
        f_file_name = "{}.finished".format(a_file_name)
        def ok_handler():
            f_window.close()

        def cancel_handler():
            f_timer.stop()
            try:
                f_proc.kill()
            except Exception as ex:
                print("Exception while killing process\n{}".format(ex))
            if os.path.exists(a_file_name):
                os.remove(a_file_name)
            if os.path.exists(f_file_name):
                os.remove(f_file_name)
            f_window.close()

        def timeout_handler():
            if f_proc.poll() != None:
                f_timer.stop()
                f_ok.setEnabled(True)
                f_cancel.setEnabled(False)
                f_time_label.setText(
                    _("Finished in {}").format(f_time_label.text()))
                os.remove(f_file_name)
                f_proc.communicate()[0]
                #f_output = f_proc.communicate()[0]
                #print(f_output)
                f_exitCode = f_proc.returncode
                if f_exitCode != 0:
                    f_window.close()
                    QtGui.QMessageBox.warning(
                        self, _("Error"),
                        _("Offline render exited abnormally with exit "
                        "code {}").format(f_exitCode))
            else:
                f_elapsed_time = time.time() - f_start_time
                f_time_label.setText(str(round(f_elapsed_time, 1)))

        f_proc = subprocess.Popen(
            a_cmd_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        f_start_time = time.time()
        f_window = QtGui.QDialog(
            MAIN_WINDOW,
            QtCore.Qt.WindowTitleHint | QtCore.Qt.FramelessWindowHint)
        f_window.setWindowTitle(_("Rendering to .wav, please wait"))
        f_window.setMinimumSize(420, 210)
        f_layout = QtGui.QGridLayout()
        f_window.setLayout(f_layout)
        f_time_label = QtGui.QLabel("")
        f_time_label.setMinimumWidth(360)
        f_layout.addWidget(f_time_label, 1, 1)
        f_timer = QtCore.QTimer()
        f_timer.timeout.connect(timeout_handler)

        f_ok_cancel_layout = QtGui.QHBoxLayout()
        f_ok_cancel_layout.addItem(
            QtGui.QSpacerItem(1, 1, QtGui.QSizePolicy.Expanding))
        f_layout.addLayout(f_ok_cancel_layout, 2, 1)
        f_ok = QtGui.QPushButton(_("OK"))
        f_ok.setMinimumWidth(75)
        f_ok.pressed.connect(ok_handler)
        f_ok.setEnabled(False)
        f_ok_cancel_layout.addWidget(f_ok)
        f_cancel = QtGui.QPushButton(_("Cancel"))
        f_cancel.setMinimumWidth(75)
        f_cancel.pressed.connect(cancel_handler)
        f_ok_cancel_layout.addWidget(f_cancel)
        f_timer.start(100)
        f_window.exec_()

    def check_for_empty_directory(self, a_file):
        """ Return true if directory is empty, show error message and
            return False if not
        """
        f_parent_dir = os.path.dirname(a_file)
        if os.listdir(f_parent_dir):
            QtGui.QMessageBox.warning(self, _("Error"),
            _("You must save the project file to an empty directory, use "
            "the 'Create Folder' button to create a directory."))
            return False
        else:
            return True

    def check_for_rw_perms(self, a_file):
        if not os.access(os.path.dirname(str(a_file)), os.W_OK):
            QtGui.QMessageBox.warning(
                self, _("Error"),
                _("You do not have read+write permissions to "
                "{}".format(global_pydaw_home)))
            return False
        else:
            return True

    def subprocess_monitor(self):
        try:
            if PYDAW_SUBPROCESS.poll() != None:
                self.subprocess_timer.stop()
                exitCode = PYDAW_SUBPROCESS.returncode
                if exitCode != 0:
                    QtGui.QMessageBox.warning(
                        self, _("Error"),
                        _("The audio engine died with error code {}, "
                        "please try restarting MusiKernel").format(exitCode))
        except Exception as ex:
            print("subprocess_monitor: {}".format(ex))

    def osc_time_callback(self):
        self.osc_server.recv(1)

    def osc_fallback(self, path, args, types, src):
        print("got unknown message '{}' from '{}'".format(path, src))
        for a, t in zip(args, types):
            print("argument of type '{}': {}".format(t, a))

    def on_new(self):
        if libmk.IS_PLAYING:
            return
        try:
            while True:
                f_file = QtGui.QFileDialog.getSaveFileName(
                    parent=self, caption=_('New Project'),
                    directory="{}/default.{}".format(
                        global_home, global_pydaw_version_string),
                    filter=global_pydaw_file_type_string)
                if not f_file is None and not str(f_file) == "":
                    f_file = str(f_file)
                    if not self.check_for_empty_directory(f_file) or \
                    not self.check_for_rw_perms(f_file):
                        continue
                    if not f_file.endswith("." + global_pydaw_version_string):
                        f_file += "." + global_pydaw_version_string
                    #global_new_project(f_file)
                    pydaw_util.set_file_setting("last-project", f_file)
                    global RESPAWN
                    RESPAWN = True
                    self.prepare_to_quit()
                break
        except Exception as ex:
            libmk.pydaw_print_generic_exception(ex)

    def on_open(self):
        if libmk.IS_PLAYING:
            return
        try:
            f_file = QtGui.QFileDialog.getOpenFileName(
                parent=self, caption=_('Open Project'),
                directory=global_default_project_folder,
                filter=global_pydaw_file_type_string)
            if f_file is None:
                return
            f_file_str = str(f_file)
            if f_file_str == "":
                return
            if not self.check_for_rw_perms(f_file):
                return
            #global_open_project(f_file_str)
            pydaw_util.set_file_setting("last-project", f_file_str)
            global RESPAWN
            RESPAWN = True
            self.prepare_to_quit()
        except Exception as ex:
            libmk.pydaw_print_generic_exception(ex)

    def on_project_history(self):
        f_result = QtGui.QMessageBox.warning(
            self, _("Warning"), _("This will close the application, "
            "restart the application after you're done with the "
            "project history editor"),
            buttons=QtGui.QMessageBox.Ok | QtGui.QMessageBox.Cancel)
        if f_result == QtGui.QMessageBox.Ok:
            libmk.PROJECT.show_project_history()
            self.ignore_close_event = False
            self.prepare_to_quit()

    def on_save(self):
        libmk.PLUGIN_UI_DICT.save_all_plugin_state()
        libmk.PROJECT.create_backup()

    def on_save_as(self):
        if libmk.IS_PLAYING:
            return
        def ok_handler():
            f_name = str(f_lineedit.text()).strip()
            f_name = f_name.replace("/", "")
            if f_name:
                libmk.PLUGIN_UI_DICT.save_all_plugin_state()
                if libmk.PROJECT.create_backup(f_name):
                    f_window.close()
                else:
                    QtGui.QMessageBox.warning(
                        self, _("Error"), _("This name already exists, "
                        "please choose another name"))

        f_window = QtGui.QDialog()
        f_window.setWindowTitle(_("Save As..."))
        f_layout = QtGui.QVBoxLayout(f_window)
        f_lineedit = QtGui.QLineEdit()
        f_lineedit.setMinimumWidth(240)
        f_lineedit.setMaxLength(48)
        f_layout.addWidget(f_lineedit)
        f_ok_layout = QtGui.QHBoxLayout()
        f_layout.addLayout(f_ok_layout)
        f_ok_button = QtGui.QPushButton(_("OK"))
        f_ok_button.pressed.connect(ok_handler)
        f_ok_layout.addWidget(f_ok_button)
        f_cancel_button = QtGui.QPushButton(_("Cancel"))
        f_ok_layout.addWidget(f_cancel_button)
        f_cancel_button.pressed.connect(f_window.close)
        f_window.exec_()

    def on_save_copy(self):
        if libmk.IS_PLAYING:
            return
        try:
            while True:
                f_new_file = QtGui.QFileDialog.getSaveFileName(
                    self, _("Save copy of project as..."),
                    directory="{}/{}.{}".format(global_default_project_folder,
                    libmk.PROJECT.project_file, global_pydaw_version_string))
                if not f_new_file is None and not str(f_new_file) == "":
                    f_new_file = str(f_new_file)
                    if not self.check_for_empty_directory(f_new_file) or \
                    not self.check_for_rw_perms(f_new_file):
                        continue
                    if not f_new_file.endswith(
                    ".{}".format(global_pydaw_version_string)):
                        f_new_file += ".{}".format(global_pydaw_version_string)
                    libmk.PLUGIN_UI_DICT.save_all_plugin_state()
                    libmk.PROJECT.save_project_as(f_new_file)
                    libmk.set_window_title()
                    pydaw_util.set_file_setting("last-project", f_new_file)
                    global RESPAWN
                    RESPAWN = True
                    self.prepare_to_quit()
                    break
                else:
                    break
        except Exception as ex:
            libmk.pydaw_print_generic_exception(ex)


    def prepare_to_quit(self):
        try:
            close_pydaw_engine()
            libmk.PLUGIN_UI_DICT.close_all_plugin_windows()
            if self.osc_server is not None:
                self.osc_timer.stop()
                self.osc_server.free()
            for f_host in self.host_windows:
                f_host.prepare_to_quit()
            self.ignore_close_event = False
            self.subprocess_timer.stop()
            libmk.prepare_to_quit()
            f_quit_timer = QtCore.QTimer(self)
            f_quit_timer.setSingleShot(True)
            f_quit_timer.timeout.connect(self.close)
            f_quit_timer.start(1000)
        except Exception as ex:
            print("Exception thrown while attempting to exit, "
                "forcing MusiKernel to exit")
            print("Exception:  {}".format(ex))
            exit(999)

    def closeEvent(self, event):
        if self.ignore_close_event:
            event.ignore()
            if libmk.IS_PLAYING:
                return
            self.setEnabled(False)
            f_reply = QtGui.QMessageBox.question(
                self, _('Message'), _("Are you sure you want to quit?"),
                QtGui.QMessageBox.Yes | QtGui.QMessageBox.Cancel,
                QtGui.QMessageBox.Cancel)
            if f_reply == QtGui.QMessageBox.Cancel:
                self.setEnabled(True)
                return
            else:
                self.prepare_to_quit()
        else:
            event.accept()

    def on_change_audio_settings(self):
        f_dialog = pydaw_device_dialog.pydaw_device_dialog(True)
        f_dialog.show_device_dialog(a_notify=True)
        if f_dialog.dialog_result:
            global RESPAWN
            RESPAWN = True
            self.prepare_to_quit()

    def on_kill_engine(self):
        libmk.IPC.pydaw_kill_engine()

    def on_open_theme(self):
        try:
            f_file = QtGui.QFileDialog.getOpenFileName(self,
                _("Open a theme file"), "{}/lib/{}/themes".format(
                pydaw_util.global_pydaw_install_prefix,
                global_pydaw_version_string), "MusiKernel Style(*.pytheme)")
            if f_file is not None and str(f_file) != "":
                f_file = str(f_file)
                f_style = pydaw_read_file_text(f_file)
                f_dir = os.path.dirname(f_file)
                f_style = pydaw_escape_stylesheet(f_style, f_dir)
                pydaw_write_file_text(global_user_style_file, f_file)
                QtGui.QMessageBox.warning(
                    MAIN_WINDOW, _("Theme Applied..."),
                    _("Please restart MusiKernel to update the UI"))
        except Exception as ex:
            libmk.pydaw_print_generic_exception(ex)

    def on_version(self):
        f_window = QtGui.QDialog(MAIN_WINDOW)
        f_window.setWindowTitle(_("Version Info"))
        f_window.setFixedSize(420, 150)
        f_layout = QtGui.QVBoxLayout()
        f_window.setLayout(f_layout)
        f_minor_version = pydaw_read_file_text(
            "{}/lib/{}/minor-version.txt".format(
                pydaw_util.global_pydaw_install_prefix,
                global_pydaw_version_string))
        f_version = QtGui.QLabel(
            "{}-{}".format(global_pydaw_version_string, f_minor_version))
        f_version.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        f_layout.addWidget(f_version)
        f_ok_button = QtGui.QPushButton(_("OK"))
        f_layout.addWidget(f_ok_button)
        f_ok_button.pressed.connect(f_window.close)
        f_window.exec_()

    def on_troubleshoot(self):
        f_window = QtGui.QDialog(MAIN_WINDOW)
        f_window.setWindowTitle(_("Troubleshooting"))
        f_window.setFixedSize(640, 460)
        f_layout = QtGui.QVBoxLayout()
        f_window.setLayout(f_layout)
        f_label = QtGui.QTextEdit(libpydaw.strings.troubleshooting)
        f_label.setReadOnly(True)
        f_layout.addWidget(f_label)
        f_ok_button = QtGui.QPushButton(_("OK"))
        f_layout.addWidget(f_ok_button)
        f_ok_button.pressed.connect(f_window.close)
        f_window.exec_()


    def on_spacebar(self):
        libmk.TRANSPORT.on_spacebar()

    def on_collapse_splitters(self):
        #self.song_region_splitter.setSizes([0, 9999])
        self.transport_splitter.setSizes([0, 9999])

    def on_restore_splitters(self):
        #self.song_region_splitter.setSizes([100, 9999])
        self.transport_splitter.setSizes([100, 9999])


    def mp3_converter_dialog(self):
        if pydaw_which("avconv") is None and \
        pydaw_which("ffmpeg") is not None:
            f_avconv = "ffmpeg"
        else:
            f_avconv = "avconv"
        f_lame = "lame"
        for f_app in (f_avconv, f_lame):
            if pydaw_which(f_app) is None:
                QtGui.QMessageBox.warning(self, _("Error"),
                    libpydaw.strings.avconv_error.format(f_app))
                return
        self.audio_converter_dialog("lame", "avconv", "mp3")

    def ogg_converter_dialog(self):
        if pydaw_which("oggenc") is None or \
        pydaw_which("oggdec") is None:
            QtGui.QMessageBox.warning(self, _("Error"),
                _("Error, vorbis-tools are not installed"))
            return
        self.audio_converter_dialog("oggenc", "oggdec", "ogg")

    def audio_converter_dialog(self, a_enc, a_dec, a_label):
        def get_cmd(f_input_file, f_output_file):
            if f_wav_radiobutton.isChecked():
                if a_dec == "avconv" or a_dec == "ffmpeg":
                    f_cmd = [a_dec, "-i", f_input_file, f_output_file]
                elif a_dec == "oggdec":
                    f_cmd = [a_dec, "--output", f_output_file, f_input_file]
            else:
                if a_enc == "oggenc":
                    f_quality = float(str(f_mp3_br_combobox.currentText()))
                    f_quality = (320.0 / f_quality) * 10.0
                    f_quality = pydaw_util.pydaw_clip_value(
                        f_quality, 3.0, 10.0)
                    f_cmd = [a_enc, "-q", str(f_quality),
                         "-o", f_output_file, f_input_file]
                elif a_enc == "lame":
                    f_cmd = [a_enc, "-b", str(f_mp3_br_combobox.currentText()),
                         f_input_file, f_output_file]
            print(f_cmd)
            return f_cmd

        def ok_handler():
            f_input_file = str(f_name.text())
            f_output_file = str(f_output_name.text())
            if f_input_file == "" or f_output_file == "":
                QtGui.QMessageBox.warning(f_window, _("Error"),
                                          _("File names cannot be empty"))
                return
            if f_batch_checkbox.isChecked():
                if f_wav_radiobutton.isChecked():
                    f_ext = ".{}".format(a_label)
                else:
                    f_ext = ".wav"
                f_ext = f_ext.upper()
                f_list = [x for x in os.listdir(f_input_file)
                    if x.upper().endswith(f_ext)]
                if not f_list:
                    QtGui.QMessageBox.warning(f_window, _("Error"),
                          _("No {} files in {}".format(f_ext, f_input_file)))
                    return
                f_proc_list = []
                for f_file in f_list:
                    f_in = "{}/{}".format(f_input_file, f_file)
                    f_out = "{}/{}{}".format(f_output_file,
                        f_file.rsplit(".", 1)[0], self.ac_ext)
                    f_cmd = get_cmd(f_in, f_out)
                    f_proc = subprocess.Popen(f_cmd)
                    f_proc_list.append((f_proc, f_out))
                for f_proc, f_out in f_proc_list:
                    f_status_label.setText(f_out)
                    QtGui.QApplication.processEvents()
                    f_proc.communicate()
            else:
                f_cmd = get_cmd(f_input_file, f_output_file)
                f_proc = subprocess.Popen(f_cmd)
                f_proc.communicate()
            if f_close_checkbox.isChecked():
                f_window.close()
            QtGui.QMessageBox.warning(self, _("Success"), _("Created file(s)"))

        def cancel_handler():
            f_window.close()

        def set_output_file_name():
            if str(f_output_name.text()) == "":
                f_file = str(f_name.text())
                if f_file:
                    f_file_name = f_file.rsplit('.')[0] + self.ac_ext
                    f_output_name.setText(f_file_name)

        def file_name_select():
            try:
                if not os.path.isdir(self.last_ac_dir):
                    self.last_ac_dir = global_home
                if f_batch_checkbox.isChecked():
                    f_dir = QtGui.QFileDialog.getExistingDirectory(f_window,
                        _("Open Folder"), self.last_ac_dir)
                    if f_dir is None:
                        return
                    f_dir = str(f_dir)
                    if f_dir == "":
                        return
                    f_name.setText(f_dir)
                    self.last_ac_dir = f_dir
                else:
                    f_file_name = QtGui.QFileDialog.getOpenFileName(
                        f_window, _("Select a file name to save to..."),
                        self.last_ac_dir,
                        filter=_("Audio Files {}").format(
                        '(*.wav *.{})'.format(a_label)))
                    if not f_file_name is None and str(f_file_name) != "":
                        f_name.setText(str(f_file_name))
                        self.last_ac_dir = os.path.dirname(f_file_name)
                        if f_file_name.lower().endswith(".{}".format(a_label)):
                            f_wav_radiobutton.setChecked(True)
                        elif f_file_name.lower().endswith(".wav"):
                            f_mp3_radiobutton.setChecked(True)
                        set_output_file_name()
                        self.last_ac_dir = os.path.dirname(f_file_name)
            except Exception as ex:
                libmk.pydaw_print_generic_exception(ex)

        def file_name_select_output():
            try:
                if not os.path.isdir(self.last_ac_dir):
                    self.last_ac_dir = global_home
                if f_batch_checkbox.isChecked():
                    f_dir = QtGui.QFileDialog.getExistingDirectory(f_window,
                        _("Open Folder"), self.last_ac_dir)
                    if f_dir is None:
                        return
                    f_dir = str(f_dir)
                    if f_dir == "":
                        return
                    f_output_name.setText(f_dir)
                    self.last_ac_dir = f_dir
                else:
                    f_file_name = QtGui.QFileDialog.getSaveFileName(
                        f_window, _("Select a file name to save to..."),
                        self.last_ac_dir)
                    if not f_file_name is None and str(f_file_name) != "":
                        f_file_name = str(f_file_name)
                        if not f_file_name.endswith(self.ac_ext):
                            f_file_name += self.ac_ext
                        f_output_name.setText(f_file_name)
                        self.last_ac_dir = os.path.dirname(f_file_name)
            except Exception as ex:
                libmk.pydaw_print_generic_exception(ex)

        def format_changed(a_val=None):
            if f_wav_radiobutton.isChecked():
                self.ac_ext = ".wav"
            else:
                self.ac_ext = ".{}".format(a_label)
            if not f_batch_checkbox.isChecked():
                f_str = str(f_output_name.text()).strip()
                if f_str != "" and not f_str.endswith(self.ac_ext):
                    f_arr = f_str.rsplit(".")
                    f_output_name.setText(f_arr[0] + self.ac_ext)

        def batch_changed(a_val=None):
            f_name.setText("")
            f_output_name.setText("")

        self.ac_ext = ".wav"
        f_window = QtGui.QDialog(MAIN_WINDOW)

        f_window.setWindowTitle(_("{} Converter".format(a_label)))
        f_layout = QtGui.QGridLayout()
        f_window.setLayout(f_layout)

        f_name = QtGui.QLineEdit()
        f_name.setReadOnly(True)
        f_name.setMinimumWidth(480)
        f_layout.addWidget(QtGui.QLabel(_("Input:")), 0, 0)
        f_layout.addWidget(f_name, 0, 1)
        f_select_file = QtGui.QPushButton(_("Select"))
        f_select_file.pressed.connect(file_name_select)
        f_layout.addWidget(f_select_file, 0, 2)

        f_output_name = QtGui.QLineEdit()
        f_output_name.setReadOnly(True)
        f_output_name.setMinimumWidth(480)
        f_layout.addWidget(QtGui.QLabel(_("Output:")), 1, 0)
        f_layout.addWidget(f_output_name, 1, 1)
        f_select_file_output = QtGui.QPushButton(_("Select"))
        f_select_file_output.pressed.connect(file_name_select_output)
        f_layout.addWidget(f_select_file_output, 1, 2)

        f_layout.addWidget(QtGui.QLabel(_("Convert to:")), 2, 1)
        f_rb_group = QtGui.QButtonGroup()
        f_wav_radiobutton = QtGui.QRadioButton("wav")
        f_wav_radiobutton.setChecked(True)
        f_rb_group.addButton(f_wav_radiobutton)
        f_wav_layout = QtGui.QHBoxLayout()
        f_wav_layout.addWidget(f_wav_radiobutton)
        f_layout.addLayout(f_wav_layout, 3, 1)
        f_wav_radiobutton.toggled.connect(format_changed)

        f_mp3_radiobutton = QtGui.QRadioButton(a_label)
        f_rb_group.addButton(f_mp3_radiobutton)
        f_mp3_layout = QtGui.QHBoxLayout()
        f_mp3_layout.addWidget(f_mp3_radiobutton)
        f_mp3_radiobutton.toggled.connect(format_changed)
        f_mp3_br_combobox = QtGui.QComboBox()
        f_mp3_br_combobox.addItems(["320", "256", "192", "160", "128"])
        f_mp3_layout.addWidget(QtGui.QLabel(_("Bitrate")))
        f_mp3_layout.addWidget(f_mp3_br_combobox)
        f_layout.addLayout(f_mp3_layout, 4, 1)

        f_batch_checkbox = QtGui.QCheckBox(_("Batch convert entire folder?"))
        f_batch_checkbox.stateChanged.connect(batch_changed)
        f_layout.addWidget(f_batch_checkbox, 6, 1)

        f_close_checkbox = QtGui.QCheckBox("Close on finish?")
        f_close_checkbox.setChecked(True)
        f_layout.addWidget(f_close_checkbox, 9, 1)

        f_ok_layout = QtGui.QHBoxLayout()
        f_ok_layout.addItem(
            QtGui.QSpacerItem(
            10, 10, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum))
        f_ok = QtGui.QPushButton(_("OK"))
        f_ok.setMinimumWidth(75)
        f_ok.pressed.connect(ok_handler)
        f_ok_layout.addWidget(f_ok)
        f_layout.addLayout(f_ok_layout, 9, 2)
        f_cancel = QtGui.QPushButton(_("Cancel"))
        f_cancel.setMinimumWidth(75)
        f_cancel.pressed.connect(cancel_handler)
        f_ok_layout.addWidget(f_cancel)
        f_status_label = QtGui.QLabel("")
        f_layout.addWidget(f_status_label, 15, 1)
        f_window.exec_()

    def on_offline_render(self):
        self.current_window.on_offline_render()

    def on_undo(self):
        self.current_window.on_undo()

    def on_redo(self):
        self.current_window.on_redo()

    def set_tooltips_enabled(self):
        f_enabled = self.tooltips_action.isChecked()
        libmk.TRANSPORT.set_tooltips(f_enabled)
        for f_module in self.host_modules:
            f_module.set_tooltips_enabled(f_enabled)

def final_gc():
    """ Brute-force garbage collect all possible objects to
        prevent the infamous PyQt SEGFAULT-on-exit...
    """
    f_last_unreachable = gc.collect()
    if not f_last_unreachable:
        print("Successfully garbage collected all objects")
        return
    for f_i in range(2, 12):
        time.sleep(0.1)
        f_unreachable = gc.collect()
        if f_unreachable == 0:
            print("Successfully garbage collected all objects "
                "in {} iterations".format(f_i))
            return
        elif f_unreachable >= f_last_unreachable:
            break
        else:
            f_last_unreachable = f_unreachable
    print("gc.collect() returned {} unreachable objects "
        "after {} iterations".format(f_unreachable, f_i))

def flush_events():
    for f_i in range(1, 10):
        if libmk.APP.hasPendingEvents():
            libmk.APP.processEvents()
            time.sleep(0.1)
        else:
            print("Successfully processed all pending events "
                "in {} iterations".format(f_i))
            return
    print("Could not process all events")


def global_check_device():
    f_device_dialog = pydaw_device_dialog.pydaw_device_dialog(
        a_is_running=True)
    f_device_dialog.check_device()

    if not pydaw_util.global_device_val_dict:
        print("It appears that the user did not select "
            "an audio device, quitting...")
        sys.exit(999)


def close_pydaw_engine():
    """ Ask the engine to gracefully stop itself, then kill the process if it
    doesn't exit on it's own"""
    libmk.IPC.stop_server()
    global PYDAW_SUBPROCESS
    if PYDAW_SUBPROCESS is not None:
        f_exited = False
        for i in range(20):
            if PYDAW_SUBPROCESS.poll() == None:
                f_exited = True
                break
            else:
                time.sleep(0.3)
        if not f_exited:
            try:
                if pydaw_util.global_pydaw_is_sandboxed:
                    print("PYDAW_SUBPROCESS did not exit on it's own, "
                          "sending SIGTERM to helper script...")
                    PYDAW_SUBPROCESS.terminate()
                else:
                    print("PYDAW_SUBPROCESS did not exit on it's "
                        "own, sending SIGKILL...")
                    PYDAW_SUBPROCESS.kill()
            except Exception as ex:
                print("Exception raised while trying to kill process: "
                    "{}".format(ex))
        PYDAW_SUBPROCESS = None

def kill_pydaw_engine():
    """ Kill any zombie instances of the engine if they exist. Otherwise, the
    UI won't be able to control the engine"""
    try:
        f_val = subprocess.check_output(['ps', '-ef'])
    except Exception as ex:
        print("kill_pydaw_engine raised Exception during process search, "
              "assuming no zombie processes {}\n".format(ex))
        return
    f_engine_name = "{}-engine".format(global_pydaw_version_string)
    f_val = f_val.decode()
    f_result = []
    for f_line in f_val.split("\n"):
        #print(f_line)
        if f_engine_name in f_line:
            try:
                f_arr = f_line.split()
                f_result.append(int(f_arr[1]))
            except Exception as ex:
                print("kill_pydaw_engine Exception adding PID {}\n\t"
                    "{}".format(f_arr[1], ex))

    if len(f_result) > 0:
        print(f_result)
        f_answer = QtGui.QMessageBox.warning(
            MAIN_WINDOW, _("Warning"),
            libpydaw.strings.multiple_instances_warning,
            buttons=QtGui.QMessageBox.Ok | QtGui.QMessageBox.Cancel)
        if f_answer == QtGui.QMessageBox.Cancel:
            exit(1)
        else:
            for f_pid in set(f_result):
                try:
                    f_kill = ["kill", "-9", f_arr[1]]
                    print(f_kill)
                    f_result = subprocess.check_output(f_kill)
                    print(f_result)
                except Exception as ex:
                    print("kill_pydaw_engine : Exception: {}".format(ex))
            time.sleep(3.0)

def open_pydaw_engine(a_project_path):
    if not global_pydaw_with_audio:
        print(_("Not starting audio because of the audio engine setting, "
              "you can change this in File->HardwareSettings"))
        return

    kill_pydaw_engine() #ensure no running instances of the engine
    f_project_dir = os.path.dirname(a_project_path)
    f_pid = os.getpid()
    print(_("Starting audio engine with {}").format(a_project_path))
    global PYDAW_SUBPROCESS
    if pydaw_util.pydaw_which("pasuspender") is not None:
        f_pa_suspend = True
    else:
        f_pa_suspend = False

    if int(pydaw_util.global_device_val_dict["audioEngine"]) >= 3 \
    and pydaw_util.pydaw_which("x-terminal-emulator") is not None:
        f_sleep = "--sleep"
        if int(pydaw_util.global_device_val_dict["audioEngine"]) == 4 and \
        pydaw_util.pydaw_which("gdb") is not None:
            f_run_with = " gdb "
            f_sleep = ""
        elif int(pydaw_util.global_device_val_dict["audioEngine"]) == 5 and \
        pydaw_util.pydaw_which("valgrind") is not None:
            f_run_with = " valgrind "
            f_sleep = ""
        else:
            f_run_with = ""
        if f_pa_suspend:
            f_cmd = (
                """pasuspender -- x-terminal-emulator -e """
                """bash -c 'ulimit -c unlimited ; """
                """{} "{}" "{}" "{}" {} {} {}; read' """.format(
                f_run_with, pydaw_util.global_pydaw_bin_path,
                global_pydaw_install_prefix, f_project_dir, f_pid,
                pydaw_util.USE_HUGEPAGES, f_sleep))
        else:
            f_cmd = (
                """x-terminal-emulator -e bash -c 'ulimit -c unlimited ; """
                """{} "{}" "{}" "{}" {} {} {}; read' """.format(
                f_run_with, pydaw_util.global_pydaw_bin_path,
                pydaw_util.global_pydaw_install_prefix, f_project_dir,
                f_pid, pydaw_util.USE_HUGEPAGES, f_sleep))
    else:
        if f_pa_suspend:
            f_cmd = 'pasuspender -- "{}" "{}" "{}" {} {}'.format(
                pydaw_util.global_pydaw_bin_path,
                pydaw_util.global_pydaw_install_prefix,
                f_project_dir, f_pid, pydaw_util.USE_HUGEPAGES)
        else:
            f_cmd = '"{}" "{}" "{}" {} {}'.format(
                pydaw_util.global_pydaw_bin_path,
                pydaw_util.global_pydaw_install_prefix,
                f_project_dir, f_pid, pydaw_util.USE_HUGEPAGES)
    print(f_cmd)
    PYDAW_SUBPROCESS = subprocess.Popen([f_cmd], shell=True)

def global_close_all():
    libmk.PLUGIN_UI_DICT.close_all_plugin_windows()
    close_pydaw_engine()
    for f_module in MAIN_WINDOW.host_modules:
        f_module.global_close_all()

def global_ui_refresh_callback(a_restore_all=False):
    """ Use this to re-open all existing items/regions/song in
        their editors when the files have been changed externally
    """
    for f_module in MAIN_WINDOW.host_modules:
        f_module.global_ui_refresh_callback(a_restore_all)

#Opens or creates a new project
def global_open_project(a_project_file, a_wait=True):
    open_pydaw_engine(a_project_file)
    libmk.PROJECT = mk_project.MkProject()
    libmk.PROJECT.suppress_updates = True
    libmk.PROJECT.open_project(a_project_file, False)
    libmk.PROJECT.suppress_updates = False
    libmk.PLUGIN_UI_DICT = mk_plugin_ui_dict(
        libmk.PROJECT, libmk.IPC, MAIN_WINDOW.styleSheet())
    for f_module in MAIN_WINDOW.host_modules:
        f_module.global_open_project(a_project_file)

def global_new_project(a_project_file, a_wait=True):
    open_pydaw_engine(a_project_file)
    libmk.PROJECT = mk_project.MkProject()
    libmk.PROJECT.new_project(a_project_file)
    MAIN_WINDOW.last_offline_dir = libmk.PROJECT.user_folder
    libmk.PLUGIN_UI_DICT = mk_plugin_ui_dict(
        libmk.PROJECT, libmk.IPC, MAIN_WINDOW.styleSheet())
    for f_module in MAIN_WINDOW.host_modules:
        f_module.global_new_project(a_project_file)


#########  Setup and run #########

libmk.APP = QtGui.QApplication(sys.argv)

libmk.APP.setWindowIcon(
    QtGui.QIcon("{}/share/pixmaps/{}.png".format(
    pydaw_util.global_pydaw_install_prefix, global_pydaw_version_string)))

libmk.APP.setStyleSheet(global_stylesheet)

QtCore.QTextCodec.setCodecForLocale(QtCore.QTextCodec.codecForName("UTF-8"))
MAIN_WINDOW = MkMainWindow()
MAIN_WINDOW.setWindowState(QtCore.Qt.WindowMaximized)

global_check_device()

PYDAW_SUBPROCESS = None

libmk.APP.lastWindowClosed.connect(libmk.APP.quit)

if not os.access(global_pydaw_home, os.W_OK):
    QtGui.QMessageBox.warning(
        MAIN_WINDOW.widget, _("Error"),
        _("You do not have read+write permissions to {}, please correct "
        "this and restart MusiKernel".format(global_pydaw_home)))
    MAIN_WINDOW.prepare_to_quit()

default_project_file = pydaw_util.get_file_setting("last-project", str, None)

if not default_project_file:
    default_project_file = "{}/default-project/default.{}".format(
        global_pydaw_home, global_pydaw_version_string)
    print("No default project using {}".format(default_project_file))

if os.path.exists(default_project_file) and \
not os.access(os.path.dirname(default_project_file), os.W_OK):
    QtGui.QMessageBox.warning(
        MAIN_WINDOW, _("Error"),
        _("You do not have read+write permissions to {}, please correct "
        "this and restart MusiKernel".format(
        os.path.dirname(default_project_file))))
    MAIN_WINDOW.prepare_to_quit()

if os.path.exists(default_project_file):
    try:
        global_open_project(default_project_file)
    except Exception as ex:
        QtGui.QMessageBox.warning(
            MAIN_WINDOW, _("Error"),
            _("Error opening project: {}\n{}\n"
            "Opening project recovery dialog.  If the problem "
            "persists or the project can't be recovered, you may "
            "need to delete your settings and/or default project "
            "in \n{}".format(
            default_project_file, ex, pydaw_util.global_pydaw_home)))
        subprocess.Popen([PROJECT_HISTORY_SCRIPT, default_project_file])
        MAIN_WINDOW.prepare_to_quit()
else:
    global_new_project(default_project_file)

RESPAWN = False

libmk.set_window_title()
libmk.APP.setStyle(QtGui.QStyleFactory.create("Fusion"))
libmk.APP.exec_()
time.sleep(0.6)
flush_events()
libmk.APP.deleteLater()
time.sleep(0.6)
libmk.APP = None
time.sleep(0.6)
final_gc()

if RESPAWN:
    CMD = [__file__]
    print("Spawning child UI process {}".format(CMD))
    CHILD_PROC = subprocess.Popen(CMD)
        #, shell=True, stdin=None, stdout=None, stderr=None, close_fds=True)
    #CHILD_PROC.wait()
    time.sleep(6.0)
    print("Parent UI process exiting")

exit(0)
