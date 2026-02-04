import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import serial
import serial.tools.list_ports
import threading
import time
import json
import os

# --- Appearance Setup ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

SETTINGS_FILE = "serial_settings.json"

class SerialTerminalApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Font Configurations ---
        self.font_terminal = ("Consolas", 16)
        self.font_ui = ("Roboto Medium", 14)

        # Window Setup
        self.title("Modern Serial Terminal")
        self.geometry("950x600")
        
        # Handle the "X" button click to save settings before closing
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Serial Connection Object
        self.serial_port = None
        self.is_connected = False
        self.is_scanning = False

        # --- Top Options Frame ---
        self.top_frame = ctk.CTkFrame(self, corner_radius=10)
        self.top_frame.grid(row=0, column=0, padx=20, pady=10, sticky="ew")

        # Port Selection
        self.lbl_port = ctk.CTkLabel(self.top_frame, text="Port:", font=self.font_ui)
        self.lbl_port.grid(row=0, column=0, padx=10, pady=10)
        
        self.port_option_menu = ctk.CTkOptionMenu(
            self.top_frame, values=["Scanning..."], width=140, font=self.font_ui, dropdown_font=self.font_ui
        )
        self.port_option_menu.grid(row=0, column=1, padx=5, pady=10)

        # Refresh Button
        self.btn_refresh = ctk.CTkButton(
            self.top_frame, text="↻", width=40, font=self.font_ui, command=self.refresh_ports
        )
        self.btn_refresh.grid(row=0, column=2, padx=5, pady=10)

        # Baud Rate Selection
        self.lbl_baud = ctk.CTkLabel(self.top_frame, text="Baud:", font=self.font_ui)
        self.lbl_baud.grid(row=0, column=3, padx=10, pady=10)
        
        self.baud_rates = ['300', '1200', '2400', '4800', '9600', '19200', '38400', '57600', '115200']
        self.baud_option_menu = ctk.CTkOptionMenu(
            self.top_frame, values=self.baud_rates, width=110, font=self.font_ui, dropdown_font=self.font_ui
        )
        self.baud_option_menu.set("9600")
        self.baud_option_menu.grid(row=0, column=4, padx=5, pady=10)

        # Auto-Detect Checkbox
        self.autobaud_var = ctk.BooleanVar(value=False)
        self.chk_autobaud = ctk.CTkCheckBox(
            self.top_frame, text="Auto-Detect", variable=self.autobaud_var, font=self.font_ui, 
            width=100, checkbox_width=20, checkbox_height=20
        )
        self.chk_autobaud.grid(row=0, column=5, padx=10, pady=10)

        # Connect Button
        self.btn_connect = ctk.CTkButton(
            self.top_frame, text="Connect", font=self.font_ui, command=self.handle_connect_press, fg_color="green"
        )
        self.btn_connect.grid(row=0, column=6, padx=20, pady=10)

        # --- Main Text Area ---
        self.text_area = ctk.CTkTextbox(
            self, width=600, height=300, corner_radius=10, font=self.font_terminal
        )
        self.text_area.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="nsew")
        self.text_area.configure(state="disabled")

        # --- Bottom Input Frame ---
        self.bottom_frame = ctk.CTkFrame(self, corner_radius=10, fg_color="transparent")
        self.bottom_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        self.bottom_frame.grid_columnconfigure(2, weight=1)

        # Clear Button
        self.btn_clear = ctk.CTkButton(
            self.bottom_frame, text="Clear", width=80, font=self.font_ui, command=self.clear_terminal, fg_color="gray"
        )
        self.btn_clear.grid(row=0, column=0, padx=(0, 10))

        # Line Ending Selection
        self.line_endings = {
            "None": "",
            "New Line (\\n)": "\n",
            "Carriage Return (\\r)": "\r",
            "Both (\\r\\n)": "\r\n"
        }
        self.ending_option = ctk.CTkOptionMenu(
            self.bottom_frame, values=list(self.line_endings.keys()), width=150, font=self.font_ui, dropdown_font=self.font_ui
        )
        self.ending_option.set("Both (\\r\\n)")
        self.ending_option.grid(row=0, column=1, padx=(0, 10))

        # Input Field
        self.input_entry = ctk.CTkEntry(
            self.bottom_frame, placeholder_text="Type command here...", font=self.font_terminal
        )
        self.input_entry.grid(row=0, column=2, padx=(0, 10), sticky="ew")
        self.input_entry.bind("<Return>", lambda event: self.send_data())

        # Send Button
        self.btn_send = ctk.CTkButton(
            self.bottom_frame, text="Send", width=90, font=self.font_ui, command=self.send_data, state="disabled"
        )
        self.btn_send.grid(row=0, column=3)

        # --- Initialize ---
        self.refresh_ports()
        self.load_settings() # Load previous settings on startup

    # --- SAVE / LOAD SETTINGS ---
    def load_settings(self):
        """Reads settings.json and updates UI elements."""
        if not os.path.exists(SETTINGS_FILE):
            return # No file yet, stick to defaults

        try:
            with open(SETTINGS_FILE, 'r') as f:
                settings = json.load(f)
            
            # Apply Baud
            if "baud" in settings and settings["baud"] in self.baud_rates:
                self.baud_option_menu.set(settings["baud"])
            
            # Apply Line Ending
            if "line_ending" in settings and settings["line_ending"] in self.line_endings:
                self.ending_option.set(settings["line_ending"])

            # Apply Auto-Detect Checkbox
            if "auto_detect" in settings:
                self.autobaud_var.set(settings["auto_detect"])

            # Apply Port (Only if it exists in the current list)
            # We do this last because refresh_ports() might have overwritten it
            saved_port = settings.get("port", "")
            current_values = self.port_option_menu.cget("values")
            if saved_port and saved_port in current_values:
                self.port_option_menu.set(saved_port)
            elif saved_port: 
                # Optional: Force set it even if not detected (useful for virtual ports)
                pass 

        except Exception as e:
            print(f"Error loading settings: {e}")

    def on_close(self):
        """Save settings and close the app."""
        settings = {
            "port": self.port_option_menu.get(),
            "baud": self.baud_option_menu.get(),
            "line_ending": self.ending_option.get(),
            "auto_detect": self.autobaud_var.get()
        }
        
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(settings, f)
        except Exception as e:
            print(f"Error saving settings: {e}")
            
        # Close connection cleanly
        self.disconnect_serial()
        self.destroy() # Actually close the window

    # --- STANDARD LOGIC ---
    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        port_list = [port.device for port in ports]
        if port_list:
            self.port_option_menu.configure(values=port_list)
            self.port_option_menu.set(port_list[0])
        else:
            self.port_option_menu.configure(values=["No Ports"])
            self.port_option_menu.set("No Ports")

    def handle_connect_press(self):
        if self.is_connected:
            self.disconnect_serial()
        elif self.is_scanning:
            self.is_scanning = False 
            self.log_to_terminal("--- Scan Cancelled ---\n")
            self.btn_connect.configure(text="Connect", fg_color="green")
        else:
            if self.autobaud_var.get():
                self.start_autobaud_scan()
            else:
                self.connect_serial_direct()

    def start_autobaud_scan(self):
        port = self.port_option_menu.get()
        if port == "No Ports" or port == "Scanning...":
            tk.messagebox.showerror("Error", "No valid port selected.")
            return
        self.is_scanning = True
        self.btn_connect.configure(text="Cancel Scan", fg_color="#D4AF37")
        self.log_to_terminal(f"--- Scanning {port} for baud rate... ---\n")
        thread = threading.Thread(target=self.perform_autobaud, daemon=True)
        thread.start()

    def perform_autobaud(self):
        port = self.port_option_menu.get()
        scan_rates = [115200, 9600, 38400, 57600, 19200, 4800, 2400, 1200]
        found_baud = None
        for baud in scan_rates:
            if not self.is_scanning: break
            self.after(0, self.log_to_terminal, f"Checking {baud}...\n")
            try:
                temp_ser = serial.Serial(port, baud, timeout=0.2)
                time.sleep(0.2) 
                if temp_ser.in_waiting > 0:
                    raw_data = temp_ser.read(temp_ser.in_waiting)
                    try:
                        text_data = raw_data.decode('utf-8')
                        printable_count = sum(1 for c in text_data if c.isprintable() or c in '\r\n\t')
                        if len(text_data) > 0 and (printable_count / len(text_data) > 0.8):
                            found_baud = baud
                            temp_ser.close()
                            break 
                    except UnicodeDecodeError: pass
                temp_ser.close()
            except Exception: pass
        self.after(0, lambda: self.finish_autobaud(found_baud))

    def finish_autobaud(self, baud):
        self.is_scanning = False
        if baud:
            self.baud_option_menu.set(str(baud))
            self.log_to_terminal(f"--- FOUND: {baud} baud. Connecting... ---\n")
            self.connect_serial_direct()
        else:
            self.log_to_terminal("--- Failed: Could not detect baud rate. ---\n")
            self.btn_connect.configure(text="Connect", fg_color="green")

    def connect_serial_direct(self):
        port = self.port_option_menu.get()
        baud = self.baud_option_menu.get()
        if port == "No Ports" or port == "Scanning...":
            tk.messagebox.showerror("Error", "No valid port selected.")
            return
        try:
            self.serial_port = serial.Serial(port, baud, timeout=1)
            self.is_connected = True
            self.btn_connect.configure(text="Disconnect", fg_color="red")
            self.btn_send.configure(state="normal")
            self.port_option_menu.configure(state="disabled")
            self.baud_option_menu.configure(state="disabled")
            self.chk_autobaud.configure(state="disabled")
            self.log_to_terminal(f"--- Connected to {port} at {baud} baud ---\n")
            self.read_thread = threading.Thread(target=self.read_serial, daemon=True)
            self.read_thread.start()
        except serial.SerialException as e:
            tk.messagebox.showerror("Connection Error", str(e))
            self.btn_connect.configure(text="Connect", fg_color="green")

    def disconnect_serial(self):
        if self.serial_port:
            self.is_connected = False
            try: self.serial_port.close()
            except: pass
            self.btn_connect.configure(text="Connect", fg_color="green")
            self.btn_send.configure(state="disabled")
            self.port_option_menu.configure(state="normal")
            self.baud_option_menu.configure(state="normal")
            self.chk_autobaud.configure(state="normal")
            self.log_to_terminal("--- Disconnected ---\n")

    def read_serial(self):
        while self.is_connected and self.serial_port.is_open:
            try:
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting).decode('utf-8', errors='ignore')
                    self.after(0, self.log_to_terminal, data)
            except Exception as e:
                self.after(0, self.log_to_terminal, f"\nError reading: {e}\n")
                break

    def send_data(self):
        if not self.is_connected: return
        message = self.input_entry.get()
        if not message: return
        ending_key = self.ending_option.get()
        ending_char = self.line_endings[ending_key]
        full_message = message + ending_char
        try:
            self.serial_port.write(full_message.encode('utf-8'))
            self.log_to_terminal(f"TX: {message}\n", is_sent=True)
            self.input_entry.delete(0, tk.END)
        except Exception as e:
            tk.messagebox.showerror("Send Error", str(e))

    def log_to_terminal(self, text, is_sent=False):
        self.text_area.configure(state="normal")
        prefix = ">> " if is_sent else ""
        self.text_area.insert(tk.END, prefix + text)
        self.text_area.see(tk.END)
        self.text_area.configure(state="disabled")

    def clear_terminal(self):
        self.text_area.configure(state="normal")
        self.text_area.delete('1.0', tk.END)
        self.text_area.configure(state="disabled")

if __name__ == "__main__":
    app = SerialTerminalApp()
    app.mainloop()