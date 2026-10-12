# Santélia — Journal des commandes : sauvegarde

> Brique 02 — séquence complète de mise en œuvre, par environnement d'exécution.
> Mise à jour : 12/10/2026

---

## Préambule — Cinq environnements, cinq périmètres

Les commandes ne s'exécutent pas au même endroit, et les confondre est la principale source
d'erreur sur ce montage.

| Environnement | Rôle |
| --- | --- |
| **Poste de travail** | Mesures, accès client, tunnels |
| **Hôte physique** | Porte le cluster et le serveur de sauvegarde primaire |
| **Cluster** | Héberge les machines applicatives à sauvegarder |
| **Serveur de sauvegarde primaire** | Stocke les sauvegardes |
| **Serveur de sauvegarde secondaire** | Porte la copie, hors du support primaire |

Deux conséquences pratiques en découlent, et elles ont chacune provoqué une erreur en séance.

**Un stockage déclaré sur l'hôte n'est pas visible depuis le cluster**, et inversement. C'est ce
qui a fait échouer la première sauvegarde, traité au point de vigilance n° 3 du document de
synthèse.

**La commande d'administration du serveur de sauvegarde n'est pas dans le chemin d'exécution
d'un utilisateur ordinaire.** Elle réside dans le répertoire des commandes réservées aux comptes
privilégiés. Sans élévation, le shell répond simplement que la commande est introuvable. Toutes
les commandes de cette famille se lancent donc avec élévation.

---

## A.1 Récupération de l'image d'installation — sur l'hôte

```
cd /var/lib/vz/template/iso

wget --no-check-certificate https://download.proxmox.com/iso/proxmox-backup-server_4.2-1.iso

sha256sum proxmox-backup-server_4.2-1.iso
```

**Contrôle :** comparer l'empreinte obtenue à celle publiée par l'éditeur. La vérification du
certificat ayant dû être désactivée, ce contrôle devient obligatoire.

---

## A.2 Création de la machine — sur l'hôte

```
qm create 320 \
  --name pbs01 \
  --ostype l26 \
  --memory 2048 --balloon 0 \
  --sockets 1 --cores 2 --cpu host \
  --scsihw virtio-scsi-single \
  --scsi0 local-lvm:20,discard=on,iothread=1 \
  --ide2 local:iso/proxmox-backup-server_4.2-1.iso,media=cdrom \
  --boot 'order=scsi0;ide2' \
  --net0 virtio,bridge=vmbr0 \
  --agent enabled=1 \
  --onboot 1
```

**Ajout du disque de données**, après l'installation :

```
qm set 320 --scsi1 local-lvm:40,discard=on,iothread=1
qm config 320 | grep scsi
```

**Contrôle de l'adresse réseau** avant installation :

```
ping -c2 <adresse-cible>
```

L'absence de réponse au format « destination injoignable » confirme que l'adresse est libre.

---

## A.3 Protection du stockage — sur l'hôte

**Constat initial :**

```
grep -rn "thin_pool_autoextend" /etc/lvm/

lvmconfig --type current activation/thin_pool_autoextend_threshold
lvmconfig --type default activation/thin_pool_autoextend_threshold
lvmconfig --type default activation/thin_pool_autoextend_percent
```

Aucune valeur n'est définie dans la configuration courante, les valeurs par défaut sont donc
inactives : le seuil effectif est de 100 %, l'extension automatique ne se déclenche jamais.

**Correction appliquée :**

```
grep -n "^activation {" /etc/lvm/lvm.conf
nano +<numero> /etc/lvm/lvm.conf
```

Section `activation`, ajouter le seuil et le pourcentage calibré.

**Application et contrôle :**

```
systemctl restart lvm2-monitor
pgrep -a dmeventd
lvmconfig --type current activation/thin_pool_autoextend_threshold

lvs <pool> -o lv_name,lv_size,data_percent,metadata_percent
vgs
```

