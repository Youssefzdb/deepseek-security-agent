#!/usr/bin/env python3
"""DeepSeek API client — auth, PoW, streaming chat."""
import json, os, sys, time, uuid, base64, subprocess, socket, ctypes
from pathlib import Path
import requests

BASE_URL = "https://chat.deepseek.com"
APM_TOKEN = "772f2fcc08224a50b0134f8d3c139a21"

HASH_C_SRC = Path(__file__).parent.parent / "deepseek_hash.c"
HASH_SO = Path(__file__).parent.parent / "deepseek_hash.so"


def _build_hash_lib():
    if HASH_SO.exists():
        return str(HASH_SO)
    if not HASH_C_SRC.exists():
        return None
    try:
        subprocess.run(
            ["cc", "-O3", "-shared", "-fPIC", "-o", str(HASH_SO), str(HASH_C_SRC), "-lcrypto"],
            capture_output=True, timeout=30
        )
        if HASH_SO.exists():
            return str(HASH_SO)
    except Exception:
        pass
    return None


class PoWSolver:
    def __init__(self):
        lib_path = _build_hash_lib()
        if lib_path:
            self.lib = ctypes.CDLL(lib_path)
            self.lib.solve_pow.argtypes = [
                ctypes.c_char_p, ctypes.c_char_p,
                ctypes.c_double, ctypes.POINTER(ctypes.c_double)
            ]
            self.lib.solve_pow.restype = ctypes.c_int
            self.mode = "c"
        else:
            self.mode = "py"

    def solve(self, challenge_hex, prefix, difficulty):
        if self.mode == "c":
            return self._solve_c(challenge_hex, prefix, difficulty)
        return self._solve_py(challenge_hex, prefix, difficulty)

    def _solve_c(self, challenge_hex, prefix, difficulty):
        ans = ctypes.c_double()
        r = self.lib.solve_pow(
            challenge_hex.encode(), prefix.encode(),
            float(difficulty), ctypes.byref(ans)
        )
        if r == 1:
            return int(ans.value)
        raise ValueError("PoW not found (C)")

    def _solve_py(self, challenge_hex, prefix, difficulty):
        chal_bytes = bytes.fromhex(challenge_hex)
        PLEN, OLEN = 136, 32
        RC = [
            0x0000000000000001, 0x0000000000008082, 0x800000000000808a,
            0x8000000080008000, 0x000000000000808b, 0x0000000080000001,
            0x8000000080008081, 0x8000000000008009, 0x000000000000008a,
            0x0000000000000088, 0x0000000080008009, 0x000000008000000a,
            0x000000008000808b, 0x800000000000008b, 0x8000000000008089,
            0x8000000000008003, 0x8000000000008002, 0x8000000000000080,
            0x000000000000800a, 0x800000008000000a, 0x8000000080008081,
            0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
        ]
        ROT = lambda x, n: ((x << n) | (x >> (64 - n))) & 0xFFFFFFFFFFFFFFFF

        def keccak(data):
            state = [0] * 25
            off = 0
            while off + PLEN <= len(data):
                for i in range(PLEN // 8):
                    state[i] ^= int.from_bytes(data[off + i*8:off + i*8 + 8], 'little')
                a = state[:]
                for rnd in range(1, 24):
                    C = [a[0]^a[5]^a[10]^a[15]^a[20], a[1]^a[6]^a[11]^a[16]^a[21],
                         a[2]^a[7]^a[12]^a[17]^a[22], a[3]^a[8]^a[13]^a[18]^a[23],
                         a[4]^a[9]^a[14]^a[19]^a[24]]
                    D = [C[4]^ROT(C[1],1), C[0]^ROT(C[2],1), C[1]^ROT(C[3],1),
                         C[2]^ROT(C[4],1), C[3]^ROT(C[0],1)]
                    for i in range(5):
                        a[i]^=D[0]; a[i+5]^=D[0]; a[i+10]^=D[0]; a[i+15]^=D[0]; a[i+20]^=D[0]
                    b = [a[0], ROT(a[1],1), ROT(a[2],62), ROT(a[3],28), ROT(a[4],27),
                         ROT(a[5],36), ROT(a[6],44), ROT(a[7],6), ROT(a[8],55), ROT(a[9],20),
                         ROT(a[10],3), ROT(a[11],10), ROT(a[12],43), ROT(a[13],25), ROT(a[14],39),
                         ROT(a[15],41), ROT(a[16],45), ROT(a[17],15), ROT(a[18],21), ROT(a[19],8),
                         ROT(a[20],18), ROT(a[21],2), ROT(a[22],61), ROT(a[23],56), ROT(a[24],14)]
                    for i in range(25):
                        a[i] = b[i] ^ (~b[(i+1)%25] & b[(i+2)%25])
                    a[0] ^= RC[rnd]
                state = a
                off += PLEN
            final = bytearray(PLEN)
            final[:len(data)-off] = data[off:]
            final[len(data)-off] = 0x06
            final[-1] |= 0x80
            for i in range(PLEN // 8):
                state[i] ^= int.from_bytes(final[i*8:i*8+8], 'little')
            a = state[:]
            for rnd in range(1, 24):
                C = [a[0]^a[5]^a[10]^a[15]^a[20], a[1]^a[6]^a[11]^a[16]^a[21],
                     a[2]^a[7]^a[12]^a[17]^a[22], a[3]^a[8]^a[13]^a[18]^a[23],
                     a[4]^a[9]^a[14]^a[19]^a[24]]
                D = [C[4]^ROT(C[1],1), C[0]^ROT(C[2],1), C[1]^ROT(C[3],1),
                     C[2]^ROT(C[4],1), C[3]^ROT(C[0],1)]
                for i in range(5):
                    a[i]^=D[0]; a[i+5]^=D[0]; a[i+10]^=D[0]; a[i+15]^=D[0]; a[i+20]^=D[0]
                b = [a[0], ROT(a[1],1), ROT(a[2],62), ROT(a[3],28), ROT(a[4],27),
                     ROT(a[5],36), ROT(a[6],44), ROT(a[7],6), ROT(a[8],55), ROT(a[9],20),
                     ROT(a[10],3), ROT(a[11],10), ROT(a[12],43), ROT(a[13],25), ROT(a[14],39),
                     ROT(a[15],41), ROT(a[16],45), ROT(a[17],15), ROT(a[18],21), ROT(a[19],8),
                     ROT(a[20],18), ROT(a[21],2), ROT(a[22],61), ROT(a[23],56), ROT(a[24],14)]
                for i in range(25):
                    a[i] = b[i] ^ (~b[(i+1)%25] & b[(i+2)%25])
                a[0] ^= RC[rnd]
            state = a
            out = bytearray(OLEN)
            for i in range(OLEN // 8):
                out[i*8:i*8+8] = state[i].to_bytes(8, 'little')
            return bytes(out)

        for nonce in range(int(difficulty)):
            full = prefix + str(nonce)
            h = keccak(full.encode())
            if h == chal_bytes:
                return nonce
        raise ValueError("PoW not found (Python)")


def rotate_tor(cookie_path=None):
    try:
        cp = cookie_path or os.environ.get("TOR_COOKIE") or "/root/.tor/control_auth_cookie"
        if not os.path.exists(cp):
            return False
        with open(cp, "rb") as f:
            cookie = f.read()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect(("127.0.0.1", 9051))
        s.send(f"AUTHENTICATE {cookie.hex()}\r\n".encode())
        time.sleep(0.5)
        if b"250" not in s.recv(1024):
            s.close(); return False
        s.send(b"SIGNAL NEWNYM\r\n")
        time.sleep(2)
        r = s.recv(1024); s.close()
        return b"250" in r
    except Exception:
        return False


class DeepSeekClient:
    def __init__(self, email, password, proxies=None):
        self.powsolver = PoWSolver()
        self.email, self.password = email, password
        self.token = None
        self.user_id = None
        self.session_id = None
        self.http = requests.Session()
        self.http.headers.update({
            "User-Agent": "DeepSeek/2.1.1 (Android 14; Build/AP3A.240905.015)",
            "Content-Type": "application/json",
            "Accept-Language": "en",
            "x-client-platform": "android",
            "x-client-version": "2.1.1",
            "x-auth-token": APM_TOKEN,
        })
        if proxies:
            self.http.proxies.update(proxies)
        self.proxies = proxies or {}
        self._try_load()
        if not self.token:
            self.login()
        if not self.session_id:
            self.create_session()

    def _try_load(self):
        sf = Path(".session.json")
        if not sf.exists():
            return False
        try:
            data = json.loads(sf.read_text())
            self.token = data.get("token")
            self.user_id = data.get("user_id")
            self.session_id = data.get("session_id")
            if self.token:
                self.http.headers["Authorization"] = f"Bearer {self.token}"
                r = self.http.get(f"{BASE_URL}/api/v0/users/me", timeout=15)
                if r.status_code == 200:
                    return True
        except Exception:
            pass
        self.token = None
        self.session_id = None
        return False

    def _save(self):
        try:
            Path(".session.json").write_text(json.dumps({
                "token": self.token, "user_id": self.user_id, "session_id": self.session_id
            }))
        except Exception:
            pass

    def login(self):
        for attempt in range(5):
            try:
                r = self.http.post(f"{BASE_URL}/api/v0/users/login", json={
                    "email": self.email, "password": self.password,
                    "device_id": str(uuid.uuid4()), "os": "android",
                }, timeout=30)
                d = r.json()
                if d.get("code") == 40029:
                    wait = 10 * (attempt + 1)
                    if attempt >= 2:
                        rotate_tor()
                        time.sleep(3)
                    time.sleep(wait)
                    continue
                if d.get("code") != 0:
                    raise Exception(f"Login error: {d}")
                user = d["data"]["biz_data"]["user"]
                self.token = user["token"]
                self.user_id = user["id"]
                self.http.headers["Authorization"] = f"Bearer {self.token}"
                self._save()
                return True
            except requests.exceptions.ConnectionError:
                if attempt < 4:
                    time.sleep(5)
                else:
                    raise
            except Exception:
                if attempt < 4:
                    time.sleep(3)
                else:
                    raise

    def create_session(self):
        r = self.http.post(f"{BASE_URL}/api/v0/chat_session/create", json={}, timeout=30)
        d = r.json()
        if d.get("code") != 0:
            raise Exception(f"Session error: {d}")
        self.session_id = d["data"]["biz_data"]["chat_session"]["id"]
        self._save()
        return self.session_id

    def solve_pow(self, target_path):
        r = self.http.post(f"{BASE_URL}/api/v0/chat/create_pow_challenge",
            json={"target_path": target_path}, timeout=30)
        d = r.json()
        if d.get("code") != 0:
            raise Exception(f"PoW error: {d}")
        chal = d["data"]["biz_data"]["challenge"]
        prefix = f"{chal['salt']}_{chal['expire_at']}_"
        answer = self.powsolver.solve(chal['challenge'], prefix, chal['difficulty'])
        pow_data = {"algorithm": "DeepSeekHashV1", "challenge": chal['challenge'],
            "salt": chal['salt'], "answer": answer, "signature": chal['signature'],
            "target_path": chal['target_path']}
        return base64.b64encode(json.dumps(pow_data).encode()).decode()

    def send_message(self, messages, model="deepseek-v3", stream=False, _retry=0):
        prompt = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        pow_header = self.solve_pow("/api/v0/chat/completion")
        body = {"messages": messages, "chat_session_id": self.session_id,
                "stream": True, "model": model, "prompt": prompt, "ref_file_ids": [],
                "thinking": {"type": "disabled"}}
        r = self.http.post(f"{BASE_URL}/api/v0/chat/completion", json=body,
            headers={"x-ds-pow-response": pow_header}, timeout=120, stream=True)
        if r.status_code == 429:
            if _retry < 3:
                time.sleep(15 * (_retry + 1))
                self.login()
                self.create_session()
                return self.send_message(messages, model, stream, _retry+1)
            raise Exception("Rate limit exceeded after retries")
        if r.status_code == 401:
            self.login()
            return self.send_message(messages, model, stream, _retry)
        if r.status_code != 200:
            raise Exception(f"HTTP {r.status_code}: {r.text[:300]}")
        if stream:
            return r
        content = ""
        event_type = None
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("event:"):
                event_type = line[6:].strip()
                continue
            if not line.startswith("data:"):
                continue
            raw = line[5:].strip()
            if not raw.startswith("{"):
                continue
            try:
                d = json.loads(raw)
                v = d.get("v")
                p = d.get("p", "")
                o = d.get("o", "")
                # rate_limit in event hint
                if event_type == "hint" and isinstance(d, dict) and d.get("type") == "error":
                    msg = d.get("content", "")
                    if "rate_limit" in d.get("finish_reason", "") or "frequent" in msg.lower():
                        if _retry < 3:
                            time.sleep(15 * (_retry + 1))
                            self.create_session()
                            return self.send_message(messages, model, stream, _retry+1)
                    raise Exception(f"API error: {msg}")
                if event_type == "close":
                    break
                # Format 1: APPEND string (with or without path)
                if isinstance(v, str) and o == "APPEND":
                    content += v
                # Format 2: plain string token (most common: {"v": "word"})
                elif isinstance(v, str) and not p and not o:
                    content += v
                # Format 3: content path append
                elif isinstance(v, str) and p and "content" in str(p):
                    content += v
                # Format 4: BATCH list
                elif isinstance(v, list) and o == "BATCH":
                    for item in v:
                        if isinstance(item, dict):
                            iv = item.get("v", "")
                            ip = item.get("p", "")
                            if isinstance(iv, str) and "content" in str(ip):
                                content += iv
                # Format 5: dict with fragments (initial load)
                elif isinstance(v, dict):
                    for frag in v.get("response", {}).get("fragments", []):
                        c = frag.get("content", "")
                        if c:
                            content += c
            except Exception as e:
                if "API error" in str(e) or "Rate limit" in str(e):
                    raise
            event_type = None
        return content

    def stream_message(self, messages, model="deepseek-v3"):
        r = self.send_message(messages, model, stream=True)
        for line in r.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            raw = line[6:]
            if not raw.startswith("{"):
                continue
            if '"v":"[DONE]"' in raw:
                break
            try:
                d = json.loads(raw)
                v = d.get("v")
                p = d.get("p")
                if isinstance(v, str):
                    if not p:
                        yield v
                    elif p.endswith("content") and d.get("o") == "APPEND":
                        yield v
                elif isinstance(v, dict):
                    for f in v.get("response", {}).get("fragments", []):
                        c = f.get("content", "")
                        if c:
                            yield c
            except (json.JSONDecodeError, TypeError):
                pass
