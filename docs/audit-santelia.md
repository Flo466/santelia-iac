# Santélia — Audit de vulnérabilités

> Audit de l'infrastructure existante. Inventaire, analyse, préconisations et preuve de remédiation.
> 26/11/2026

---

## 1. Périmètre et cadre

L'audit porte sur le cluster Proxmox déployé dans les briques 01 et 02, et non sur une maquette. La demande est celle d'un DSI : savoir ce qui est exposé, avec quelle gravité, et dans quel ordre corriger.

### 1.1 Cibles auditées

| Cible | Adresse | Rôle |
| --- | --- | --- |
| `pve-a` | 192.168.1.151 | Nœud principal du cluster |
| `pve-b` | 192.168.1.152 | Nœud secondaire |
| `pve-c` | 192.168.1.153 | Votant de quorum |

### 1.2 Cadre et autorisation

L'auditeur est **propriétaire et administrateur** du réseau audité. Aucune cible hors de ce réseau n'a été scannée. Le balayage de découverte a porté sur l'ensemble du segment, puis l'inventaire détaillé a été restreint aux trois nœuds du cluster.

| Hors périmètre | Raison |
| --- | --- |
| `srv-dpi-santelia` — 192.168.1.160 | Machine applicative, aucune donnée métier déployée |
| `pbs01` — 192.168.1.161 | Serveur de sauvegarde, à traiter dans une seconde passe |
| Autres hôtes du segment | Usage domestique, sans lien avec Santélia |

### 1.3 Choix d'adaptation

| Choix retenu | Justification |
| --- | --- |
| Station d'audit hébergée sur l'hyperviseur | Un seul mécanisme d'accès, et une position réseau identique à celle d'un poste interne |
| Une seule interface réseau | La station est déjà sur le segment commun ; la double carte n'apporterait rien |
| Adressage `192.168.1.0/24` | Réseau réel de l'infrastructure auditée, dont l'auditeur est propriétaire |
| Adresse fixe en `.245` | Hors plage d'attribution automatique, vérifiée libre avant attribution |
| Analyse non authentifiée | Aucun compte privilégié fourni à l'outil pendant le scan |

**Ce que ces choix changent à la valeur du test.** Rien : ils ne réduisent pas la portée de l'analyse. L'audit porte sur une infrastructure réellement en service, avec ses écarts réels, et non sur une maquette reconstituée pour l'exercice.

---

## 2. Méthode et outillage

| Outil | Version | Rôle |
| --- | --- | --- |
| Nmap | 7.99 | Découverte, inventaire des ports, identification de services |
| OpenVAS / GVM | 25.04.0 | Détection de vulnérabilités |

### 2.1 Station d'audit

| Élément | Valeur |
| --- | --- |
| Machine | `kali-audit`, machine virtuelle dédiée |
| Adresse | 192.168.1.245, hors plage d'attribution automatique |
| Ressources | **6 Gio de mémoire**, 2 vCPU, **45 Gio de disque** |
| Position réseau | Pont `vmbr0`, segment de niveau 2 commun avec les cibles |

**Pourquoi la position compte.** La station voit exactement ce que verrait un poste interne au réseau, non un poste d'administration filtré. L'accès SSH passe par un rebond via l'hôte physique, mais **le rebond ne concerne que la session d'administration** : les scans partent de la station.

### 2.2 Construction de la station, de bout en bout

| # | Étape | Point déterminant |
| --- | --- | --- |
| 1 | Création de la machine | Processeur **natif**, mémoire dynamique désactivée, démarrage automatique **désactivé** |
| 2 | Mise en réseau sur le pont | Adresse vérifiée libre, hors plage d'attribution automatique |
| 3 | Installation du système | **Serveur SSH obligatoire**, sans lui aucune administration à distance |
| 4 | Installation de GVM et synchronisation | L'initialisation ne doit pas être interrompue |
| 5 | Droit réseau du moteur | **Sans ce droit, le scan s'arrête à 0 %** |
| 6 | Activation des services au démarrage | Aucun n'est actif par défaut : un redémarrage perd la pile |
| 7 | Tunnel vers l'interface | Écoute locale uniquement, jamais exposée au segment |