Le démon de surveillance n'est **pas** déclaré comme service indépendant sur cette version : son
contrôle s'effectue par recherche de processus.

---

## A.4 Accès à l'interface par tunnel SSH — sur le poste de travail

**Configuration retenue :**

```
Host <alias-hote>
    HostName <hote-physique>
    User root
    IdentityFile ~/.ssh/id_ed25519
    LocalForward 8007 <adresse-pbs>:8007
    ControlMaster auto
    ControlPath ~/.ssh/cm-%r@%h
    ControlPersist 12h
```

**Contrôles :**

```
ssh -G <alias-hote> | grep -E "^(hostname|user|localforward|control)"

ssh -Nf <alias-hote>
ssh -O check <alias-hote>
ss -tlnp | grep 8007
```

L'écoute doit se faire **exclusivement sur l'adresse de bouclage**, ce qui confirme que le port
de l'interface d'administration n'est jamais exposé sur le réseau.

---

## A.5 Entrepôt de données — sur le serveur de sauvegarde

```
proxmox-backup-manager datastore list
proxmox-backup-manager cert info | grep -i fingerprint
```

**Relevé de l'empreinte du certificat** — elle servira à authentifier le serveur lors du
raccordement.

**Préparation du stockage**, depuis l'interface : onglet `Stockage et disques`, puis création
d'un répertoire sur le disque de données.

**Contrôle :**

```
df -h | grep datastore
lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT
```

Le répertoire est référencé **par identifiant unique** et non par nom de disque, ce qui rend le
montage stable dans le temps.

---

## A.6 Compte de service — sur le serveur de sauvegarde

```
proxmox-backup-manager user list
proxmox-backup-manager acl list
```

Le compte doit apparaître au format `<utilisateur>@<royaume>`, sans doublon de royaume. Les
permissions portent sur le seul entrepôt concerné, avec un rôle d'écriture et un rôle de lecture.
Le principe appliqué est le moindre privilège.

---

## A.7 Raccordement du cluster — sur un nœud du cluster

```
pvesm status
pvesm list <stockage-pbs>
```

L'état « actif » du stockage valide simultanément quatre éléments : connectivité réseau,
authentification du compte, adéquation des permissions et conformité de l'empreinte du certificat.

---

## A.8 Sauvegarde

```
vzdump <vmid> --storage <stockage-pbs> --mode snapshot --compress zstd
```

Le mode instantané sauvegarde sans interrompre le service. Le journal doit mentionner l'appel à
l'**agent invité** pour geler puis libérer le système de fichiers : c'est ce qui garantit une
sauvegarde cohérente applicative.

```
pvesm list <stockage-pbs>
```

---

## A.9 Restauration

**Vers un identifiant de machine distinct**, afin de préserver l'originale :

```
qmrestore <stockage-pbs>:backup/vm/<vmid>/<horodatage> <vmid-cible> --storage <stockage-zfs>
```

**Contrôles après restauration :**

```
qm config <vmid-cible>
qm list
```

**Test fonctionnel :**

```
qm agent <vmid-cible> network-get-interfaces
ping -c2 <adresse-cible>
curl -s http://<adresse-cible>/<chemin-temoin>
```

**Attention :** la copie restaurée reprend l'identité réseau de l'originale, adresse matérielle
comprise. Le contrôle des interfaces le confirme. Toute mise en service simultanée exige une
renumérotation.

**Arrêt d'une ressource gérée en haute disponibilité :** la commande d'arrêt directe est
arbitrée par le gestionnaire, qui relance la machine. L'arrêt effectif passe par le gestionnaire.

---

## A.10 Installation du serveur de sauvegarde secondaire — sur une machine physique distincte

Le second serveur est le point qui rend la stratégie 3-2-1 réelle. Tant qu'il n'existe qu'un seul
serveur de sauvegarde, et qu'il vit sur la machine qu'il protège, la sauvegarde disparaît avec la
donnée.

