#!/usr/bin/env python3
"""Predefined security tools — optional helpers, not required."""
from .executor import Executor


class PredefinedTools:
    def __init__(self, executor: Executor):
        self.exec = executor

    def nmap(self, target, ports=None, flags="-sV -sC -T4"):
        ports_arg = f"-p {ports}" if ports else "-p-"
        return self.exec.run(f"nmap {flags} {ports_arg} {target}")

    def gobuster_dir(self, url, wordlist=None, extensions="php,html,txt"):
        wl = wordlist or "/usr/share/wordlists/dirb/common.txt"
        return self.exec.run(f"gobuster dir -u {url} -w {wl} -x {extensions} -t 50")

    def gobuster_dns(self, domain, wordlist=None):
        wl = wordlist or "/usr/share/wordlists/seclists/Discovery/DNS/subdomains-top1million-5000.txt"
        return self.exec.run(f"gobuster dns -d {domain} -w {wl} -t 50")

    def nikto(self, target):
        return self.exec.run(f"nikto -h {target}")

    def sqlmap(self, url, flags="--dbs --batch"):
        return self.exec.run(f'sqlmap -u "{url}" {flags}')

    def subfinder(self, domain):
        return self.exec.run(f"subfinder -d {domain} -silent")

    def whatweb(self, target):
        return self.exec.run(f"whatweb {target} -v")

    def dig(self, domain, type="A"):
        return self.exec.run(f"dig {domain} {type}")

    def whois(self, target):
        return self.exec.run(f"whois {target}")

    def curl(self, url, flags="-sI"):
        return self.exec.run(f"curl {flags} {url}")

    def ping(self, target, count=4):
        return self.exec.run(f"ping -c {count} {target}")

    def traceroute(self, target):
        return self.exec.run(f"traceroute {target}")

    def dirb(self, url, wordlist=None):
        wl = wordlist or "/usr/share/wordlists/dirb/common.txt"
        return self.exec.run(f"dirb {url} {wl}")

    def enum4linux(self, target):
        return self.exec.run(f"enum4linux -a {target}")

    def wpscan(self, url):
        return self.exec.run(f"wpscan --url {url} --enumerate vp,vt,u")

    def hydra(self, target, service, userlist, passlist):
        return self.exec.run(f"hydra -L {userlist} -P {passlist} {target} {service}")
