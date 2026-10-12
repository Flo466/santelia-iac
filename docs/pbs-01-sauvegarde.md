# Santélia — Sauvegarde et restauration

> Brique 02 — Proxmox Backup Server. Stratégie 3-2-1 complète : sauvegarde dédupliquée,
> restauration testée, et copie secondaire sur une machine physique distincte.
> Mise à jour : 12/10/2026

---

## 1. Objet

Le cahier des charges identifie la sauvegarde comme le second besoin du projet : centraliser
les sauvegardes, prévoir une copie secondaire, et permettre la restauration des données.

Le test de recette consiste à lancer une sauvegarde, puis à restaurer. Les preuves attendues
sont le journal de sauvegarde et la preuve de restauration. Les relevés bruts
correspondants sont reproduits en **annexe A**, en fin de document.

Un point de vocabulaire, parce qu'il prête à confusion : cette brique ne traite pas la
continuité de service. Celle-ci relève de la haute disponibilité, qui permet à une machine de
redémarrer ailleurs. La sauvegarde répond à une autre question, revenir à un état antérieur connu.

---

## 2. Résultat

| Opération | Mesure |
| --- | --- |
| Sauvegarde | **12 secondes** (82 % réutilisé), puis **9 secondes** (98 % réutilisé) |
| Déduplication | **82 %** à la première passe, **98 %** à la seconde |
| Restauration | **9,27 secondes** à 884 Mo/s |
| Copie secondaire | **442 Mio** au premier transfert, **16,43 Mio** au second |
| Cohérence | Applicative, agent invité sollicité |

La copie restaurée a été démarrée, puis le service témoin interrogé depuis plusieurs points du
réseau. Elle est fonctionnelle.

Cinq points à retenir.

**La sauvegarde s'est faite sans interrompre le service**, en mode instantané. C'est ce que le
cahier des charges demande pour la sauvegarde des données.

**Elle est cohérente applicative.** Le journal mentionne l'appel à l'agent invité, qui gèle puis
libère le système de fichiers avant et après la capture. Sans lui, la sauvegarde resterait
utilisable mais serait comparable à un arrêt brutal.

**La restauration a réellement été exécutée**, vers une machine distincte de l'originale. Une
sauvegarde qui n'a jamais été restaurée ne prouve rien.

**La seconde sauvegarde n'a transféré que 2 % des données.** Sur 8 Gio, 7,88 Gio étaient déjà
présents dans l'entrepôt et ont été réutilisés. C'est la déduplication qui travaille, et c'est ce
qui rend une sauvegarde quotidienne tenable dans le temps.

**La copie secondaire se resynchronise sans retransférer ce qu'elle possède déjà.** Le second
passage a coûté 16,43 Mio contre 442 Mio au premier : l'archive déjà présente a été reconnue
comme inchangée et laissée telle quelle.

---

## 3. Ce qui a été mis en place

Deux serveurs de sauvegarde, sur deux machines physiques distinctes.

**Le serveur primaire** est une machine virtuelle hébergée sur l'hôte, avec un entrepôt
dédupliqué de 40 Go. Deux choix d'architecture : une machine virtuelle plutôt qu'un conteneur,
parce que l'application nécessite un accès direct au stockage, et un disque de données ajouté
après l'installation, pour que l'installateur n'ait qu'un seul disque à préparer.

**Le serveur secondaire** est installé en paquet natif sur une machine physique distincte de
l'hôte, sans hyperviseur. Il porte l'entrepôt de la copie, dans un sous-répertoire de son volume
de sauvegarde, séparé du dépôt de sauvegarde de fichiers déjà en exploitation sur cette machine.

### La stratégie 3-2-1

| Copie | Support | État |
| --- | --- | --- |
| **1** | Volumes du cluster | Donnée vivante, répliquée entre nœuds |
| **2** | Serveur de sauvegarde primaire, sur l'hôte | **En place** |
| **3** | Serveur de sauvegarde secondaire, machine physique distincte | **En place** |

