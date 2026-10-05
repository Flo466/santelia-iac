# Santélia — Annexe : journal des commandes exécutées

> Document rendable — reconstitution de la séquence complète de mise en œuvre de la brique haute disponibilité.
> Permet à un tiers de rejouer le montage et sert de matière première à l'écriture des rôles d'automatisation.
> 05/10/2026

---

## Préambule — Les quatre environnements d'exécution

Les commandes ne s'exécutent pas au même endroit. Cette distinction est essentielle : une erreur de contexte constitue la principale source d'échec du montage.

| Environnement | Accès | Rôle |
| --- | --- | --- |
| **Poste de travail** | direct | Mesures, surveillance, accès client |
| **Hôte physique** | réseau local ou distant | Contient les trois nœuds du cluster |
| **Nœuds du cluster** (`pve-a`, `pve-b`, `pve-c`) | rebond via l'hôte | Constituent le cluster |
| **Machine invitée** (machine de test) | réseau d'administration | Héberge le dispositif témoin |

---

## A.1 Vérifications préalables sur l'hôte physique

### A.1.1 Prérequis de virtualisation imbriquée

```
cat /sys/module/kvm_intel/parameters/nested
```

**Résultat attendu :** `Y`. Sans cette activation, un nœud démarre mais refuse de lancer ses propres machines virtuelles.

### A.1.2 Inventaire du stockage

```
pvesm status
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,TRAN
vgs && lvs
cat /etc/pve/storage.cfg
```

**Objet :** identifier les stockages disponibles, leur type, leur capacité libre, et vérifier qu'aucun disque n'est occupé par un autre projet.

### A.1.3 Inventaire mémoire et système

```
free -h
hostnamectl
pveversion
```

### A.1.4 Inventaire réseau

```
cat /etc/network/interfaces
bridge link
ip -4 -br addr
```

### A.1.5 État du filtrage réseau

```
pve-firewall status
iptables -S FORWARD
cat /proc/sys/net/ipv4/ip_forward
```

**Objet :** vérifier que le routage est actif et que les règles de transfert autorisent les communications nécessaires.

### A.1.6 Catalogue des modèles de conteneurs

```
pveam update
pveam available --section system | grep -iE "debian|ubuntu"
pveam list local
```

**Objet :** identifier les images disponibles pour les futurs conteneurs. `update` rafraîchit le catalogue, il ne télécharge rien.

### A.1.7 Vérification de l'unicité d'une adresse

```
ping -c1 <adresse-visee>
ip neigh | grep <adresse-visee>
```

**Résultat attendu :** perte de paquets à 100 %, aucune entrée de voisinage. L'adresse est libre.

> `arp` n'est plus disponible sur les distributions récentes. Utiliser `ip neigh`.

---

## A.2 Création et duplication des nœuds

### A.2.1 Création du premier nœud

```
qm create 310 \
  --name pve-a \
  --ostype l26 \
  --memory 4096 --balloon 0 \
  --sockets 1 --cores 2 --cpu host \
  --scsihw virtio-scsi-single \
  --scsi0 local-lvm:24,discard=on,iothread=1 \
  --ide2 local:iso/proxmox-ve_8.4-1.iso,media=cdrom \
  --boot 'order=scsi0;ide2' \
  --net0 virtio,bridge=vmbr0 \
  --net1 virtio,bridge=vmbr2 \
  --agent enabled=1 \
  --onboot 1
```

**Paramètres déterminants :**

| Paramètre | Rôle |
| --- | --- |
| `--cpu host` | **Indispensable.** Sans lui, le nœud ne peut pas virtualiser |
| `--balloon 0` | Désactive la gestion mémoire dynamique, erratique en imbrication |
| `--onboot 1` | Retour automatique après redémarrage de l'hôte |
| `discard=on` | Récupération des blocs libérés côté stockage |
| Deux interfaces | Une pour l'administration et le cluster, une pour le réseau de service |

> Les guillemets simples autour de `'order=scsi0;ide2'` sont obligatoires : sans eux, l'interpréteur de commandes coupe la ligne au point-virgule.

### A.2.2 Contrôle de la configuration

```
qm config 310
qm config 310 | grep -E "^(cpu|memory|balloon|cores|boot|onboot)"
```

**Objet :** vérifier la présence effective de `cpu: host`, `balloon: 0`, `onboot: 1` avant tout démarrage.

### A.2.3 Installation du système

Installation depuis l'image d'installation Proxmox, avec les choix suivants : système de fichiers **ZFS en disque unique**, plafond de cache mémoire à **512 Mio**, nom complet de machine, adresse statique et passerelle.

### A.2.4 Contrôles dans le nœud après installation

```
grep -c vmx /proc/cpuinfo
zpool status
pvesm status
cat /sys/module/zfs/parameters/zfs_arc_max
free -h
```

