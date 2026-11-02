import json
import socket
import threading
import time
import queue
import ssl
import requests
import struct
import select
import paho.mqtt.client as mqtt
import ftplib
import zipfile
import io
import base64
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from logger_config import log_info, log_error, log_debug, log_warn

# Bambu Lab Filament Mapping
BAMBU_FILAMENTS = {
    "GFA00": "Bambu PLA Basic", "GFA01": "Bambu PLA Matte", "GFA02": "Bambu PLA Metal",
    "GFA05": "Bambu PLA Silk", "GFA06": "Bambu PLA Silk+", "GFA07": "Bambu PLA Marble",
    "GFA08": "Bambu PLA Sparkle", "GFA09": "Bambu PLA Tough", "GFA11": "Bambu PLA Aero",
    "GFA12": "Bambu PLA Glow", "GFA13": "Bambu PLA Dynamic", "GFA15": "Bambu PLA Galaxy",
    "GFA16": "Bambu PLA Wood", "GFA50": "Bambu PLA-CF", "GFB00": "Bambu ABS",
    "GFB01": "Bambu ASA", "GFB02": "Bambu ASA-Aero", "GFB50": "Bambu ABS-GF",
    "GFB51": "Bambu ASA-CF", "GFB60": "PolyLite ABS", "GFB61": "PolyLite ASA",
    "GFB98": "Generic ASA", "GFB99": "Generic ABS", "GFC00": "Bambu PC",
    "GFC01": "Bambu PC FR", "GFC99": "Generic PC", "GFG00": "Bambu PETG Basic",
    "GFG01": "Bambu PETG Translucent", "GFG02": "Bambu PETG HF", "GFG50": "Bambu PETG-CF",
    "GFG60": "PolyLite PETG", "GFG96": "Generic PETG HF", "GFG97": "Generic PCTG",
    "GFG98": "Generic PETG-CF", "GFG99": "Generic PETG", "GFL00": "PolyLite PLA",
    "GFL01": "PolyTerra PLA", "GFL03": "eSUN PLA+", "GFL04": "Overture PLA",
    "GFL05": "Overture Matte PLA", "GFL06": "Fiberon PETG-ESD", "GFL50": "Fiberon PA6-CF",
    "GFL51": "Fiberon PA6-GF", "GFL52": "Fiberon PA12-CF", "GFL53": "Fiberon PA612-CF",
    "GFL54": "Fiberon PET-CF", "GFL55": "Fiberon PETG-rCF", "GFL95": "Generic PLA High Speed",
    "GFL96": "Generic PLA Silk", "GFL98": "Generic PLA-CF", "GFL99": "Generic PLA",
    "GFN03": "Bambu PA-CF", "GFN04": "Bambu PAHT-CF", "GFN05": "Bambu PA6-CF",
    "GFN06": "Bambu PPA-CF", "GFN08": "Bambu PA6-GF", "GFN96": "Generic PPA-GF",
    "GFN97": "Generic PPA-CF", "GFN98": "Generic PA-CF", "GFN99": "Generic PA",
    "GFP95": "Generic PP-GF", "GFP96": "Generic PP-CF", "GFP97": "Generic PP",
    "GFP98": "Generic PE-CF", "GFP99": "Generic PE", "GFR98": "Generic PHA",
    "GFR99": "Generic EVA", "GFS00": "Bambu Support W", "GFS01": "Bambu Support G",
    "GFS02": "Bambu Support For PLA", "GFS03": "Bambu Support For PA/PET", "GFS04": "Bambu PVA",
    "GFS05": "Bambu Support For PLA/PETG", "GFS06": "Bambu Support for ABS", "GFS97": "Generic BVOH",
    "GFS98": "Generic HIPS", "GFS99": "Generic PVA", "GFT01": "Bambu PET-CF",
    "GFT02": "Bambu PPS-CF", "GFT97": "Generic PPS", "GFT98": "Generic PPS-CF",
    "GFU00": "Bambu TPU 95A HF", "GFU01": "Bambu TPU 95A", "GFU02": "Bambu TPU for AMS",
    "GFU98": "Generic TPU for AMS", "GFU99": "Generic TPU"
}

def get_bambu_filament_name(idx):
    if not idx: return ""
    return BAMBU_FILAMENTS.get(idx, "Unknown")

# Base Printer Class
class BasePrinter:
    def __init__(self, config):
        self.config = config
        self.ip = config.get('ip')
        self.name = config.get('name', 'Unknown Printer')
        self.type = config.get('type')
        self.status = {
            'state': 'offline',
            'temp_nozzle': 0,
            'temp_bed': 0,
            'progress': 0,
            'filename': '',
            'remaining_time': 0,
            'layer': 0,
            'total_layers': 0,
            'finish_time': '--',
            'total_usage': config.get('total_usage', 0.0)
        }
        self.last_update = 0
        self.last_usage_time = time.time()

    def connect(self):
        pass

    def update(self):
        pass

    def _reset_status(self):
        """Limpa os dados dinâmicos da impressora."""
        self.status.update({
            'state': 'off',
            'temp_nozzle': 0,
            'temp_bed': 0,
            'progress': 0,
            'filename': '',
            'remaining_time': 0,
            'layer': 0,
            'total_layers': 0,
            'finish_time': '--',
            'target_nozzle': 0,
            'target_bed': 0,
            'chamber_temp': 0,
            'fan_part': 0,
            'fan_aux': 0,
            'fan_chamber': 0,
            'ams': [],
            'hms': [],
            'wifi_signal': 0
        })
        self.last_frame = None

    def send_command(self, command, **kwargs):
        pass

    def stop(self):
        """Para todos os serviços e threads da impressora."""
        pass

    def get_status(self):
        s = self.status.copy()
        s['id'] = self.config.get('id')
        s['name'] = self.name
        s['type'] = self.type
        s['ip'] = self.ip
        s['serial'] = self.config.get('serial', '')
        s['access_code'] = self.config.get('access_code', '')
        s['camera_url'] = self.config.get('camera_url', '')
        s['custom_camera'] = self.config.get('custom_camera', False)
        s['camera_refresh'] = self.config.get('camera_refresh', False)
        s['refresh_interval'] = self.config.get('refresh_interval', 5000)
        s['enabled'] = self.config.get('enabled', True)
        s['last_update'] = self.last_update
        return s

