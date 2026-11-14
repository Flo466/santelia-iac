# Santélia — Configuration des trois nœuds Proxmox

> Brique 01 — architecture, prérequis, procédures et contrôles.
> Dernière mise à jour : 05/10/2026

---

## 1. Objet

Configuration de la brique **Proxmox VE HA**, chargée d'héberger les VM critiques en haute disponibilité afin de limiter les interruptions de service.

**Statut :** cluster créé et opérationnel, quorate, trois nœuds, anneaux de communication vérifiés. Réplication et groupe de haute disponibilité opérationnels.

Répond à l'exigence n° 1 du cahier des charges, priorité **Must** : « Accès continu au DPI via haute disponibilité des VM » [5].

---

## 2. Écarts assumés

Déclarés explicitement, puisque la recette doit démontrer la conformité de façon objective.

| Écart | Justification | Impact |
| --- | --- | --- |
| Trois nœuds sur **une seule machine physique** | Contrainte matérielle du laboratoire | La maquette démontre le **mécanisme** de quorum, de réplication et de bascule, pas la résistance à la panne de l'hôte |
| **Pare-feu Proxmox désactivé** | Simplification de l'environnement de test | À activer en production |
| `host_key_checking = False` côté Ansible | Environnement de test | Écart de sécurité documenté, à corriger en production |
| **Aucun swap** dans les nœuds | Comportement par défaut sur ZFS | Acceptable en laboratoire, à surveiller |
| ZFS en **RAID0, disque unique** | Un seul disque virtuel par nœud | Aucune redondance du pool, qui sert à la réplication, pas à la tolérance de panne |
| **Un seul chemin de communication de cluster** | Configuration par défaut | Pas de redondance du lien de quorum |

---

## 3. Architecture

| Nœud | Rôle | vCPU | RAM | Disque |
| --- | --- | --- | --- | --- |
| `pve-a` | Nœud principal | 2 | 4 Gio | 24 Gio |
| `pve-b` | Nœud secondaire | 2 | 4 Gio | 24 Gio |
| `pve-c` | Votant de quorum | 2 | 4 Gio | 24 Gio |

### Trois nœuds plutôt que deux

| | Trois nœuds | Deux nœuds |
| --- | --- | --- |
| Majorité stricte | **2 sur 3**, atteignable sans rien ajouter | 2 sur 2, aucune perte tolérée |
| Dispositif externe de vote | **Aucun** | QDevice obligatoire |
| Stockage partagé | **Aucun** | Export NFS nécessaire |
| Perte d'un nœud | Cluster opérationnel | Quorum perdu |

**Trois nœuds suppriment le QDevice, l'export NFS et la complexité qui va avec.**

### Les trois nœuds sur la même machine

Un processeur identique autorise l'exposition du **type CPU natif** et supprime toute contrainte de compatibilité pour la migration à chaud. Un nœud sur une seconde machine de génération différente aurait imposé un modèle de CPU conservateur, au détriment des performances.

---

## 4. Prérequis techniques

| Paramètre | Valeur | Justification |
| --- | --- | --- |
| Virtualisation imbriquée | exposée à l'invité | Sinon un nœud démarre mais **refuse de lancer ses propres machines** |
| Type de CPU de la machine | **Natif** | Sans lui, le nœud démarre mais ne peut pas virtualiser |
| Gestion mémoire dynamique | **Désactivée** | Comportement erratique dans un hyperviseur virtualisé |
| Récupération des blocs libérés | **Activée** | Le stockage thin récupère les blocs libérés |
| Démarrage automatique | **Activé** | Les nœuds reviennent après redémarrage de l'hôte |
| Cartes réseau | Deux | Une administration, une service |
| Plafond du cache ZFS | **512 Mio** par nœud | Par défaut ZFS prend la moitié de la RAM, soit la saturation à trois nœuds de 4 Gio |

---

## 5. Stockage

| Volume, hôte physique | Taille | Rôle |
| --- | --- | --- |
| Système | 69 Gio | Système, modèles de conteneurs, images ISO |
| Thin pool | 141 Gio | **Disques des machines virtuelles** |
| Sauvegardes | 60 Gio libres | Sauvegardes `vzdump` |
| Disque annexe | 245 Gio | Réservé à un autre projet, hors périmètre |

Les disques des nœuds vivent dans le **thin pool** : un disque de 24 Gio annoncé n'occupe que l'espace réellement écrit.

**Chaque nœud est installé en ZFS sur disque unique.** Ce choix ne vise pas la redondance mais le **nom du pool** : Proxmox nomme son pool système de façon identique partout, ce qui rend la **réplication native entre nœuds** possible. C'est ce mécanisme qui permet à une VM de redémarrer sur un nœud survivant.

Capacité utile constatée : environ **20,8 Gio** sur 24, ZFS réservant près de 13 % pour ses métadonnées.

---

## 6. Réseau

| Interface | Rôle |
| --- | --- |
| **Administration** | Accès web et SSH, trafic de cluster Corosync |
| **Service** | Segment L2 commun aux instances du service applicatif |

**Corosync échange ses votes en multicast sur le même segment de niveau 2.** Il ne doit **jamais** traverser un NAT, sous peine de votes fantômes et de pertes de quorum inexpliquées.

**Accès distant.** Les nœuds ne sont pas des machines indépendantes sur le réseau : l'administration passe par **rebond SSH** via l'hôte physique, en local comme à distance.

**Adressage.** Six adresses statiques : trois pour les nœuds, trois réservées aux futurs services. Toutes **exclues de la plage DHCP**.

---

## 7. Duplication d'un nœud

Le clonage duplique l'identité. Trois éléments à régénérer dans chaque clone, **avant tout test de connexion**.

| Élément | Risque si dupliqué |
| --- | --- |
| **Clés d'hôte SSH** | Rejet des connexions, alertes, échec du clustering |
| **Identifiant machine** | Comportements erratiques, traces ambiguës. **Une restauration le recopie** |
| **Adresse réseau** | Conflit, coupures intermittentes |

### Procédure, dans cet ordre

| # | Opération |
| --- | --- |
| 1 | Renommer la machine |
| 2 | **Supprimer** les clés d'hôte existantes |
| 3 | Les régénérer |
| 4 | Régénérer l'identifiant machine |
| 5 | Modifier l'adresse réseau et le fichier de résolution local |
| 6 | Redémarrer le service SSH |
| 7 | Redémarrer la machine |

### Pièges documentés

**L'outil de génération de clés ne régénère jamais une clé existante.** Il crée les clés manquantes et reste totalement silencieux quand il n'a rien à faire. Sans l'étape de suppression, le clone conserve l'identité de la source. C'est l'erreur la plus coûteuse de cette phase.

**Le provisionnement automatique annule un renommage, silencieusement.** Il réapplique le nom d'origine et le fichier de résolution à chaque démarrage, tant que la conservation du nom n'est pas explicitement demandée. Le contrôle de durabilité — redémarrer puis relire le nom — est la seule preuve que le changement a tenu.

### Clonage et restauration, deux cas différents

| | Clonage | Restauration |
| --- | --- | --- |
| Identifiant matériel | **régénéré** par l'opération | **recopié** depuis l'originale |
| Identifiant machine | unique dès le premier démarrage | identique à celui de l'originale |
| Régénération | ceinture de sécurité | **obligation** |

Sur une machine virtuelle, l'identifiant machine est **dérivé de l'identifiant matériel exposé par l'hyperviseur**. Une restauration recopiant cet identifiant, la régénération reproduit la même valeur si elle n'est pas précédée du changement.

### Symptômes d'une identité dupliquée

| Symptôme | Ce qu'il révèle |
| --- | --- |
| Le client SSH signale la clé connue sous un **autre nom ou une autre adresse** | Partage d'identité |
| La connexion s'établit puis se coupe avant toute authentification | Le service SSH accepte le TCP puis meurt faute de clé |
| Le service SSH apparaît actif | Il ne sert aucune connexion |

Le commentaire associé à chaque clé d'hôte indique le nom de la machine qui l'a générée : c'est le contrôle immédiat.

---

## 8. Vérifications réalisées

| Contrôle | Méthode | Résultat |
| --- | --- | --- |
| Virtualisation imbriquée | flag `vmx` du processeur | présent, non nul sur les trois nœuds |
| Pool ZFS | état et nom du pool système | `rpool` en ligne, **nom identique** partout |
| Espace disponible | espace libre de chaque pool | ~21,5 Gio libres par nœud |
| Cache ZFS | plafond en mémoire | 512 Mio appliqués |
| Unicité des noms | nom d'hôte | trois valeurs distinctes |
| Unicité des identités | identifiants machine et empreintes SSH | trois valeurs distinctes |
| Unicité réseau | adresses matérielles déclarées et observées | trois adresses distinctes |
| Accès automatisé | connexion SSH **sans mot de passe** | réussie sur les trois nœuds |

> Une adresse matérielle identique sur deux nœuds peut venir d'un **cache réseau obsolète**. Vider la table et réinterroger avant de conclure au conflit.
>
> Un pont réseau hérite de l'adresse matérielle de son premier port : comportement normal.

---

## 9. Cluster

Créé et assemblé le **05/10/2026**, quorate.

| Caractéristique | Valeur |
| --- | --- |
| Nom | `santelia` |
| Transport | `knet` |
| Authentification sécurisée | activée |
| Nœuds | **3** |
| Votes attendus | **3** |
| **Majorité requise** | **2** |
| État | `Quorate` |

| Étape | Date | Version de configuration |
| --- | --- | --- |
| Création sur le nœud principal | 05/10 à **09:18** | 1 |
| Jonction du 2e nœud | 05/10 à **09:27** | 2 |
| Jonction du 3e nœud | 05/10 à **09:30** | 3 |

### Piège de la jonction

La jonction échoue si le **fichier de résolution local** contient encore les informations de la source. Deux causes constatées après clonage :

| Cause | Effet |
| --- | --- |
| Adresse héritée pointant vers le nœud source | Le cluster ne détermine pas l'adresse locale et refuse la jonction |
| Nom pleinement qualifié erroné | Résolution incohérente avec le nom court |

Correction : la ligne de résolution doit associer **la bonne adresse** au **nom complet correct**, suivi du **nom court**. Contrôle : nom court, nom complet et résolution doivent concorder.

> C'est le **quatrième effet du clonage**, après les clés d'hôte, l'identifiant machine et l'adressage. Il justifie à lui seul l'automatisation de la procédure.

---

## 10. Contrôles post-création

| Contrôle | Résultat |
| --- | --- |
| État du cluster | trois nœuds, trois votes, quorum à deux, « quorate » |
| Liste des membres | trois nœuds, **un vote chacun** |
| **Anneaux Corosync** | **tous les liens connectés, aucun paquet perdu** |
| Cohérence des pools de réplication | nom identique sur les trois nœuds |
| Unicité des identifiants machine | trois valeurs distinctes |

> Le contrôle des **anneaux Corosync** est le plus souvent négligé. Il révèle les clusters qui fonctionnent en apparence et perdent leur quorum sans explication au bout de quelques semaines. À systématiser après toute opération.

---

## 11. État

| Élément | État |
| --- | --- |
| Hôte physique | opérationnel, virtualisation imbriquée active |
| Trois nœuds Proxmox | installés, identités uniques, administrables à distance |
| **Cluster** | ✅ créé le 05/10/2026, quorate, majorité à 2 |
| Anneaux de communication | ✅ tous les liens actifs |
| Réplication entre nœuds | ✅ opérationnelle, état `OK` |
| Groupe de haute disponibilité | ✅ configuré, ressource critique rattachée |

---

## 12. Recette

| Brique | Test | Résultat attendu | Preuve exigée |
| --- | --- | --- | --- |
| **HA / Proxmox VE** | simuler l'indisponibilité d'un nœud hébergeant une VM critique | service disponible ou rétabli dans le délai cible | **compte rendu + horodatage** |
| **Sauvegarde / PBS** | lancer une sauvegarde puis tester une restauration | sauvegarde exploitable, restauration réussie | **journal + preuve de restauration** |
| **Supervision / Zabbix** | vérifier la remontée et déclencher une alerte | 30 postes visibles, alerte remontée | **capture ou export + journal** |
| **IaC / Ansible** | déployer une machine de test, puis rejouer le playbook | configuration identique, sans action manuelle | **playbook + sortie + état final** |

La recette vérifie chaque brique **séparément puis conjointement**, sur l'**environnement de validation avant la mise en production**.

### Indicateurs proposés

La perte maximale est scindée en deux : la réplication couvre la panne matérielle, la sauvegarde couvre le retour à un état antérieur. Un chiffre unique ne peut pas décrire les deux risques.

| Domaine | Indicateur | Cible proposée |
| --- | --- | --- |
| Disponibilité | Perte en cas de panne matérielle d'un nœud | < 15 min, portée par la réplication |
| Sauvegarde | Perte de récupération en cas de sinistre logique | < 24 h 30, portée par la sauvegarde et sa copie |
| Sauvegarde | Temps de restauration d'une VM critique | < 30 min |
| Ansible | Temps de déploiement ou de reconfiguration | < 15 min |
| Zabbix | Réactivité des alertes vers la DSI | < 2 min |

---

## 13. Exigences et priorités

| # | Exigence | Priorité | Brique |
| --- | --- | --- | --- |
| 1 | Accès continu au DPI via haute disponibilité des VM | **Must** | Proxmox VE HA |
| 2 | Sauvegarde 3-2-1 et restauration | **Must** | PBS et copie secondaire |
| 3 | Automatisation des serveurs et applications | **Must** | Ansible et playbooks |
| 4 | Supervision centralisée des 30 postes | Should | Zabbix |

Les exigences **Must** sont traitées en priorité, en vérifiant que les options retenues restent compatibles avec l'enveloppe de 15 000 €.

---

*Les identifiants techniques détaillés — adressage complet, empreintes, identifiants machine — sont conservés dans une annexe interne non jointe.*

*Source : cahier des charges Santélia, Bloc 2 AIS — Groupe 2.*