**Résultats attendus :**

| Commande | Attendu |
| --- | --- |
| `grep -c vmx` | Valeur non nulle — le nœud sait virtualiser |
| `zpool status` | Pool système en ligne |
| `pvesm status` | Stockages `local` et `local-zfs` actifs |
| `zfs_arc_max` | Valeur du plafond appliquée |

### A.2.5 Extinction et duplication

```
qm shutdown 310
qm clone 310 311 --name pve-b --full --storage local-lvm
qm clone 310 312 --name pve-c --full --storage local-lvm
qm list
```

**Objet :** créer deux clones indépendants. Le nœud source est éteint au préalable.

### A.2.6 Contrôle des adresses matérielles des clones

```
qm config 310 | grep ^net0
qm config 311 | grep ^net0
qm config 312 | grep ^net0
```

**Résultat attendu :** trois adresses matérielles distinctes. La duplication régénère normalement ces adresses, mais le contrôle est systématique.

---

## A.3 Correction d'identité des clones

> **Procédure à appliquer dans chaque clone, avant tout test de connexion.** Jamais sur le nœud source : l'opération interrompt l'accès distant.

### A.3.1 Séquence complète

```
hostnamectl set-hostname pve-b

rm -f /etc/ssh/ssh_host_*
ssh-keygen -A
ls -la /etc/ssh/ssh_host_*

truncate -s 0 /etc/machine-id
systemd-machine-id-setup
cat /etc/machine-id

systemctl restart ssh
reboot
```

**Point critique :** la commande de génération de clés **ne régénère jamais une clé existante**. Elle ne crée que les clés absentes et reste silencieuse lorsqu'il n'y a rien à faire. La suppression préalable est donc obligatoire.

### A.3.2 Contrôle de l'unicité

```
hostname
hostname -f
getent hosts pve-b
cat /etc/machine-id
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

**Objet :** les trois valeurs doivent être distinctes d'un nœud à l'autre. Le commentaire associé à la clé indique le nom de la machine qui l'a générée, ce qui révèle immédiatement un partage d'identité.

### A.3.3 Correction du fichier de résolution local

Le fichier doit associer la bonne adresse au nom complet correct, suivi du nom court :

```
192.168.1.152 pve-b.local pve-b
```

### A.3.4 Contrôle côté poste de travail

```
ssh-keygen -R <adresse>
ssh pve-b hostname
ssh -o BatchMode=yes pve-b hostname
```

**Objet :** la seconde commande réenregistre l'empreinte, la troisième doit répondre **sans mot de passe**, ce qui valide l'authentification par clé.

---

## A.4 Création et contrôle du cluster

### A.4.1 Création

```
pvecm create santelia
pvecm status
```

### A.4.2 Jonction des nœuds secondaires

```
pvecm add 192.168.1.151
```

À exécuter depuis chaque nœud à joindre. Demande le mot de passe du nœud initial, puis l'acceptation de son empreinte de clé.

### A.4.3 Contrôles du cluster

```
pvecm status
pvecm nodes
corosync-cfgtool -s
```

**Résultats attendus :**

| Élément | Attendu |
| --- | --- |
| Nœuds | 3 |
| Votes attendus | 3 |
| Majorité requise | 2 |
| État | Quorate |
| Anneaux de communication | Tous les liens connectés |

### A.4.4 Contrôle de la synchronisation horaire

```
timedatectl | grep -iE "synchronized|NTP"
```

**Objet :** la stabilité du quorum dépend directement de la synchronisation des horloges entre nœuds.

### A.4.5 Contrôle de l'espace des pools de réplication

```
for h in pve-a pve-b pve-c; do echo "=== $h"; ssh $h 'zpool list -o name,size,alloc,free'; done
```

**Objet :** vérifier que les pools portent **le même nom** sur les trois nœuds, condition technique de la réplication native.

### A.4.6 Relevé des fichiers de configuration du cluster

```
cat /etc/pve/corosync.conf
cat /etc/pve/replication.cfg
cat /etc/pve/ha/groups.cfg
```

---

## A.5 Préparation de la machine de test

### A.5.1 Récupération de l'image cloud

```
mkdir -p /root/iso && cd /root/iso
wget <url-de-l-image-cloud>
ls -lh
```

**Contrôle :** le fichier doit faire plusieurs centaines de mégaoctets. Une taille de quelques kilo-octets indique une page d'erreur.

### A.5.2 Création de la coquille

```
qm create 100 \
  --name vm-test-ha \
  --ostype l26 \
  --memory 1024 --balloon 0 --cores 1 \
  --scsihw virtio-scsi-single \
  --net0 virtio,bridge=vmbr0 \
  --agent enabled=1 \
  --onboot 1
```

### A.5.3 Import, raccordement et agrandissement du disque

```
qm importdisk 100 <fichier-image>.qcow2 local-zfs