Le point qui fait la différence : un serveur de sauvegarde installé sur la machine qu'il protège
ne protège de rien. Si l'hôte tombe, la donnée et sa sauvegarde disparaissent ensemble. C'est ce
qui justifie la troisième copie sur une machine distincte.

### Sauvegarde et réplication, deux besoins distincts

La réplication entre nœuds apporte de la disponibilité. Elle ne protège pas de la perte de
données, car elle réplique aussi les erreurs : une suppression ou une corruption se propage d'un
nœud à l'autre.

La sauvegarde permet de revenir à un état antérieur connu. Les deux mécanismes sont
complémentaires et ne se substituent pas l'un à l'autre.

### Encadré — la copie secondaire, de bout en bout

**Le problème posé.** La sauvegarde primaire vit sur l'hôte qu'elle protège. Une panne matérielle
de cet hôte emporterait la donnée et sa sauvegarde en même temps. La troisième copie doit donc
vivre ailleurs.

**Le support retenu.** Une machine physique distincte de l'hôte, en paquet natif, qui accueille
l'entrepôt de la copie. Sa capacité disponible, très supérieure au besoin, laisse de la marge
pour les machines suivantes.

**La confiance avant le transfert.** L'empreinte du certificat du serveur primaire a été relevée,
puis déclarée sur le serveur secondaire. Sans ce contrôle, une interception réseau pourrait
rediriger la copie vers un serveur tiers, qui l'accepterait sans rien signaler.

**Le sens de la copie.** C'est le serveur secondaire qui tire les données, il ne les reçoit pas.
Le serveur primaire n'a donc aucune connaissance de la copie et n'a besoin d'aucun droit sur
elle. Un compte en lecture seule lui suffit.

**Deux comptes, deux rôles, aucun droit superflu.** Le serveur secondaire se présente avec un
compte qui n'a que la lecture sur l'entrepôt source. Un compte local, distinct, porte l'écriture
sur l'entrepôt copié. Ni l'un ni l'autre ne dispose d'un droit d'administration.

| Étape | Où | Opération | Relevé |
| --- | --- | --- | --- |
| Entrepôt | Serveur secondaire | Création de l'entrepôt de la copie | Capacité disponible largement suffisante |
| Lecture | Serveur primaire | Compte de service en lecture seule | Rôle de lecture sur le seul entrepôt source |
| Confiance | Primaire, puis secondaire | Empreinte du certificat relevée puis déclarée | `78:05:ce:...:0f:26` |
| Déclaration | Serveur secondaire | Dépôt distant rattaché au primaire | Adresse et compte de lecture |
| Planification | Serveur secondaire | Tâche de synchronisation, toutes les 30 minutes | Sens tiré, sans écrire chez la source |
| Première passe | — | Transfert initial de l'archive | **442,898 Mio** en 363 blocs |
| Seconde passe | — | Reprise après une nouvelle sauvegarde | **16,43 Mio** en 32 blocs |

**Ce que la copie ajoute à la fenêtre de perte.** La tâche de synchronisation se déclenche toutes
les 30 minutes, mais elle ne fait que propager l'archive la plus récente du serveur primaire.
Elle ne peut pas copier une sauvegarde qui n'existe pas encore.

| Mécanisme | Fréquence | Ce qu'il apporte |
| --- | --- | --- |
| Réplication des volumes | 15 min | Disponibilité. Ne protège pas de la perte de données |
| Sauvegarde sur le primaire | quotidienne | Point de restauration — **fenêtre de perte : 24 h** |
| Synchronisation de la copie | 30 min | Propagation vers la copie — **+30 min au pire** |

**Fenêtre de perte de bout en bout : 24 h 30 min au pire.** C'est le maillon le plus lent qui
impose le rythme. La copie peut être parfaitement à jour et néanmoins ne contenir qu'une archive
de la veille, si la sauvegarde nocturne a échoué. La fréquence de la copie ne doit donc pas être
présentée comme la fenêtre de perte de la stratégie.

