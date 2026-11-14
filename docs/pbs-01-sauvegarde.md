# Santélia — Sauvegarde et restauration

> Brique 02 — Proxmox Backup Server. Trois copies, deux supports, une hors du support primaire.
> Mise à jour : 12/10/2026

---

## 1. Résultat

| Opération | Mesure |
| --- | --- |
| Sauvegarde initiale | **12 s**, 82 % réutilisé |
| Sauvegarde suivante | **9 s**, 98 % réutilisé |
| Restauration | **9,27 s** à 884 Mo/s, 8 Gio restitués |
| Copie, 1re passe | **442,898 Mio** en 363 blocs |
| Copie, 2e passe | **16,43 Mio** en 32 blocs |
| Cohérence | applicative, agent invité sollicité |
| Service pendant la sauvegarde | **non interrompu**, mode instantané |

**Une sauvegarde jamais restaurée ne prouve rien.** La restauration a donc été exécutée, vers une machine distincte, et le service interrogé depuis deux chemins.

| Propriété | Preuve |
| --- | --- |
| La sauvegarde ne coupe pas le service | mode instantané |
| La sauvegarde est cohérente | gel puis libération du système de fichiers par l'agent invité |
| La restauration aboutit | machine restaurée démarrée, service fonctionnel |
| La copie ne retransfère rien | 16,43 Mio au second passage contre 442 Mio au premier |

---

## 2. Stratégie 3-2-1

| Copie | Support | État |
| --- | --- | --- |
| **1** | Volumes du cluster, répliqués entre nœuds | Donnée vivante |
| **2** | Serveur primaire, machine virtuelle sur l'hôte | En place |
| **3** | Serveur secondaire, machine physique distincte | En place |

**Ce qui justifie la troisième copie.** Un serveur de sauvegarde installé sur la machine qu'il protège ne protège de rien : la panne emporte la donnée et sa sauvegarde ensemble.

| | Serveur primaire | Serveur secondaire |
| --- | --- | --- |
| Support | Machine virtuelle sur l'hôte | Paquet natif, machine physique distincte |
| Entrepôt | 40 Go, dédupliqué | Sous-répertoire de son volume de sauvegarde |
| Rôle | Déposer les archives | Tirer la copie |
| Compte | `pve-backup@pbs`, écriture et lecture | `pbs-sync@pbs`, écriture locale |

### Sauvegarde et réplication

| Mécanisme | Apporte | Ne protège pas de |
| --- | --- | --- |
| Réplication entre nœuds | La disponibilité, la machine redémarre ailleurs | Une suppression ou une corruption, qu'elle réplique fidèlement |
| Sauvegarde | Le retour à un état antérieur connu | L'indisponibilité, il faut restaurer |

---

## 3. Chaîne de copie

| Étape | Où | Opération | Relevé |
| --- | --- | --- | --- |
| Entrepôt | Secondaire | Création de l'entrepôt copié | Capacité largement suffisante |
| Lecture | Primaire | Compte de service en lecture seule | `pbs-reader@pbs`, rôle `DatastoreReader` |
| Confiance | Primaire → secondaire | Empreinte du certificat relevée puis déclarée | `78:05:ce:…:0f:26` |
| Déclaration | Secondaire | Dépôt distant rattaché au primaire | Adresse et compte de lecture |
| Planification | Secondaire | Synchronisation toutes les 30 minutes | Sens tiré, aucun droit d'écriture chez la source |
| Propriétaire | Secondaire | Compte sous lequel la tâche s'exécute | `root@pam`, propriétaire des groupes de sauvegarde |

**Sens de la copie.** Le secondaire tire, il ne reçoit pas. Le primaire ignore l'existence de la copie et n'a aucun droit dessus : un compte en lecture seule lui suffit.