**Démarrage automatique désactivé, volontairement.** Une station d'audit ne se relance pas avec l'hyperviseur.

**Le point de rupture le plus coûteux est l'étape 5.** Installation complète, interface qui répond, flux synchronisé, et aucun scan ne démarre.

```
getcap /usr/sbin/openvas
```

| Résultat | Interprétation |
| --- | --- |
| `cap_net_admin,cap_net_raw=eip` | Le moteur peut analyser |
| Sortie vide | Le scan échouera à 0 % : droit à ajouter |

```
sudo setcap cap_net_raw,cap_net_admin+eip /usr/sbin/openvas
```

**Accès à l'interface**, sur l'adresse de bouclage uniquement :

```
ssh -L 9392:127.0.0.1:9392 kali-audit
```

### 2.3 Dimensionnement — un constat mesuré

Le dimensionnement initial du disque, fixé à **28 Gio**, s'est révélé insuffisant pendant la synchronisation du flux de vulnérabilités. Le dimensionnement n'était cadré que sur la mémoire et les processeurs, sans indication de taille de disque : l'arbitrage a donc été fait à l'installation, et il était trop court.

| Élément | Valeur constatée |
| --- | --- |
| Tests de vulnérabilités téléchargés | **95 109** |
| Occupation après synchronisation | 27 Gio sur 28 |
| Cause de l'occupation | Flux NVT, base PostgreSQL, paquets GVM |
| Conséquence | **Disque plein, arrêt de PostgreSQL, interface indisponible** |

**Correction appliquée.** Disque porté à **45 Gio**, avec redémarrage de l'invité nécessaire pour que le noyau relise la taille du disque avant extension de la partition.

**Recommandation pour un déploiement ultérieur.**

| Ressource | Minimum | Confortable |
| --- | --- | --- |
| Disque | 45 Gio | 60 Gio |
| Mémoire | **6 Gio** | 8 Gio |
| Processeurs | 2 | 4 |

**Sur la mémoire.** La machine a été portée à 6 Gio. En dessous, le moteur est arrêté par le système pour manque de mémoire et la synchronisation ne se termine jamais.

**Enseignement.** Une base de vulnérabilités complète n'est pas un outil léger. Le chiffre de 28 Gio correspondait à un système et un outil installés, pas à un flux synchronisé. Ce constat ne figure dans aucun document de référence : il vient de la mise en œuvre.

### 2.4 Vocabulaire de l'analyse

| Terme | Définition retenue |
| --- | --- |
| **Vulnérabilité** | Faiblesse d'un système : service mal configuré, logiciel obsolète, accès trop large |
| **Menace** | Ce qui peut exploiter la faiblesse : attaquant, logiciel malveillant, erreur humaine |
| **Risque** | Vulnérabilité × menace × conséquences. La même faille sur un serveur de test et sur le DPI n'a pas la même valeur |
| **CVE** | Identifiant public d'une faille connue, permettant de retrouver l'avis et le correctif |
| **CVSS** | Note de gravité de 0 à 10 : faible 0,1 à 3,9 ; moyenne 4,0 à 6,9 ; élevée 7,0 à 8,9 ; critique 9,0 à 10 |
| **QoD** | *Quality of Detection*, confiance de l'outil dans sa propre détection, en pourcentage |
| **Faux positif** | Alerte de l'outil qui ne correspond pas à une faille réelle : d'où la colonne « à vérifier » |
| **Priorité** | P1 immédiat, P2 dans le mois, P3 plus tard. Elle dépend de la gravité **et** de l'importance de la machine |

---

## 3. Inventaire

### 3.1 Découverte du segment

```
nmap -sn 192.168.1.0/24
```

**16 hôtes actifs sur 256**, en 5,4 secondes.

| Machine | Adresse | Constructeur déclaré | Rôle |
| --- | --- | --- | --- |
| `proxmox-hote` | 192.168.1.150 | Dell | Hôte physique |
| `pve-a` | 192.168.1.151 | Proxmox Server Solutions | Nœud principal |
| `pve-b` | 192.168.1.152 | Proxmox Server Solutions | Nœud secondaire |
| `pve-c` | 192.168.1.153 | Proxmox Server Solutions | Votant de quorum |
| `srv-dpi-santelia` | 192.168.1.160 | Proxmox Server Solutions | Machine applicative |
| `pbs01` | 192.168.1.161 | Proxmox Server Solutions | Sauvegarde primaire |
| `srv-debian` | 192.168.1.125 | Dell | Sauvegarde secondaire |
| `kali-audit` | 192.168.1.245 | — | Station d'audit |

Les huit autres hôtes relèvent de l'usage domestique du réseau et sortent du périmètre.

### 3.2 Ce qu'apprend un attaquant en cinq secondes

Trois choses, sans aucun privilège et sans déclencher d'alerte :

**La cartographie.** Seize machines actives, leur adresse, leur adresse matérielle. L'attaquant sait combien de cibles il a devant lui avant d'avoir testé le moindre port.

**La nature de l'infrastructure.** Le préfixe matériel `BC:24:11` identifie sans ambiguïté cinq machines virtuelles Proxmox : les trois nœuds, la machine applicative et le serveur de sauvegarde. Le cluster est donc immédiatement reconnaissable et séparable du reste du parc — ce qui désigne aussi les cibles les plus intéressantes.

**La topologie physique.** Deux machines Dell en `.150` et `.125` indiquent les hôtes porteurs. L'attaquant comprend qu'il a affaire à une infrastructure virtualisée sur deux châssis, et non à des serveurs isolés.

### 3.3 Tableau d'inventaire des trois nœuds

| Machine | IP | Ports ouverts | Service / version | Rôle pour Santélia |
| --- | --- | --- | --- | --- |
| `pve-a` | 192.168.1.151 | 22, 111, 3128, 8006 | OpenSSH 9.2p1 Debian 12 · rpcbind 2-4 · proxy SPICE · interface web | Nœud principal, héberge la machine critique |
| `pve-b` | 192.168.1.152 | 22, 111, 3128, 8006 | identique | Nœud secondaire, cible de réplication |
| `pve-c` | 192.168.1.153 | 22, 111, 3128, 8006 | identique | Votant de quorum |

**65 531 ports fermés sur 65 535.** Les trois nœuds présentent une signature strictement identique, ce qui est cohérent avec leur création par clonage.

### 3.4 Deux enseignements de méthode

**Pourquoi les noms de service affichés sont faux.**

Un scan **sans identification de version** lit simplement la correspondance entre numéro de port et nom de service. Il affiche donc `squid-http` pour 3128 et `wpl-analytics` pour 8006, alors qu'il s'agit du proxy SPICE et de l'interface d'administration Proxmox. C'est une **déduction par convention**, pas une observation.

L'option qui tranche est **`-sV`**. Le même port 3128 s'affiche alors « Proxmox Virtual Environment REST API ». C'est la démonstration directe que le nom seul ne prouve rien.

**Second enseignement :** le port 8006 n'appartient pas aux mille ports les plus courants. Il n'apparaît qu'au scan complet. Une analyse limitée aux ports usuels conclurait à tort que l'interface d'administration n'est pas exposée.

### 3.5 Absence notable

**Aucun service NFS.** Le port 2049 est fermé sur les trois nœuds, contrairement à la configuration de référence. Le stockage des machines virtuelles n'est pas exposé par ce protocole.

**Conséquence sur l'analyse.** Le constat le plus critique de la référence — un partage de stockage lisible par toute machine du réseau — n'existe pas dans ce périmètre. Les constats retenus portent donc sur les services effectivement exposés.

---

## 4. Analyse et priorisation

### 4.1 Tableau des constats

| N° | Constat (hôte:port, service) | Pourquoi c'est un risque | Gravité | À vérifier |
| --- | --- | --- | --- | --- |
| 1 | `pve-a/b/c:8006` — interface d'administration Proxmox | Donne la maîtrise complète de l'infrastructure qui héberge le service critique | **Haute** | Non, mesuré |
| 2 | `pve-a/b/c:22` — SSH, OpenSSH 9.2p1 | Surface d'attaque pour des tentatives d'authentification répétées | **Moyenne** | Non, mesuré |
| 3 | `pve-a/b/c:111` — rpcbind | Révèle les programmes RPC disponibles, facilite l'énumération | **Faible** | Non, mesuré |

### 4.2 Justification de chaque constat

**Constat 1.** L'interface web permet de créer, détruire et déplacer les machines virtuelles. Elle est joignable depuis n'importe quelle adresse du segment, y compris depuis les objets connectés du réseau domestique. Sa compromission équivaut à la perte de l'infrastructure.

**Constat 2.** Le service SSH accepte les connexions de tout le réseau, avec le nombre de tentatives par défaut. La faille n'est pas dans le service lui-même mais dans son exposition et dans l'absence de limitation.

**Constat 3.** `rpcbind` ne donne pas d'accès direct, mais il indique à un attaquant quels services RPC existent. Comme aucun service NFS ne l'accompagne, l'exposition réelle reste faible.

### 4.3 Décisions et priorités

| N° | Décision | Priorité | Raison liée à Santélia |
| --- | --- | --- | --- |
| 1 | **Corriger** | **P1** | Cette interface pilote l'infrastructure qui porte le DPI. Une compromission arrête la prise de rendez-vous, exactement l'incident que le projet doit empêcher |
| 2 | **Corriger** | **P2** | Mesure de réduction de surface, à traiter dans le mois. Elle ne bloque pas le service |
| 3 | **Compenser** | **P3** | Aucun service NFS ne l'accompagne. Le risque est informatif, pas opérationnel |

---

## 5. Préconisations

| Priorité | Préconisation | Mesure | État |
| --- | --- | --- | --- |
| **P1** | Filtrer l'accès à l'interface d'administration | Activer le pare-feu Proxmox, avec les règles minimales | **Planifié** — non exécuté dans cette passe |
| **P2** | Limiter les tentatives d'authentification SSH | `MaxAuthTries` ramené à 3 | **Exécuté**, voir section 6.1 |
| **P2** | Retirer les algorithmes cryptographiques faibles | Six algorithmes MAC conservés sur dix | **Exécuté**, voir section 6.6 |
| **P3** | Réduire l'exposition RPC | Désactiver `rpcbind` si aucun service NFS n'est utilisé | **Différé** |

### 5.1 Pourquoi le filtrage n'est pas exécuté dans cette passe

Le pare-feu Proxmox filtre **aussi** le trafic interne au cluster : communication de quorum, migration, gestion de disponibilité. Une règle trop stricte coupe le cluster et provoque l'incident qu'on cherchait à éviter.

Cette mesure exige donc une fenêtre d'intervention, une session de secours ouverte, une application sur **un seul nœud** puis un contrôle avant extension. Elle ne s'improvise pas en fin de séance.

**Ce n'est pas un renoncement, c'est un séquencement.** La correction retenue pour la preuve est celle qui présente le meilleur rapport bénéfice/risque immédiat.

---

## 6. Remédiation et preuve

### 6.1 Mesure retenue

**Réduire le nombre de tentatives d'authentification SSH à 3**, sur le nœud `pve-a`.

| Critère | Évaluation |
| --- | --- |
| Risque pour le cluster | **Nul** : le réglage ne touche pas aux communications entre nœuds |
| Réversible | Oui, une ligne et un redémarrage du service |
| Mesurable | Oui, une commande donne la valeur effective avant et après |

**Ce que cette mesure ne fait pas.** Elle réduit la surface d'attaque, elle ne supprime pas l'exposition. Le service reste joignable depuis tout le réseau. C'est une mesure de réduction, à compléter par le filtrage P1.

**Avertissement respecté.** `PermitRootLogin` n'est **pas** modifié : les nœuds du cluster communiquent entre eux en SSH avec le compte root. Le désactiver casserait le cluster.

### 6.2 État AVANT

| Relevé | Valeur |
| --- | --- |
| `maxauthtries` avant modification | **6** |
| Cluster avant modification | **3 nœuds, 3 votes, quorum 2, Quorate** |

Le relevé du fichier montre la directive **présente mais commentée** :

```
35:#MaxAuthTries 6
```

Elle existe donc pour information, sans effet : le serveur applique sa valeur par défaut.

### 6.3 Modification

```
nano /etc/ssh/sshd_config
# MaxAuthTries 3

sshd -t
systemctl restart ssh
```

Le test de syntaxe précède systématiquement le redémarrage : une configuration invalide couperait l'accès distant au nœud.

### 6.4 État APRÈS

| Relevé | Valeur | Verdict |
| --- | --- | --- |
| `maxauthtries` après modification | **3** | Mesure appliquée |
| Nouvelle connexion SSH fonctionnelle | `hostname` renvoie **pve-a** | Service opérationnel |
| Cluster après modification | **3 nœuds, 3 votes, quorum 2, Quorate** | Aucune régression |
| Ports ouverts au re-scan | **22, 111, 3128** — identiques au relevé initial | Aucune dégradation |

**Résultat : 6 → 3, sans interruption de service et sans perte de quorum.**

### 6.5 Contrôle de non-régression

```
sshd -T | grep -i maxauthtries
pvecm status
nmap -sV 192.168.1.151
```

Le troisième vérifie que le cluster reste joignable depuis la station d'audit, et que les ports ouverts n'ont pas changé.

**Une réserve à connaître.** Le contrôle a été fait avec un scan des mille ports les plus courants, qui ne voit pas le port 8006. La comparaison stricte exigerait un scan complet. Elle a été faite avant modification, pas après : limite du relevé, sans incidence sur la mesure.

### 6.6 Seconde remédiation — algorithmes d'authentification SSH

Même nature que la précédente : configuration du service, aucun effet sur le quorum.

**État AVANT**, depuis la station d'audit :

```
nmap -p 22 --script ssh2-enum-algos 192.168.1.151
```

**10 algorithmes MAC annoncés**, dont quatre faibles : `umac-64-etm`, `hmac-sha1-etm`, `umac-64`, `hmac-sha1`.

**Modification**, un fichier de réglage dédié :

```
echo 'MACs hmac-sha2-256-etm@openssh.com,hmac-sha2-512-etm@openssh.com,umac-128-etm@openssh.com,hmac-sha2-256,hmac-sha2-512,umac-128@openssh.com' > /etc/ssh/sshd_config.d/10-macs.conf

sshd -t
sshd -T | grep -i '^macs'
systemctl reload ssh
```

**Point de vigilance rencontré.** Après création du fichier, la valeur effective affichait déjà les six algorithmes, mais le relevé réseau en annonçait toujours dix. Ni le fichier ni son inclusion n'étaient en cause : l'**absence de rechargement du service** laissait l'ancienne configuration active. `sshd -t` valide une syntaxe, il ne prouve pas qu'une modification est appliquée.

**État APRÈS** :

| Relevé | Valeur |
| --- | --- |
| Algorithmes MAC annoncés | **6**, contre 10 avant |
| `umac-64` et `hmac-sha1` | **disparus** |
| Nouvelle connexion SSH | fonctionnelle |
| Cluster | toujours quorate |

**Confirmé par l'outil** : le second scan ne remonte plus le résultat « Weak MAC Algorithm(s) Supported » (section 7.4).

**Retour arrière** : supprimer le fichier puis recharger le service.

---

## 7. Analyse de vulnérabilités OpenVAS

### 7.1 Outil et flux

| Élément | Valeur |
| --- | --- |
| Version | GVM 25.04.0, scanner OpenVAS 23.51.0, gestionnaire 26.41.0 |
| Tests de vulnérabilités disponibles | **95 109** |
| Tests produits | 534 |
| Référentiels | SCAP et CERT présents |

### 7.2 Cible et configuration retenues

| Champ | Valeur |
| --- | --- |
| Nom de la cible | `Santelia-pve-a` |
| Hôte | 192.168.1.151 |
| Configuration de scan | Full and fast |
| Mode | non authentifié |

### 7.3 Résultats — deux scans comparés

**Premier scan, avant remédiation. Durée 29 minutes.** 54 résultats, dont 1 CVE.

| Sévérité | Nombre | Détail |
| --- | --- | --- |
| **Critique** | **1** | Proxmox VE End of Life — 10,0 |
| Élevée | 0 | |
| Moyenne | 0 | |
| **Basse** | **3** | TCP Timestamps 2,6 · **Weak MAC 2,6** · ICMP Timestamp 2,1 |
| Log (0,0) | 50 | Informations, pas des failles |

**Second scan, après remédiation des algorithmes MAC. Durée 21 minutes.**

| Sévérité | Nombre | Évolution |
| --- | --- | --- |
| **Critique** | **1** | Inchangé — Proxmox VE End of Life |
| Élevée | 0 | — |
| Moyenne | 0 | — |
| **Basse** | **2** | **3 → 2** |

### 7.4 La preuve par l'outil

| Résultat | Premier scan | Second scan |
| --- | --- | --- |
| Proxmox VE End of Life | 10,0 — critique | 10,0 — critique |
| TCP Timestamps Information Disclosure | 2,6 — basse | 2,6 — basse |
| **Weak MAC Algorithm(s) Supported (SSH)** | **2,6 — basse, port 22** | **disparu** |
| ICMP Timestamp Reply Information Disclosure | 2,1 — basse | 2,1 — basse |

**Le résultat visé a disparu du rapport.** Les six algorithmes restants ne sont plus considérés comme faibles : la remédiation est confirmée par deux sources indépendantes, l'énumération directe des algorithmes négociés et le scan de vulnérabilités.

**Ce que le scan ne voit pas.** L'interface d'administration sur 8006 ne produit aucun résultat de vulnérabilité : c'est une exposition, pas une faille. Nmap reste la source du constat n° 1.

### 7.5 Un résultat à nuancer — la détection de fin de vie

| Élément examiné | Constat |
| --- | --- |
| Gravité annoncée | **10,0**, note maximale |
| QoD | 80 % : l'outil n'est pas certain |
| Méthode de détection | Empreinte de version sur une réponse HTTP, pas un test actif |
| Vérification de la version réelle | `pveversion` — 8.4, publiée en 2024, encore maintenue |
| Nature du risque | **État de maintenance**, pas une faille exploitable |

**Ce qui fait nuancer.** Ce résultat ne décrit pas une faiblesse technique : il signale qu'une version plus récente existe. Aucune exploitation n'y est associée, et la version installée reçoit toujours ses correctifs. Le classer en priorité absolue reviendrait à traiter un indicateur de veille comme une vulnérabilité.

**Comment le vérifier et le traiter.** Contrôler la version réelle sur les trois nœuds, consulter le cycle de maintenance de l'éditeur, puis décider d'une fenêtre de mise à jour. La criticité réelle porte sur le **processus** — personne ne surveille les versions — plus que sur la machine.

