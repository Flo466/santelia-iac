# Santélia — Supervision : déploiement de la plateforme

> Brique 03 — Zabbix en conteneurs. Plateforme déployée hors de l'infrastructure supervisée.
> 27/11/2026

---

## 1. Objet

Mettre en place une supervision centralisée du parc Santélia : savoir qu'un service est tombé avant que l'utilisateur ne le signale.

Répond à l'exigence n° 4 du cahier des charges, priorité **Should** : supervision centralisée des postes avec remontée d'alerte.

---

## 2. Où la plateforme est installée, et pourquoi

| Emplacement possible | Écarté parce que |
| --- | --- |
| Sur l'hôte Proxmox | Il supervise le cluster qu'il héberge : si l'hôte tombe, la supervision tombe avec lui |
| Dans un nœud du cluster | Même défaut, à l'échelle du nœud |
| **Sur `srv-debian`, machine physique distincte** | **Retenu** |

**Le principe.** Un serveur de supervision installé sur la machine qu'il surveille ne peut pas signaler la panne de cette machine. La plateforme vit donc sur un châssis distinct de celui qui porte le cluster.

**Ce que ça permet de démontrer.** Couper un nœud Proxmox et voir l'alerte partir depuis une machine qui, elle, n'a pas bougé.

---

## 3. La machine d'accueil

| Élément | Valeur |
| --- | --- |
| Machine | `srv-debian`, Dell OptiPlex 7040, Debian 13 |
| Adresse | 192.168.1.125 |
| Mémoire | **15 Gio** dont 8,8 disponibles avant déploiement |
| Disque de données | `/mnt/data`, 220 Go dont **198 libres** |
| Disque de sauvegarde | `/mnt/backup` — **non utilisé**, réservé à la copie de la brique 02 |
| Conteneurs déjà en service | 12, dont Nextcloud, Immich, Vaultwarden, Open WebUI, Portainer, Watchtower |

La plateforme de conteneurs existe déjà, elle héberge les services du quotidien. La supervision s'y ajoute comme une pile de plus, isolée par son propre réseau.

Le disque de sauvegarde n'est pas touché : il porte la copie secondaire de la brique 02.

---

## 4. Pourquoi des conteneurs

| Approche | Ce qu'elle impose |
| --- | --- |
| Paquets natifs | Installation système, dépendances PHP et PostgreSQL gérées à la main, mise à jour qui touche l'hôte |
| **Conteneurs** | **Environnement isolé, reproductible, supprimable sans trace** |

Trois raisons concrètes de choisir les conteneurs sur cette machine :

**La cohérence.** Douze services tournent déjà en conteneurs. Ajouter une pile de paquets natifs créerait deux régimes d'exploitation à maintenir.

**L'isolation.** La pile Zabbix dispose de son propre réseau Docker. Sa base n'est joignable que par le serveur et l'interface, jamais depuis l'hôte.

**La réversibilité.** Un `docker compose down -v` efface la pile entièrement. Sur une maquette de validation, c'est ce qui permet de rejouer un déploiement à zéro sans réinstaller une machine.

---

## 5. La composition de la pile

```
stacks/zabbix/
├── docker-compose.yml
├── .env.example
└── README.md
```

### Le fichier de composition

```yaml
services:
  zabbix-db:
    image: postgres:16-alpine
    container_name: zabbix-db
    restart: unless-stopped
    environment:
      POSTGRES_USER: zabbix
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: zabbix
      TZ: Europe/Paris
    volumes:
      - zabbix-db-data:/var/lib/postgresql/data
    networks:
      - zabbix-net
    labels:
      com.centurylinklabs.watchtower.enable: "false"

  zabbix-server:
    image: zabbix/zabbix-server-pgsql:alpine-7.0-latest
    container_name: zabbix-server
    restart: unless-stopped
    environment:
      DB_SERVER_HOST: zabbix-db
      POSTGRES_USER: zabbix
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: zabbix
      TZ: Europe/Paris
    ports:
      - "10051:10051"
    depends_on:
      - zabbix-db
    networks:
      - zabbix-net
    labels:
      com.centurylinklabs.watchtower.enable: "false"

  zabbix-web:
    image: zabbix/zabbix-web-nginx-pgsql:alpine-7.0-latest
    container_name: zabbix-web
    restart: unless-stopped
    environment:
      ZBX_SERVER_HOST: zabbix-server
      DB_SERVER_HOST: zabbix-db
      POSTGRES_USER: zabbix
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: zabbix
      PHP_TZ: Europe/Paris
      ZBX_SERVER_NAME: Santelia - supervision
    ports:
      - "8087:8080"
    depends_on:
      - zabbix-server
    networks:
      - zabbix-net
    labels:
      com.centurylinklabs.watchtower.enable: "false"

volumes:
  zabbix-db-data:

networks:
  zabbix-net:
```

### Lecture des directives

