import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, LEFT, RIGHT, BOLD, CENTER, MONOSPACE, TRANSPARENT
import os
import datetime
import platform
import subprocess
import shutil
from contextlib import asynccontextmanager

from .adb_manager import ADBManager
from .file_manager import FileManager
from .utils import get_human_readable_size, get_file_type_icon

@asynccontextmanager
async def busy_cursor(window):
    try:
        window.cursor = "wait" # Using a generic string for busy cursor
        yield
    finally:
        window.cursor = toga.constants.NORMAL # Using toga.constants.NORMAL for default

class adbfs(toga.App):
    async def _get_text_input(self, title, message, initial_value=""):
        future = self.loop.create_future()
        dialog = toga.Window(title=title, closable=False)

        def on_ok(widget):
            future.set_result(text_input.value)
            dialog.close()

        def on_cancel(widget):
            future.set_result(None)
            dialog.close()

        box = toga.Box(style=Pack(direction=COLUMN, padding=20))
        box.add(toga.Label(message, style=Pack(padding_bottom=10)))
        text_input = toga.TextInput(value=initial_value, style=Pack(flex=1), on_confirm=on_ok)
        box.add(text_input)

        button_box = toga.Box(style=Pack(direction=ROW, padding_top=20))
        button_box.add(toga.Button("Cancel", on_press=on_cancel, style=Pack(flex=1)))
        button_box.add(toga.Button("OK", on_press=on_ok, style=Pack(flex=1)))
        box.add(button_box)
        
        # Add key handler for Escape
        def key_handler(window, key, modifiers):
            if key == toga.Key.ESCAPE:
                on_cancel(None) # Call on_cancel
                return True # Event handled
            return False # Event not handled

        dialog.on_key_down = key_handler

        dialog.content = box
        dialog.show()

        return await future

    async def _get_pair_input(self, title):
        future = self.loop.create_future()
        dialog = toga.Window(title=title, closable=False)

        def on_ok(widget):
            future.set_result((ip_input.value, pairing_code_input.value))
            dialog.close()

        def on_cancel(widget):
            future.set_result((None, None))
            dialog.close()

        ip_input = toga.TextInput(placeholder="IP Address:Port", style=Pack(flex=1), on_confirm=on_ok)
        pairing_code_input = toga.TextInput(placeholder="Pairing Code", style=Pack(flex=1), on_confirm=on_ok)

        box = toga.Box(style=Pack(direction=COLUMN, padding=20))
        box.add(toga.Label("Enter device IP address and pairing code:", style=Pack(padding_bottom=10)))
        box.add(ip_input)
        box.add(toga.Label("Pairing Code:", style=Pack(padding_top=10, padding_bottom=10)))
        box.add(pairing_code_input)

        button_box = toga.Box(style=Pack(direction=ROW, padding_top=20))
        button_box.add(toga.Button("Cancel", on_press=on_cancel, style=Pack(flex=1)))
        button_box.add(toga.Button("OK", on_press=on_ok, style=Pack(flex=1)))
        box.add(button_box)

        # Add key handler for Escape
        def key_handler(window, key, modifiers):
            if key == toga.Key.ESCAPE:
                on_cancel(None) # Call on_cancel
                return True # Event handled
            return False # Event not handled

        dialog.on_key_down = key_handler

        dialog.content = box
        dialog.show()

        return await future

    def startup(self):
        """Construct and show the Toga application."""
        self.adb_manager = ADBManager()
        self.file_manager = FileManager(self.adb_manager)

        self.current_device = None
        self.current_remote_path = "/"
        self.current_local_path = os.path.join(os.path.expanduser('~'), "Downloads")

        self.local_sort_column = 'name'
        self.local_sort_direction = 1
        self.remote_sort_column = 'name'
        self.remote_sort_direction = 1
        self.last_selected_remote_row = None

        self.local_raw_data = [] # Initialize
        self.remote_raw_data = [] # Initialize

        # Create commands for context menus
        local_context_menu_group = toga.Group(None)
        rename_local_cmd = toga.Command(
            self.rename_selected_local_file,
            text="Rename",
            tooltip="Rename selected file",
            group=local_context_menu_group,
        )

        remote_context_menu_group = toga.Group(None)
        rename_remote_cmd = toga.Command(
            self.rename_selected_remote_file,
            text="Rename",
            tooltip="Rename selected file",
            group=remote_context_menu_group,
        )

        self.clipboard = None

        copy_remote_cmd = toga.Command(
            self.copy_selected_remote_files,
            text="Copy",
            shortcut=toga.Key.MOD_1 + 'c',
            group=remote_context_menu_group,
        )
        cut_remote_cmd = toga.Command(
            self.cut_selected_remote_files,
            text="Cut",
            shortcut=toga.Key.MOD_1 + 'x',
            group=remote_context_menu_group,
        )
        self.paste_remote_cmd = toga.Command(
            self.paste_remote_files,
            text="Paste",
            shortcut=toga.Key.MOD_1 + 'v',
            group=remote_context_menu_group,
        )
        self.paste_remote_cmd.enabled = False

        # --- Main layout ---
        main_box = toga.Box(style=Pack(direction=COLUMN, padding=10))

        # --- Control Panel ---
        control_box = toga.Box(style=Pack(direction=COLUMN, padding_bottom=10))
        
        # Device selection
        device_box = toga.Box(style=Pack(direction=ROW, alignment=CENTER))
        device_box.add(toga.Label("Device:", style=Pack(padding_right=10)))
        self.device_selection = toga.Selection(style=Pack(flex=1))
        self.device_selection.on_select = self.on_device_selected
        device_box.add(self.device_selection)
        refresh_button = toga.Button("Refresh", on_press=self.refresh_devices, style=Pack(padding_left=10))
        device_box.add(refresh_button)

        self.adb_actions_button = toga.Button(
            "ADB Actions",
            on_press=self.show_adb_actions_window,
            style=Pack(padding_left=5)
        )
        device_box.add(self.adb_actions_button)
        
        # Paths
        local_path_box = toga.Box(style=Pack(direction=ROW, alignment=CENTER, padding_top=5))
        local_path_box.add(toga.Label("Local Path:", style=Pack(padding_right=10)))
        self.local_path_input = toga.TextInput(value=self.current_local_path, style=Pack(flex=1))
        local_path_box.add(self.local_path_input)
        browse_button = toga.Button("Browse", on_press=self.browse_local_path, style=Pack(padding_left=10))
        local_path_box.add(browse_button)

        remote_path_box = toga.Box(style=Pack(direction=ROW, alignment=CENTER, padding_top=5))
        remote_path_box.add(toga.Label("Remote Path:", style=Pack(padding_right=10)))
        self.remote_path_input = toga.TextInput(value=self.current_remote_path, style=Pack(flex=1))
        remote_path_box.add(self.remote_path_input)
        go_button = toga.Button("Go", on_press=self.navigate_remote_path, style=Pack(padding_left=10))
        remote_path_box.add(go_button)

        control_box.add(device_box)
        control_box.add(local_path_box)
        control_box.add(remote_path_box)

        # --- File Explorer ---
        explorer_box = toga.Box(style=Pack(direction=ROW, flex=1, padding_top=10))
        
        # Local files
        local_panel = toga.Box(style=Pack(direction=COLUMN, flex=1, padding_right=5))
        local_panel.add(toga.Label("Local Files", style=Pack(font_weight=BOLD, text_align=CENTER)))
        
        local_sort_toolbox = toga.Box(style=Pack(direction=ROW, alignment=CENTER, padding_top=5))
        local_sort_toolbox.add(toga.Label("정렬 기준:", style=Pack(padding_right=10)))
        local_sort_buttons = toga.Box(style=Pack(direction=ROW))
        local_sort_buttons.add(toga.Button("Name", on_press=lambda w: self.sort_local_table('name'), style=Pack(flex=1)))
        local_sort_buttons.add(toga.Button("Type", on_press=lambda w: self.sort_local_table('type'), style=Pack(flex=1)))
        local_sort_buttons.add(toga.Button("Size", on_press=lambda w: self.sort_local_table('size'), style=Pack(flex=1)))
        local_sort_buttons.add(toga.Button("Date", on_press=lambda w: self.sort_local_table('date'), style=Pack(flex=1)))
        local_sort_toolbox.add(local_sort_buttons)
        local_panel.add(local_sort_toolbox)

        self.local_file_table = toga.Table(headings=["Name", "Type", "Size", "Date"], on_activate=self.on_local_file_activate, style=Pack(flex=1), multiple_select=True)
        self.local_file_table.context_menu = local_context_menu_group
        local_panel.add(self.local_file_table)

        local_buttons = toga.Box(style=Pack(direction=ROW, padding_top=5))
        local_buttons.add(toga.Button("Refresh", on_press=self.refresh_local_file_list, style=Pack(flex=1)))
        local_buttons.add(toga.Button("New Folder", on_press=self.create_local_directory, style=Pack(flex=1)))
        local_buttons.add(toga.Button("Delete", on_press=self.delete_selected_local_file, style=Pack(flex=1)))
        local_buttons.add(toga.Button("Rename", on_press=self.rename_selected_local_file, style=Pack(flex=1)))
        local_buttons.add(toga.Button("Upload", on_press=self.upload_selected_local_file, style=Pack(flex=1)))
        local_panel.add(local_buttons)

        # Remote files
        remote_panel = toga.Box(style=Pack(direction=COLUMN, flex=1, padding_left=5))
        remote_panel.add(toga.Label("Remote Files", style=Pack(font_weight=BOLD, text_align=CENTER)))

        remote_sort_toolbox = toga.Box(style=Pack(direction=ROW, alignment=CENTER, padding_top=5))
        remote_sort_toolbox.add(toga.Label("정렬 기준:", style=Pack(padding_right=10)))
        remote_sort_buttons = toga.Box(style=Pack(direction=ROW))
        remote_sort_buttons.add(toga.Button("Name", on_press=lambda w: self.sort_remote_table('name'), style=Pack(flex=1)))
        remote_sort_buttons.add(toga.Button("Type", on_press=lambda w: self.sort_remote_table('type'), style=Pack(flex=1)))
        remote_sort_buttons.add(toga.Button("Size", on_press=lambda w: self.sort_remote_table('size'), style=Pack(flex=1)))
        remote_sort_buttons.add(toga.Button("Date", on_press=lambda w: self.sort_remote_table('date'), style=Pack(flex=1)))
        remote_sort_toolbox.add(remote_sort_buttons)
        remote_panel.add(remote_sort_toolbox)

        self.remote_file_table = toga.Table(
            headings=["Name", "Type", "Size", "Date"],
            on_activate=self.on_remote_file_activate,
            on_select=self.on_remote_file_select,
            style=Pack(flex=1),
            multiple_select=True
        )
        self.remote_file_table.context_menu = remote_context_menu_group
        remote_panel.add(self.remote_file_table)

        remote_buttons = toga.Box(style=Pack(direction=ROW, padding_top=5))
        remote_buttons.add(toga.Button("Refresh", on_press=self.refresh_remote_file_list, style=Pack(flex=1)))
        remote_buttons.add(toga.Button("New Folder", on_press=self.create_remote_directory, style=Pack(flex=1)))
        remote_buttons.add(toga.Button("Delete", on_press=self.delete_selected_remote_file, style=Pack(flex=1)))
        remote_buttons.add(toga.Button("Rename", on_press=self.rename_selected_remote_file, style=Pack(flex=1)))
        remote_buttons.add(toga.Button("Download", on_press=self.download_selected_remote_file, style=Pack(flex=1)))
        remote_panel.add(remote_buttons)

        explorer_box.add(local_panel)
        explorer_box.add(remote_panel)

        # --- Clipboard Status Label ---
        self.clipboard_label = toga.Label("", style=Pack(padding_top=5, text_align=CENTER))

        # --- Log Area ---
        log_box = toga.Box(style=Pack(direction=COLUMN, padding_top=10))
        log_box.add(toga.Label("Log", style=Pack(font_weight=BOLD)))
        self.log_view = toga.MultilineTextInput(readonly=True, style=Pack(flex=1, height=150, font_family=MONOSPACE))
        self.progress_bar = toga.ProgressBar(max=100, style=Pack(padding_top=5))
        log_box.add(self.log_view)
        log_box.add(self.progress_bar)

        # --- Add components to main box ---
        main_box.add(control_box)
        main_box.add(explorer_box)
        main_box.add(self.clipboard_label)
        main_box.add(log_box)

        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = main_box
        self.main_window.show()

        self.add_background_task(self.refresh_devices)
        self.add_background_task(self.refresh_local_file_list)

    def log_message(self, message):
        self.log_view.value += message + '\n'
        self.log_view.scroll_to_bottom()

    async def refresh_devices(self, widget=None):
        async with busy_cursor(self.main_window):
            self.log_message("Refreshing devices...")
            devices = await self.loop.run_in_executor(None, self.adb_manager.get_connected_devices)
            self.log_message(f"Found devices: {devices}")
            
            items = [f"{d['name']} ({d['id']})" for d in devices]
            self.device_selection.items = items
            
            if devices:
                self.log_message(f"{len(devices)} devices found.")
                if len(devices) == 1:
                    self.log_message("One device found, selecting it automatically.")
                    item_string = f"{devices[0]['name']} ({devices[0]['id']})"
                    self.device_selection.value = item_string
                    await self.on_device_selected()
                else:
                    self.log_message("Multiple devices found. Please select a device from the list.")
            else:
                self.log_message("No devices found.")

    async def on_device_selected(self, widget=None):
        selection = self.device_selection.value
        self.log_message(f"on_device_selected triggered with selection: {selection}")
        if selection:
            device_id = selection.split('(')[-1].rstrip(')')
            self.current_device = device_id
            self.adb_manager.set_current_device(device_id)
            self.log_message(f"Device selected: {selection}")
            self.log_message(f"Current device set to: {self.current_device}")
            
            initial_path = "/sdcard"
            self.log_message(f"Resolving initial path: {initial_path}")
            final_path = await self.resolve_remote_path(initial_path)
            
            if final_path:
                self.current_remote_path = final_path
                self.remote_path_input.value = self.current_remote_path
                await self.refresh_remote_file_list()
            else:
                self.log_message(f"Failed to resolve initial path: {initial_path}")
                # Fallback to root if /sdcard fails to resolve
                self.current_remote_path = "/"
                self.remote_path_input.value = self.current_remote_path
                await self.refresh_remote_file_list()
        else:
            self.log_message("on_device_selected: selection is empty.")

    async def on_remote_file_select(self, widget, row=None): # Add default value for row
        # With multiple_select=True, Toga/Cocoa passes row=None.
        # This breaks the rename-on-second-click feature.
        # Disabling it for now to avoid incorrect behavior.
        # A more complex implementation would be needed to track selection changes.
        pass



    async def restart_adb_server(self, widget=None):
        self.log_message("restart_adb_server method called.")
        async with busy_cursor(self.main_window):
            self.log_message("Attempting to restart ADB server...")
            success, message = await self.loop.run_in_executor(None, self.adb_manager.restart_server)
            if success:
                self.log_message(message)
                await self.refresh_devices()
            else:
                self.log_message(f"Failed to restart ADB server: {message}")
                await self.main_window.error_dialog("ADB Server Error", message)

    async def show_adb_actions_window(self, widget):
        # Create a new window
        action_window = toga.Window(title="ADB Actions", size=(300, 200), closable=True)
        
        # Create a box to hold the buttons
        box = toga.Box(style=Pack(direction=COLUMN, padding=10))

        async def pair_action_handler(widget):
            await self._execute_adb_action(self.pair_device, action_window)

        # Pair Button
        pair_button = toga.Button(
            "Pair Device...",
            on_press=pair_action_handler,
            style=Pack(flex=1, padding=5)
        )
        box.add(pair_button)

        async def connect_action_handler(widget):
            await self._execute_adb_action(self.connect_device, action_window)

        # Connect Button
        connect_button = toga.Button(
            "Connect Device...",
            on_press=connect_action_handler,
            style=Pack(flex=1, padding=5)
        )
        box.add(connect_button)

        async def restart_action_handler(widget):
            await self._execute_adb_action(self.restart_adb_server, action_window)

        # Restart Server Button
        restart_button = toga.Button(
            "Restart ADB Server",
            on_press=restart_action_handler,
            style=Pack(flex=1, padding=5)
        )
        box.add(restart_button)

        action_window.content = box
        action_window.show()

    async def _execute_adb_action(self, action_func, window_to_close):
        # Execute the action
        await action_func()
        # Close the window after the action is done
        window_to_close.close()

    async def pair_device(self, widget=None):
        self.log_message("pair_device method called.")
        ip_address, pairing_code = await self._get_pair_input('Pair Device')
        
        if ip_address and pairing_code:
            self.log_message(f"IP address for pairing: {ip_address}")
            self.log_message(f"Pairing code entered.")
            async with busy_cursor(self.main_window):
                self.log_message(f"Attempting to pair with {ip_address}...")
                success, message = await self.loop.run_in_executor(None, self.adb_manager.pair_device, ip_address, pairing_code)
                if success:
                    self.log_message(f"Pairing successful: {message}")
                    self.log_message(f"Attempting to connect to {ip_address} after successful pairing...")
                    connect_success, connect_message = await self.loop.run_in_executor(None, self.adb_manager.connect_device, ip_address)
                    if connect_success:
                        self.log_message(f"Connection successful after pairing: {connect_message}")
                    else:
                        self.log_message(f"Connection failed after pairing: {connect_message}")
                    await self.refresh_devices()
                else:
                    self.log_message(f"Pairing failed: {message}")
                    await self.main_window.error_dialog("Pairing Failed", message)
        else:
            self.log_message("IP address or pairing code not provided. Pairing cancelled.")

    async def connect_device(self, widget=None):
        self.log_message("connect_device method called.")
        ip_address = await self._get_text_input('Connect Device', 'Enter IP address and port:')
        if ip_address:
            self.log_message(f"IP address for connecting: {ip_address}")
            async with busy_cursor(self.main_window):
                self.log_message(f"Attempting to connect to {ip_address}...")
                success, message = await self.loop.run_in_executor(None, self.adb_manager.connect_device, ip_address)
                if success:
                    self.log_message(f"Connection successful: {message}")
                    await self.refresh_devices()
                else:
                    self.log_message(f"Connection failed: {message}")
                    await self.main_window.error_dialog("Connection Failed", message)
        else:
            self.log_message("IP address not provided. Connection cancelled.")

    async def browse_local_path(self, widget=None):
        try:
            folder_path = await self.main_window.select_folder_dialog("Select Local Path")
            if folder_path:
                self.current_local_path = str(folder_path)
                self.local_path_input.value = self.current_local_path
                await self.refresh_local_file_list()
        except ValueError:
            pass

    async def navigate_remote_path(self, widget=None):
        self.current_remote_path = self.remote_path_input.value
        await self.refresh_remote_file_list()

    async def refresh_local_file_list(self, widget=None):
        async with busy_cursor(self.main_window):
            self.log_message(f"Loading local files from: {self.current_local_path}")
            try:
                def load_local_files():
                    items = []
                    parent_path = os.path.dirname(self.current_local_path)
                    if parent_path and parent_path != self.current_local_path:
                        items.append({
                            'name': "⬆️ ..",
                            'type': "Parent",
                            'size': "-",
                            'date': "",
                            'full_path': parent_path
                        })

                    for item_name in os.listdir(self.current_local_path):
                        item_path = os.path.join(self.current_local_path, item_name)
                        try:
                            stat = os.stat(item_path)
                            is_directory = os.path.isdir(item_path)
                            
                            if is_directory:
                                file_type = "Folder"
                                size = ""
                            else:
                                file_type = "File"
                                size = get_human_readable_size(stat.st_size)
                            
                            date = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                            
                            items.append({
                                'name': f"{ '📁' if is_directory else get_file_type_icon(item_name) } {item_name}",
                                'type': file_type,
                                'size': size,
                                'date': date,
                                'full_path': item_path 
                            })
                        except (OSError, IOError):
                            continue
                    return items

                raw_items = await self.loop.run_in_executor(None, load_local_files)
                self.local_raw_data = raw_items # Store raw data
                # Apply the current sort order after loading new data
                self.sort_local_table(None)
                self.log_message(f"Loaded {len(raw_items)} local items.")

            except Exception as e:
                self.log_message(f"Failed to load local files: {e}")

    async def refresh_remote_file_list(self, widget=None):
        if not self.current_device:
            self.log_message("No device selected.")
            return
        self.log_message(f"Loading remote files from: {self.current_remote_path}")
        
        async with busy_cursor(self.main_window):
            try:
                files = await self.loop.run_in_executor(None, self.adb_manager.get_file_list, f"'{self.current_remote_path}'")
                
                items = []
                if self.current_remote_path != "/":
                    parent_path = os.path.dirname(self.current_remote_path)
                    if not parent_path or parent_path == ".":
                        parent_path = "/"
                    items.append({
                        'name': "⬆️ ..",
                        'type': "Parent",
                        'size': "-",
                        'date': "",
                        'full_path': parent_path
                    })

                for file_info in files:
                    # Initialize variables to ensure they always have a value
                    icon, file_type, size = "📄", "File", ""

                    is_directory = file_info.get('is_directory', False)
                    is_link = file_info.get('is_link', False)
                    name = file_info['name']
                    
                    if file_info.get('is_directory', False):
                        file_type = "Folder"
                        icon = "📁"
                        size = ""
                    elif file_info.get('is_link', False):
                        file_type = "Link"
                        icon = "🔗"
                        size = ""
                    # Reconstruct the full path from the unquoted base path and the name
                    # to avoid path pollution from the adb_manager call.
                    correct_full_path = os.path.join(self.current_remote_path, name).replace('//', '/')

                    items.append({
                        'name': f"{icon} {name}",
                        'type': file_type,
                        'size': size,
                        'date': file_info['date'],
                        'full_path': correct_full_path
                    })

                
                raw_items = items # 'items' already contains dictionaries
                self.remote_raw_data = raw_items # Store raw data
                # Apply the current sort order after loading new data
                self.sort_remote_table(None)
                self.log_message(f"Loaded {len(raw_items)} remote items.")

            except Exception as e:
                self.log_message(f"Failed to load remote files: {e}")

    async def on_local_file_activate(self, widget, row):
        print(f"DEBUG: Local file activated: {row.name if row else 'None'}") # Add debug print
        if not row:
            return
        
        if row.type == "Parent":
            self.current_local_path = os.path.dirname(self.current_local_path)
            self.local_path_input.value = self.current_local_path
            self.local_sort_column = 'name'
            self.local_sort_direction = 1
            await self.refresh_local_file_list()
        elif row.type == "Folder":
            self.current_local_path = row.full_path
            self.local_path_input.value = self.current_local_path
            self.local_sort_column = 'name'
            self.local_sort_direction = 1
            await self.refresh_local_file_list()
        else: # File
            try:
                if platform.system() == 'Darwin':
                    subprocess.run(['open', row.full_path])
                elif platform.system() == 'Windows':
                    os.startfile(row.full_path)
                else:
                    subprocess.run(['xdg-open', row.full_path])
            except Exception as e:
                self.log_message(f"Could not open file: {e}")

    async def _download_and_open_file(self, remote_path):
        file_name = os.path.basename(remote_path)
        local_path = os.path.join(self.current_local_path, file_name)

        async with busy_cursor(self.main_window):
            self.log_message(f"Downloading {remote_path} to {local_path} and opening...")

            def progress_handler(transferred, total):
                def update_progress():
                    if total > 0:
                        self.progress_bar.value = (transferred / total) * 100
                    else:
                        if not self.progress_bar.is_running:
                            self.progress_bar.start()
                self.loop.call_soon_threadsafe(update_progress)

            def download_job():
                return self.adb_manager.pull_file(f"'{remote_path}'", local_path, progress_handler)

            self.progress_bar.value = 0
            success = await self.loop.run_in_executor(None, download_job)
            
            if self.progress_bar.is_running:
                self.progress_bar.stop()
            self.progress_bar.value = 0

            if success:
                self.log_message("Download complete.")
                await self.refresh_local_file_list()
                try:
                    if platform.system() == 'Darwin':
                        subprocess.run(['open', local_path])
                    elif platform.system() == 'Windows':
                        os.startfile(local_path)
                    else:
                        subprocess.run(['xdg-open', local_path])
                except Exception as e:
                    self.log_message(f"Could not open file: {e}")
            else:
                self.log_message("Download failed.")
                await self.main_window.error_dialog("Error", "Download failed.")

    async def resolve_remote_path(self, path):
        for _ in range(10): # Limit to 10 levels of links to avoid infinite loops
            is_link = await self.loop.run_in_executor(None, self.adb_manager.is_link, f"'{path}'")
            if is_link:
                target = await self.loop.run_in_executor(None, self.adb_manager.get_link_target, f"'{path}'")
                if not target:
                    self.log_message(f"Could not resolve link target for {path}")
                    await self.main_window.error_dialog("Error", "Could not resolve link target.")
                    return None
                
                if not target.startswith('/'):
                    target = os.path.join(os.path.dirname(path), target)
                path = os.path.normpath(target).replace('\\', '/')
                self.log_message(f"🔗 Following link to: {path}")
            else:
                return path
        self.log_message(f"Too many levels of symbolic links for {path}")
        await self.main_window.error_dialog("Error", "Too many levels of symbolic links.")
        return None

    async def on_remote_file_activate(self, widget, row):
        print(f"DEBUG: Remote file activated: {row.name if row else 'None'}")
        if not row:
            return

        # Prioritize the 'type' information from the row object, which is more reliable
        # than performing a new check that might fail intermittently.
        if row.type == "Folder" or row.type == "Parent":
            self.current_remote_path = row.full_path
            self.remote_path_input.value = self.current_remote_path
            self.log_message(f"Entering directory: {self.current_remote_path}")
            self.remote_sort_column = 'name'
            self.remote_sort_direction = 1
            await self.refresh_remote_file_list()
            return

        path_to_process = row.full_path

        # For links, we must resolve the path and then check if the target is a directory.
        if row.type == "Link":
            self.log_message(f"🔗 Resolving link: {path_to_process}")
            final_path = await self.resolve_remote_path(path_to_process)
            if not final_path:
                return  # Stop if link resolution fails
            path_to_process = final_path

            is_dir = await self.loop.run_in_executor(None, self.adb_manager.is_directory, f"'{path_to_process}'")
            if is_dir:
                self.current_remote_path = path_to_process
                self.remote_path_input.value = self.current_remote_path
                self.log_message(f"Entering directory: {self.current_remote_path}")
                self.remote_sort_column = 'name'
                self.remote_sort_direction = 1
                await self.refresh_remote_file_list()
                return

        # If it's not a Folder, Parent, or a Link to a directory, treat it as a file.
        self.log_message(f"Target is a file: {path_to_process}")
        await self._download_and_open_file(path_to_process)

    async def create_local_directory(self, widget):
        folder_name = await self._get_text_input("Create Folder", "Enter folder name:")
        if folder_name:
            try:
                os.makedirs(os.path.join(self.current_local_path, folder_name), exist_ok=True)
                await self.refresh_local_file_list()
            except Exception as e:
                self.log_message(f"Error creating local directory: {e}")
                await self.main_window.error_dialog("Error", f"Could not create directory: {e}")

    async def delete_selected_local_file(self, widget):
        selection = self.local_file_table.selection
        if not selection:
            await self.main_window.info_dialog("Delete", "No file selected.")
            return

        file_names = ", ".join([row.name.split(' ', 1)[1] if ' ' in row.name else row.name for row in selection])
        message = f"Are you sure you want to delete {len(selection)} item(s): {file_names}?"
        if len(message) > 200:
            message = f"Are you sure you want to delete {len(selection)} item(s)?"

        confirmed = await self.main_window.confirm_dialog("Delete", message)
        if confirmed:
            success_count = 0
            failures = []
            for row in selection:
                try:
                    if os.path.isdir(row.full_path):
                        shutil.rmtree(row.full_path)
                    else:
                        os.remove(row.full_path)
                    success_count += 1
                except Exception as e:
                    failures.append(row.name)
                    self.log_message(f"Error deleting local file {row.name}: {e}")
            
            self.log_message(f"Successfully deleted {success_count} item(s).")
            if failures:
                self.log_message(f"Failed to delete {len(failures)} item(s): {', '.join(failures)}.")
                await self.main_window.error_dialog("Error", f"Could not delete: {', '.join(failures)}")

            await self.refresh_local_file_list()

    async def rename_selected_local_file(self, widget):
        selection = self.local_file_table.selection
        if not selection:
            await self.main_window.info_dialog("Rename", "No file selected.")
            return

        if len(selection) > 1:
            await self.main_window.info_dialog("Rename", "Please select only one file to rename.")
            return

        row = selection[0]
        old_name = row.name.split(' ', 1)[1] if ' ' in row.name else row.name
        new_name = await self._get_text_input("Rename", "Enter new name:", initial_value=old_name)

        if new_name and new_name != old_name:
            old_path = row.full_path
            new_path = os.path.join(self.current_local_path, new_name)
            try:
                os.rename(old_path, new_path)
                await self.refresh_local_file_list()
            except Exception as e:
                self.log_message(f"Error renaming local file: {e}")
                await self.main_window.error_dialog("Error", f"Could not rename file: {e}")

    async def upload_selected_local_file(self, widget):
        if not self.current_device:
            await self.main_window.info_dialog("Error", "No device selected.")
            return
        
        selection = self.local_file_table.selection
        if not selection:
            await self.main_window.info_dialog("Upload", "No file selected.")
            return

        files_to_upload = [row for row in selection if row.type != "Folder"]
        if not files_to_upload:
            await self.main_window.info_dialog("Upload", "Cannot upload folders. Please select files.")
            return

        if len(files_to_upload) < len(selection):
            await self.main_window.info_dialog("Upload", "Skipping folders. Only files will be uploaded.")

        async with busy_cursor(self.main_window):
            failures = []
            for row in files_to_upload:
                local_path = row.full_path
                file_name = row.name.split(' ', 1)[1] if ' ' in row.name else row.name
                remote_path = os.path.join(self.current_remote_path, file_name).replace('\\', '/')

                self.log_message(f"Uploading {local_path} to {remote_path}")
                
                def progress_handler(transferred, total):
                    def update_progress():
                        if total > 0:
                            self.progress_bar.value = (transferred / total) * 100
                    self.loop.call_soon_threadsafe(update_progress)

                def upload_job():
                    return self.adb_manager.push_file(local_path, f"'{remote_path}'", progress_handler)
                self.progress_bar.value = 0
                success = await self.loop.run_in_executor(None, upload_job)
                self.progress_bar.value = 0

                if success:
                    self.log_message(f"Upload of {file_name} complete.")
                else:
                    self.log_message(f"Upload of {file_name} failed.")
                    failures.append(file_name)
            
            await self.refresh_remote_file_list()

            if failures:
                await self.main_window.error_dialog("Error", f"Failed to upload some files: {', '.join(failures)}")
            else:
                self.log_message("All selected files uploaded successfully.")

    async def create_remote_directory(self, widget):
        if not self.current_device:
            await self.main_window.info_dialog("Error", "No device selected.")
            return
        
        folder_name = await self._get_text_input("Create Remote Folder", "Enter folder name:")
        if folder_name:
            remote_path = os.path.join(self.current_remote_path, folder_name).replace('\\', '/')
            async with busy_cursor(self.main_window):
                self.log_message(f"Creating remote directory: {remote_path}")
                success = await self.loop.run_in_executor(None, self.adb_manager.create_directory, f"'{remote_path}'")
                if success:
                    self.log_message("Directory created.")
                    await self.refresh_remote_file_list()
                else:
                    self.log_message("Failed to create directory.")
                    await self.main_window.error_dialog("Error", "Failed to create directory.")

    async def delete_selected_remote_file(self, widget):
        if not self.current_device:
            await self.main_window.info_dialog("Error", "No device selected.")
            return
        selection = self.remote_file_table.selection
        if not selection:
            await self.main_window.info_dialog("Delete", "No file selected.")
            return

        items_to_delete = [row for row in selection if row.type != "Parent"]

        if not items_to_delete:
            await self.main_window.info_dialog("Delete", "Cannot delete the parent directory entry.")
            return

        file_names = ", ".join([row.name.split(' ', 1)[1] if ' ' in row.name else row.name for row in items_to_delete])
        message = f"Are you sure you want to delete {len(items_to_delete)} item(s): {file_names}?"
        if len(message) > 200: # Avoid overly long dialog messages
            message = f"Are you sure you want to delete {len(items_to_delete)} item(s)?"

        confirmed = await self.main_window.confirm_dialog("Delete", message)
        if confirmed:
            async with busy_cursor(self.main_window):
                failures = []
                for row in items_to_delete:
                    # Quote the path to handle spaces and special characters
                    quoted_path = f"'{row.full_path}'"
                    self.log_message(f"Deleting remote file: {quoted_path}")
                    success = await self.loop.run_in_executor(None, self.adb_manager.delete_file, quoted_path)
                    if not success:
                        failures.append(row.name)
                        self.log_message(f"Failed to delete file: {quoted_path}")
                
                await self.refresh_remote_file_list()

                if failures:
                    self.log_message(f"Failed to delete: {', '.join(failures)}")
                    await self.main_window.error_dialog("Error", f"Failed to delete some files: {', '.join(failures)}")
                else:
                    self.log_message("All selected files deleted.")

    async def rename_selected_remote_file(self, widget):
        if not self.current_device:
            await self.main_window.info_dialog("Error", "No device selected.")
            return
        
        selection = self.remote_file_table.selection
        if not selection:
            await self.main_window.info_dialog("Rename", "No file selected.")
            return

        if len(selection) > 1:
            await self.main_window.info_dialog("Rename", "Please select only one file to rename.")
            return

        row = selection[0]

        if row.type == "Parent":
            await self.main_window.info_dialog("Rename", "Cannot rename the parent directory entry.")
            return

        old_name = row.name.split(' ', 1)[1] if ' ' in row.name else row.name
        new_name = await self._get_text_input("Rename", "Enter new name:", initial_value=old_name)

        if new_name and new_name != old_name:
            old_path = row.full_path
            new_path = os.path.join(self.current_remote_path, new_name).replace('\\', '/')
            
            async with busy_cursor(self.main_window):
                # Quote the paths to handle spaces and special characters
                quoted_old_path = f"'{old_path}'"
                quoted_new_path = f"'{new_path}'"
                self.log_message(f"Renaming remote file {quoted_old_path} to {quoted_new_path}")
                success = await self.loop.run_in_executor(None, self.adb_manager.rename_file, quoted_old_path, quoted_new_path)
                
                if success:
                    self.log_message("Rename successful.")
                    await self.refresh_remote_file_list()
                else:
                    self.log_message("Rename failed.")
                    await self.main_window.error_dialog("Error", "Could not rename file.")

    async def download_selected_remote_file(self, widget):
        if not self.current_device:
            await self.main_window.info_dialog("Error", "No device selected.")
            return
        selection = self.remote_file_table.selection
        if not selection:
            await self.main_window.info_dialog("Download", "No file selected.")
            return

        files_to_download = [row for row in selection if row.type != "Folder"]
        if not files_to_download:
            await self.main_window.info_dialog("Download", "Cannot download folders. Please select files.")
            return

        if len(files_to_download) < len(selection):
            await self.main_window.info_dialog("Download", "Skipping folders. Only files will be downloaded.")

        async with busy_cursor(self.main_window):
            failures = []
            for row in files_to_download:
                remote_path = row.full_path
                file_name = row.name.split(' ', 1)[1] if ' ' in row.name else row.name
                local_path = os.path.join(self.current_local_path, file_name)

                self.log_message(f"Downloading {remote_path} to {local_path}")

                def progress_handler(transferred, total):
                    def update_progress():
                        if total > 0:
                            self.progress_bar.value = (transferred / total) * 100
                        else:
                            if not self.progress_bar.is_running:
                                self.progress_bar.start()
                    
                    self.loop.call_soon_threadsafe(update_progress)

                def download_job():
                    return self.adb_manager.pull_file(remote_path, local_path, progress_handler)

                self.progress_bar.value = 0
                success = await self.loop.run_in_executor(None, download_job)
                
                if self.progress_bar.is_running:
                    self.progress_bar.stop()
                self.progress_bar.value = 0

                if success:
                    self.log_message(f"Download of {file_name} complete.")
                else:
                    self.log_message(f"Download of {file_name} failed.")
                    failures.append(file_name)
            
            await self.refresh_local_file_list()

            if failures:
                await self.main_window.error_dialog("Error", f"Failed to download some files: {', '.join(failures)}")
            else:
                self.log_message("All selected files downloaded successfully.")

    def sort_table(self, table, raw_data, column, sort_column_attr, sort_direction_attr):
        if column is None:
            # Re-apply the current sort order without toggling
            column = getattr(self, sort_column_attr)
            new_direction = getattr(self, sort_direction_attr)
        else:
            # This is a user click on a column header, so toggle
            current_sort_column = getattr(self, sort_column_attr)
            current_sort_direction = getattr(self, sort_direction_attr)

            if current_sort_column == column:
                new_direction = -current_sort_direction
            else:
                new_direction = 1
            
            setattr(self, sort_column_attr, column)
            setattr(self, sort_direction_attr, new_direction)

        parent_item = []
        data_to_sort = []

        # Handle parent item (⬆️ ..) separately
        if raw_data and raw_data[0].get('type') == 'Parent':
            parent_item = [raw_data[0]]
            data_to_sort = raw_data[1:]
        else:
            data_to_sort = raw_data

        def sort_key(item): # 'item' is now a dictionary
            val = item.get(column) # Access dictionary key
            if column == 'size':
                if val == '-': return -1
                try:
                    # Need to handle formatted size for sorting
                    if isinstance(val, str):
                        num, unit = val.split()
                        units = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4, 'PB': 1024**5}
                        return float(num) * units.get(unit, 1)
                    return val # If it's already a number
                except:
                    return 0
            if column == 'date':
                if not val: return ""
                return val
            # For 'name' and 'type', ensure case-insensitive sorting
            return str(val).lower() if val is not None else ""

        data_to_sort.sort(key=sort_key, reverse=new_direction == -1)
        
        table.data = parent_item + data_to_sort

    def sort_local_table(self, column):
        self.sort_table(self.local_file_table, self.local_raw_data, column, 'local_sort_column', 'local_sort_direction')

    def sort_remote_table(self, column):
        self.sort_table(self.remote_file_table, self.remote_raw_data, column, 'remote_sort_column', 'remote_sort_direction')

    def update_clipboard_label(self):
        if not self.clipboard or not self.clipboard.get('paths'):
            self.clipboard_label.text = ""
            self.paste_remote_cmd.enabled = False
            return

        operation = self.clipboard['operation']
        paths = self.clipboard['paths']
        
        if len(paths) == 1:
            path_str = os.path.basename(paths[0])
        else:
            path_str = f"{len(paths)} items"

        op_str = "복사됨" if operation == 'copy' else "잘라내기"
        self.clipboard_label.text = f"{path_str} {op_str}"
        self.paste_remote_cmd.enabled = True

    async def copy_selected_remote_files(self, widget):
        selection = self.remote_file_table.selection
        if not selection:
            await self.main_window.info_dialog("Copy", "No file selected.")
            return
        
        paths = [row.full_path for row in selection]
        self.clipboard = {'operation': 'copy', 'paths': paths}
        self.update_clipboard_label()
        self.log_message(f"Copied {len(paths)} items to clipboard.")

    async def cut_selected_remote_files(self, widget):
        selection = self.remote_file_table.selection
        if not selection:
            await self.main_window.info_dialog("Cut", "No file selected.")
            return
        
        paths = [row.full_path for row in selection]
        self.clipboard = {'operation': 'cut', 'paths': paths}
        self.update_clipboard_label()
        self.log_message(f"Cut {len(paths)} items to clipboard.")

    async def paste_remote_files(self, widget):
        if not self.clipboard or not self.clipboard.get('paths'):
            await self.main_window.info_dialog("Paste", "Clipboard is empty.")
            return

        operation = self.clipboard['operation']
        source_paths = self.clipboard['paths']
        destination_dir = self.current_remote_path

        for src_path in source_paths:
            if destination_dir.startswith(src_path + '/'):
                await self.main_window.error_dialog("Paste Error", f"Cannot {operation} '{os.path.basename(src_path)}' into a subdirectory of itself.")
                return

        async with busy_cursor(self.main_window):
            failures = []
            for src_path in source_paths:
                file_name = os.path.basename(src_path)
                dest_path = os.path.join(destination_dir, file_name).replace('\\', '/')

                if os.path.dirname(src_path.rstrip('/')) == destination_dir.rstrip('/'):
                    if operation == 'copy':
                        self.log_message(f"Copying a file into the same directory is not supported yet. Skipping {file_name}.")
                        failures.append(f"{file_name} (copy to same dir)")
                        continue
                    else: # cut
                        continue
                
                if operation == 'copy':
                    is_dir = await self.loop.run_in_executor(None, self.adb_manager.is_directory, src_path)
                    if is_dir:
                        self.log_message(f"Copying directories is not supported yet. Skipping {file_name}.")
                        failures.append(f"{file_name} (is a directory)")
                        continue

                if operation == 'copy':
                    self.log_message(f"Copying {src_path} to {dest_path}")
                    import tempfile
                    with tempfile.TemporaryDirectory() as temp_dir:
                        local_temp_path = os.path.join(temp_dir, file_name)
                        
                        self.log_message(f"Pulling {src_path} to temporary location...")
                        pull_success = await self.loop.run_in_executor(None, self.adb_manager.pull_file, f"'{src_path}'", local_temp_path, None)
                        
                        if pull_success:
                            self.log_message(f"Pushing from temporary location to {dest_path}...")
                            push_success = await self.loop.run_in_executor(None, self.adb_manager.push_file, local_temp_path, f"'{dest_path}'", None)
                            if not push_success:
                                failures.append(file_name)
                                self.log_message(f"Failed to push {file_name}.")
                        else:
                            failures.append(file_name)
                            self.log_message(f"Failed to pull {file_name}.")

                else: # cut (move)
                    self.log_message(f"Moving {src_path} to {dest_path}")
                    success = await self.loop.run_in_executor(None, self.adb_manager.rename_file, f"'{src_path}'", f"'{dest_path}'")
                    if not success:
                        failures.append(file_name)
                        self.log_message(f"Failed to move {file_name}.")

        if operation == 'cut':
            self.clipboard = None 
            self.update_clipboard_label()

        await self.refresh_remote_file_list()

        if failures:
            await self.main_window.error_dialog("Paste Error", f"Failed to {operation} some items: {', '.join(failures)}")
        else:
            self.log_message(f"Paste ({operation}) successful.")


def main():
    return adbfs()