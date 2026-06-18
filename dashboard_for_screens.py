import csv
import datetime
import os
import sys
import argparse
import tkinter as tk
from tkinter import font
from ctypes import windll

# ==============================================================================
# CONFIGURATION & TESTING CONTROLS
# ==============================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEDULE_FILE = os.path.join(SCRIPT_DIR, 'schedule.csv')

BOTTOM_TEXT = "*Master Overview Dashboard developed for Tech Cornwall T-Level Placement Project."

# ------------------------------------------------------------------------------
# ⏱️ TIME TRAVEL TESTING OVERRIDE:
START_TEST_TIME = datetime.datetime(2026, 7, 2, 11, 15, 0) # YYYY, MM, DD, HH, MM, SS
# ------------------------------------------------------------------------------

CONFERENCE_DATE = datetime.date.today()

# --- Colour palette ---
PALETTE_BASE_BG = "#f68b3b"       # Main header orange
PALETTE_DASH_BG = "#e5e5e5"       # Dashboard background
PALETTE_CARD_BG_IDLE = "#ffffff"  # Quiet room
PALETTE_CARD_BG_ACTIVE = "#fdba3e"# Active talk occurring
PALETTE_CARD_BG_WARN = "#ffbc03"  # Pre-start warning
PALETTE_TEXT_DARK = "#3e3e3f"
PALETTE_TEXT_LIGHT = "#ffffff"
PALETTE_TEXT_MUTED = "#6b6b6b"

ROOM_BADGE_COLORS = {
    "ENGINEERING": "#c83432",
    "DESIGN & PRODUCT": "#0066a8",
    "TEAMS": "#6b6b6b",
    "ORGANISATIONS": "#0a8750",
    "WORKSHOPS": "#5a3ca9",
}

SECONDS_BEFORE_INTERMISSION_WARNING = 5 * 60


def set_dpi_awareness():
    if sys.platform.startswith("win"):
        try:
            windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def parse_date_flexible(date_str: str) -> datetime.date | None:
    clean_str = date_str.strip()
    if not clean_str: return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try: return datetime.datetime.strptime(clean_str, fmt).date()
        except ValueError: pass
    return None