**Pourquoi la tâche reste sous le compte d'administration.** Un groupe de sauvegarde ne peut être copié que par son propriétaire, et les groupes appartiennent au compte qui a produit les sauvegardes. Le compte de service `pbs-sync@pbs` existe et porte le seul droit d'écriture sur l'entrepôt copié ; l'y rattacher imposerait de transférer la propriété de chaque groupe, y compris ceux des machines à venir. Le compte dédié reste donc en place comme cible d'une restriction ultérieure, une fois le périmètre stabilisé.

**Sans contrôle d'empreinte**, le secondaire accepterait le certificat présenté par n'importe quel serveur répondant à cette adresse, et une interception suffirait à rediriger la copie ailleurs.

### Deux pertes, deux cibles

| | **Perte de disponibilité** | **Perte de récupération** |
| --- | --- | --- |
| Cause type | Nœud qui tombe, disque qui meurt | Suppression, corruption, rançongiciel, erreur de manipulation |
| Mécanisme | Réplication et gestion de disponibilité | Sauvegarde dédupliquée et copie secondaire |
| Rythme | 15 min | Quotidienne, plus 30 min de propagation |
| **Perte maximale** | **15 min** | **24 h 30 au pire** |
| Rétablissement | **2 min 24 s** mesurés, cible de 5 à 10 min | Restauration mesurée à 9,27 s pour 8 Gio |
| Angle mort | Réplique aussi les erreurs | Ne rend pas le service disponible |

**Ce que la copie ajoute.** Elle ne réduit pas la perte de récupération, elle en réduit le **délai de propagation**. C'est une propriété de fiabilité de la copie, pas de fraîcheur de la donnée.

**Le chiffre à ne pas annoncer.** « 30 minutes » décrit la fréquence de la copie. Annoncé comme perte maximale, il est faux d'un facteur 48, et l'écart ne se découvre qu'au moment de restaurer.

---

## 4. Points de vigilance

| # | Point | Mesure appliquée |
| --- | --- | --- |
| 1 | Image téléchargée sans vérification du certificat | Contrôle systématique de l'empreinte |
| 2 | Identifiant de compte avec un doublon de royaume | Suppression et recréation |
| 3 | Stockage déclaré au mauvais niveau | Déclaration corrigée au niveau du cluster |
| 4 | Identité réseau reprise après restauration | Extinction de l'originale, ou renumérotation |
| 5 | Arrêt arbitré par le gestionnaire de disponibilité | Passage par le gestionnaire |
| 6 | Adresse IPv6 globale exposée | Attribution à désactiver, ou filtrage explicite |
| 7 | Copie hébergée sur le volume du dépôt de fichiers | Stockage dédié à prévoir, arbitrage assumé |
| 8 | Fréquence de copie confondue avec la perte maximale | Deux pertes chiffrées séparément |

**N° 4 — identité réseau.** Une restauration restitue l'adresse matérielle de l'originale. Deux machines identiques sur le même segment provoquent un conflit, et le service devient injoignable sans message d'erreur.
> Règle : renumérotation avant toute mise en service simultanée.

**N° 6 — adresse IPv6 globale.** L'invité obtient une adresse IPv6 publique en plus de son IPv4 privée. La traduction d'adresses ne s'applique pas à IPv6 : l'infrastructure paraît protégée alors qu'un second protocole contourne le mécanisme.
> Principal enseignement de sécurité de la brique.

**N° 8 — fréquence de copie.** Une tâche toutes les 30 minutes donne l'impression d'une perte de 30 minutes. Elle ne propage pourtant qu'une archive déjà existante.

---

## 5. Recette

| Indicateur | Mesure | Statut |
| --- | --- | --- |
| Sauvegarde exécutée | 12 s puis 9 s, archives créées | Conforme |
| Restauration testée | 9,27 s à 884 Mo/s | Conforme |
| Copie restaurée fonctionnelle | service interrogé depuis deux chemins | Conforme |
| Cohérence de la sauvegarde | agent invité sollicité | Conforme |
| Taux de réutilisation | 82 %, puis 98 % | Conforme |
| Copie secondaire présente | plusieurs points de restauration, machine distincte | Conforme |
| Rétention configurée | 7 quotidiennes, 4 hebdomadaires, 3 mensuelles | Conforme |
| Perte de disponibilité | **15 min** au pire, intervalle de réplication | Conforme |
| Perte de récupération | **24 h 30** au pire, sauvegarde et propagation | Conforme |