**Réserve assumée.** La tâche de synchronisation s'exécute aujourd'hui avec les droits du compte
d'administration du serveur secondaire. Un compte dédié a été créé avec le seul rôle d'écriture
sur l'entrepôt copié, en vue de restreindre la tâche à ce périmètre.

---

## 4. Points de vigilance

Huit points relevés en conditions réelles. Forme courte.

| # | Point | Mesure appliquée |
| --- | --- | --- |
| 1 | Image téléchargée sans vérification du certificat | Contrôle systématique de l'empreinte |
| 2 | Identifiant de compte saisi avec un doublon de royaume | Suppression et recréation |
| 3 | Stockage déclaré sur le mauvais niveau | Déclaration corrigée au niveau du cluster |
| 4 | Identité réseau reprise après restauration | Extinction de l'originale, ou renumérotation |
| 5 | Arrêt arbitré par le gestionnaire de disponibilité | Passage par le gestionnaire |
| 6 | Adresse IPv6 globale exposée | Attribution à désactiver, ou filtrage explicite |
| 7 | Copie secondaire hébergée sur le volume du dépôt de fichiers | Stockage dédié à prévoir, arbitrage assumé |
| 8 | Fréquence de copie confondue avec la fenêtre de perte | Fenêtre calculée sur le maillon le plus lent |

Trois d'entre eux méritent une phrase.

**Le point 4.** Une restauration restitue l'identité réseau de la machine, adresse matérielle
comprise. Deux machines identiques sur le même segment provoquent un conflit, et le service
devient injoignable sans aucun message d'erreur. Règle qui en découle : toute restauration exige
une renumérotation avant mise en service simultanée.

**Le point 6.** Le système invité obtient automatiquement une adresse IPv6 publique, en plus de
son adresse IPv4 privée. La traduction d'adresses qui protège IPv4 ne s'applique pas à IPv6.
L'infrastructure semble protégée, alors qu'un second protocole contourne le mécanisme. Ce point
illustre une fausse sensation de sécurité, et il constitue le principal enseignement de sécurité
de cette brique.

**Le point 8.** Une tâche de copie déclenchée toutes les 30 minutes donne l'impression d'une
fenêtre de perte de 30 minutes. C'est faux : la copie ne fait que propager une archive existante.
Annoncer une fenêtre trop optimiste affaiblit l'ensemble de la stratégie, car l'écart ne se
découvre qu'au moment où l'on cherche à restaurer.

---

## 5. Recette et conformité

| Indicateur | Mesure | Statut |
| --- | --- | --- |
| Sauvegarde exécutée | 12 s puis 9 s, archives créées | Conforme |
| Restauration testée | 9,27 s à 884 Mo/s | Conforme |
| Copie restaurée fonctionnelle | Service interrogé depuis deux chemins | Conforme |
| Cohérence de la sauvegarde | Agent invité sollicité | Conforme |
| Taux de déduplication | 82 %, puis 98 % | Conforme |
| Copie secondaire présente | Plusieurs points de restauration sur une machine distincte | Conforme |
| Rétention configurée | 7 quotidiennes, 4 hebdomadaires, 3 mensuelles | Conforme |
| Fenêtre de perte définie | 24 h 30 min au pire, de bout en bout | Conforme |

La rétention est portée par la tâche de sauvegarde planifiée. L'espace occupé n'est réellement
libéré qu'à l'exécution de la collecte des blocs orphelins, tâche distincte et planifiée
séparément sur le serveur de sauvegarde.

---

## 6. Suite donnée

| Étape | Objet |
| --- | --- |
| Chiffrement de l'entrepôt | Protection des données au repos, clé conservée hors du serveur |
| Élargissement du périmètre | Étendre la sauvegarde aux autres machines de l'infrastructure |
| Stockage dédié à la copie secondaire | Isoler la copie du dépôt de fichiers (point de vigilance n° 7) |
| Restriction de la tâche de copie | Rattacher la tâche au compte dédié créé à cet effet |

