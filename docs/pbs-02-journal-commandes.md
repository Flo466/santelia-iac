# Santélia — Journal des commandes : sauvegarde

> Brique 02 — séquence complète de mise en œuvre, par environnement d'exécution.
> Mise à jour : 08/10/2026

---

## Préambule — Trois environnements, trois périmètres

Les commandes ne s'exécutent pas au même endroit, et confondre les deux premiers est la principale source d'erreur sur ce montage.

| Environnement | Rôle |
| --- | --- |
| **Hôte physique** | Porte le cluster et la machine de sauvegarde |
| **Cluster** | Héberge les machines applicatives à sauvegarder |
| **Serveur de sauvegarde** | Stocke les sauvegardes |

Un stockage déclaré sur l'hôte n'est **pas** visible depuis le cluster, et inversement. C'est ce qui a provoqué l'échec de la première sauvegarde, traitée au point de vigilance n° 5.

---

## A.1 Récupération de l'image d'installation — sur l'hôte

```
cd /var/lib/vz/template/iso

wget --no-check-certificate https://download.proxmox.com/iso/proxmox-backup-server_4.2-1.iso

sha256sum proxmox-backup-server_4.2-1.iso
```

**Contrôle :** comparer l'empreinte obtenue à celle publiée par l'éditeur. La vérification du certificat ayant dû être désactivée, ce contrôle devient obligatoire.

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

Aucune valeur n'est définie dans la configuration courante, les valeurs par défaut sont donc inactives : le seuil effectif est de 100 %, l'extension automatique ne se déclenche jamais.

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

Le démon de surveillance n'est **pas** déclaré comme service indépendant sur cette version : son contrôle s'effectue par recherche de processus.

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

L'écoute doit se faire **exclusivement sur l'adresse de bouclage**, ce qui confirme que le port de l'interface d'administration n'est jamais exposé sur le réseau.

---

## A.5 Entrepôt de données — sur le serveur de sauvegarde

```
proxmox-backup-manager datastore list
proxmox-backup-manager cert info | grep -i fingerprint
```

**Relevé de l'empreinte du certificat** — elle servira à authentifier le serveur lors du raccordement.

**Préparation du stockage**, depuis l'interface : onglet `Stockage et disques`, puis création d'un répertoire sur le disque de données.

**Contrôle :**

```
df -h | grep datastore
lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT
```

Le répertoire est référencé **par identifiant unique** et non par nom de disque, ce qui rend le montage stable dans le temps.

---

## A.6 Compte de service — sur le serveur de sauvegarde

```
proxmox-backup-manager user list
proxmox-backup-manager acl list
```

Le compte doit apparaître au format `<utilisateur>@<royaume>`, sans doublon de royaume. Les permissions portent sur le seul entrepôt concerné, avec un rôle d'écriture et un rôle de lecture. Le principe appliqué est le moindre privilège.

---

## A.7 Raccordement du cluster — sur un nœud du cluster

```
pvesm status
pvesm list <stockage-pbs>
```

L'état « actif » du stockage valide simultanément quatre éléments : connectivité réseau, authentification du compte, adéquation des permissions et conformité de l'empreinte du certificat.

---

## A.8 Sauvegarde

```
vzdump <vmid> --storage <stockage-pbs> --mode snapshot --compress zstd
```

Le mode instantané sauvegarde sans interrompre le service. Le journal doit mentionner l'appel à l'**agent invité** pour geler puis libérer le système de fichiers : c'est ce qui garantit une sauvegarde cohérente applicative.

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

**Attention :** la copie restaurée reprend l'identité réseau de l'originale, adresse matérielle comprise. Le contrôle des interfaces le confirme. Toute mise en service simultanée exige une renumérotation.

**Arrêt d'une ressource gérée en haute disponibilité :** la commande d'arrêt directe est arbitrée par le gestionnaire, qui relance la machine. L'arrêt effectif passe par le gestionnaire.

---

## A.10 Copie secondaire

*(à compléter — troisième copie de la stratégie 3-2-1)*

---

*Documentation publiée depuis le dépôt du projet — version du 08/10/2026.*