**Installation en paquet natif**, sans hyperviseur : la machine est dédiée, elle n'a pas à
héberger d'autres charges.

```
apt update
apt install proxmox-backup-server
```

**Choix demandé pendant l'installation.** L'agent de messagerie intégré demande son type de
configuration. Retenir « **système local uniquement** ».

| Élément | Valeur retenue |
| --- | --- |
| Type de configuration de messagerie | Système local uniquement |
| Nom de messagerie système | `<nom-complet-de-la-machine>.local` |

Le serveur n'a aucun besoin d'émettre du courrier vers l'extérieur : il n'en produit que pour ses
propres notifications, qui restent consultables localement. Choisir une configuration ouverte au
réseau aurait conduit l'agent à tenter des remises vers des serveurs distants, à se faire
refuser, et à remplir le journal d'erreurs sans aucun bénéfice.

**Contrôles après installation :**

```
systemctl status proxmox-backup-proxy --no-pager | head -5
ss -tlnp | grep 8007
ip -br addr
```

| Contrôle | Valeur attendue | Objet |
| --- | --- | --- |
| Service | actif | L'interface répond |
| Port **8007** | en écoute | L'interface est joignable |
| Adresse principale | **inchangée** | La configuration réseau n'a pas été altérée |

**Le troisième contrôle est le plus important des trois.** L'installation installe un nouveau jeu
d'outils réseau, susceptible de reprendre la gestion des interfaces et de casser la configuration
existante. C'est le risque identifié au point de vigilance n° 5 du document de synthèse. L'adresse
inchangée confirme que la protection appliquée a tenu, et que la machine reste joignable.

---

## A.11 Entrepôt de la copie — sur le serveur secondaire

L'entrepôt de la copie est posé dans un sous-répertoire, jamais à la racine : il cohabite sur le
même volume avec un dépôt de sauvegarde de fichiers déjà en exploitation, et les deux ne doivent
pas se mélanger.

**Préparation du répertoire :**

```
id backup
sudo mkdir -p /mnt/backup/pbs-datastore
sudo chown backup:backup /mnt/backup/pbs-datastore
sudo chmod 0750 /mnt/backup/pbs-datastore
ls -ld /mnt/backup/pbs-datastore
```

Relevé :

```
drwxr-x--- 2 backup backup 4096  /mnt/backup/pbs-datastore
```

**Lecture :** le propriétaire est le compte de service créé par l'installation, et les droits sont
restreints au propriétaire. Ces deux points sont **obligatoires** : un entrepôt qui n'appartient
pas au compte de service est refusé à la création.

**Création de l'entrepôt :**

```
sudo proxmox-backup-manager datastore create <entrepot-copie> /mnt/backup/pbs-datastore
sudo proxmox-backup-manager datastore list
```

Relevé :

```
TASK OK
│ santelia-copie │ /mnt/backup/pbs-datastore │
```

La création affiche une progression d'amorçage de la structure de blocs, puis se termine par
`TASK OK`. L'entrepôt est dédupliqué par blocs, comme celui du serveur primaire.

---

## A.12 Comptes de service de la synchronisation — deux comptes, deux rôles

La copie mobilise **deux comptes distincts**, un par serveur, et aucun des deux ne dispose d'un
droit d'administration.

**Sur le serveur secondaire — droit d'écriture sur l'entrepôt copié :**

```
sudo proxmox-backup-manager user create <compte-sync>@pbs --password '<mot-de-passe>'
sudo proxmox-backup-manager acl update /datastore/<entrepot-copie> DatastoreBackup --auth-id <compte-sync>@pbs
sudo proxmox-backup-manager user list
sudo proxmox-backup-manager acl list
```

Relevés :

```
│ pbs-sync@pbs │      1 │  never │
```

```
│ pbs-sync@pbs │ /datastore/santelia-copie │         1 │ DatastoreBackup │
```

**Sur le serveur primaire — droit de lecture seule sur l'entrepôt source :**