| Directive | Rôle |
| --- | --- |
| `image` | Version figée ou flottante. `alpine-7.0-latest` suit les correctifs de la branche 7.0 |
| `container_name` | Nom fixe plutôt que généré, pour retrouver les conteneurs dans `docker ps` |
| `restart: unless-stopped` | Relance après redémarrage de la machine, sauf arrêt volontaire |
| `ports` | `8087:8080` signifie port de l'hôte vers port du conteneur |
| `volumes` | `zabbix-db-data:/var/lib/postgresql/data` : volume nommé monté sur le répertoire de la base |
| `networks` | Tous les services partagent `zabbix-net` et se joignent par leur nom |
| `depends_on` | Ordre de démarrage, pas attente de disponibilité |
| `labels` | Marquage des conteneurs, voir point de vigilance n° 4 |

### Le rôle des trois services

| Service | Image | Rôle |
| --- | --- | --- |
| `zabbix-db` | `postgres:16-alpine` | Stocke l'inventaire, l'historique et les déclencheurs |
| `zabbix-server` | `zabbix/zabbix-server-pgsql:alpine-7.0-latest` | Collecte, évalue, déclenche |
| `zabbix-web` | `zabbix/zabbix-web-nginx-pgsql:alpine-7.0-latest` | Interface d'administration |

### Le fichier `.env`

```
DB_PASSWORD=<mot de passe>
```

Le fichier `.env` vit à côté du compose, sur la machine, et n'est jamais versionné. `docker compose` le lit automatiquement au lancement et substitue `${DB_PASSWORD}` dans les trois services qui en ont besoin.

| Fichier | Versionné | Contenu |
| --- | --- | --- |
| `docker-compose.yml` | Oui | Structure, images, `${DB_PASSWORD}` |
| `.env.example` | Oui | Le nom de la variable, sans la valeur |
| `.env` | **Non** | La valeur réelle |

**Pourquoi cette séparation.** Le fichier de composition part sur un dépôt public. Le secret reste sur la machine. `.env` est déclaré dans le `.gitignore` du projet, et un contrôle le confirme avant tout commit :

```
git status --short
```

Aucun `.env` ne doit apparaître dans la sortie.

**Si le fichier manque**, `${DB_PASSWORD}` devient une chaîne vide, PostgreSQL refuse de démarrer et `zabbix-db` boucle en redémarrage. C'est le premier endroit à regarder quand la pile ne monte pas.

---

## 6. Choix techniques

| Choix | Raison |
| --- | --- |
| **Volume Docker nommé** pour la base | Un montage de répertoire impose la correspondance des identifiants système, source classique du refus d'accès au premier démarrage |
| **Réseau Docker dédié** | Les conteneurs se joignent par leur nom, sans exposer la base sur l'hôte |
| **Fuseau Europe/Paris** sur les trois services | Les alertes et les graphiques sont à l'heure locale, pas en UTC |
| **Port 8087** en façade | 8080 est déjà occupé deux fois sur la machine, 8007 est pris par la copie de sauvegarde |
| **Port 10051** exposé | C'est celui qu'écouteront les agents |
| **Mot de passe dans un fichier `.env`** | Le fichier de composition est versionné sur un dépôt public, la base ne doit pas y figurer |
| **`depends_on` plutôt qu'une attente active** | Suffisant ici, mais voir le point de vigilance n° 3 |

### Le cas du mot de passe

Le fichier `.env` vit à côté du compose, sur la machine, et n'est jamais versionné. Le compose contient `${DB_PASSWORD}`, que Docker Compose substitue au lancement en lisant ce fichier.

Sans `.env`, la variable devient vide et PostgreSQL refuse de démarrer.

---

## 7. Déploiement

Le fichier de composition vit dans le dépôt du projet. La machine ne fait que l'exécuter : le compose est une source, pas un état local.

| Étape | Opération |
| --- | --- |
| 1 | Récupération du fichier de composition et de son modèle de variables |
| 2 | Copie du modèle en `.env`, renseignement du mot de passe, restriction des droits |
| 3 | Démarrage de la pile |
| 4 | Attente de l'initialisation de la base |

**Images récupérées en 9,2 secondes.** 28 couches au total, la plus lente en 7,5 s.

**Conteneurs démarrés dans la seconde** : la base en 1,2 s, puis le serveur et l'interface.

---

## 8. Vérifications

| Contrôle | Résultat obtenu |
| --- | --- |
| Trois conteneurs en service | Oui |
| Base prête | `database system is ready to accept connections` |
| Interface accessible | Code de réponse valide sur le port 8087 |
| Connexion | `Admin`, mot de passe par défaut **changé immédiatement** |
| Serveur à l'écoute des agents | Port 10051 exposé |

Le serveur redémarre une à deux fois au premier lancement, le temps que la base initialise son schéma. Après stabilisation, les trois composants restent en service.

