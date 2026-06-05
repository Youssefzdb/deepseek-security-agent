#!/usr/bin/env python3
"""
Predefined security & recon tools.
Each method auto-checks tool availability and returns (output, returncode).
"""
from .executor import Executor


class PredefinedTools:
    def __init__(self, executor: Executor):
        self.ex = executor

    # ── Network recon ─────────────────────────────────────────────────────────
    def nmap(self, target: str, ports: str | None = None,
             flags: str = "-sV -sC -T4") -> tuple[str, int]:
        """Port scan with optional port range."""
        ports_arg = f"-p {ports}" if ports else "-p-"
        return self.ex.run(f"nmap {flags} {ports_arg} {target}")

    def ping(self, target: str, count: int = 4) -> tuple[str, int]:
        return self.ex.run(f"ping -c {count} {target}")

    def traceroute(self, target: str) -> tuple[str, int]:
        return self.ex.run(f"traceroute -m 20 {target}")

    def whois(self, target: str) -> tuple[str, int]:
        return self.ex.run(f"whois {target}")

    def dig(self, domain: str, record_type: str = "A") -> tuple[str, int]:
        return self.ex.run(f"dig +short {domain} {record_type}")

    def curl(self, url: str, flags: str = "-sIL --max-time 10") -> tuple[str, int]:
        return self.ex.run(f"curl {flags} '{url}'")

    # ── Web recon ─────────────────────────────────────────────────────────────
    def whatweb(self, target: str) -> tuple[str, int]:
        self.ex.install_if_missing("whatweb")
        return self.ex.run(f"whatweb -v {target}")

    def nikto(self, target: str) -> tuple[str, int]:
        return self.ex.run(f"nikto -h {target} -nointeractive")

    def wpscan(self, url: str, enumerate: str = "vp,vt,u") -> tuple[str, int]:
        return self.ex.run(f"wpscan --url {url} --enumerate {enumerate} --no-banner")

    # ── Directory / DNS brute-force ───────────────────────────────────────────
    def gobuster_dir(self, url: str, wordlist: str | None = None,
                     extensions: str = "php,html,txt,bak") -> tuple[str, int]:
        wl = wordlist or "/usr/share/wordlists/dirb/common.txt"
        return self.ex.run(
            f"gobuster dir -u {url} -w {wl} -x {extensions} -t 50 -q"
        )

    def gobuster_dns(self, domain: str, wordlist: str | None = None) -> tuple[str, int]:
        wl = wordlist or "/usr/share/seclists/Discovery/DNS/subdomains-top1million-5000.txt"
        return self.ex.run(f"gobuster dns -d {domain} -w {wl} -t 50 -q")

    def dirb(self, url: str, wordlist: str | None = None) -> tuple[str, int]:
        wl = wordlist or "/usr/share/wordlists/dirb/common.txt"
        return self.ex.run(f"dirb {url} {wl} -S")

    def ffuf(self, url: str, wordlist: str | None = None,
             extensions: str = "php,html") -> tuple[str, int]:
        wl = wordlist or "/usr/share/wordlists/dirb/common.txt"
        return self.ex.run(
            f"ffuf -u {url}/FUZZ -w {wl} -e {extensions} -mc 200,301,302,403 -s"
        )

    # ── Subdomain enumeration ─────────────────────────────────────────────────
    def subfinder(self, domain: str) -> tuple[str, int]:
        return self.ex.run(f"subfinder -d {domain} -silent")

    def amass(self, domain: str) -> tuple[str, int]:
        return self.ex.run(f"amass enum -passive -d {domain}")

    # ── Exploitation ──────────────────────────────────────────────────────────
    def sqlmap(self, url: str, flags: str = "--dbs --batch --level=2") -> tuple[str, int]:
        return self.ex.run(f'sqlmap -u "{url}" {flags}')

    def hydra(self, target: str, service: str,
              userlist: str, passlist: str) -> tuple[str, int]:
        return self.ex.run(
            f"hydra -L {userlist} -P {passlist} {target} {service} -t 4"
        )

    def metasploit_run(self, resource_file: str) -> tuple[str, int]:
        """Run a metasploit resource file."""
        return self.ex.run(f"msfconsole -q -r {resource_file}")

    # ── SMB / AD ──────────────────────────────────────────────────────────────
    def enum4linux(self, target: str) -> tuple[str, int]:
        return self.ex.run(f"enum4linux -a {target}")

    def smbclient(self, target: str, share: str = "",
                  user: str = "anonymous") -> tuple[str, int]:
        return self.ex.run(f"smbclient //{target}/{share} -U {user} -N -l /tmp/smb_log")

    # ── Passive OSINT ─────────────────────────────────────────────────────────
    def theHarvester(self, domain: str, source: str = "all") -> tuple[str, int]:
        return self.ex.run(
            f"theHarvester -d {domain} -b {source} -l 200"
        )

    def shodan_cli(self, query: str) -> tuple[str, int]:
        return self.ex.run(f"shodan search '{query}'")

    # ── Utilities ─────────────────────────────────────────────────────────────
    def nc_banner(self, host: str, port: int) -> tuple[str, int]:
        """Grab banner from TCP port."""
        return self.ex.run(f"echo '' | nc -w 3 {host} {port}", timeout=10)

    def hash_identify(self, hash_str: str) -> tuple[str, int]:
        return self.ex.run(f"echo '{hash_str}' | hashid")

    def john(self, hash_file: str, wordlist: str | None = None) -> tuple[str, int]:
        wl = f"--wordlist={wordlist}" if wordlist else "--wordlist=/usr/share/wordlists/rockyou.txt"
        return self.ex.run(f"john {hash_file} {wl}")

    def hashcat(self, hash_file: str, mode: int = 0,
                wordlist: str | None = None) -> tuple[str, int]:
        wl = wordlist or "/usr/share/wordlists/rockyou.txt"
        return self.ex.run(f"hashcat -m {mode} {hash_file} {wl} --force")