---

## 7. Journal des commandes

La séquence complète de mise en œuvre, environnement par environnement, est regroupée dans le
document **Journal des commandes : sauvegarde**, qui accompagne celui-ci. Il couvre les cinq
environnements d'exécution : poste de travail, hôte physique, cluster, serveur de sauvegarde
primaire et serveur de sauvegarde secondaire.

Les mesures d'exécution de la stratégie 3-2-1, sorties de ce journal pour ne pas l'alourdir, sont
regroupées en **annexe A** du présent document.

---

## Annexe A — Preuves brutes du test 3-2-1

Relevés reproduits tels quels, sans retraitement. Ce sont les preuves exigées par la recette :
journal de sauvegarde et preuve de restauration. Les durées citées dans les tableaux du document
sont les durées de tâche, telles que Proxmox les enregistre, et non les seuls temps de transfert.

| Copie | Support | Preuve correspondante |
| --- | --- | --- |
| **1** | Volumes du cluster | État du cluster, quorum et réplication — document de configuration du cluster |
| **2** | Serveur de sauvegarde primaire | **A.1** à **A.4** |
| **3** | Serveur de sauvegarde secondaire | **A.5** à **A.7** |

### A.1 Première sauvegarde — 08/10/2026

```
INFO: VM Name: vm-test-ha
INFO: include disk 'scsi0' 'local-zfs:vm-100-disk-0' 8G
INFO: backup mode: snapshot
INFO: creating Proxmox Backup Server archive 'vm/100/2026-10-08T10:36:00Z'
INFO: issuing guest-agent 'fs-freeze' command
INFO: issuing guest-agent 'fs-thaw' command
INFO: scsi0: dirty-bitmap status: created new
INFO: 100% (8.0 GiB of 8.0 GiB) in 11s, read: 1.5 GiB/s
INFO: backup is sparse: 6.47 GiB (80%) total zero data
INFO: backup was done incrementally, reused 6.59 GiB (82%)
INFO: transferred 8.00 GiB in 11 seconds (744.7 MiB/s)
INFO: Finished Backup of VM 100 (00:00:12)
INFO: Backup job finished successfully
```

**Lecture.** Le gel puis la libération du système de fichiers par l'agent invité attestent la
cohérence applicative de la copie. Le `dirty-bitmap status: created new` indique qu'il s'agit de
la toute première sauvegarde de cette machine : aucun historique de blocs modifiés n'existait
avant elle. Les 82 % réutilisés ne proviennent donc pas d'une archive antérieure, mais de la
**déduplication des blocs nuls** — les 6,59 Gio réutilisés correspondent aux 6,47 Gio de données
creuses du disque. C'est ce qui explique qu'une première sauvegarde de 8 Gio se termine en
12 secondes.

### A.2 Sauvegarde suivante — 12/10/2026

```
INFO: backup mode: snapshot
INFO: issuing guest-agent 'fs-freeze' command
INFO: issuing guest-agent 'fs-thaw' command
INFO: 100% (8.0 GiB of 8.0 GiB) in 8s, read: 1.5 GiB/s
INFO: backup is sparse: 6.43 GiB (80%) total zero data
INFO: backup was done incrementally, reused 7.88 GiB (98%)
INFO: Finished Backup of VM 100 (00:00:09)
INFO: Backup job finished successfully
```

**Lecture.** Cette fois la déduplication joue sur les deux tableaux : les blocs nuls, comme à la
première passe, et les blocs déjà écrits dans l'entrepôt lors de cette passe. 7,88 Gio sur 8 sont
réutilisés, soit 98 %.

### A.3 Restauration — 08/10/2026, vers la machine 101

Le journal compte 320 lignes de progression. Extraits déterminants :