def load_full_schedule(filename: str):
    schedule: list[dict] = []
    try:
        with open(filename, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                clean_row = {k.strip(): v for k, v in row.items() if k}
                row_track = clean_row.get('Track') or clean_row.get('Room Name') or clean_row.get('Room')
                if not row_track:
                    continue

                date_obj = parse_date_flexible(clean_row.get('Date') or '') or CONFERENCE_DATE
                time_str = (clean_row.get('Start Time') or '').strip()
                if not time_str: continue
                
                # Split time ranges like "11:00am - 11:45am" down to just the start time
                if "-" in time_str:
                    time_str = time_str.split("-")[0].strip()

                try:
                    # Parse 12-hour format with AM/PM
                    start_time_obj = datetime.datetime.strptime(time_str.lower(), '%I:%M%p').time()
                except ValueError:
                    try:
                        start_time_obj = datetime.datetime.strptime(time_str, '%H:%M').time()
                    except ValueError:
                        continue

                start_datetime = datetime.datetime.combine(date_obj, start_time_obj)
                duration_str = (clean_row.get('Duration') or '').strip()
                duration_minutes = int(duration_str) if duration_str.isdigit() else 0
                end_datetime = start_datetime + datetime.timedelta(minutes=duration_minutes)

                schedule.append({
                    'track': row_track.strip(),
                    'date': date_obj,
                    'type': (clean_row.get('Type') or 'Talk').strip(),
                    'start': start_datetime,
                    'end': end_datetime,
                    'speaker': (clean_row.get('Speaker') or '').strip(),
                    'title': (clean_row.get('Talk Title') or clean_row.get('Title') or '').strip(),
                })
        schedule.sort(key=lambda e: e['start'])
        return schedule
    except Exception as e:
        print(f"ERROR: Failed to load schedule: {e}")
        return []


def compute_display_state_for_track(track_schedule: list[dict], now: datetime.datetime):
    current = None
    upcoming: list[dict] = []

    for e in track_schedule:
        if e['start'].date() == now.date():
            if e['start'] <= now < e['end']:
                current = e
            if e['start'] >= now:
                upcoming.append(e)

    next_event = upcoming[0] if upcoming else None

    if not current and not next_event:
        return {'mode': 'none', 'current': None, 'next_event': None}
    if current:
        return {'mode': 'in_talk', 'current': current, 'next_event': next_event}

    delta = next_event['start'] - now
    seconds_to_start = int(delta.total_seconds())
    event_type = (next_event.get('type') or '').strip().lower()

    if event_type not in ("break", "social") and seconds_to_start <= SECONDS_BEFORE_INTERMISSION_WARNING:
        mode = 'pre_start'
    else:
        mode = 'normal'

    return {'mode': mode, 'current': None, 'next_event': next_event}


class MasterDashboardApp:
    def __init__(self, root, schedule_file: str = SCHEDULE_FILE, width: int = 1920, height: int = 1080):
        self.root = root
        self.root.title("Master Schedule Dashboard")
        self.root.configure(bg=PALETTE_DASH_BG)
        
        self.schedule_file = schedule_file
        self.all_events = load_full_schedule(schedule_file)
        
        self.tracks = sorted(list(set(e['track'] for e in self.all_events)))
        
        self.initial_real_time = datetime.datetime.now()
        
        self.screen_width = width
        self.screen_height = height
        scale = min(self.screen_width / 1920, self.screen_height / 1080)
        scale = max(1, scale)
        self.scale = scale

        self.title_font = font.Font(family='KG Second Chances Solid', size=max(int(24 * scale), 14), weight='bold')
        self.room_font = font.Font(family='KG Second Chances Solid', size=max(int(20 * scale), 12), weight='bold')
        self.text_font = font.Font(family='KG Second Chances Solid', size=max(int(14 * scale), 10))

        # --- Top Header Bar ---
        self.header_frame = tk.Frame(root, bg=PALETTE_BASE_BG, height=int(80 * self.scale))
        self.header_frame.pack(fill="x", side="top")

        self.header_title = tk.Label(self.header_frame, text="LIVE EVENTS OVERVIEW", fg=PALETTE_TEXT_LIGHT, bg=PALETTE_BASE_BG, font=self.title_font)
        self.header_title.pack(side="left", padx=int(30 * self.scale), pady=int(15 * self.scale))

        self.time_label = tk.Label(self.header_frame, text="00:00", fg=PALETTE_TEXT_LIGHT, bg=PALETTE_BASE_BG, font=self.title_font)
        self.time_label.pack(side="right", padx=int(30 * self.scale), pady=int(15 * self.scale))

        # --- Main Grid Layout Frame ---
        self.grid_container = tk.Frame(root, bg=PALETTE_DASH_BG)
        self.grid_container.pack(fill="both", expand=True, padx=int(20 * self.scale), pady=int(20 * self.scale))

        self.room_cards = {}
        self.setup_grid()

        self.update_interval_ms = 1000
        self.update()

    def setup_grid(self):
        num_rooms = len(self.tracks)
        if num_rooms == 0:
            err_lbl = tk.Label(self.grid_container, text="No tracks or rooms found in schedule.csv", font=self.title_font, bg=PALETTE_DASH_BG)
            err_lbl.pack(expand=True)
            return

        cols = 3 if num_rooms > 4 else 2
        for i in range(cols):
            self.grid_container.grid_columnconfigure(i, weight=1, uniform="equal")

        for index, room_name in enumerate(self.tracks):
            r = index // cols
            c = index % cols
            
            self.grid_container.grid_rowconfigure(r, weight=1, uniform="equal")

            card = tk.Frame(self.grid_container, bg=PALETTE_CARD_BG_IDLE, bd=2, relief="groove")
            card.grid(row=r, column=c, padx=10, pady=10, sticky="nsew")

            badge_color = ROOM_BADGE_COLORS.get(room_name.upper(), "#3e3e3f")
            title_banner = tk.Frame(card, bg=badge_color)
            title_banner.pack(fill="x", side="top")

            lbl_room = tk.Label(title_banner, text=room_name.upper(), fg=PALETTE_TEXT_LIGHT, bg=badge_color, font=self.room_font, anchor="w", padx=10)
            lbl_room.pack(fill="x", pady=4)

            content_frame = tk.Frame(card, bg=PALETTE_CARD_BG_IDLE, padx=10, pady=10)
            content_frame.pack(fill="both", expand=True)

            lbl_now_status = tk.Label(content_frame, text="NOW:", font=self.text_font, fg=PALETTE_TEXT_MUTED, bg=PALETTE_CARD_BG_IDLE, anchor="w")
            lbl_now_status.pack(fill="x")

            lbl_now_details = tk.Label(content_frame, text="Empty / Available", font=self.text_font, fg=PALETTE_TEXT_DARK, bg=PALETTE_CARD_BG_IDLE, anchor="w", justify="left")
            lbl_now_details.pack(fill="x", pady=(0, 10))

            lbl_next_status = tk.Label(content_frame, text="NEXT:", font=self.text_font, fg=PALETTE_TEXT_MUTED, bg=PALETTE_CARD_BG_IDLE, anchor="w")
            lbl_next_status.pack(fill="x")

            lbl_next_details = tk.Label(content_frame, text="No scheduled events", font=self.text_font, fg=PALETTE_TEXT_DARK, bg=PALETTE_CARD_BG_IDLE, anchor="w", justify="left")
            lbl_next_details.pack(fill="x")

            self.room_cards[room_name] = {
                "card": card, "content_frame": content_frame, "now_status": lbl_now_status,
                "now_details": lbl_now_details, "next_status": lbl_next_status, "next_details": lbl_next_details
            }

    def update(self):
        real_now = datetime.datetime.now()
        if 'START_TEST_TIME' in globals():
            time_passed = real_now - self.initial_real_time
            now = START_TEST_TIME + time_passed
            now = now.replace(microsecond=0)
        else:
            now = real_now.replace(microsecond=0)

        self.time_label.config(text=now.strftime("%H:%M:%S"))

        for room_name in self.tracks:
            track_schedule = [e for e in self.all_events if e['track'] == room_name]
            state = compute_display_state_for_track(track_schedule, now)
            
            widgets = self.room_cards[room_name]
            
            bg_color = PALETTE_CARD_BG_IDLE
            now_text = "Open Room / Break"
            next_text = "None Scheduled"
            now_status_lbl = "NOW:"

            if state['mode'] == 'in_talk' and state['current']:
                bg_color = PALETTE_CARD_BG_ACTIVE
                c = state['current']
                speaker_str = f" ({c['speaker']})" if c['speaker'] else ""
                now_text = f"{c['title']}{speaker_str}\nEnds: {c['end'].strftime('%H:%M')}"
                now_status_lbl = " ON STAGE:"
                
            elif state['mode'] == 'pre_start' and state['next_event']:
                bg_color = PALETTE_CARD_BG_WARN
                n = state['next_event']
                speaker_str = f" ({n['speaker']})" if n['speaker'] else ""
                now_text = f" STARTING SOON\n{n['title']}{speaker_str}"
                now_status_lbl = " WARNING:"

            if state['next_event'] and state['mode'] != 'pre_start':
                n = state['next_event']
                speaker_str = f" - {n['speaker']}" if n['speaker'] else ""
                next_text = f"[{n['start'].strftime('%H:%M')}] {n['title']}{speaker_str}"
            elif state['mode'] == 'in_talk' or state['mode'] == 'pre_start':
                upcoming = [e for e in track_schedule if e['start'] > now]
                if state['mode'] == 'pre_start' and upcoming:
                    upcoming.pop(0)
                if upcoming:
                    f = upcoming[0]
                    speaker_str = f" - {f['speaker']}" if f['speaker'] else ""
                    next_text = f"[{f['start'].strftime('%H:%M')}] {f['title']}{speaker_str}"

            widgets["card"].configure(bg=bg_color)
            widgets["content_frame"].configure(bg=bg_color)
            widgets["now_status"].configure(text=now_status_lbl, bg=bg_color)
            widgets["now_details"].configure(text=now_text, bg=bg_color)
            widgets["next_status"].configure(bg=bg_color)
            widgets["next_details"].configure(text=next_text, bg=bg_color)

        self.root.after(self.update_interval_ms, self.update)


def position_on_monitor(window, monitor_index):
    """Positions the application borderless full screen on a chosen monitor index using native Win32 API calls."""
    window.update_idletasks()
    
    monitors = []
    if sys.platform.startswith("win"):
        try:
            import ctypes
            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                            ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

            def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
                rect = ctypes.cast(lprcMonitor, ctypes.POINTER(RECT)).contents
                monitors.append({
                    "x": int(rect.left), "y": int(rect.top),
                    "width": int(rect.right - rect.left), "height": int(rect.bottom - rect.top)
                })
                return True

            MonitorEnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(RECT), ctypes.c_long)
            cb_proc = MonitorEnumProc(callback)
            ctypes.windll.user32.EnumDisplayMonitors(None, None, cb_proc, 0)
        except Exception:
            monitors = []

    prim_w = window.winfo_screenwidth()
    prim_h = window.winfo_screenheight()

    if monitor_index < len(monitors):
        m = monitors[monitor_index]
        w, h, x, y = m["width"], m["height"], m["x"], m["y"]
    else:
        w, h, y = prim_w, prim_h, 0
        x = 0 if monitor_index == 0 else prim_w

    window.overrideredirect(True)
    window.geometry(f"{w}x{h}+{x}+{y}")
    return w, h


if __name__ == "__main__":
    set_dpi_awareness()
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--monitor', type=int, default=0, help="Target Monitor Index (0=Laptop Screen, 1=External screen)")
    args = parser.parse_args()

    root = tk.Tk()
    
    width, height = position_on_monitor(root, args.monitor)
    root.focus_force()
    root.bind("<Escape>", lambda e: root.destroy())
    
    app = MasterDashboardApp(root, schedule_file=SCHEDULE_FILE, width=width, height=height)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass