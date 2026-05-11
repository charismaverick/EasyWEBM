import sys
import os
import subprocess
import json
import threading
import re
import glob
from tkinter import Tk, Button, filedialog, scrolledtext, END
from tkinter.ttk import Progressbar

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

ffmpeg_path = resource_path("ffmpeg.exe")
ffprobe_path = resource_path("ffprobe.exe")

class ConverterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("VP9 4MB Compressor")
        
        self.btn_select = Button(root, text="Select Video", command=self.manual_select, height=2, font=("Segoe UI", 10))
        self.btn_select.pack(pady=10, fill='x', padx=50)

        self.progress = Progressbar(root, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(pady=10, padx=50, fill='x')

        self.log_area = scrolledtext.ScrolledText(root, state='disabled', height=15, font=("Consolas", 9))
        self.log_area.pack(pady=10, padx=10, fill='both', expand=True)

        if len(sys.argv) > 1:
            self.start_conversion_thread(sys.argv[1])

    def log(self, message):
        self.log_area.configure(state='normal')
        self.log_area.insert(END, message + "\n")
        self.log_area.see(END)
        self.log_area.configure(state='disabled')

    def manual_select(self):
        file_path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.mkv *.avi *.mov *.webm")])
        if file_path: 
            self.start_conversion_thread(file_path)

    def start_conversion_thread(self, file_path):
        self.btn_select.config(state='disabled')
        self.progress['value'] = 0
        threading.Thread(target=self.convert_video, args=(file_path,), daemon=True).start()

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
                percent = min((current_frame / total_frames) * 100, 100)
                self.progress['value'] = percent
                self.root.update_idletasks()

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

    def convert_video(self, input_file):
        try:
            # 1. Probe Video Info
            cmd_info = f'"{ffprobe_path}" -v error -count_packets -show_entries stream=codec_type,nb_read_packets,duration,width,height -show_entries format=duration -of json "{input_file}"'
            info_raw = subprocess.check_output(cmd_info, shell=True, creationflags=0x08000000)
            info = json.loads(info_raw)
            
            video_stream = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
            has_audio = any(s['codec_type'] == 'audio' for s in info['streams'])
            
            if not video_stream:
                raise Exception("No video stream found in file.")

            total_frames = int(video_stream.get('nb_read_packets', 0))
            duration = float(video_stream.get('duration', info.get('format', {}).get('duration', 1)))
            
            # Get dimensions to detect orientation
            orig_w = int(video_stream.get('width', 0))
            orig_h = int(video_stream.get('height', 0))

            # 2. Bitrate Math
            audio_buffer = 64 if has_audio else 0
            video_kbps = max(((4 * 1024 * 1024 * 8 / duration) / 1000 * 0.95) - audio_buffer, 100)
            self.log(f"Calculated bitrate: {video_kbps:.0f}kbps")
            
            # 3. Resolution Logic (Targeting the shortest side)
            if video_kbps < 220: target_size = 240
            elif video_kbps < 300: target_size = 360
            elif video_kbps < 400: target_size = 480
            elif video_kbps < 500: target_size = 576
            else: target_size = 720
            self.log(f"Output resolution: {target_size}p")
            self.log(f"Orientation: {'Portrait' if orig_h > orig_w else 'Landscape'}")
            self.log(f"Audio detected: {'Yes' if has_audio else 'No'}")

            # Apply target to the shortest side
            if orig_h > orig_w:
                # Portrait: Width is shortest, set Width to target, Height auto
                target_size = min(orig_w, target_size)
                res = f"{target_size}:-2:flags=lanczos"
            else:
                # Landscape/Square: Height is shortest (or equal), set Height to target, Width auto
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
                '-tile-columns'
            ]
            if orig_h > orig_w:
                vp9_settings += '1'
            else:
                vp9_settings += '2'
                
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

            self.log(f"\nSUCCESS!\nSaved to: {os.path.basename(output_file)}")
            
        except Exception as e:
            self.log(f"\nERROR: {e}")
        finally:
            self.cleanup_logs() 
            self.progress['value'] = 0
            self.btn_select.config(state='normal')
def center_window(window, width=600, height=450):
    window.update_idletasks()
    sw = window.winfo_screenwidth()
    sh = window.winfo_screenheight()
    x = (sw // 2) - (width // 2)
    y = (sh // 2) - (height // 2)
    window.geometry(f'{width}x{height}+{x}+{y}')

if __name__ == "__main__":
    root = Tk()
    root.withdraw()
    center_window(root, 600, 450)
    app = ConverterGUI(root)
    root.deiconify()
    root.mainloop()
