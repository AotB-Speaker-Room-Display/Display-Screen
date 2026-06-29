import csv
import datetime
import os
import sys
import tkinter as tk
from tkinter import font, messagebox
from ctypes import windll

# ==============================================================================
# CONFIGURATION & TESTING CONTROLS
# ==============================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEDULE_FILE = os.path.join(SCRIPT_DIR, 'schedule.csv')

BOTTOM_TEXT = "*This Timetable Software was Developed by Dylan Hankers for a Tech Cornwall T-Level Placement Project."

# ------------------------------------------------------------------------------
# ⏱️ TIME TRAVEL TESTING OVERRIDE
# ------------------------------------------------------------------------------
START_TEST_TIME = datetime.datetime(2026, 7, 2, 10, 8, 0) # YYYY, MM, DD, HH, MM, SS
# ------------------------------------------------------------------------------

CONFERENCE_DATE = datetime.date.today()

PALETTE_BASE_BG = "#f68b3b"
PALETTE_BASE_BG2 = "#ffbc03"    
PALETTE_TALK_BG = "#fdba3e"     
PALETTE_TEXT_DARK = "#5b3b00"   
PALETTE_TEXT_LIGHT = "#ffffff"  
PALETTE_TEXT_BLACK = "#3e3e3f"  

ROOM_BADGE_STYLES: dict[str, dict[str, str]] = {
    "ENGINEERING": {"bg": "#c83432", "fg": "#ffffff"},
    "DESIGN & PRODUCT": {"bg": "#0066a8", "fg": "#ffffff"},
    "TEAMS": {"bg": "#6b6b6b", "fg": "#ffffff"},
    "ORGANISATIONS": {"bg": "#0a8750", "fg": "#ffffff"},
    "WORKSHOPS": {"bg": "#5a3ca9", "fg": "#ffffff"},
}

SECONDS_BEFORE_INTERMISSION_WARNING = 5 * 60  


def set_dpi_awareness():
    """Ensure the app behaves consistently across Windows scaling levels."""
    if sys.platform.startswith("win"):
        try:
            # Per-Monitor DPI Aware (Value 2 handles mixed monitor scalings correctly)
            windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def infer_event_type_from_title(title: str, current_type: str) -> str:
    """Infer the event kind when the CSV leaves the type blank."""
    normalized_title = title.strip().lower()
    if not current_type or current_type.strip() == "":
        exact_break_titles = {
            "break", "lunch", "breakfast", "meal", "intermission",
            "beach party", "dydh da - welcome to day 1", "meur ras - thank you!",
        }
        exact_social_titles = {
            "welcome", "party", "social", "dydh da", "meur ras", "beach party",
        }
        if normalized_title in exact_break_titles:
            return "break"
        if normalized_title in exact_social_titles:
            return "social"
        return "Talk"
    return current_type.strip() or "Talk"


def is_global_event_row(title: str, event_type: str) -> bool:
    """Allow only clearly shared events to appear on every screen."""
    normalized_title = title.strip().lower()
    normalized_type = event_type.strip().lower()

    if normalized_type in {"break", "social"}:
        return True

    return normalized_title in {
        "breakfast", "lunch", "dydh da - welcome to day 1",
        "meur ras - thank you!", "beach party", "welcome", "keynote", "break",
    }


def parse_date_flexible(date_str: str) -> datetime.date | None:
    clean_str = date_str.strip()
    if not clean_str:
        return None
    try:
        return datetime.datetime.strptime(clean_str, '%Y-%m-%d').date()
    except ValueError:
        pass
    try:
        return datetime.datetime.strptime(clean_str, '%d/%m/%Y').date()
    except ValueError:
        pass
    return None