# Moonraker (Klipper) Implementation
class MoonrakerPrinter(BasePrinter):
    def __init__(self, config):
        super().__init__(config)
        self.current_filename = ""
        self.led_pin = "LED" 
        self._fetch_webcams()
        self._discover_objects()

    def _discover_objects(self):
        try:
            url = f"http://{self.ip}/printer/objects/list"
            resp = requests.get(url, timeout=2)
            if resp.status_code == 200:
                objs = resp.json().get('result', {}).get('objects', [])
                # Procura por pinos de LED conhecidos
                if 'output_pin caselight' in objs: self.led_pin = "caselight"
                elif 'output_pin LED' in objs: self.led_pin = "LED"
                
                log_info(f"[{self.ip}] Moonraker descoberto: LED={self.led_pin}")
        except Exception as e:
            log_error(f"[{self.ip}] Erro ao descobrir objetos Moonraker: {e}")

    def _fetch_webcams(self):
        try:
            url = f"http://{self.ip}/server/webcams/list"
            resp = requests.get(url, timeout=2)
            if resp.status_code == 200:
                webcams = resp.json().get('result', {}).get('webcams', [])
                if webcams:
                    cam = webcams[0]
                    stream = cam.get('stream_url', '')
                    if stream:
                        if stream.startswith('/'):
                            self.status['auto_camera_url'] = f"http://{self.ip}{stream}"
                        else:
                            self.status['auto_camera_url'] = stream
        except:
            pass

    def get_status(self):
        s = super().get_status()
        s['auto_camera_url'] = self.status.get('auto_camera_url', '')
        return s

    def _fetch_metadata(self, filename):
        if not filename:
            self.status['cover_image'] = None
            return
        try:
            url = f"http://{self.ip}/server/files/metadata?filename={filename}"
            resp = requests.get(url, timeout=2)
            if resp.status_code == 200:
                data = resp.json().get('result', {})
                thumbs = data.get('thumbnails', [])
                if thumbs:
                    # Pick largest thumbnail
                    thumb = thumbs[-1]
                    self.status['cover_image'] = f"http://{self.ip}/server/files/gcodes/{thumb['relative_path']}"
                else:
                    self.status['cover_image'] = None
        except:
            self.status['cover_image'] = None

    def update(self):
        # Incrementar horas de uso se estiver imprimindo
        now = time.time()
        if self.status.get('state', '').lower() in ['printing', 'running']:
            delta = now - self.last_usage_time
            self.status['total_usage'] = self.status.get('total_usage', 0) + (max(0, delta) / 3600.0)
        self.last_usage_time = now

        try:
            url = f"http://{self.ip}/printer/objects/query?print_stats&extruder&heater_bed&display_status&fan&toolhead&virtual_sdcard&output_pin%20{self.led_pin}&temperature_sensor%20mcu_temp&temperature_sensor%20chamber_temp&system_stats"
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                res = data.get('result', {}).get('status', {})
                
                # Update status
                if 'print_stats' in res:
                    state = res['print_stats'].get('state', 'unknown')
                    # Map 'standby' to 'idle' for UI consistency
                    self.status['state'] = 'idle' if state == 'standby' else state
                    
                    filename = res['print_stats'].get('filename', '')
                    if filename != self.current_filename:
                        self.current_filename = filename
                        self._fetch_metadata(filename)
                    
                    self.status['filename'] = filename
                    self.status['print_duration'] = res['print_stats'].get('print_duration', 0)
                
                if 'extruder' in res:
                    self.status['temp_nozzle'] = res['extruder'].get('temperature', 0)
                    self.status['target_nozzle'] = res['extruder'].get('target', 0)
                
                if 'heater_bed' in res:
                    self.status['temp_bed'] = res['heater_bed'].get('temperature', 0)
                    self.status['target_bed'] = res['heater_bed'].get('target', 0)
                
                if 'display_status' in res:
                    self.status['progress'] = res['display_status'].get('progress', 0) * 100
                
                # Fetch LED value
                lp = f'output_pin {self.led_pin}'
                if lp in res:
                    self.status['led_val'] = int(res[lp].get('value', 0) * 100)
                
                # Fetch Fan part value
                if 'fan' in res:
                    self.status['fan_val'] = int(res['fan'].get('speed', 0) * 100)
                
                
                # Remaining time and Finish time from virtual_sdcard or print_stats
                rem_time = 0
                if 'virtual_sdcard' in res:
                    # Klipper approach: (1 - progress) * total_duration / progress (very rough)
                    # Better to use Moonraker's estimation if available
                    pass
                
                if 'print_stats' in res:
                    # Some Moonraker versions provide it here
                    stats = res['print_stats']
                    # print_duration is elapsed. We need remaining.
                    # Usually we get it from display_status if available
                    pass
                
                if 'display_status' in res and 'progress' in res['display_status']:
                    # We can't always get exact remaining from simple query, 
                    # but if we have progress and elapsed, we can estimate
                    prog = res['display_status'].get('progress', 0)
                    elapsed = res['print_stats'].get('print_duration', 0) if 'print_stats' in res else 0
                    if prog > 0 and prog < 1:
                        total_est = elapsed / prog
                        rem_time = (total_est - elapsed) / 60 # minutes
                        self.status['remaining_time'] = int(rem_time)
                        finish_dt = datetime.now() + timedelta(minutes=rem_time)
                        self.status['finish_time'] = finish_dt.strftime("%H:%M")
                    elif prog >= 1:
                        self.status['remaining_time'] = 0
                        self.status['finish_time'] = '--'
                
                
                self.last_update = time.time()
                return True
            else:
                self.status['state'] = 'offline'
        except Exception as e:
            log_debug(f"Moonraker update failed for {self.ip}: {e}")
            self.status['state'] = 'offline'
        return False

    def send_command(self, command, **kwargs):
        try:
            if command == 'pause':
                requests.post(f"http://{self.ip}/printer/print/pause", timeout=3)
            elif command == 'resume':
                requests.post(f"http://{self.ip}/printer/print/resume", timeout=3)
            elif command == 'stop':
                requests.post(f"http://{self.ip}/printer/print/cancel", timeout=3)
            elif command == 'home':
                requests.post(f"http://{self.ip}/printer/gcode/script",
                    json={'script': 'G28'}, timeout=3)
            elif command == 'motors_off':
                requests.post(f"http://{self.ip}/printer/gcode/script",
                    json={'script': 'M84'}, timeout=3)
            elif command == 'gcode':
                gcode = kwargs.get('gcode', '')
                if gcode:
                    requests.post(f"http://{self.ip}/printer/gcode/script",
                        json={'script': gcode}, timeout=3)
            elif command == 'fan':
                val = int(kwargs.get('val', 0))
                self.status['fan_val'] = val
                pwm = int(val / 100 * 255)
                # Part fan is standard M106 P0
                requests.post(f"http://{self.ip}/printer/gcode/script",
                    json={'script': f'M106 P0 S{pwm}'}, timeout=3)
            elif command == 'led':
                val = int(kwargs.get('val', 0))
                self.status['led_val'] = val
                fval = val / 100.0
                requests.post(f"http://{self.ip}/printer/gcode/script",
                    json={'script': f'SET_PIN PIN={self.led_pin} VALUE={fval:.2f}'}, timeout=3)
                # Se for M355 compatível, envia também apenas para garantir
                if self.led_pin == "LED":
                    pwm = int(val / 100 * 255)
                    requests.post(f"http://{self.ip}/printer/gcode/script",
                        json={'script': f'M355 S{1 if val > 0 else 0} P{pwm}'}, timeout=3)
            elif command == 'reboot':
                requests.post(f"http://{self.ip}/machine/reboot", timeout=3)
        except Exception as e:
            log_error(f"Moonraker command error: {e}")

    def get_snapshot(self):
        try:
            # Try to determine snapshot URL
            base_ip = self.ip.split(':')[0]
            # If camera_url is in config, use it but replace action=stream with action=snapshot
            cam_url = self.config.get('camera_url', '')
            
            snap_url = ""
            if 'action=stream' in cam_url:
                snap_url = cam_url.replace('action=stream', 'action=snapshot')
            elif cam_url:
                # If explicit URL but not mjpg-streamer standard, try as is (unlikely for stream link)
                snap_url = cam_url
            else:
                # Default guess for K1/Moonraker
                # K1 usually on port 4409 for camera? Config says ip:4409
                if ':' in self.ip:
                    snap_url = f"http://{self.ip}/webcam/?action=snapshot"
                else:
                    snap_url = f"http://{self.ip}:4409/webcam/?action=snapshot"

            resp = requests.get(snap_url, timeout=2)
            if resp.status_code == 200:
                return resp.content
        except Exception as e:
            # log_debug(f"Snapshot failed: {e}")
            pass
        return None

    def stop(self):
        self._reset_status()