---

## 9. Points de vigilance

| # | Point | Mesure appliquée |
| --- | --- | --- |
| 1 | Port 8080 déjà occupé deux fois sur la machine d'accueil | Interface déplacée sur 8087, vérifié libre avant déploiement |
| 2 | Base de données sur un montage de répertoire | Volume Docker nommé retenu |
| 3 | `depends_on` n'attend pas que la base soit prête, seulement qu'elle soit démarrée | Le serveur redémarre de lui-même jusqu'à ce que la base réponde |
| 4 | Le service de mise à jour automatique ignore le marquage posé sur les conteneurs | Réserve assumée, voir ci-dessous |
| 5 | L'hôte « Zabbix server » créé automatiquement ne peut pas être supervisé | Aucun agent installé, contrôles désactivés automatiquement |
| 6 | L'image allégée n'embarque pas tous les modules d'interrogation | Items marqués « non supportés » : bruit dans les journaux, sans conséquence |

**N° 3 — l'attente de la base.** `depends_on` garantit l'ordre de démarrage, pas la disponibilité. Le serveur tente de se connecter, échoue, redémarre, et finit par trouver la base. C'est visible dans les journaux et sans conséquence, mais ce n'est pas une attente propre.

**N° 4 — mise à jour automatique.** La machine exécute un service qui met à jour les conteneurs chaque nuit à 4 h. Il ne lit pas le marquage posé sur les trois conteneurs, qui reste donc sans effet. Une mise à jour de la pile peut survenir sans intervention, avec un risque de migration de schéma sur la base.

**N° 5 — l'angle mort du superviseur.** Zabbix se crée automatiquement un hôte à son propre nom et tente de l'interroger par agent. Aucun agent n'étant installé, il échoue, réessaie, puis désactive temporairement les contrôles.

> Un serveur de supervision sans agent sur lui-même ne surveille pas son propre socle. Deux réponses possibles : désactiver l'hôte, ou déployer un agent. La seconde seule supprime l'angle mort.

**N° 6 — image allégée.** Les modules Java, SNMP, IPMI, VMware et générateur de rapports ne sont pas embarqués. Le serveur crée leurs indicateurs et les marque comme non supportés.

---

## Annexe A — Relevés bruts

### A.1 État de la machine avant déploiement

```
              total       utilisé      libre     partagé tamp/cache   disponible
Mem:            15Gi       6,7Gi       1,3Gi       193Mi       8,0Gi       8,8Gi
Échange:       7,8Gi        90Mi       7,7Gi

/dev/sdc1          220G     11G  198G   5% /mnt/data
/dev/sdb1          457G     22G  413G   5% /mnt/backup

LISTEN 0  4096  127.0.0.1:8080        0.0.0.0:*
LISTEN 0  4096  100.108.182.100:8080  0.0.0.0:*
LISTEN 0  1024  *:8007                 *:*

Docker version 26.1.5+dfsg1
Docker Compose version 2.26.1-4
```

8080 est occupé deux fois, 8007 l'est aussi. 8087 et 10051 sont libres.

### A.2 Déploiement

```
[+] Running 28/28
zabbix-server Pulled     4.2s
zabbix-web Pulled        7.1s
zabbix-db Pulled         9.2s

[+] Running 5/5
Network zabbix_zabbix-net       Created   0.1s
Volume "zabbix_zabbix-db-data"  Created   0.0s
Container zabbix-db             Started   1.2s
Container zabbix-server         Started   0.1s
Container zabbix-web            Started   0.0s
```

### A.3 État des conteneurs

```
NAME            IMAGE                                           STATUS
zabbix-db       postgres:16-alpine                              Up
zabbix-server   zabbix/zabbix-server-pgsql:alpine-7.0-latest    Up   0.0.0.0:10051->10051/tcp
zabbix-web      zabbix/zabbix-web-nginx-pgsql:alpine-7.0-latest Up   0.0.0.0:8087->8080/tcp
```

### A.4 Journaux de la base

```
2026-11-27 18:25:06.580 CET [1] LOG:  listening on IPv4 address "0.0.0.0", port 5432
2026-11-27 18:25:06.585 CET [1] LOG:  listening on Unix socket "/run/postgresql/.s.PGSQL.5432"
2026-11-27 18:25:06.602 CET [1] LOG:  database system is ready to accept connections
```

### A.5 Journaux du serveur — messages attendus

```
item "Zabbix server:zabbix[process,java poller,avg,busy]" became not supported:
No "java poller" processes started.

Zabbix agent item "agent.ping" on host "Zabbix server" failed: another network error
temporarily disabling Zabbix agent checks on host "Zabbix server": interface unavailable
```

Première ligne, module absent de l'image allégée. Seconde ligne, aucun agent installé sur le serveur lui-même.

---

*Documentation technique — plateforme déployée, hôtes à raccorder.*