qm set 100 --scsi0 local-zfs:vm-100-disk-0
qm resize 100 scsi0 8G
```

**Point critique :** l'agrandissement est obligatoire. Les images cloud sont volontairement minuscules, deux à trois gigaoctets, afin que la taille finale soit choisie au déploiement.

### A.5.4 Disque d'amorçage, ordre de démarrage et console série

```
qm set 100 --ide2 local-zfs:cloudinit
qm set 100 --boot order=scsi0
qm set 100 --serial0 socket --vga serial0
```

**Objet :** le disque secondaire transporte les instructions d'amorçage. La console série est nécessaire car les images cloud n'ont pas d'affichage graphique.

### A.5.5 Renseignement de la configuration de provisionnement

```
qm set 100 \
  --ciuser admin \
  --sshkeys /root/.ssh/authorized_keys \
  --ipconfig0 ip=192.168.1.160/24,gw=192.168.1.1 \
  --nameserver 192.168.1.1
```

### A.5.6 Contrôle avant démarrage

```
qm config 100
qm start 100
qm status 100
```

**Objet :** vérifier la présence du disque **avec sa taille finale**, du périphérique d'amorçage, de l'ordre de démarrage, de la console série et des paramètres de provisionnement.

### A.5.7 Contrôles après démarrage

Depuis le poste de travail, après un délai de 30 à 60 secondes :

```
ping -c3 192.168.1.160
ssh admin@192.168.1.160 hostname
ssh admin@192.168.1.160 'df -h /; cloud-init status; systemctl is-active qemu-guest-agent'
```

**Résultats attendus :** réponse réseau, connexion **sans mot de passe**, partition racine étendue à la taille demandée, provisionnement terminé.

### A.5.8 Correction de l'agent invité

```
sudo apt update && sudo apt install -y qemu-guest-agent nginx fcgiwrap
sudo systemctl enable --now qemu-guest-agent nginx fcgiwrap.socket
```

Contrôle depuis le nœud hébergeur :

```
qm agent 100 ping && echo "AGENT OK"
qm agent 100 get-osinfo
```

---

## A.6 Mise en service du dispositif témoin

### A.6.1 Script du témoin

```
sudo mkdir -p /usr/lib/cgi-bin
sudo chmod 755 /usr/lib/cgi-bin

sudo tee /usr/lib/cgi-bin/uptime.sh > /dev/null << 'EOF'
#!/bin/bash
echo "Content-Type: text/html"
echo ""
echo "<h1>vm-test-ha</h1>"
echo "<p>Boot: $(uptime -s)</p>"
echo "<p>Repondu le: $(date -u '+%Y-%m-%d %H:%M:%S UTC')</p>"
echo "<p>Uptime: $(uptime -p)</p>"
EOF

sudo chmod 755 /usr/lib/cgi-bin/uptime.sh
```

### A.6.2 Activation de la passerelle d'exécution

Bloc à insérer dans la section serveur de `/etc/nginx/sites-available/default` :

```
location /cgi-bin/ {
    gzip off;
    root /usr/lib/;
    fastcgi_pass unix:/var/run/fcgiwrap.socket;
    include /etc/nginx/fastcgi_params;
}
```

### A.6.3 Contrôle de la configuration et rechargement

```
sudo nginx -t && sudo systemctl reload nginx
curl -s http://192.168.1.160/cgi-bin/uptime.sh
```

**Objet :** la validation de configuration précède toujours le rechargement. Un rechargement sur une configuration invalide fait tomber le service.

### A.6.4 Relevé de l'état de référence

```
curl -s http://192.168.1.160/cgi-bin/uptime.sh
ssh admin@192.168.1.160 'uptime -s'
```

**Objet :** consigner l'horodatage de démarrage **avant** toute manipulation, afin de disposer d'un point de comparaison.

---

## A.7 Réplication et gestion de la disponibilité

### A.7.1 Création du job de réplication

```
pvesr create-local-job 100-0 pve-b --schedule '*/15'
pvesr list
pvesr status
```

**Point d'attention :** l'identifiant du job est composé du numéro de machine et d'un index, sous la forme `<vmid>-<index>`. Un identifiant simple est refusé.

### A.7.2 Synchronisation immédiate

```
pvesr run --id 100-0
```

**Objet :** ne pas attendre la prochaine échéance. À exécuter systématiquement **avant toute coupure volontaire**.

### A.7.3 Contrôle de la présence du volume sur le nœud cible

```
ssh pve-b 'zfs list | grep vm-100'
```

**Résultat attendu :** le volume de la machine est présent sur le nœud secondaire, preuve que la réplication est effective.

### A.7.4 Gestion du job

```
pvesr disable 100-0
pvesr enable 100-0
pvesr delete 100-0
```

> La désactivation du job **élargit** la fenêtre de perte de données. Elle est à éviter avant une coupure volontaire.

### A.7.5 Déclaration en ressource à haute disponibilité

```
ha-manager add vm:100
ha-manager status

