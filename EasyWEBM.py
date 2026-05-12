import sys
import os
import subprocess
import json
import threading
import re
import glob
import customtkinter as ctk # Replaced tkinter
from tkinter import filedialog, END

# Appearance Settings
ctk.set_appearance_mode("Dark")  # Options: "System", "Light", "Dark"
ctk.set_default_color_theme("blue") # Options: "blue", "green", "dark-blue"

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

ffmpeg_path = resource_path("ffmpeg.exe")
ffprobe_path = resource_path("ffprobe.exe")

import customtkinter as ctk
from tkinter import filedialog, END
class ConverterGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.withdraw()
        self.title("EasyWEBM")

        # Initial State
        self.current_file = None
        self.target_bitrate_var = ctk.StringVar(value="0")
        self.target_res_var = ctk.StringVar(value="720p")

        # 1. ADJUSTED CONSTANTS
        # Internal frame is 600. With 20px padding on each side, window needs 640.
        self.main_content_width = 600
        self.padding = 20
        self.base_width = self.main_content_width + (self.padding * 2)

        self.adv_width = 300
        self.height = 500
        self.advanced_mode = False

        # 2. GRID CONFIG
        self.grid_columnconfigure(0, weight=0, minsize=self.base_width)
        self.grid_columnconfigure(1, weight=0, minsize=self.adv_width)
        self.grid_rowconfigure(0, weight=1)  # Allow row to expand

        # 3. MAIN FRAME (The rigid container)
        self.main_frame = ctk.CTkFrame(self, width=self.main_content_width, fg_color="transparent")
        # Use the same padding here as calculated in base_width
        self.main_frame.grid(row=0, column=0, sticky="nsew", padx=self.padding, pady=self.padding)
        self.main_frame.grid_propagate(False)
        # Grid weights inside the main frame
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=0)  # Header
        self.main_frame.grid_rowconfigure(1, weight=0)  # Progress
        self.main_frame.grid_rowconfigure(2, weight=1)  # LOG AREA - Gets extra space
        # --- UI ELEMENTS ---
        self.header_row = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.header_row.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        self.header_row.grid_columnconfigure(0, weight=1)

        self.btn_select = ctk.CTkButton(self.header_row, text="Select Video",
                                        command=self.manual_select, height=40)
        self.btn_select.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        self.btn_adv_toggle = ctk.CTkButton(self.header_row, text="⚙", width=40, height=40,
                                            command=self.toggle_advanced)
        self.btn_adv_toggle.grid(row=0, column=1)

        self.progress = ctk.CTkProgressBar(self.main_frame)
        self.progress.set(0)
        self.progress.grid(row=1, column=0, sticky="ew", pady=(0, 20))

        # LOG AREA - Removed fixed height, using sticky="nsew" to fill row 2
        self.log_area = ctk.CTkTextbox(self.main_frame, state='disabled', font=("Consolas", 12))
        self.log_area.grid(row=2, column=0, sticky="nsew")
        # --- ADVANCED PANE ---
        self.adv_pane = ctk.CTkFrame(self, width=self.adv_width, corner_radius=0, border_width=1)
        self.adv_pane.grid_propagate(False)

        ctk.CTkLabel(self.adv_pane, text="Target Bitrate (kbps):").pack(anchor="w", padx=20, pady=(20, 0))
        self.entry_bitrate = ctk.CTkEntry(self.adv_pane, textvariable=self.target_bitrate_var)
        self.entry_bitrate.pack(fill="x", padx=20, pady=(0, 10))

        self.btn_start = ctk.CTkButton(self.adv_pane, text="START ENCODING", fg_color="green",
                                       hover_color="darkgreen", command=self.convert_video_advanced)
        self.btn_start.pack(side="bottom", pady=20, padx=20, fill="x")

        self.after(10, self.center_window)
    def toggle_advanced(self):
        self.advanced_mode = not self.advanced_mode

        current_x = self.winfo_x()
        current_y = self.winfo_y()

        if self.advanced_mode:
            new_width = self.base_width + self.adv_width
            # Update geometry BEFORE showing the pane to ensure space exists
            self.geometry(f"{new_width}x{self.height}+{current_x}+{current_y}")
            self.adv_pane.grid(row=0, column=1, sticky="nsew")
            self.btn_adv_toggle.configure(fg_color="gray30")
            self.log("> Using advanced mode")
        else:
            # Hide the pane FIRST, then shrink the window
            self.adv_pane.grid_forget()
            self.geometry(f"{self.base_width}x{self.height}+{current_x}+{current_y}")
            self.btn_adv_toggle.configure(fg_color=["#3B8ED0", "#1F6AA5"])
            self.log("> Using automatic mode")

    def center_window(self):
        # Center based on the initial base_width
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        x = (screen_width // 2) - (self.base_width // 2)
        y = (screen_height // 2) - (self.height // 2)

        self.geometry(f'{self.base_width}x{self.height}+{x}+{y}')
        self.deiconify()

    def manual_select(self):
        file_path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.mkv *.avi *.mov *.webm")])
        if file_path:
            self.current_file = file_path
            if self.advanced_mode:
                self.log(f"Video Selected: {file_path}\nAdjust settings and click START.")
                self.pre_calculate_params(file_path)
            else:
                self.start_conversion_thread(file_path)

    def pre_calculate_params(self, file_path):
        """Logic to probe file and fill entries without starting conversion."""
        # You would move your FFPROBE logic here to fill self.target_bitrate_var
        # For now, let's just log
        self.log("Probing file for optimal settings...")
        # (Insert your existing ffprobe logic here to update UI fields)

    def convert_video_advanced(self):
        if self.current_file:
            self.start_conversion_thread(self.current_file)
        else:
            self.log("Error: No file selected!")

    def log(self, message):
        self.log_area.configure(state='normal')
        self.log_area.insert(END, message + "\n")
        self.log_area.see(END)
        self.log_area.configure(state='disabled')

    def manual_select(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Video files", "*.mp4 *.mkv *.avi *.mov *.webm")]
        )
        if file_path:
            if self.advanced_mode:
                self.log("Loading video parameters")
            else:
                self.start_conversion_thread(file_path)


    def start_conversion_thread(self, file_path):
        self.btn_select.configure(state='disabled')
        self.progress.set(0)
        threading.Thread(target=self.convert_video_auto, args=(file_path,), daemon=True).start()

    def run_ffmpeg_with_progress(self, cmd, total_frames, label):
        self.log(f"Starting {label}...")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            encoding='utf-8',
            errors='replace',
            creationflags=0x08000000
        )

        frame_pattern = re.compile(r'frame=\s*(\d+)')

        for line in process.stdout:
            match = frame_pattern.search(line)
            if match and total_frames > 0:
                current_frame = int(match.group(1))
                percent = min((current_frame / total_frames), 1.0) # ctk uses 0.0 to 1.0
                self.progress.set(percent)

        process.wait()
        if process.returncode != 0:
            raise Exception(f"FFmpeg failed with code {process.returncode}")

    def cleanup_logs(self):
        patterns = ["ffmpeg2pass-*.log", "ffmpeg2pass-*.log.data", "ffmpeg2pass-*.log.mbtree"]
        for pattern in patterns:
            for f in glob.glob(pattern):
                try:
                    os.remove(f)
                except:
                    pass
    def get_video_info(self, input_file):
        cmd_info = f'"{ffprobe_path}" -v error -count_packets -show_entries stream=codec_type,nb_read_packets,duration,width,height -show_entries format=duration -of json "{input_file}"'
        info_raw = subprocess.check_output(cmd_info, shell=True, creationflags=0x08000000)
        return json.loads(info_raw)

    def convert_video_auto(self, input_file):
        try:
            # 1. Probe Video Info

            info = self.get_video_info(input_file)

            video_stream = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
            has_audio = any(s['codec_type'] == 'audio' for s in info['streams'])

            if not video_stream:
                raise Exception("No video stream found in file.")

            total_frames = int(video_stream.get('nb_read_packets', 0))
            duration = float(video_stream.get('duration', info.get('format', {}).get('duration', 1)))

            orig_w = int(video_stream.get('width', 0))
            orig_h = int(video_stream.get('height', 0))

            # 2. Bitrate Math
            audio_buffer = 64 if has_audio else 0
            video_kbps = max(((4 * 1024 * 1024 * 8 / duration) / 1000 * 0.95) - audio_buffer, 100)
            self.log(f"Calculated bitrate: {video_kbps:.0f}kbps")

            # 3. Resolution Logic
            if video_kbps < 220: target_size = 240
            elif video_kbps < 300: target_size = 360
            elif video_kbps < 400: target_size = 480
            elif video_kbps < 500: target_size = 576
            else: target_size = 720

            self.log(f"Targeting: {target_size}p | Audio: {'Yes' if has_audio else 'No'}")

            if orig_h > orig_w:
                target_size = min(orig_w, target_size)
                res = f"{target_size}:-2:flags=lanczos"
            else:
                target_size = min(orig_h, target_size)
                res = f"-2:{target_size}:flags=lanczos"

            output_file = os.path.splitext(input_file)[0] + "_4mb.webm"
            self.cleanup_logs()

            # 4. Build Commands
            cpu_threads = os.cpu_count() or 0
            vp9_settings = [
                '-c:v', 'libvpx-vp9',
                '-b:v', f'{int(video_kbps)}k',
                '-auto-alt-ref', '6',
                '-lag-in-frames', '25',
                '-row-mt', '1',
                '-threads', str(cpu_threads),
                '-tile-columns', '1' if orig_h > orig_w else '2'
            ]

            pass1 = [ffmpeg_path, '-y', '-i', input_file] + vp9_settings + [
                '-pass', '1', '-an', '-f', 'null', '-vf', f'scale={res}', 'NUL'
            ]

            pass2 = [ffmpeg_path, '-y', '-i', input_file] + vp9_settings + ['-pass', '2']
            if has_audio:
                pass2 += ['-c:a', 'libopus', '-b:a', f'{audio_buffer}k']
            else:
                pass2 += ['-an']

            pass2 += ['-vf', f'scale={res}', output_file]

            self.run_ffmpeg_with_progress(pass1, total_frames, f"Pass 1 (Analysis)")
            self.run_ffmpeg_with_progress(pass2, total_frames, "Pass 2 (Encoding)")

            self.log(f"\nSUCCESS!\nSaved to: {os.path.basename(output_file)}\n")

        except Exception as e:
            self.log(f"\nERROR: {e}")
        finally:
            self.cleanup_logs()
            self.progress.set(0)
            self.btn_select.configure(state='normal')

if __name__ == "__main__":
    app = ConverterGUI()
    app.mainloop()