La rétention est portée par la tâche planifiée. L'espace n'est réellement libéré qu'à l'exécution de la collecte des blocs orphelins, tâche distincte et planifiée séparément.

---

## 6. Renvois

| Objet | Document |
| --- | --- |
| Séquence de mise en œuvre, environnement par environnement | Journal des commandes : sauvegarde |
| Relevés bruts, journaux et débits | Annexe A, ci-dessous |

---

## Annexe A — Preuves brutes du test 3-2-1

Relevés reproduits tels quels, sans retraitement. Durées de tâche telles que Proxmox les enregistre.

| Copie | Support | Preuve |
| --- | --- | --- |
| **1** | Volumes du cluster | État du cluster, quorum et réplication — document de configuration |
| **2** | Serveur primaire | **A.1** à **A.4** |
| **3** | Serveur secondaire | **A.5** à **A.7** |

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

`dirty-bitmap status: created new` : première sauvegarde de cette machine, aucun historique de blocs modifiés n'existait. Les 82 % réutilisés viennent donc de la **déduplication des blocs nuls**, pas d'une archive antérieure.

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

7,88 Gio sur 8 réutilisés. La déduplication joue cette fois sur les blocs nuls **et** sur les blocs déjà écrits dans l'entrepôt.

### A.3 Restauration — 08/10/2026, vers la machine 101

Journal de 320 lignes, extraits déterminants :

```
restore proxmox backup image: /usr/bin/pbs-restore --repository
  pve-backup@pbs@192.168.1.161:datastore-santelia
starting to restore snapshot 'vm/100/2026-10-08T10:36:00Z'
progress 28% (read 2407530496 bytes, zeroes = 33% (805306368 bytes), duration 9 sec)
[…]
restore image complete (bytes=8589934592, duration=9.27s, speed=884.00MB/s)
TASK OK
```

**C'est la preuve de restauration.** Archive du 08/10, extraite de l'entrepôt primaire, vers une machine d'identifiant distinct. Les 8 589 934 592 octets correspondent exactement aux 8 Gio du disque : restauration complète. Débit d'entrepôt local, sans traversée de lien réseau.

### A.4 Points de restauration de l'entrepôt primaire

```
Volid                                              Format   Type     Size         VMID
pbs-santelia:backup/vm/100/2026-10-08T10:36:00Z    pbs-vm   backup   8589936103   100
pbs-santelia:backup/vm/100/2026-10-12T13:02:02Z    pbs-vm   backup   8589936099   100
```

Deux archives espacées dans le temps, correspondant aux journaux A.1 et A.2.

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

### A.6 Seconde passe — reprise après une nouvelle sauvegarde

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

| Passe | Snapshot déjà présent | Transféré | Blocs | Débit |
| --- | --- | --- | --- | --- |
| Première | — | **442,898 Mio** | 363 | 108,618 Mio/s |
| Seconde | reconnu inchangé, laissé tel quel | **16,43 Mio** | 32 | 82,282 Mio/s |

**Deux mécanismes se cumulent.** L'archive présente n'est pas retransférée, et pour la nouvelle, seuls les blocs absents de l'entrepôt local traversent le réseau. Le primaire déduplique à l'écriture, le secondaire à la lecture.

### A.7 Occupation de l'entrepôt de la copie

```
718M    /mnt/backup/pbs-datastore
Sys. de fichiers Taille Utilisé Dispo Uti% Monté sur
/dev/sdb1          457G     20G  414G   5% /mnt/backup
```

Une fraction de la capacité disponible. La marge est large pour les machines suivantes.

---

*Documentation publiée depuis le dépôt du projet — version du 12/10/2026.*