# Elegoo (Saturn 3 Ultra) Implementation - UDP
def _tcp_port(value, default):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


class ElegooPrinter(BasePrinter):
    def __init__(self, config):
        super().__init__(config)
        self.port = _tcp_port(config.get('port'), 3000)
        # Resin printers don't have nozzle/bed temperatures
        self.status.pop('temp_nozzle', None)
        self.status.pop('temp_bed', None)

    def _send_command(self, message):
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(1.5) # Aumentar ligeiramente
            sock.sendto(message.encode(), (self.ip, self.port))
            data, _ = sock.recvfrom(65535)
            return json.loads(data.decode())
        except socket.timeout:
            # log_debug(f"Elegoo timeout: {self.ip}")
            return None
        except Exception as e:
            log_debug(f"Elegoo error: {e}")
            return None
        finally:
            if sock:
                try: sock.close()
                except: pass

    def update(self):
        # Incrementar horas de uso se estiver imprimindo
        now = time.time()
        if self.status.get('state', '').lower() in ['printing', 'running']:
            delta = now - self.last_usage_time
            self.status['total_usage'] = self.status.get('total_usage', 0) + (max(0, delta) / 3600.0)
        self.last_usage_time = now

        data = self._send_command("M99999")
        if data:
            # Structure from user's working example:
            # response.get("Data", {}).get("Status", {}).get("PrintInfo", {})
            wrapper = data.get("Data", {})
            status = wrapper.get("Status", {})
            info = status.get("PrintInfo", {})

            # Status translation
            status_code = status.get("CurrentStatus", -1)
            status_map = {0: "Idle", 1: "Printing", 2: "Paused", 3: "Error"}
            self.status['state'] = status_map.get(status_code, "Unknown").lower()
            
            if info:
                self.status['layer'] = info.get("CurrentLayer", 0)
                self.status['total_layers'] = info.get("TotalLayer", 0)
                self.status['filename'] = info.get("Filename", "")
                
                # Progress calculation
                if self.status['total_layers'] > 0:
                    self.status['progress'] = (self.status['layer'] / self.status['total_layers']) * 100
                else:
                    self.status['progress'] = 0
                
                # Time calculation (ticks to minutes for fmtEta compatibility)
                current_ticks = info.get("CurrentTicks", 0)
                total_ticks = info.get("TotalTicks", 0)
                if total_ticks > current_ticks:
                    remaining_ticks = total_ticks - current_ticks
                    # remaining_time in minutes for fmtEta
                    self.status['remaining_time'] = (remaining_ticks // 1000) // 60
                    
                    # Estimate finish time string (HH:mm)
                    remaining_seconds = remaining_ticks / 1000
                    finish_dt = datetime.now() + timedelta(seconds=remaining_seconds)
                    self.status['finish_time'] = finish_dt.strftime("%H:%M")
                else:
                    self.status['remaining_time'] = 0
                    self.status['finish_time'] = '--'
            
            self.last_update = time.time()
            return True
        else:
            self.status['state'] = 'offline'
            return False

    def send_command(self, command, **kwargs):
        if command == 'pause':
            self._send_command("M25")
        elif command == 'resume':
            self._send_command("M24")
        elif command == 'stop':
            self._send_command("M33")

    def stop(self):
        self._reset_status()

class BambuCameraThread(threading.Thread):
    def __init__(self, ip, access_code, callback):
        super().__init__(daemon=True)
        self.ip = ip
        self.access_code = access_code
        self.callback = callback
        self._stop_event = threading.Event()
        self.jpeg_channel = False

    def stop(self):
        self._stop_event.set()

    def _port_open(self, port):
        sock = socket.socket()
        sock.settimeout(2)
        try:
            sock.connect((self.ip, port))
            return True
        except OSError:
            return False
        finally:
            sock.close()

    def run(self):
        self.setName(f"BambuCamera-{self.ip}")
        # X1C e H2D com vídeo de rede ligado entregam H.264 em rtsps na porta 322.
        # A1 e P1 entregam JPEG na porta 6000.
        if self._port_open(322) and shutil.which("ffmpeg"):
            log_info(f"[{self.ip}] Câmera pelo vídeo de rede.")
            while not self._stop_event.is_set():
                self._read_rtsp()
                if self._stop_event.wait(5):
                    break
            return
        if self._port_open(322) and not shutil.which("ffmpeg"):
            log_error(f"[{self.ip}] A câmera desta impressora precisa do ffmpeg instalado.")
        log_info(f"[{self.ip}] Câmera pelo JPEG da porta 6000.")
        while not self._stop_event.is_set():
            self._read_mjpeg()
            if self._stop_event.wait(5):
                break

    def _read_rtsp(self):
        url = f"rtsps://bblp:{self.access_code}@{self.ip}:322/streaming/live/1"
        proc = subprocess.Popen(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-rtsp_transport", "tcp",
                "-i", url, "-an", "-vf", "fps=1",
                "-q:v", "8", "-f", "mjpeg", "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        buf = b""
        try:
            while not self._stop_event.is_set():
                chunk = proc.stdout.read(65536)
                if not chunk:
                    break
                buf += chunk
                while True:
                    start = buf.find(b"\xff\xd8")
                    end = buf.find(b"\xff\xd9", start + 2) if start >= 0 else -1
                    if start < 0 or end < 0:
                        if start > 0:
                            buf = buf[start:]
                        elif start < 0 and len(buf) > 2_000_000:
                            buf = buf[-2:]
                        break
                    self.callback(bytes(buf[start:end + 2]))
                    buf = buf[end + 2:]
        finally:
            proc.kill()
            proc.wait(timeout=5)

    def _read_mjpeg(self):
        username = "bblp"
        auth_data = bytearray()
        auth_data += struct.pack("<I", 0x40)
        auth_data += struct.pack("<I", 0x3000)
        auth_data += struct.pack("<I", 0)
        auth_data += struct.pack("<I", 0)
        auth_data += username.encode("ascii").ljust(32, b"\x00")
        auth_data += str(self.access_code).encode("ascii")[:32].ljust(32, b"\x00")

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.set_ciphers("DEFAULT@SECLEVEL=1:AES128-SHA")
        ctx.options |= ssl.OP_NO_SSLv2 | ssl.OP_NO_SSLv3 | ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1

        try:
            sock = socket.create_connection((self.ip, 6000), timeout=3)
            sock.settimeout(3)
            try:
                secured = ctx.wrap_socket(sock, server_hostname=None)
            except Exception:
                sock.close()
                raise
            with secured:
                time.sleep(0.5)
                secured.sendall(auth_data)
                buffer = bytearray()
                secured.setblocking(False)
                while not self._stop_event.is_set():
                    try:
                        try:
                            ready = select.select([secured], [], [], 0.5)
                        except (OSError, ValueError):
                            break
                        if not ready[0]:
                            continue
                        incoming = secured.recv(16384)
                        if not incoming:
                            break
                        buffer += incoming
                        while len(buffer) >= 16:
                            payload_size = int.from_bytes(buffer[0:4], byteorder="little")
                            if payload_size <= 0 or payload_size > 1_000_000:
                                buffer = buffer[1:]
                                continue
                            if len(buffer) < 16 + payload_size:
                                break
                            magic = int.from_bytes(buffer[4:8], byteorder="little")
                            packet = bytes(buffer[16:16 + payload_size])
                            del buffer[:16 + payload_size]
                            # H2D responde o pedido de JPEG com a recusa do navegador de arquivos.
                            # A1 entrega o JPEG nesse mesmo canal e não cai aqui.
                            if magic == 0x0003013F and payload_size <= 16 and packet.find(b"\xff\xd8") < 0:
                                if not getattr(self, "_liveview_hint", False):
                                    self._liveview_hint = True
                                    log_info(
                                        f"[{self.ip}] A câmera não está liberada. "
                                        "No painel da impressora, em LAN, ative o vídeo local (LAN Only Liveview)."
                                    )
                                if self._port_open(322) and shutil.which("ffmpeg"):
                                    log_info(f"[{self.ip}] Câmera pelo vídeo de rede.")
                                    self._read_rtsp()
                                    return
                                if self._stop_event.wait(30):
                                    return
                                return
                            start = packet.find(b"\xff\xd8")
                            end = packet.rfind(b"\xff\xd9")
                            if start >= 0 and end > start:
                                self.jpeg_channel = True
                                self.callback(packet[start:end + 2])
                    except ssl.SSLWantReadError:
                        continue
                    except Exception as exc:
                        log_debug(f"[{self.ip}] Câmera JPEG: {exc}")
                        break
        except Exception as exc:
            log_debug(f"[{self.ip}] Câmera JPEG não abriu: {exc}")

# Helper for Implicit FTP TLS (used by Bambu Lab)
class ImplicitFTP_TLS(ftplib.FTP_TLS):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sock = None

    @property
    def sock(self):
        return self._sock

    @sock.setter
    def sock(self, value):
        if value is not None and not isinstance(value, ssl.SSLSocket):
            value = self.context.wrap_socket(value)
        self._sock = value

    def ntransfercmd(self, cmd, rest=None):
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            session = self.sock.session
            if isinstance(self.sock, ssl.SSLSocket):
                session = self.sock.session
            conn = self.context.wrap_socket(conn, server_hostname=self.host, session=session)
        return conn, size


class BambuFileChannel:
    """Navegador de arquivos da porta 6000, só leitura: lista os envios e lê um item de dentro do 3mf."""

    LOGIN = 0x0101013F
    CTRL = 0x0102013F
    LIST_INFO = 1
    SUB_FILE = 2

    def __init__(self, ip, access_code, timeout=15):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        raw = socket.create_connection((ip, 6000), timeout=5)
        try:
            self.sock = ctx.wrap_socket(raw, server_hostname=None)
        except Exception:
            raw.close()
            raise
        self.sock.settimeout(timeout)
        self.frame_seq = 1
        self.cmd_seq = 1
        try:
            code = str(access_code or "").encode("ascii", "replace")[:8].ljust(8, b"\0")
            self._send(self.LOGIN, b"bblp".ljust(8, b"\0") + code)
            self._read_frame()
            setup = {
                "sequence": 0,
                "mtype": 12291,
                "req": {
                    "t_av": 1, "mtype": 12289, "peer_t": 3,
                    "pid": f"{int(time.time() * 1000) & 0xFFFFFFFF:08x}", "ver": "02.03.00.00",
                },
            }
            self._send(self.CTRL, json.dumps(setup, separators=(",", ":")).encode())
            reply, _ = self._split(self._read_frame())
            if not reply or int(reply.get("result", -1)) != 0:
                raise RuntimeError(f"porta 6000 recusou a sessão: {reply}")
        except Exception:
            self.close()
            raise

    def _send(self, magic, payload):
        self.sock.sendall(struct.pack("<IIII", len(payload), magic, self.frame_seq, 0) + payload)
        self.frame_seq += 1

    def _read_exact(self, size):
        data = bytearray()
        while len(data) < size:
            chunk = self.sock.recv(size - len(data))
            if not chunk:
                raise ConnectionError("porta 6000 fechou a sessão")
            data += chunk
        return bytes(data)

    def _read_frame(self):
        size = struct.unpack_from("<I", self._read_exact(16), 0)[0]
        return self._read_exact(size) if size else b""

    @staticmethod
    def _split(data):
        if not data.startswith(b"{"):
            return None, data
        try:
            _, end = json.JSONDecoder().raw_decode(data.decode("latin-1"))
            reply = json.loads(data[:end].decode("utf-8"))
        except ValueError:
            return None, data
        rest = data[end:]
        return reply, rest[2:] if rest.startswith(b"\n\n") else rest

    def request(self, cmdtype, req, timeout=20):
        seq = self.cmd_seq
        self.cmd_seq += 1
        body = {"mtype": 12289, "cmdtype": cmdtype, "sequence": seq, "req": req}
        self._send(self.CTRL, json.dumps(body, separators=(",", ":")).encode())
        data = b""
        deadline = time.time() + timeout
        while time.time() < deadline:
            reply, chunk = self._split(self._read_frame())
            if not reply or int(reply.get("sequence", -1)) != seq:
                continue
            data += chunk
            detail = reply.get("reply") if isinstance(reply.get("reply"), dict) else {}
            if int(reply.get("result", -1)) == 1 or detail.get("continue"):
                continue
            return reply, data
        raise TimeoutError(f"porta 6000 não respondeu ao comando {cmdtype}")

    def list_models(self):
        # H2D responde a lista do pendrive em "external"; "udisk" e a memória interna devolvem erro.
        for storage in ("external", "udisk", ""):
            req = {"type": "model", "api_version": 2, "notify": "DETAIL"}
            if storage:
                req["storage"] = storage
            reply, _ = self.request(self.LIST_INFO, req)
            if int(reply.get("result", -1)) == 0:
                return list((reply.get("reply") or {}).get("file_lists") or [])
        return []

    def read_member(self, path, member):
        reply, data = self.request(self.SUB_FILE, {"paths": [f"{path}#{member}"]})
        return data if int(reply.get("result", -1)) == 0 and data else None

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass

def _split_packed_temp(value):
    """Temperatura Bambu: float simples, ou inteiro com atual nos 16 bits baixos e meta nos altos."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, float) and not value.is_integer():
        return value, 0
    try:
        raw = int(value)
    except (TypeError, ValueError):
        return None
    return raw & 0xFFFF, (raw >> 16) & 0xFFFF


# Bambu Lab Implementation - MQTT
class BambuPrinter(BasePrinter):
    def __init__(self, config):
        super().__init__(config)
        self.serial = config.get('serial')
        self.access_code = config.get('access_code')
        self.client = None
        self.connected_flag = False
        self.lock = threading.Lock()
        self.cam_thread = None
        self.last_frame = None
        self.metadata_thread = None
        self.current_filename = ""
        self._meta_token = 0
        
        # New status fields
        self.status.update({
            'target_nozzle': 0,
            'target_bed': 0,
            'chamber_temp': 0,
            'fan_part': 0,
            'fan_aux': 0,
            'fan_chamber': 0,
            'ams': [],
            'hms': [],
            'speed_level': 2, # Normal
            'wifi_signal': 0,
            'task_name': '',
            'print_weight': 0,
            'active_tray_name': 'None',
            'active_tray_uuid': '',
            'firmware_update': {'current': '', 'latest': '', 'available': False},
            'print_error': {'code': 0, 'message': ''}
        })
        # total_usage já está no BasePrinter.status
        self.start_time = None

    def connect(self):
        # Conexão em thread para não travar a inicialização do server
        if not self.config.get('enabled', True): return
        if self.client: return
        thread = threading.Thread(target=self._do_connect, daemon=True)
        thread.start()

    def _do_connect(self):
        log_info(f"[{self.ip}] Conectando ao MQTT e Câmera...")
        self.client = mqtt.Client(client_id=f"aditiva-{int(time.time())}")
        self.client.username_pw_set("bblp", self.access_code)
        
        # Contexto SSL - Igual ao exemplo que funciona
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        context.set_ciphers('DEFAULT@SECLEVEL=1:AES128-SHA')
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        self.client.tls_set_context(context)
        
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        try:
            self.client.connect(self.ip, 8883, 10) 
            self.client.loop_start()
            
            # Aguardar o MQTT estabilizar antes de abrir a câmera (importante para X1C)
            time.sleep(2)
            
            if not self.cam_thread:
                self.cam_thread = BambuCameraThread(self.ip, self.access_code, self.on_frame)
                self.cam_thread.start()
        except Exception as e:
            log_error(f"[{self.ip}] Falha na conexão MQTT: {e}")
            self.status['state'] = 'offline'

    def stop(self):
        log_info(f"[{self.ip}] Parando serviços Bambu (Threads e MQTT)...")
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except: pass
        if self.cam_thread:
            try:
                self.cam_thread.stop()
            except: pass
        self.connected_flag = False
        self._reset_status()
        self.status['state'] = 'off'
        

    def on_frame(self, frame):
        self.last_frame = frame

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected_flag = True
            topic = f"device/{self.serial}/report"
            client.subscribe(topic)
            self.request_push()

    def request_push(self):
        if not self.connected_flag: return
        msg_push = {"pushing": {"sequence_id": "0", "command": "pushall"}}
        self.client.publish(f"device/{self.serial}/request", json.dumps(msg_push))
        
        # Também pedir infos (versão, usage_hours etc)
        msg_info = {"info": {"sequence_id": "0", "command": "get_version"}}
        self.client.publish(f"device/{self.serial}/request", json.dumps(msg_info))

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            self.parse_bambu_json(payload)
            self.last_update = time.time()
        except Exception as e:
            log_error(f"Error parsing Bambu msg: {e}")

    def parse_bambu_json(self, data):
        with self.lock:
            # Pegar dados de print (pode estar no topo ou dentro de data)
            p = data.get('print', {})
            
            # Se 'print' não existe, data pode ser o próprio dicionário de status em alguns casos
            # Mas geralmente a Bambu manda {"print": {...}} ou {"ams": {...}}
            
            if p:
                if 'gcode_state' in p:
                    self.status['state'] = p['gcode_state'].lower()
                if 'mc_percent' in p:
                    self.status['progress'] = p['mc_percent']
                if 'mc_remaining_time' in p:
                    # A Bambu manda minutos. O cartão e o protocolo leem segundos.
                    minutes = int(p['mc_remaining_time'] or 0)
                    self.status['remaining_time'] = minutes * 60
                    dt = datetime.now() + timedelta(minutes=minutes)
                    self.status['finish_time'] = dt.strftime("%H:%M")
                layer_block = p.get('3D') if isinstance(p.get('3D'), dict) else {}
                if 'layer_num' in p or 'layer_num' in layer_block:
                    self.status['layer'] = p.get('layer_num', layer_block.get('layer_num'))
                if 'total_layer_num' in p or 'total_layer_num' in layer_block:
                    self.status['total_layers'] = p.get('total_layer_num', layer_block.get('total_layer_num'))
                if isinstance(p.get('lights_report'), list):
                    for light in p['lights_report']:
                        if isinstance(light, dict) and light.get('node') == 'chamber_light':
                            self.status['led_val'] = 100 if light.get('mode') == 'on' else 0
                if 'nozzle_temper' in p:
                    self.status['temp_nozzle'] = p['nozzle_temper']
                if 'nozzle_target_temper' in p:
                    self.status['target_nozzle'] = p['nozzle_target_temper']
                if 'bed_temper' in p:
                    self.status['temp_bed'] = p['bed_temper']
                if 'bed_target_temper' in p:
                    self.status['target_bed'] = p['bed_target_temper']
                if 'chamber_temper' in p:
                    self.status['chamber_temp'] = p['chamber_temper']

                # H2D e firmware novo: o segundo bico e a câmara vêm em print.device,
                # com a temperatura atual nos 16 bits baixos e a meta nos 16 altos.
                device = p.get('device') if isinstance(p.get('device'), dict) else {}
                if not device and isinstance(data.get('device'), dict):
                    device = data.get('device')
                extruder = device.get('extruder') if isinstance(device.get('extruder'), dict) else {}
                entries = extruder.get('info') if isinstance(extruder.get('info'), list) else []
                sides = {}
                for entry in entries:
                    if not isinstance(entry, dict) or 'temp' not in entry:
                        continue
                    try:
                        eid = int(entry.get('id'))
                    except (TypeError, ValueError):
                        continue
                    if eid not in (0, 1):
                        continue
                    split = _split_packed_temp(entry.get('temp'))
                    if split is None:
                        continue
                    sides[eid] = split
                if 0 in sides and 1 in sides:
                    self.status['temp_nozzle_right'], self.status['target_nozzle_right'] = sides[0]
                    self.status['temp_nozzle_left'], self.status['target_nozzle_left'] = sides[1]
                    self.status['nozzle_count'] = 2
                    try:
                        active = (int(extruder.get('state')) >> 4) & 0xF
                    except (TypeError, ValueError):
                        active = None
                    if active in sides:
                        self.status['active_nozzle'] = active
                        self.status['temp_nozzle'], self.status['target_nozzle'] = sides[active]
                ctc = device.get('ctc') if isinstance(device.get('ctc'), dict) else {}
                ctc_temp = ctc.get('info', {}).get('temp') if isinstance(ctc.get('info'), dict) else None
                if ctc_temp is not None:
                    split = _split_packed_temp(ctc_temp)
                    if split is not None:
                        self.status['chamber_temp'] = split[0]
                        if split[1]:
                            self.status['target_chamber'] = split[1]
                nozzle_block = device.get('nozzle') if isinstance(device.get('nozzle'), dict) else {}
                nozzle_infos = nozzle_block.get('info') if isinstance(nozzle_block.get('info'), list) else []
                for entry in nozzle_infos:
                    if not isinstance(entry, dict):
                        continue
                    try:
                        nid = int(entry.get('id'))
                        diameter = round(float(entry.get('diameter')), 2) if entry.get('diameter') not in (None, '') else None
                    except (TypeError, ValueError):
                        continue
                    ntype = str(entry.get('type') or '')
                    if len(nozzle_infos) > 1 and nid == 0:
                        if diameter is not None:
                            self.status['nozzle_diameter_right'] = diameter
                        if ntype:
                            self.status['nozzle_type_right'] = ntype
                    elif nid == 1:
                        if diameter is not None:
                            self.status['nozzle_diameter_left'] = diameter
                        if ntype:
                            self.status['nozzle_type_left'] = ntype
                    elif nid == 0:
                        if diameter is not None:
                            self.status['nozzle_diameter'] = diameter
                        if ntype:
                            self.status['nozzle_type'] = ntype
                if 'gcode_file' in p:
                    self.status['gcode_file'] = p['gcode_file']
                if 'plate_idx' in p:
                    try:
                        self.status['plate_idx'] = int(p['plate_idx'])
                    except (TypeError, ValueError):
                        pass
                if 'gcode_start_time' in p:
                    try:
                        started = int(float(p['gcode_start_time']))
                        if started > 10_000_000_000:
                            started //= 1000
                        if started > 0:
                            self.status['_job_started'] = started
                            self.status['started_at'] = datetime.fromtimestamp(started, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                            self.status['elapsed_time'] = max(0, int(time.time()) - started)
                    except (TypeError, ValueError, OSError, OverflowError):
                        pass
                plate = self._plate_number()
                if 'subtask_name' in p:
                    new_file = p['subtask_name']
                    if new_file and (new_file != self.current_filename or plate != self.status.get('_cover_plate')):
                        self.current_filename = new_file
                        self.status['filename'] = new_file
                        self.status['task_name'] = new_file.replace('.gcode', '').replace('.3mf', '')
                        self.status['cover_image'] = None
                        self.status['print_weight'] = 0
                        self.status['_cover_plate'] = plate
                        self._start_metadata_fetch(new_file)
                elif self.current_filename and plate != self.status.get('_cover_plate'):
                    self.status['cover_image'] = None
                    self.status['_cover_plate'] = plate
                    self._start_metadata_fetch(self.current_filename)
                if 'cooling_fan_speed' in p:
                    self.status['fan_part'] = round((int(p['cooling_fan_speed']) / 15.0) * 100)
                if 'big_fan1_speed' in p:
                    self.status['fan_aux'] = round((int(p['big_fan1_speed']) / 15.0) * 100)
                if 'big_fan2_speed' in p:
                    self.status['fan_chamber'] = round((int(p['big_fan2_speed']) / 15.0) * 100)
                if 'spd_lvl' in p:
                    self.status['speed_level'] = p['spd_lvl']
                if 'wifi_signal' in p:
                    try:
                        self.status['wifi_signal'] = int(p['wifi_signal'].replace('dBm', ''))
                    except: pass
                if 'hms' in p:
                    self.status['hms'] = p['hms']
                
                # Print Error e HMS handling
                if 'print_error' in p:
                    err_code = p['print_error']
                    self.status['print_error'] = {
                        'code': err_code,
                        'message': f"Erro {err_code:X}" if err_code != 0 else ""
                    }
            # AMS e VT Tray (Carretel Externo)
            # Podem estar no topo ou dentro de 'print'
            ams_data = data.get('ams') or p.get('ams', {})
            vt_data = data.get('vt_tray') or p.get('vt_tray', {})
            
            # Determinar ams/tray ativos
            active_ams = -1
            active_tray = -1
            tray_now = ams_data.get('tray_now') or p.get('tray_now')
            if tray_now is not None:
                try:
                    tn = int(tray_now)
                    if tn == 254: # Externo
                        active_ams = 254
                        active_tray = 0
                    elif tn < 254:
                        active_ams = tn >> 2
                        active_tray = tn & 0x03
                except: pass
            
            # Sobrescrever se houver info mais específica no print (comum em Full Report)
            if 'mc_ams_index' in p: active_ams = p['mc_ams_index']
            if 'mc_tray_index' in p: active_tray = p['mc_tray_index']

            trays = []
            
            # 1. Processar Unidades AMS
            for unit in ams_data.get('ams', []):
                unit_id = int(unit.get('id', 0))
                humidity = unit.get('humidity', '')
                humidity_raw = unit.get('humidity_raw')
                unit_temp = unit.get('temp')
                dry_time = unit.get('dry_time')
                for t in unit.get('tray', []):
                    tray_id = int(t.get('id', 0))
                    is_active = (unit_id == active_ams and tray_id == active_tray)
                    
                    f_type = t.get('tray_type', '')
                    f_color = t.get('tray_color', 'FFFFFF')
                    if not f_color.startswith('#'): f_color = '#' + f_color
                    f_brand = t.get('tray_sub_brands', '')
                    f_remain = t.get('remain', -1)
                    idx = t.get('tray_info_idx', '')
                    f_uuid = t.get('tray_uuid', '')
                    
                    # Um slot é considerado vazio se não tiver tipo nem idx
                    is_empty = not f_type and not idx
                    
                    # Identificar nome amigável
                    f_name = get_bambu_filament_name(idx)
                    if f_name == "Unknown" and f_brand:
                        f_name = f"{f_brand} {f_type}".strip()
                    elif f_name == "Unknown":
                        f_name = f_type or "Desconhecido"

                    trays.append({
                        'ams': unit_id,
                        'id': tray_id,
                        'type': f_type,
                        'brand': f_brand,
                        'name': f_name,
                        'color': f_color,
                        'remain': f_remain,
                        'uuid': f_uuid,
                        'humidity': humidity,
                        'humidity_raw': humidity_raw,
                        'temp': unit_temp,
                        'dry_time': dry_time,
                        'nozzle': None,
                        'active': is_active,
                        'empty': is_empty
                    })

            # 2. Processar VT Tray (Carretel Externo/Lateral)
            if vt_data:
                is_active = (active_ams == 254 or active_ams == 255) # 255 as vezes significa externo em alguns modelos
                f_type = vt_data.get('tray_type', '')
                f_color = vt_data.get('tray_color', 'FFFFFF')
                if not f_color.startswith('#'): f_color = '#' + f_color
                f_remain = vt_data.get('remain', -1)
                idx = vt_data.get('tray_info_idx', '')
                f_brand = vt_data.get('tray_sub_brands', '')
                f_uuid = vt_data.get('tray_uuid', '')
                
                # Identificar nome amigável
                f_name = get_bambu_filament_name(idx)
                if f_name == "Unknown" and f_brand:
                    f_name = f"{f_brand} {f_type}".strip()
                elif f_name == "Unknown":
                    f_name = f_type or "Desconhecido"

                # Só adicionar se não estiver totalmente vazio ou se for o ativo
                if f_type or is_active:
                    trays.append({
                        'ams': 254, # ID reservado para Externo
                        'id': 0,
                        'type': f_type,
                        'brand': f_brand,
                        'name': f_name,
                        'uuid': f_uuid,
                        'color': f_color,
                        'remain': f_remain,
                        'humidity': 'N/A',
                        'active': is_active,
                        'empty': not f_type
                    })

            # Qual bico está usando cada bandeja. id 0 = direito, id 1 = esquerdo.
            # snow: índice do AMS nos bits altos, bandeja nos 2 bits baixos.
            device = p.get('device') if isinstance(p, dict) and isinstance(p.get('device'), dict) else {}
            if not device and isinstance(data.get('device'), dict):
                device = data.get('device')
            extruder = device.get('extruder') if isinstance(device.get('extruder'), dict) else {}
            for entry in extruder.get('info') or []:
                if not isinstance(entry, dict) or 'snow' not in entry:
                    continue
                try:
                    eid = int(entry.get('id'))
                    snow = int(entry.get('snow'))
                except (TypeError, ValueError):
                    continue
                if eid not in (0, 1):
                    continue
                ams_index = snow >> 8
                tray_index = snow & 0x3
                if ams_index >= 255:
                    continue
                side = 'right' if eid == 0 else 'left'
                for tray in trays:
                    try:
                        if int(tray['ams']) == ams_index and int(tray['id']) == tray_index:
                            tray['nozzle'] = side
                    except (TypeError, ValueError):
                        continue

            if trays:
                self.status['ams'] = trays
                # Encontrar nome do tray ativo
                active_t = next((t for t in trays if t['active']), None)
                if active_t:
                    self.status['active_tray_name'] = active_t['name']
                    self.status['active_tray_uuid'] = active_t.get('uuid', '')
                else:
                    self.status['active_tray_name'] = 'None'
                    self.status['active_tray_uuid'] = ''

            # Dados do comando "info" (get_version)
            info = data.get('info', {})
            if info:
                msg = info.get('command')
                if msg == 'get_version':
                    # Extrair versões
                    for dev in info.get('module', []):
                        if dev.get('name') == 'ota':
                            self.status['firmware_update']['current'] = dev.get('sw_ver', '')
                    
                    # Tentar pegar usage hours se reportado
                    if 'usage_hours' in info:
                        self.status['total_usage'] = info['usage_hours']

            # Track usage hours localmente se não vier da impressora
            if self.status['state'] in ['running', 'printing']:
                if self.start_time is None:
                    self.start_time = time.time()
                else:
                    # Incrementar uso (aproximado)
                    now = time.time()
                    self.status['total_usage'] += (now - self.start_time) / 3600.0
                    self.start_time = now
            else:
                self.start_time = None

    def _plate_number(self):
        gcode = str(self.status.get('gcode_file') or '')
        match = re.search(r'plate_(\d+)\.gcode', gcode)
        if match:
            return match.group(1)
        try:
            number = int(self.status.get('plate_idx'))
        except (TypeError, ValueError):
            return '1'
        return str(number) if number > 0 else '1'

    def _start_metadata_fetch(self, filename):
        self._meta_token += 1
        token = self._meta_token
        self.metadata_thread = threading.Thread(
            target=self._fetch_metadata_ftp, args=(filename, token), daemon=True,
        )
        self.metadata_thread.start()

    def _fetch_metadata_ftp(self, filename, token=0):
        # Retries are important for X1C as the file might not be ready immediately
        # Aumentado para 12 tentativas (aprox 60s) como no exemplo oficial
        listed = False
        for attempt in range(12):
            try:
                log_debug(f"[{self.ip}] FTP Metadata (Tentativa {attempt+1}): {filename}")
                context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                
                ftp = ImplicitFTP_TLS(context=context)
                ftp.connect(self.ip, 990, timeout=10)
                ftp.login("bblp", self.access_code)
                ftp.prot_p()
                
                # Lista de caminhos para tentar encontrar o 3mf
                # X1C e P1P as vezes usam nomes fixos ou pastas diferentes
                search_files = [filename]
                if not filename.endswith('.3mf'):
                    search_files.append(filename + ".3mf")
                    search_files.append(filename + ".gcode.3mf")
                
                # Nomes comuns em impressões via cloud
                search_files.extend(["ftp_model.3mf", "model.3mf", "_model_.3mf"])
                
                target_path = None
                for f_name in search_files:
                    for folder in ["/cache", ""]:
                        p = f"{folder}/{f_name}" if folder else f"/{f_name}"
                        try:
                            # log_debug(f"[{self.ip}] Testando FTP: {p}")
                            ftp.size(p)
                            target_path = p
                            break
                        except: continue
                    if target_path: break
                    
                if target_path:
                    log_debug(f"[{self.ip}] FTP: Baixando {target_path}...")
                    bio = io.BytesIO()
                    ftp.retrbinary(f"RETR {target_path}", bio.write)
                    ftp.quit()
                    
                    if token != self._meta_token:
                        return
                    bio.seek(0)
                    reported = wanted = self._plate_number()
                    with zipfile.ZipFile(bio) as z:
                        names = set(z.namelist())
                        try:
                            with z.open('Metadata/slice_info.config') as f:
                                tree = ET.parse(f)
                            wanted = self._image_plate(tree, reported)
                            for plate in tree.findall('plate'):
                                meta = {item.get('key'): item.get('value') for item in plate}
                                if str(meta.get('index') or '') != wanted:
                                    continue
                                if meta.get('weight'):
                                    self.status['print_weight'] = float(meta['weight'])
                        except Exception as e:
                            log_debug(f"[{self.ip}] Erro ao processar Zip: {e}")
                        image = None
                        for candidate in (
                            f'Metadata/plate_{wanted}.png',
                            f'Metadata/top_{wanted}.png',
                            f'Metadata/pick_{wanted}.png',
                        ) if wanted else ():
                            if candidate in names:
                                image = base64.b64encode(z.read(candidate)).decode('ascii')
                                break
                        if image and token == self._meta_token:
                            self.status['cover_image'] = image
                            self.status['_cover_plate'] = reported
                            log_info(f"[{self.ip}] Miniatura da placa {wanted}.")
                    return
                else:
                    ftp.quit()
            except Exception as e:
                log_debug(f"[{self.ip}] Erro FTP (Tentativa {attempt+1}): {e}")

            if token != self._meta_token:
                return
            if attempt >= 1 and self._files_channel_allowed():
                found = self._fetch_cover_files_channel(filename, token)
                if found:
                    return
                listed = listed or found is False
            time.sleep(5)
        log_info(f"[{self.ip}] Não consegui baixar a miniatura de {filename}.")
        if listed:
            log_info(
                f"[{self.ip}] O arquivo não está no cartão ou pendrive da impressora. "
                "Envie para o armazenamento externo para a miniatura aparecer."
            )

    @staticmethod
    def _image_plate(tree, reported):
        # H2D informa plate_1.gcode mesmo quando o 3mf enviado só tem outra placa fatiada.
        sliced = []
        for plate in tree.findall('plate'):
            meta = {item.get('key'): item.get('value') for item in plate}
            if meta.get('index'):
                sliced.append(str(meta['index']))
        if len(sliced) == 1:
            return sliced[0]
        if not sliced or reported in sliced:
            return reported
        return None

    def _files_channel_allowed(self):
        # A1 e P1 usam a porta 6000 para a câmera JPEG; não abrir outra sessão nela.
        if str(self.serial or '').upper().startswith(('030', '039', '01P', '01S')):
            return False
        return not getattr(self.cam_thread, 'jpeg_channel', False)

    def _fetch_cover_files_channel(self, filename, token):
        # H2D guarda o envio em /media/usb0/cache/<nome>.gcode.3mf e não abre o FTPS.
        # Da memória interna a impressora não deixa baixar (allow_internal_model_download = false).
        # Devolve True com a miniatura, False quando listou e não achou, None quando a porta não respondeu.
        gcode = str(self.status.get('gcode_file') or '')
        exact = gcode.rsplit('/', 1)[-1] if gcode.endswith('.3mf') else ''
        names = {filename, f"{filename}.3mf", f"{filename}.gcode.3mf"} if filename else set()
        started = int(self.status.get('_job_started') or 0)
        channel = None
        try:
            channel = BambuFileChannel(self.ip, self.access_code)
            candidates = []
            for item in channel.list_models():
                path = str(item.get('path') or item.get('name') or '')
                base = path.rsplit('/', 1)[-1]
                try:
                    stamp = int(item.get('time') or 0)
                except (TypeError, ValueError):
                    stamp = 0
                if exact and base == exact:
                    candidates.append((2, stamp, path))
                elif base in names:
                    # Mesmo nome de um envio antigo não serve: o arquivo tem que ser deste trabalho.
                    if started and stamp and not (started - 43200 <= stamp <= started + 900):
                        continue
                    candidates.append((1 if '/cache/' in path else 0, stamp, path))
            if not candidates:
                return False
            path = max(candidates)[2]
            reported = self._plate_number()
            info = channel.read_member(path, 'Metadata/slice_info.config')
            tree = ET.fromstring(info) if info else ET.Element('config')
            wanted = self._image_plate(tree, reported)
            if not wanted:
                log_debug(f"[{self.ip}] {path} não tem a placa {reported} fatiada.")
                return False
            image = channel.read_member(path, f'Metadata/plate_{wanted}.png')
            if not image or not image.startswith(b'\x89PNG\r\n\x1a\n'):
                return False
            weight = None
            for plate in tree.findall('plate'):
                meta = {item.get('key'): item.get('value') for item in plate}
                if str(meta.get('index') or '') == wanted and meta.get('weight'):
                    weight = float(meta['weight'])
            if token != self._meta_token:
                return True
            if weight is not None:
                self.status['print_weight'] = weight
            self.status['cover_image'] = base64.b64encode(image).decode('ascii')
            self.status['_cover_plate'] = reported
            log_info(f"[{self.ip}] Miniatura da placa {wanted} pela porta 6000.")
            return True
        except Exception as e:
            log_debug(f"[{self.ip}] Arquivos pela porta 6000: {e}")
            return None
        finally:
            if channel is not None:
                channel.close()

    def update(self):
        # Incrementar horas de uso se estiver imprimindo
        now = time.time()
        if self.status.get('state', '').lower() in ['running', 'printing']:
            delta = now - self.last_usage_time
            self.status['total_usage'] = self.status.get('total_usage', 0) + (max(0, delta) / 3600.0)
        self.last_usage_time = now

        if not self.connected_flag or (time.time() - self.last_update > 30):
            self.request_push()
            if time.time() - self.last_update > 60:
                 self.status['state'] = 'offline'

    def send_command(self, command, **kwargs):
        if not self.connected_flag: return
        topic = f"device/{self.serial}/request"
        
        msg = {}
        if command == 'pause':
            msg = {"print": {"command": "pause", "sequence_id": "0"}}
        elif command == 'resume':
            msg = {"print": {"command": "resume", "sequence_id": "0"}}
        elif command == 'stop':
            msg = {"print": {"command": "stop", "sequence_id": "0"}}
        elif command == 'led':
            val = int(kwargs.get('val', 0))
            msg = {"system": {"sequence_id": "0", "command": "ledctrl", "led_node": "chamber_light", "led_mode": "on" if val > 0 else "off"}}
        elif command == 'speed':
            val = int(kwargs.get('val', 2))
            msg = {"print": {"sequence_id": "0", "command": "speed_level", "param": str(val)}}
        
        # Movement and extrusion controls REMOVED as per user request
        # elif command == 'home': ...
        # elif command == 'move': ...
        # elif command == 'extrude': ...
        # elif command == 'motors_off': ...
        
        if msg:
            self.client.publish(topic, json.dumps(msg))


def create_printer_from_config(config):
    p_type = config.get('type')
    if p_type == 'moonraker':
        return MoonrakerPrinter(config)
    elif p_type == 'elegoo':
        return ElegooPrinter(config)
    elif p_type == 'bambu':
        p = BambuPrinter(config)
        p.connect()
        return p
    return None