def load_schedule(filename: str, track_name: str | None = None):
    schedule: list[dict] = []
    try:
        with open(filename, mode='r', newline='', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            for row in reader:
                clean_row = {}
                for k, v in row.items():
                    if k is None:
                        continue
                    key = k.strip().lstrip('\ufeff')
                    clean_row[key] = (v.strip() if v else '')

                title = (clean_row.get('Talk Title') or clean_row.get('Title') or clean_row.get('Speaker/Title') or '').strip()
                raw_type = clean_row.get('Type', '')
                event_type = infer_event_type_from_title(title, raw_type)
                is_global_event = is_global_event_row(title, event_type)

                row_track = clean_row.get('Track', '')
                if not is_global_event and track_name and row_track and row_track.strip().upper() != track_name.strip().upper():
                    continue

                date_str = clean_row.get('Date') or ''
                date_obj = parse_date_flexible(date_str)
                
                if date_str and date_obj is None:
                    print(f"WARNING: Skipping row due to unrecognizable Date format ('{date_str}').")
                    continue
                elif date_obj is None:
                    date_obj = CONFERENCE_DATE

                time_str = clean_row.get('Start Time', '')
                if not time_str:
                    continue
                
                if '-' in time_str:
                    time_str = time_str.split('-')[0].strip()

                try:
                    start_time_obj = datetime.datetime.strptime(time_str, '%H:%M').time()
                except ValueError:
                    try:
                        start_time_obj = datetime.datetime.strptime(time_str, '%I:%M%p').time()
                    except ValueError:
                        try:
                            start_time_obj = datetime.datetime.strptime(time_str, '%I:%M %p').time()
                        except ValueError:
                            print(f"WARNING: Skipping row due to invalid Start Time format ('{clean_row.get('Start Time')}').")
                            continue

                start_datetime = datetime.datetime.combine(date_obj, start_time_obj)

                duration_str = clean_row.get('Duration', '')
                if not duration_str:
                    continue
                try:
                    duration_minutes = int(duration_str)
                except ValueError:
                    continue
                end_datetime = start_datetime + datetime.timedelta(minutes=duration_minutes)

                speaker = clean_row.get('Speaker', '')
                synopsis = clean_row.get('Synopsis', '')
                room_name = (clean_row.get('Room Name') or clean_row.get('Room') or '').strip()

                event = {
                    'track': row_track.strip() if row_track else None,
                    'date': date_obj,
                    'type': event_type,
                    'start': start_datetime,
                    'end': end_datetime,
                    'speaker': speaker,
                    'title': title,
                    'synopsis': synopsis,
                    'room_name': room_name or None,
                }
                schedule.append(event)

        schedule.sort(key=lambda e: e['start'])
        return schedule
    except FileNotFoundError:
        print(f"ERROR: Schedule file not found at: {filename}")
        return []
    except Exception as e:
        print(f"ERROR: Failed to load schedule: {e}")
        return []


def compute_display_state(schedule: list[dict], now: datetime.datetime):
    current = None
    upcoming: list[dict] = []

    for e in schedule:
        if e['start'].date() == now.date():
            if e['start'] <= now < e['end']:
                current = e
            if e['start'] >= now:
                upcoming.append(e)

    next_event = upcoming[0] if upcoming else None
    following_event = upcoming[1] if len(upcoming) > 1 else None

    if not current and not next_event:
        return {'mode': 'none', 'current': None, 'next_event': None, 'following_event': None, 'seconds_to_start': None}

    if current:
        return {'mode': 'in_talk', 'current': current, 'next_event': next_event, 'following_event': following_event, 'seconds_to_start': None}

    if next_event is None:
        return {'mode': 'none', 'current': None, 'next_event': None, 'following_event': None, 'seconds_to_start': None}

    delta = next_event['start'] - now
    seconds_to_start = int(delta.total_seconds())

    event_type = (next_event.get('type') or '').strip().lower()
    if event_type not in ("break", "social") and seconds_to_start <= SECONDS_BEFORE_INTERMISSION_WARNING:
        mode = 'pre_start'
    else:
        mode = 'normal'

    return {
        'mode': mode,
        'current': None,
        'next_event': next_event,
        'following_event': following_event,
        'seconds_to_start': max(seconds_to_start, 0),
    }


def format_timedelta(td):
    total = int(td.total_seconds())
    if total < 0:
        total = 0
    hrs, rem = divmod(total, 3600)
    mins, secs = divmod(rem, 60)
    if hrs:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


class SpeakerDisplayApp:
    def __init__(self, root, schedule_file: str = SCHEDULE_FILE, track_name: str | None = None):
        self.root = root
        self.root.title("Speaker Display")
        self.root.configure(bg=PALETTE_BASE_BG2)

        self.track_name = track_name
        self.schedule = load_schedule(schedule_file, track_name=track_name)
        self.initial_real_time = datetime.datetime.now()
        
        self.screen_width = root.winfo_width()
        self.screen_height = root.winfo_height()
        
        scale = min(self.screen_width / 1920, self.screen_height / 1080)
        scale = max(1.0, scale)
        self.scale = scale
        
        self.large_size = max(int(54 * scale), 24)
        self.mid_size = max(int(32 * scale), 16)
        self.small_size = max(int(26 * scale), 14)
        self.bottom_size = max(int(12 * scale), 8)
        self.wrap_length = int(self.screen_width * 0.7)
        self.pad_x = int(40 * scale)
        self.pad_y_small = int(10 * scale)
        self.pad_y_large = int(30 * scale)

        self.large_font = font.Font(family='KG Second Chances Solid', size=self.large_size, weight='bold')
        self.mid_font = font.Font(family='KG Second Chances Sketch', size=self.mid_size)
        self.small_font = font.Font(family='KG Second Chances Solid', size=self.small_size, weight='normal')
        self.bottom_font = font.Font(family='KG Second Chances Sketch', size=self.bottom_size, weight='normal')

        self.header_frame = tk.Frame(root, bg=PALETTE_BASE_BG2)
        self.header_frame.pack(fill="x", pady=(8, 4))

        self.header_label = tk.Label(
            self.header_frame,
            text="",
            fg=PALETTE_TEXT_LIGHT,
            bg=PALETTE_BASE_BG,
            font=self.small_font,
            padx=int(16 * self.scale),
            pady=int(4 * self.scale),
        )
        self.header_label.pack(side="left", padx=self.pad_x)

        self.close_button = tk.Button(
            self.header_frame,
            text="✖",
            command=self.confirm_quit,
            fg=PALETTE_TEXT_BLACK,
            bg=PALETTE_BASE_BG2,
            activebackground=PALETTE_BASE_BG,
            activeforeground=PALETTE_TEXT_LIGHT,
            font=self.small_font,
            bd=0,
            relief="flat",
            highlightthickness=0,
            cursor="hand2",
            padx=int(10 * self.scale),
            pady=int(2 * self.scale),
        )
        self.close_button.pack(side="right", padx=(0, self.pad_x))

        self.time_label = tk.Label(
            self.header_frame,
            text="",
            fg=PALETTE_TEXT_BLACK,
            bg=PALETTE_BASE_BG2,
            font=self.small_font,
        )
        self.time_label.pack(side="right", padx=(0, self.pad_x))

        self.card_frame = tk.Frame(
            root,
            bg=PALETTE_BASE_BG2,
            highlightbackground=PALETTE_TEXT_DARK,
            highlightthickness=2,
            bd=0,
        )
        self.card_frame.pack(expand=True, fill="both", padx=int(60 * self.scale), pady=(int(10 * self.scale), int(40 * self.scale)))

        inner = tk.Frame(self.card_frame, bg=PALETTE_BASE_BG2)
        inner.pack(expand=True, fill="both", padx=int(40 * self.scale), pady=self.pad_y_large)

        inner.grid_rowconfigure(0, weight=1)
        inner.grid_rowconfigure(1, weight=0)
        inner.grid_rowconfigure(2, weight=1)
        inner.grid_columnconfigure(0, weight=1)

        content = tk.Frame(inner, bg=PALETTE_BASE_BG2)
        content.grid(row=1, column=0, sticky="n")

        self.status_label = tk.Label(content, text='', fg=PALETTE_TEXT_DARK, bg=PALETTE_BASE_BG2, font=self.mid_font)
        self.title_label = tk.Label(content, text='', fg=PALETTE_TEXT_DARK, bg=PALETTE_BASE_BG2, font=self.large_font, wraplength=self.wrap_length, justify='center')
        self.info_label = tk.Label(content, text='', fg=PALETTE_TEXT_DARK, bg=PALETTE_BASE_BG2, font=self.mid_font, wraplength=self.wrap_length, justify='center')
        self.extra_label = tk.Label(content, text='', fg=PALETTE_TEXT_DARK, bg=PALETTE_BASE_BG2, font=self.small_font, wraplength=self.wrap_length, justify='center')
        self.bottom_label = tk.Label(content, text='', fg=PALETTE_TEXT_DARK, bg=PALETTE_BASE_BG2, font=self.bottom_font, wraplength=self.wrap_length, justify='center')

        self.status_label.pack(pady=(0, self.pad_y_small))
        self.title_label.pack(pady=self.pad_y_small)
        self.info_label.pack(pady=self.pad_y_small)
        self.extra_label.pack(pady=(self.pad_y_small, 0))
        self.bottom_label.pack(pady=(int(20 * self.scale), 0))

        self.update_interval_ms = 1000
        self.update()

    def _apply_theme(self, *, bg: str, card_bg: str, title_fg: str, body_fg: str, extra_fg: str | None = None):
        if extra_fg is None:
            extra_fg = PALETTE_TEXT_DARK
        self.root.configure(bg=bg)
        self.header_frame.configure(bg=bg)
        self.time_label.configure(bg=bg, fg=PALETTE_TEXT_BLACK)
        self.card_frame.configure(bg=card_bg, highlightbackground=PALETTE_TEXT_LIGHT, highlightthickness=2)
        self.status_label.configure(bg=card_bg, fg=body_fg)
        self.title_label.configure(bg=card_bg, fg=title_fg)
        self.info_label.configure(bg=card_bg, fg=body_fg)
        self.extra_label.configure(bg=card_bg, fg=PALETTE_TEXT_BLACK)
        self.bottom_label.configure(bg=card_bg, fg=PALETTE_TEXT_BLACK)

    def confirm_quit(self):
        if messagebox.askyesno("Close Speaker Display", "Are you sure you want to close the program?"):
            self.root.destroy()
            sys.exit(0)

    def update(self):
        real_now = datetime.datetime.now()
        if 'START_TEST_TIME' in globals():
            time_passed = real_now - self.initial_real_time
            now = START_TEST_TIME + time_passed
            now = now.replace(microsecond=0)
        else:
            now = real_now.replace(microsecond=0)

        if not self.schedule:
            self.status_label.config(text='FAIL-SAFE: No schedule loaded')
            self.title_label.config(text='Waiting for schedule...')
            self.info_label.config(text=f"Ensure schedule.csv is placed in the exact same folder as this script.")
            self.extra_label.config(text='')
            self.bottom_label.config(text=BOTTOM_TEXT)
            self.root.after(self.update_interval_ms, self.update)
            return

        state = compute_display_state(self.schedule, now)
        mode = state['mode']
        current = state['current']
        next_event = state['next_event']
        following = state['following_event']

        self.time_label.config(text=now.strftime("%H:%M"))

        badge_room_name = None
        if current and current.get('room_name'):
            badge_room_name = current['room_name']
        elif next_event and next_event.get('room_name'):
            badge_room_name = next_event['room_name']

        if badge_room_name:
            up = badge_room_name.upper()
            style = ROOM_BADGE_STYLES.get(up, {"bg": PALETTE_TEXT_BLACK, "fg": PALETTE_TEXT_LIGHT})
            self.header_label.configure(text=up, bg=style["bg"], fg=style["fg"])
        else:
            self.header_label.configure(text="", bg=PALETTE_BASE_BG2, fg=PALETTE_TEXT_LIGHT)

        if mode == 'none':
            self._apply_theme(bg=PALETTE_BASE_BG2, card_bg=PALETTE_BASE_BG2, title_fg=PALETTE_TEXT_BLACK, body_fg=PALETTE_TEXT_BLACK)
            self.status_label.config(text='No more events in this room today')
            self.title_label.config(text='Thank you for attending')
            self.info_label.config(text='')
            self.extra_label.config(text='')
            self.bottom_label.config(text=BOTTOM_TEXT)

        elif mode == 'in_talk' and current:
            speaker = current['speaker'] or ''
            title = current['title'] or ''
            synopsis = current['synopsis'] or ''
            end_time_str = current['end'].strftime('%H:%M')

            self._apply_theme(bg=PALETTE_BASE_BG2, card_bg=PALETTE_BASE_BG2, title_fg=PALETTE_TEXT_DARK, body_fg=PALETTE_TEXT_DARK)
            self.status_label.config(text='Now on stage')
            main_text = f"{speaker}\n{title}" if speaker else title
            self.title_label.config(text=main_text)
            self.info_label.config(text=f"Scheduled to end at {end_time_str}")

            if next_event:
                n_speaker = next_event['speaker'] or ''
                n_title = next_event['title'] or ''
                n_start = next_event['start'].strftime('%H:%M')
                next_text = f"Next: {n_speaker} – {n_title} ({n_start})" if n_speaker else f"Next: {n_title} ({n_start})"
                self.extra_label.config(text=f"{synopsis}\n\n{next_text}" if synopsis else next_text)
            else:
                self.extra_label.config(text=synopsis)
            self.bottom_label.config(text=BOTTOM_TEXT)

        elif mode == 'pre_start' and next_event:
            speaker = next_event['speaker'] or ''
            title = next_event['title'] or ''
            synopsis = next_event['synopsis'] or ''
            start_time_str = next_event['start'].strftime('%H:%M')

            secs = state['seconds_to_start'] or 0
            minutes_remaining = max((secs + 59) // 60, 0)

            self._apply_theme(bg=PALETTE_BASE_BG2, card_bg=PALETTE_BASE_BG2, title_fg=PALETTE_TEXT_DARK, body_fg=PALETTE_TEXT_DARK)

            countdown_str = format_timedelta(datetime.timedelta(seconds=secs))
            self.status_label.config(text=f"Starting soon – {minutes_remaining} minute warning")
            main_text = f"{speaker}\n{title}" if speaker else title
            self.title_label.config(text=main_text)
            self.info_label.config(text=f"Scheduled start: {start_time_str}  ·  T-minus {countdown_str}")
            self.extra_label.config(text=synopsis)
            self.bottom_label.config(text=BOTTOM_TEXT)

        elif mode == 'normal' and next_event:
            speaker = next_event['speaker'] or ''
            title = next_event['title'] or ''
            start_time_str = next_event['start'].strftime('%H:%M')

            self._apply_theme(bg=PALETTE_BASE_BG2, card_bg=PALETTE_BASE_BG2, title_fg=PALETTE_TEXT_BLACK, body_fg=PALETTE_TEXT_BLACK)
            self.status_label.config(text='Upcoming in this room')
            main_text = f"{speaker}\n{title}" if speaker else title
            self.title_label.config(text=main_text)
            self.info_label.config(text=f"Starts at {start_time_str}")

            if following:
                f_speaker = following['speaker'] or ''
                f_title = following['title'] or ''
                f_start = following['start'].strftime('%H:%M')
                following_text = f"Following: {f_speaker} – {f_title} ({f_start})" if f_speaker else f"Following: {f_title} ({f_start})"
                self.extra_label.config(text=following_text)
            else:
                self.extra_label.config(text='')
            self.bottom_label.config(text=BOTTOM_TEXT)

        self.root.after(self.update_interval_ms, self.update)


def force_monitor_placement(window, display_num):
    """Bypasses Tkinter's buggy fullscreen toggle by manually tracking geometry canvas mapping."""
    window.update_idletasks()
    x, y, w, h = 0, 0, window.winfo_screenwidth(), window.winfo_screenheight()
    
    if sys.platform.startswith("win"):
        try:
            from ctypes import windll, c_int, WINFUNCTYPE, c_void_p, Structure, POINTER
            class RECT(Structure):
                _fields_ = [("left", c_int), ("top", c_int), ("right", c_int), ("bottom", c_int)]
            
            user32 = windll.user32
            monitors_found = []
            
            def _cb(hMonitor, hdcMonitor, lprcMonitor, dwData):
                rect = lprcMonitor.contents
                monitors_found.append((rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top))
                return 1
            
            MonitorEnumProc = WINFUNCTYPE(c_int, c_void_p, c_void_p, POINTER(RECT), c_void_p)
            callback_proc = MonitorEnumProc(_cb)
            user32.EnumDisplayMonitors(None, None, callback_proc, 0)
            
            if len(monitors_found) >= 2 and display_num == 2:
                x, y, w, h = monitors_found[1]
            elif len(monitors_found) >= 1:
                x, y, w, h = monitors_found[0]
        except Exception as e:
            print(f"Hardware detection query error fallback applied: {e}")
            if display_num == 2:
                x = window.winfo_screenwidth()

    window.overrideredirect(True)
    window.geometry(f"{w}x{h}+{x}+{y}")
    window.update_idletasks()


if __name__ == "__main__":
    set_dpi_awareness()

    cli_track_arg = sys.argv[1] if len(sys.argv) > 1 else None

    if cli_track_arg:
        chosen_track = cli_track_arg
        chosen_display = 1
        root = tk.Tk()
        force_monitor_placement(root, chosen_display)
    else:
        root = tk.Tk()
        root.title("Setup Configurator")
        root.geometry("450x520")
        root.configure(bg="#ffffff")
        root.resizable(False, False)

        # Custom Title Design Panel Matching Layout Block
        header_panel = tk.Label(
            root, 
            text="DISPLAY SELECTION", 
            bg=PALETTE_BASE_BG, 
            fg=PALETTE_TEXT_LIGHT, 
            font=("Arial", 14, "bold"), 
            pady=15
        )
        header_panel.pack(fill="x", side="top", pady=(0, 20))

        tracks = [
            "ENGINEERING", "DESIGN & PRODUCT", "TEAMS", "ORGANISATIONS", "WORKSHOPS",
            "STUDIO A", "STUDIO C", "STUDIO K", "STUDIO L", "STUDIO E", "STUDIO F", "LAWN", "GYLLY BEACH"
        ]

        selected_track = tk.StringVar(value=tracks[0])
        selected_display = tk.IntVar(value=1)

        # Main wrapper container area
        body_frame = tk.Frame(root, bg="#ffffff", padx=25)
        body_frame.pack(fill="both", expand=True)

        # --- ROOM SELECTION BLOCK ---
        tk.Label(
            body_frame, text="Room", font=("Arial", 11, "bold"), 
            fg=PALETTE_TEXT_BLACK, bg="#ffffff", anchor="w"
        ).pack(fill="x", pady=(0, 5))

        # A beautiful drop-down panel structure replacing default system look
        dropdown_frame = tk.Frame(body_frame, bg="#f0f0f0", bd=1, relief="solid")
        dropdown_frame.pack(fill="x", pady=(0, 25))

        track_option = tk.OptionMenu(dropdown_frame, selected_track, *tracks)
        track_option.config(
            font=("Arial", 11), bg="#fdfdfd", fg=PALETTE_TEXT_BLACK, 
            activebackground="#f5f5f5", activeforeground=PALETTE_TEXT_BLACK,
            relief="flat", bd=0, highlightthickness=0, indicatoron=True,
            anchor="w", direction="below"
        )
        track_option["menu"].config(font=("Arial", 11), bg="#ffffff", fg=PALETTE_TEXT_BLACK, bd=1)
        track_option.pack(fill="x", padx=2, pady=2)

        # --- SCREEN SELECTION BLOCK ---
        tk.Label(
            body_frame, text="Screen", font=("Arial", 11, "bold"), 
            fg=PALETTE_TEXT_BLACK, bg="#ffffff", anchor="w"
        ).pack(fill="x", pady=(0, 5))

        # Custom interactive flat selector cards for output paths
        def update_display_cards():
            if selected_display.get() == 1:
                card1.config(bg="#f68b3b", fg="#ffffff", highlightbackground="#f68b3b")
                card2.config(bg="#f9f9f9", fg=PALETTE_TEXT_BLACK, highlightbackground="#dcdcdc")
            else:
                card1.config(bg="#f9f9f9", fg=PALETTE_TEXT_BLACK, highlightbackground="#dcdcdc")
                card2.config(bg="#f68b3b", fg="#ffffff", highlightbackground="#f68b3b")

        card1 = tk.Button(
            body_frame, text="Screen 1 (Laptop / Primary Display)", font=("Arial", 10, "bold"),
            bg="#f9f9f9", fg=PALETTE_TEXT_BLACK, bd=0, highlightthickness=2, highlightbackground="#dcdcdc",
            activebackground="#f68b3b", activeforeground="#ffffff", relief="flat", cursor="hand2", pady=12,
            command=lambda: [selected_display.set(1), update_display_cards()]
        )
        card1.pack(fill="x", pady=4)

        card2 = tk.Button(
            body_frame, text="Screen 2 (External Monitor)", font=("Arial", 10, "bold"),
            bg="#f9f9f9", fg=PALETTE_TEXT_BLACK, bd=0, highlightthickness=2, highlightbackground="#dcdcdc",
            activebackground="#f68b3b", activeforeground="#ffffff", relief="flat", cursor="hand2", pady=12,
            command=lambda: [selected_display.set(2), update_display_cards()]
        )
        card2.pack(fill="x", pady=(4, 25))

        update_display_cards() # Initialize selection highlight states

        config_box = {"track": tracks[0], "display": 1}

        def on_start():
            config_box["track"] = selected_track.get()
            config_box["display"] = selected_display.get()
            root.destroy()

        # Action execution button
        start_button = tk.Button(
            body_frame, text="Start Display", command=on_start,
            font=("Arial", 11, "bold"), bg=PALETTE_TEXT_BLACK, fg="#ffffff",
            activebackground="#2a2a2b", activeforeground="#ffffff",
            bd=0, relief="flat", cursor="hand2", padx=30, pady=10
        )
        start_button.pack(pady=(10, 20))

        root.mainloop()

        root = tk.Tk()
        chosen_track = config_box["track"]
        chosen_display = config_box["display"]

    force_monitor_placement(root, chosen_display)
    app = SpeakerDisplayApp(root, schedule_file=SCHEDULE_FILE, track_name=chosen_track)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