**L'enseignement.** Une note de 10 sur un résultat à 80 % de confiance, fondé sur une empreinte de version, illustre pourquoi la colonne « à vérifier » existe dans le tableau des constats. L'outil propose, l'auditeur décide.

**Et sur la QoD.** Le filtre par défaut du rapport est `min_qod=70` : l'interface masque les détections de confiance inférieure à 70 %. Les résultats à vérifier en premier sont donc ceux qu'on ne voit pas sans baisser ce seuil — une alerte grave à 40 % de confiance reste invisible sur un écran qui semble propre.

---

## 8. Ce que cet audit relie au dossier Santélia

| Écart déjà documenté | Ce que l'audit en fait |
| --- | --- |
| **Pare-feu Proxmox désactivé** | Passe de « simplification assumée » à **constat mesuré, gravité haute, priorité P1** |
| Vérification d'empreinte désactivée côté Ansible | Reste un écart ouvert, non mesurable par scan externe |
| Adresse IPv6 globale sur les invités | Constat confirmé sur la station d'audit, à étendre aux nœuds |

**Et une justification supplémentaire pour l'automatisation.** Une correction appliquée à la main revient au prochain rebuild. Une règle de filtrage décrite dans un rôle Ansible, rejouée à chaque déploiement, garantit que la correction tient. L'audit produit le constat ; l'automatisation garantit qu'il ne réapparaît pas.

---

## Annexe A — Relevés bruts

Relevés reproduits tels qu'ils ont été obtenus. Les blocs sont des extraits : les lignes de latence et les listes d'hôtes complètes ont été écartées.

### A.1 Découverte du segment

```
Nmap done: 256 IP addresses (16 hosts up) scanned in 5.41 seconds
```

### A.2 Nœud principal — scan complet et identification

```
Nmap scan report for 192.168.1.151
Not shown: 997 closed tcp ports (reset)
PORT     STATE SERVICE VERSION
22/tcp   open  ssh     OpenSSH 9.2p1 Debian 2+deb12u5 (protocol 2.0)
111/tcp  open  rpcbind 2-4 (RPC #100000)
3128/tcp open  http    Proxmox Virtual Environment REST API 3.0
MAC Address: BC:24:11:91:2B:7B (Proxmox Server Solutions GmbH)
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

### A.3 Nœud principal — scan des 65 535 ports

```
Nmap scan report for 192.168.1.151
Not shown: 65531 closed tcp ports (reset)
PORT     STATE SERVICE
22/tcp   open  ssh
111/tcp  open  rpcbind
3128/tcp open  squid-http
8006/tcp open  wpl-analytics
MAC Address: BC:24:11:91:2B:7B (Proxmox Server Solutions GmbH)
```

**Lecture :** les services 3128 et 8006 sont nommés d'après leur numéro de port. L'identification avec l'option `-sV` montre qu'il s'agit du proxy SPICE et de l'interface d'administration.

### A.4 Nœuds secondaires — scan des 65 535 ports

```
Nmap scan report for 192.168.1.152
Not shown: 65531 closed tcp ports (reset)
PORT     STATE SERVICE
22/tcp   open  ssh
111/tcp  open  rpcbind
3128/tcp open  squid-http
8006/tcp open  wpl-analytics
MAC Address: BC:24:11:BB:44:D4 (Proxmox Server Solutions GmbH)
```

```
Nmap scan report for 192.168.1.153
Not shown: 65531 closed tcp ports (reset)
PORT     STATE SERVICE
22/tcp   open  ssh
111/tcp  open  rpcbind
3128/tcp open  squid-http
8006/tcp open  wpl-analytics
MAC Address: BC:24:11:AF:C8:7C (Proxmox Server Solutions GmbH)
```

### A.5 État du cluster — avant remédiation

```
Quorum information
------------------
Nodes:            3
Total votes:      3
Quorum:           2
Flags:            Quorate
```

### A.6 Remédiation SSH — avant et après

```
# Avant
maxauthtries 6