```
restore proxmox backup image: /usr/bin/pbs-restore --repository
  pve-backup@pbs@192.168.1.161:datastore-santelia
starting to restore snapshot 'vm/100/2026-10-08T10:36:00Z'
progress 28% (read 2407530496 bytes, zeroes = 33% (805306368 bytes), duration 9 sec)
[…]
restore image complete (bytes=8589934592, duration=9.27s, speed=884.00MB/s)
TASK OK
```

**Lecture — c'est la preuve de restauration.** L'archive restaurée est bien celle du 08/10,
extraite de l'entrepôt du serveur de sauvegarde primaire, vers une machine d'identifiant
distinct, la 101. Les 8 589 934 592 octets annoncés correspondent exactement aux 8 Gio du disque :
la restauration est complète et non partielle. Le débit de 884 MiB/s sur 9,27 secondes est celui
d'un entrepôt local, sans traversée de lien réseau.

### A.4 Points de restauration présents dans l'entrepôt primaire

```
Volid                                              Format   Type     Size         VMID
pbs-santelia:backup/vm/100/2026-10-08T10:36:00Z    pbs-vm   backup   8589936103   100
pbs-santelia:backup/vm/100/2026-10-12T13:02:02Z    pbs-vm   backup   8589936099   100
```

**Lecture :** deux archives espacées dans le temps, correspondant aux deux journaux ci-dessus.
C'est cette régularité qui rend la fenêtre de perte annoncée tenable.

### A.5 Première passe de synchronisation — transfert initial

```
Found 1 groups to sync (out of 1 total)
[vm/100]: 2026-10-08T10:36:00Z: start sync
[vm/100]: 2026-10-08T10:36:00Z/drive-scsi0.img.fidx: downloaded 442.898 MiB (108.618 MiB/s)
[vm/100]: 2026-10-08T10:36:00Z: sync done
[vm/100]: percentage done: 100.00% (1/1 snapshots)
Summary: sync job pulled 442.898 MiB in 363 chunks (average rate: 108.618 MiB/s)
TASK OK
```

### A.6 Seconde passe de synchronisation — reprise après une nouvelle sauvegarde

```
[vm/100]: re-sync snapshot 2026-10-08T10:36:00Z
[vm/100]: 2026-10-08T10:36:00Z: no data changes
[vm/100]: percentage done: 50.00% (1/2 snapshots)
[vm/100]: 2026-10-12T13:02:02Z/drive-scsi0.img.fidx: downloaded 16.43 MiB (82.282 MiB/s)
[vm/100]: 2026-10-12T13:02:02Z: sync done
[vm/100]: percentage done: 100.00% (2/2 snapshots)
Summary: sync job pulled 16.43 MiB in 32 chunks (average rate: 82.282 MiB/s)
TASK OK
```

| Passe | Snapshot déjà présent | Données transférées | Blocs | Débit |
| --- | --- | --- | --- | --- |
| Première | — | **442,898 Mio** | 363 | 108,618 Mio/s |
| Seconde | reconnu inchangé, laissé tel quel | **16,43 Mio** | 32 | 82,282 Mio/s |

**Lecture — deux mécanismes se cumulent.** L'archive déjà présente n'est pas retransférée : le
serveur secondaire la reconnaît comme inchangée et la laisse en place. Et pour la nouvelle
archive, seuls les blocs absents de son propre entrepôt traversent le réseau — 16,43 Mio pour
8 Gio de machine, exactement comme la déduplication à la source. Les deux serveurs travaillent
donc en relais : le primaire déduplique à l'écriture, le secondaire déduplique à la lecture.

### A.7 Occupation de l'entrepôt de la copie

```
718M    /mnt/backup/pbs-datastore
Sys. de fichiers Taille Utilisé Dispo Uti% Monté sur
/dev/sdb1          457G     20G  414G   5% /mnt/backup
```

**Lecture :** la copie occupe une fraction de la capacité disponible. La marge est large pour les
machines suivantes.

---

*Documentation publiée depuis le dépôt du projet — version du 12/10/2026.*