ha-manager groupadd santelia-ha --nodes "pve-a:2,pve-b:1"
cat /etc/pve/ha/groups.cfg

ha-manager set vm:100 --group santelia-ha
ha-manager config
```

**Objet :** le groupe restreint les nœuds d'accueil possibles et définit leur ordre de préférence. Sans groupe, la ressource peut redémarrer sur n'importe quel nœud, y compris un nœud qui ne dispose pas du volume répliqué.

### A.7.6 Commandes de gestion de la ressource

```
ha-manager set vm:100 --state started
ha-manager set vm:100 --state stopped
ha-manager set vm:100 --state disabled
ha-manager set vm:100 --state ignored

ha-manager migrate vm:100 pve-a
```

**Règle d'exploitation :** une seule opération à la fois. Tant que la ressource présente un état transitoire, aucune intervention ne doit être engagée.

---

## A.8 Simulation de panne et mesure

### A.8.1 Surveillance en tâche de fond, depuis le poste de travail

```
nohup bash -c '
  echo "SURVEILLANCE $(date +%T)"
  d=""
  while true; do
    if curl -s --max-time 2 http://192.168.1.160 >/dev/null 2>&1; then
      if [ -n "$d" ]; then
        echo "RETOUR DU SERVICE : $(date +%T)"
        echo "DUREE INTERRUPTION : $(( $(date +%s) - d )) secondes"
        d=""
      fi
    else
      if [ -z "$d" ]; then echo "COUPURE : $(date +%T)"; d=$(date +%s); fi
    fi
    sleep 1
  done
' > /tmp/test-ha.log 2>&1 &
```

**Objet :** détecter la transition indisponibilité / rétablissement et calculer la durée. Lancée **avant** la coupure, elle rend la mesure indépendante de toute observation manuelle.

### A.8.2 Coupure du nœud hébergeur

Depuis l'hôte physique :

```
qm stop 310
```

**Objet :** provoquer une indisponibilité brutale et non un arrêt propre, conformément au test de recette attendu : « panne contrôlée sur une VM » [1].

### A.8.3 Relevé du résultat

```
cat /tmp/test-ha.log
```

### A.8.4 Preuves de la reprise

```
curl -s http://192.168.1.160/cgi-bin/uptime.sh
ssh pve-b 'qm list | grep 100'
ssh pve-b 'ha-manager status'
ssh pve-b 'journalctl -u pve-ha-crm --since "15 min ago" --no-pager'
```

**Objet :** démontrer le redémarrage par un horodatage de démarrage distinct, et relever la chronologie complète de la reprise côté gestionnaire.

### A.8.5 Restitution de la ressource

À effectuer **après stabilisation complète** de l'état :

```
qm start 310
ssh pve-a 'pvecm status; ha-manager status'
```

**Point critique :** le retour du nœud avant la fin de la séquence de reprise place la ressource en état de sécurisation et bloque le redémarrage.

### A.8.6 Remise en service de la réplication

```
pvesr list
pvesr enable 100-0
pvesr run --id 100-0
```

---

## A.9 Récapitulatif des fichiers de configuration concernés

| Fichier | Emplacement | Rôle |
| --- | --- | --- |
| Configuration réseau | `/etc/network/interfaces` | Interfaces et ponts |
| Résolution locale | `/etc/hosts` | Nom court et nom complet de la machine |
| Configuration du cluster | `/etc/pve/corosync.conf` | Membres et transport |
| Groupes de disponibilité | `/etc/pve/ha/groups.cfg` | Nœuds d'accueil et priorités |
| Ressources gérées | `/etc/pve/ha/resources.cfg` | Machines et conteneurs sous surveillance |
| Jobs de réplication | `/etc/pve/replication.cfg` | Sources, cibles et planification |
| Configuration de la machine | `/etc/pve/qemu-server/<vmid>.conf` | Paramètres de la machine virtuelle |

---

## A.10 Portée de cette annexe

Ces commandes ont été exécutées manuellement, une par une, lors de la mise au point du montage.

**Elles constituent la cible de la phase d'automatisation** : le cahier des charges prévoit d'« automatiser et standardiser les configurations des serveurs et des applications », avec protection des secrets [1]. Chaque séquence décrite ici correspond à un futur rôle d'automatisation, rejouable et documenté.

> Sept points de vigilance relevés lors de la mise au point, répartis entre la configuration du cluster (volume d'amorçage non répliqué, fichier de résolution local des clones, agents invités) et l'exploitation de la haute disponibilité (fenêtre de réplication, séquencement des interventions). Ils sont détaillés dans le document de recette associé.

---

_Source : cahier des charges Santélia, Bloc 2 AIS — Groupe 2._