```
proxmox-backup-manager user create <compte-lecture>@pbs --password '<mot-de-passe>'
proxmox-backup-manager acl update /datastore/<entrepot-primaire> DatastoreReader --auth-id <compte-lecture>@pbs
proxmox-backup-manager user list
proxmox-backup-manager acl list
```

Relevés :

```
│ pbs-reader@pbs │ /datastore/datastore-santelia │         1 │ DatastoreReader │
│ pve-backup@pbs │ /datastore/datastore-santelia │         1 │ DatastoreBackup │
│ pve-backup@pbs │ /datastore/datastore-santelia │         1 │ DatastoreReader │
```

**Lecture du partage des rôles :**

| Compte | Serveur | Rôle | Usage |
| --- | --- | --- | --- |
| `pve-backup@pbs` | Primaire | écriture et lecture | Le cluster qui dépose ses sauvegardes |
| `pbs-reader@pbs` | Primaire | **lecture seule** | Le serveur secondaire qui tire la copie |
| `pbs-sync@pbs` | Secondaire | écriture | Le compte local d'écriture de la copie |

Le compte de lecture ne porte **aucun** rôle d'écriture. C'est le moindre privilège appliqué : la
synchronisation est une opération de lecture par nature, elle n'a aucune raison de pouvoir écrire
chez la source.

**Contrôle de forme :** l'identifiant apparaît au format `<utilisateur>@<royaume>`, avec un seul
royaume. Un royaume en double rend le compte inutilisable, erreur relevée au point de vigilance
n° 2 du document de synthèse.

---

## A.13 Empreinte du certificat et déclaration du dépôt distant

**Relevé de l'empreinte, sur le serveur primaire :**

```
proxmox-backup-manager cert info | grep -i fingerprint
```

```
Fingerprint (sha256): 78:05:ce:aa:b3:32:56:40:9b:27:8c:0f:12:78:cd:2f:e9:1a:39:71:96:d2:
                     10:04:dd:f3:00:ac:e2:d4:0f:26
```

**Déclaration du dépôt distant, sur le serveur secondaire :**

```
sudo proxmox-backup-manager remote create <nom-remote> \
  --host <adresse-primaire> \
  --auth-id <compte-lecture>@pbs \
  --password '<mot-de-passe>' \
  --fingerprint <empreinte-sha256>
```

**Contrôle :**

```
sudo proxmox-backup-manager remote list
sudo proxmox-backup-manager remote show <nom-remote>
```

Relevé :

```
│ name        │ pbs01
│ auth-id     │ pbs-reader@pbs
│ host        │ 192.168.1.161
│ fingerprint │ 78:05:ce:aa:b3:32:56:40:9b:27:8c:0f:12:78:cd:2f:e9:1a:39:71:96:d2:10:04:…
```

**Point de méthode.** L'empreinte se passe **sans guillemets** : elle ne contient que des
deux-points et des caractères hexadécimaux, rien que le shell puisse interpréter. Le mot de passe,
à l'inverse, se passe **entre guillemets simples** : sans eux, les caractères spéciaux qu'il
contient sont interprétés par le shell et la commande part en arrière-plan.

**Pourquoi cette empreinte compte.** Sans elle, le serveur secondaire accepterait le certificat
que lui présenterait n'importe quel serveur répondant à cette adresse. Une interception réseau
suffirait à rediriger la copie vers un serveur tiers, qui l'accepterait sans rien signaler.
C'est le point de contrôle de confiance décrit au point de vigilance n° 8 du document de synthèse.

---

## A.14 Tâche de synchronisation — sur le serveur secondaire

**Création de la tâche :**

```
sudo proxmox-backup-manager sync-job create <nom-tache> \
  --remote <nom-remote> \
  --remote-store <entrepot-primaire> \
  --store <entrepot-copie> \
  --schedule '*/30'

sudo proxmox-backup-manager sync-job list
sudo proxmox-backup-manager sync-job show <nom-tache>
```