# Fichier de configuration
35:#MaxAuthTries 6

# Après modification
35:MaxAuthTries 3

# Valeur effectivement appliquée après redémarrage du service
maxauthtries 3
```

**Lecture :** la directive était présente mais commentée, donc inactive — le serveur appliquait sa valeur par défaut de 6. La décommenter avec la valeur 3 rend la limitation effective.

### A.7 Contrôles de non-régression

```
Nodes:            3
Total votes:      3
Quorum:           2
Flags:            Quorate
```

```
pve-a
```

```
Nmap scan report for 192.168.1.151
Not shown: 997 closed tcp ports (reset)
PORT     STATE SERVICE VERSION
22/tcp   open  ssh     OpenSSH 9.2p1 Debian 2+deb12u5 (protocol 2.0)
111/tcp  open  rpcbind 2-4 (RPC #100000)
3128/tcp open  http    Proxmox Virtual Environment REST API 3.0
MAC Address: BC:24:11:91:2B:7B (Proxmox Server Solutions GmbH)
```

**Lecture :** le cluster est toujours quorate, une nouvelle connexion SSH aboutit, et l'inventaire des ports est inchangé. La mesure n'a dégradé aucun service.

### A.8 Capacité réseau du moteur de scan

```
/usr/sbin/openvas cap_net_admin,cap_net_raw=eip
```

**Lecture :** sans cette capacité, aucun scan ne démarre.

### A.9 Premier scan — 29 minutes

```
Scan Duration  0:29 h
Scan Status    Done
Hosts scanned  1
Results        54
CVEs           1
Filter         apply_overrides=0 levels=chml min_qod=70
```

```
Proxmox Virtual Environment End of Life Detection   10.0 (Critical)  QoD 80%  general/tcp
TCP Timestamps Information Disclosure                2.6 (Low)        QoD 80%  general/tcp
Weak MAC Algorithm(s) Supported (SSH)                2.6 (Low)        QoD 80%  22/tcp
ICMP Timestamp Reply Information Disclosure          2.1 (Low)        QoD 80%  general/icmp
```

### A.10 Remédiation des algorithmes MAC — avant et après

```
# AVANT — 10 algorithmes annoncés
umac-64-etm@openssh.com        umac-128-etm@openssh.com
hmac-sha2-256-etm@openssh.com  hmac-sha2-512-etm@openssh.com
hmac-sha1-etm@openssh.com      umac-64@openssh.com
umac-128@openssh.com           hmac-sha2-256
hmac-sha2-512                  hmac-sha1

# APRÈS — 6 algorithmes annoncés
hmac-sha2-256-etm@openssh.com  hmac-sha2-512-etm@openssh.com
umac-128-etm@openssh.com       hmac-sha2-256
hmac-sha2-512                  umac-128@openssh.com
```

**Lecture :** les quatre algorithmes faibles ont disparu. La correction a été appliquée après le premier scan : on mesure l'état avant, puis on corrige.

### A.11 Second scan — 21 minutes, après remédiation

```
Scan Duration  0:21 h
Scan Status    Done
```

```
Proxmox Virtual Environment End of Life Detection   10.0 (Critical)  QoD 80%  general/tcp
TCP Timestamps Information Disclosure                2.6 (Low)        QoD 80%  general/tcp
ICMP Timestamp Reply Information Disclosure          2.1 (Low)        QoD 80%  general/icmp
```

**Lecture :** le résultat « Weak MAC Algorithm(s) Supported (SSH) » a disparu du rapport. Les deux autres résultats de gravité basse sont inchangés, ainsi que la détection de fin de vie. La remédiation est confirmée par l'outil.

---

*Documentation technique — deux scans exécutés, deux remédiations prouvées.*
