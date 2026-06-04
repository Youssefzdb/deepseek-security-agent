# 🤖 DeepSeek Security Agent

Agent autonome en terminal, propulsé par **DeepSeek** (V3 / R1 / Coder), conçu pour les tests de sécurité et l'automatisation de tâches complexes.

---

## 📁 Structure du projet

```
deepseek-agent/
├── main.py                  # Point d'entrée principal
├── requirements.txt         # Dépendances Python
├── deepseek_hash.c          # Solveur PoW en C (performance)
├── deepseek_hash.so         # Binaire compilé (généré automatiquement)
│
├── core/
│   ├── client.py            # Client API DeepSeek (auth, PoW, streaming)
│   └── agent.py             # Moteur de l'agent (Plan → Todo → Execute)
│
├── tools/
│   ├── executor.py          # Gestionnaire d'exécution de commandes
│   └── predefined.py        # Outils prédéfinis (nmap, sqlmap, etc.)
│
└── ui/
    └── terminal.py          # Interface terminal Rich (couleurs, panels, todo list)
```

---

## ⚙️ Installation

### 1. Prérequis

```bash
python3 --version   # >= 3.11
pip install -r requirements.txt
```

### 2. Compiler le solveur PoW (optionnel, mais recommandé pour la vitesse)

```bash
cc -O3 -shared -fPIC -o deepseek_hash.so deepseek_hash.c -lcrypto
```

> Si vous n'avez pas `cc`, l'agent utilise automatiquement le fallback Python.

---

## 🚀 Utilisation

### Mode interactif (REPL)

```bash
python main.py --email votre@email.com --password VotreMotDePasse
```

### Mode message unique (non-interactif)

```bash
python main.py --email EMAIL --password PASS --message "scan le réseau 192.168.1.0/24"
```

### Via variables d'environnement

```bash
export DEEPSEEK_EMAIL="votre@email.com"
export DEEPSEEK_PASSWORD="VotreMotDePasse"
python main.py
```

### Via fichier de configuration JSON

```bash
# config.json
{
  "email": "votre@email.com",
  "password": "VotreMotDePasse"
}

python main.py --config config.json
```

---

## 🛠️ Options de la ligne de commande

| Option | Défaut | Description |
|--------|--------|-------------|
| `--email` | env `DEEPSEEK_EMAIL` | Email du compte DeepSeek |
| `--password` | env `DEEPSEEK_PASSWORD` | Mot de passe DeepSeek |
| `--config` | — | Fichier JSON avec email/password |
| `--model` | `deepseek-v3` | Modèle à utiliser |
| `--max-rounds` | `20` | Rounds max par tâche |
| `--tor` | `false` | Utiliser Tor (socks5://127.0.0.1:9050) |
| `--proxy` | — | Proxy SOCKS5 personnalisé |
| `--no-color` | `false` | Désactiver les couleurs |
| `--message` | — | Commande unique (mode non-interactif) |

---

## 🤖 Modèles disponibles

| Modèle | Utilisation |
|--------|-------------|
| `deepseek-v3` | Tâches générales, scripting, recon (recommandé) |
| `deepseek-r1` | Raisonnement complexe, analyse de vulnérabilités |
| `deepseek-coder` | Génération et analyse de code |

```bash
# Changer de modèle au démarrage
python main.py --model deepseek-r1

# Changer de modèle en cours de session
>>> /model deepseek-coder
```

---

## 🔧 Outils disponibles

L'agent peut utiliser tous ces outils de manière autonome :

| Outil | Description |
|-------|-------------|
| `exec` | Exécution de commandes shell arbitraires |
| `nmap` | Scan réseau et détection de services |
| `gobuster` | Brute-force de répertoires et DNS |
| `nikto` | Scanner de vulnérabilités web |
| `sqlmap` | Détection et exploitation d'injections SQL |
| `subfinder` | Énumération de sous-domaines |
| `whatweb` | Détection de technologies web |
| `curl` | Requêtes HTTP/HTTPS |
| `dig` | Requêtes DNS |
| `whois` | Informations sur les domaines |
| `ping` | Test de connectivité |
| `read_file` | Lecture de fichiers |
| `write_file` | Création/écriture de fichiers |
| `edit_file` | Modification partielle de fichiers |

---

## 📋 Système Todo (Plan → Execute)

Pour les tâches complexes (multi-étapes), l'agent utilise un système **Plan → Todo → Execute** :

1. **Planning** : L'agent analyse la tâche et génère un plan en étapes
2. **Todo list** : Chaque étape est ajoutée comme un todo avec statut (○ pending / ✓ done)
3. **Exécution** : Chaque étape est exécutée indépendamment et marquée comme terminée

```
📋 PLAN:
  ○ [0] $ mkdir -p /tmp/projet
  ○ [1] write /tmp/projet/main.py
  ○ [2] $ python3 /tmp/projet/main.py
  ○ [3] $ ls -la /tmp/projet

  ▶  [1/4] $ mkdir -p /tmp/projet
  ✅ [1/4] done
  ▶  [2/4] write /tmp/projet/main.py
  ✅ [2/4] done
  ...
```

---

## 💬 Commandes en session interactive

| Commande | Description |
|----------|-------------|
| `/help` | Afficher l'aide |
| `/new` | Nouvelle session DeepSeek |
| `/clear` | Effacer l'historique de conversation |
| `/model <nom>` | Changer de modèle |
| `/tools` | Lister les outils disponibles |
| `/save <fichier>` | Sauvegarder la conversation en JSON |
| `/load <fichier>` | Charger une conversation sauvegardée |
| `/exit` | Quitter |

---

## 🌐 Utilisation avec Tor / Proxy

```bash
# Via Tor (doit être installé et actif)
python main.py --tor

# Via proxy SOCKS5 personnalisé
python main.py --proxy socks5://127.0.0.1:1080

# Installer Tor sur Debian/Ubuntu
sudo apt install tor && sudo systemctl start tor
```

---

## 📝 Exemples de tâches

```bash
# Scan réseau
>>> scan the network 192.168.1.0/24 and find open ports

# Recon web complet
>>> do a full recon on example.com: subdomains, ports, technologies, directories

# Injection SQL
>>> test example.com/login for SQL injection vulnerabilities

# Création de projet
>>> create a Python project with main.py, utils.py, run it and show output

# Analyse de fichier
>>> read /etc/passwd and find accounts with shell access
```

---

## 🔒 Avertissement légal

> Cet outil est destiné **uniquement** aux tests de sécurité **autorisés**.
> N'utilisez cet agent que sur des systèmes pour lesquels vous avez une autorisation explicite.
> L'utilisation non autorisée est illégale et contraire à l'éthique.

---

## 🏗️ Architecture interne

```
Utilisateur
    │
    ▼
main.py (CLI + REPL)
    │
    ├── DeepSeekClient (core/client.py)
    │     ├── Auth (email/password → token)
    │     ├── PoW Solver (C ou Python)
    │     └── HTTP session avec streaming
    │
    └── Agent (core/agent.py)
          ├── plan()         → Découpe la tâche en étapes
          ├── execute_step() → Exécute chaque étape (fast-path ou LLM)
          ├── execute_tool() → exec / read_file / write_file / edit_file
          └── todo_list      → Suivi de progression
```

---

## 📦 Dépendances

```
requests>=2.28.0   # HTTP client
rich>=13.0.0       # Terminal UI (couleurs, panels, tables)
```

> Pour le proxy Tor : `pip install requests[socks]`