Relevé :

```
│ id           │ copie-depuis-pbs01
│ remote-store │ datastore-santelia
│ store        │ santelia-copie
│ remote       │ pbs01
│ schedule     │ */30
```

**Le sens de la copie.** La tâche est **tirée** par le serveur secondaire, elle n'est pas poussée
par le primaire. Le serveur primaire n'a donc aucune connaissance de la copie, et aucun droit sur
elle : un compte en lecture seule lui suffit. C'est ce qui rend la copie robuste, et c'est ce que
la colonne de direction vide confirme.

**Exécution manuelle, pour la recette :**

```
sudo proxmox-backup-manager sync-job run <nom-tache>
```

**Relevés d'exécution :** les deux passes de synchronisation, leurs débits et leur tableau de
synthèse sont reportés en **annexe A du document de synthèse « Sauvegarde et restauration »**.
La présente section ne conserve que la mise en place de la tâche et ses contrôles.

---

## A.15 Sauvegarde planifiée — sur un nœud du cluster

La sauvegarde a été lancée manuellement pour la recette. Elle doit ensuite être planifiée, sans
quoi elle ne se reproduit jamais, et la copie secondaire ne copie qu'une archive figée.

**Création de la tâche planifiée :**

```
pvesh create /cluster/backup \
  --storage <stockage-pbs> \
  --vmid <vmid> \
  --schedule "02:00" \
  --mode snapshot \
  --compress zstd \
  --prune-backups "keep-daily=7,keep-weekly=4,keep-monthly=3" \
  --comment "<libelle>"
```

**Contrôles :**

```
cat /etc/pve/jobs.cfg
pvesh get /cluster/backup
```

Relevé :

```
vzdump: <identifiant-de-tache>
       comment Sauvegarde quotidienne de la machine critique
       schedule 02:00
       compress zstd
       enabled 1
       mode snapshot
       prune-backups keep-daily=7,keep-monthly=3,keep-weekly=4
       storage pbs-santelia
       vmid 100
```

| Paramètre | Valeur | Objet |
| --- | --- | --- |
| `schedule` | `02:00` | Une exécution par jour |
| `mode` | `snapshot` | Sauvegarde sans interruption de service |
| `compress` | `zstd` | Compression avant transfert |
| `prune-backups` | 7 quotidiennes, 4 hebdomadaires, 3 mensuelles | Profondeur d'historique conservée |
| `enabled` | `1` | La tâche est active |

**Exécution manuelle de contrôle :**

```
vzdump <vmid> --storage <stockage-pbs> --mode snapshot --compress zstd
```

**Relevés d'exécution :** journal de sauvegarde, liste des points de restauration présents et
occupation de l'entrepôt copié sont reportés en **annexe A du document de synthèse**. La
présente section ne conserve que la planification de la tâche et ses contrôles.

---

## A.16 Fenêtre de perte, de bout en bout

Trois mécanismes agissent à trois rythmes différents. Ils ne se cumulent pas, et c'est le plus
lent qui impose la fenêtre de perte de la stratégie.

| Mécanisme | Rythme | Ce qu'il apporte |
| --- | --- | --- |
| Réplication des volumes | 15 min | Disponibilité. Ne protège pas de la perte de données |
| Sauvegarde sur le serveur primaire | Quotidienne | Point de restauration exploitable |
| Synchronisation de la copie | 30 min | Propagation de l'archive la plus récente |

**Fenêtre de perte au pire : 24 h 30.** La synchronisation peut être parfaitement à jour et
néanmoins ne contenir qu'une archive de la veille, si la sauvegarde nocturne n'a pas produit de
nouvelle archive. La fréquence de la copie ne doit donc jamais être présentée comme la fenêtre de
perte de la stratégie : le maillon le plus lent commande.

---

*Documentation publiée depuis le dépôt du projet — version du 12/10/2026.*
