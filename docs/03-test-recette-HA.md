# Santélia — Test de recette HA : simulation de panne de nœud

> Brique testée : Proxmox VE HA — « Héberger les VM critiques dans une architecture de haute disponibilité afin de limiter les interruptions »
> Exigence associée : n° 1, « Accès continu au DPI via haute disponibilité des VM » — priorité **Must**
> TP Bloc 2 AIS, Groupe 2 (Florent, Youcef, Robin) — 05/10/2026

---

## 1. Objet et cadre

La recette associée à cette brique demande de **simuler l'indisponibilité d'un nœud hébergeant une VM critique**, avec pour résultat attendu que « le service reste disponible ou est rétabli dans le délai cible », et pour preuve un « **compte rendu + horodatage** ».

L'indicateur contractuel est un **retour du service critique dans un délai cible de 5 à 10 minutes**.

### Architecture de test

| Élément | Valeur |
| --- | --- |
| Cluster | 3 nœuds Proxmox VE imbriqués, quorum à 2 sur 3 |
| Objet de test | Machine virtuelle minimale, provisionnée par image cloud et cloud-init |
| Système invité | Debian 13 |
| Dispositif témoin | Serveur web + page dynamique affichant l'horodatage de démarrage |
| Protection | Réplication ZFS vers un second nœud, intervalle 15 minutes |
| Gestion de la disponibilité | Ressource HA rattachée à un groupe à priorités de nœuds |

### Méthode de mesure

Une **surveillance en tâche de fond** interroge le service témoin chaque seconde et relève l'instant exact de la coupure, celui du rétablissement, et calcule la durée. La mesure est ainsi indépendante de toute observation manuelle.

Le témoin est une **page dynamique** qui lit l'état réel de la machine à chaque requête : heure de démarrage, heure de réponse, ancienneté. Une page statique ne permettrait pas de distinguer un redémarrage effectif d'une réponse servie depuis un cache.

> Toutes les mesures utilisent **une seule horloge de référence**. Le système invité est en UTC alors que le poste de travail est en heure locale : mélanger les deux sources fausserait tout calcul de durée.

---

## 2. Résultats

### 2.1 Synthèse

| Indicateur | Cible | Mesure | Statut |
| --- | --- | --- | --- |
| **Retour du service critique** | **5 à 10 min** | **2 min 24 s** | ✅ **Conforme** |
| Durée d'indisponibilité totale | — | 144 s | — |
| Détection de la perte du nœud | — | 6 s | — |
| Décision de reprise par le gestionnaire | — | 2 min 06 s | — |
| Service opérationnel après reprise | Doit répondre | Page CGI fonctionnelle | ✅ |
| Quorum pendant la panne | Rester opérationnel | Maintien de 2 votes sur 3 | ✅ |

**La cible est tenue avec une marge importante** : 2 min 24 s mesurées contre 5 à 10 minutes demandées.

### 2.2 Chronologie détaillée

| Heure | Événement | Écart |
| --- | --- | --- |
| 11:38:40 | Coupure brutale du nœud hébergeur (simulation de panne) | — |
| 11:38:46 | Le nœud est détecté comme injoignable | **6 s** |
| 11:39:36 | La ressource est déclarée perdue, séquence de sécurisation engagée | 50 s |
| 11:40:46 | Décision de reprise : redémarrage annoncé sur le nœud survivant | 70 s |
| **11:41:04** | **Le service répond de nouveau** | **18 s** |

### 2.3 Point de méthode essentiel

Le gestionnaire annonce la ressource « démarrée » à **11:40:46**, mais le service n'est réellement joignable qu'à **11:41:04**. Ces **18 secondes** correspondent au démarrage du système invité puis à celui des services applicatifs.

> **À retenir : l'hyperviseur considère une machine démarrée bien avant que le service rendu ne le soit.**
> Un indicateur calculé sur l'état de la machine est optimiste. L'engagement de continuité doit se mesurer sur la **réponse du service**, comme cela a été fait ici.

### 2.4 Comportement du quorum

| État | Avant la panne | Pendant la panne |
| --- | --- | --- |
| Nœuds | 3 | **2** |
| Votes attendus | 3 | 3 |
| Majorité requise | 2 | 2 |
| État | Quorate | **Quorate** |

**C'est le résultat le plus significatif du test.** La perte d'un nœud n'a pas fait perdre le quorum, ce qui a permis au gestionnaire de déclencher la reprise. Une architecture à deux nœuds aurait perdu le quorum, et aucune reprise n'aurait été possible sans dispositif externe supplémentaire.

### 2.5 Preuve de redémarrage effectif

| Moment | Horodatage de démarrage de la machine |
| --- | --- |
| Avant la panne | 09:26:17 |
| **Après la reprise sur le nœud survivant** | **09:40:56** |

L'horodatage de démarrage est **différent**, ce qui atteste d'un redémarrage réel et non d'une simple réponse mise en cache. Cette valeur est fournie par le dispositif témoin lui-même, à chaque requête.

---

## 3. Points de vigilance identifiés

Ces points ont été mis en évidence lors de la mise au point du montage. Ils conditionnent la réussite d'une reprise et sont à intégrer à la procédure d'exploitation.

### 3.1 Volume d'amorçage local non répliqué

**Constat.** Le volume d'amorçage généré localement par l'hyperviseur pour le provisionnement automatique **n'est pas transmis par la réplication**, contrairement au disque système. Sa présence sur le nœud défaillant ne suffit pas.

**Conséquence.** Un démarrage peut échouer intégralement après une attente complète, avec pour seul message l'absence du volume attendu.

**Mesure appliquée.** Le volume d'amorçage n'est plus nécessaire après provisionnement complet de la machine : il peut être détaché, la machine ne dépendant alors que du disque répliqué.

**Piste de production.** Le **stockage partagé**, qui expose les mêmes volumes à tous les nœuds, supprime cette classe de problème par construction.

**Réserve à documenter.** Le détachement du volume d'amorçage retire la possibilité de modifier la configuration invitée par le mécanisme de provisionnement automatique. Ce compromis est acceptable pour une machine déjà provisionnée.

### 3.2 Fenêtre de perte de données liée à l'intervalle de réplication

**Constat.** Une configuration appliquée **manuellement après la dernière synchronisation** n'est pas présente sur la copie répliquée. Lors d'une reprise, elle est donc absente sur le nœud d'accueil.

**Conséquence.** Le service redémarre, mais dans un état antérieur. La fenêtre de perte correspond à l'intervalle de réplication, soit **15 minutes** dans notre configuration : c'est la définition même du **RPO**.

**Mesure appliquée.** **Forcer une synchronisation immédiatement avant toute coupure volontaire.** Cette opération a été validée : lors du test de référence, le service témoin s'est retrouvé **intact et fonctionnel** après la reprise.

**Effet induit à connaître.** La désactivation du mécanisme de réplication avant un test **élargit** la fenêtre de perte au lieu de la réduire. Elle doit être évitée.

### 3.3 Séquencement des interventions

**Constat.** Une intervention effectuée pendant que le gestionnaire de disponibilité traite encore un incident place la ressource dans un état de sécurisation anti-double-exécution, dans lequel le redémarrage est volontairement refusé.

**Explication.** Ce comportement est **attendu et indispensable** : il garantit qu'une même machine ne peut pas se retrouver en fonctionnement simultané sur deux nœuds. Il se résout de lui-même une fois la séquence terminée.

**Règle d'exploitation.** **Une seule opération de disponibilité à la fois.** Tant que la ressource se trouve dans un état transitoire, aucune intervention ne doit être engagée.

**Corollaire pour la mesure.** Les essais de reprise doivent être espacés et l'état de la ressource vérifié comme **stabilisé** avant toute nouvelle manipulation.

---

## 4. Conclusion

### 4.1 Ce que le test démontre

| Affirmation | Preuve |
| --- | --- |
| La reprise automatique sur un autre nœud fonctionne | Reprise déclenchée et aboutie sans intervention manuelle |
| **Le service est réellement rétabli** | Page témoin fonctionnelle après la reprise |
| **La cible de rétablissement est tenue** | **2 min 24 s** contre 5 à 10 min demandées |
| Le quorum survit à la perte d'un nœud | 2 votes sur 3 maintenus |
| Le redémarrage est prouvé | Horodatage de démarrage distinct, fourni par le témoin |
| La perte de données peut être maîtrisée | Synchronisation forcée avant coupure, service intact après reprise |

### 4.2 Cohérence avec la stratégie du projet

Le cahier des charges retient Proxmox VE HA comme brique de continuité de service, en réponse à « l'accès continu au DPI » et à la réduction du temps d'interruption. L'incident de référence du projet — une panne de plus de six heures bloquant la prise de rendez-vous sur un site — est ici ramené à **2 min 24 s**.

### 4.3 Lien avec l'automatisation

Les points de vigilance des sections 3.1 et 3.2 ont une cause commune : une configuration **appliquée manuellement** sur un nœud, sans possibilité de rejeu. Elle est perdue dès qu'une reprise ou une synchronisation de disque intervient.

Ce constat est la justification expérimentale de l'exigence suivante : « automatiser et standardiser les configurations des serveurs et des applications », avec protection des secrets. Une configuration décrite et rejouable ne peut pas être perdue de cette manière.

Ce résultat relie directement deux briques du projet et constitue un argument à présenter en recette.

---

## 5. Suites à donner

| Suite | Objet |
| --- | --- |
| Restitution de la ressource sur son nœud prioritaire | Vérifier le retour à trois nœuds et la stabilité |
| Nouveau test après standardisation | Démontrer que la configuration survit à une reprise grâce au rejeu |
| Mesure du RPO réel | Chronométrer précisément la fenêtre de perte avec synchronisation forcée |
| Second chemin de communication de cluster | Écart à documenter, pour supprimer le point unique |
| Test de recette suivant | Sauvegarde et restauration (brique PBS) — « journal de sauvegarde + preuve de restauration » |

---

## 6. Rappel des cibles de recette

| Brique | Test | Résultat attendu | Preuve | Statut |
| --- | --- | --- | --- | --- |
| **HA / Proxmox VE** | Simuler l'indisponibilité d'un nœud hébergeant une VM critique | Le service reste disponible ou est rétabli dans le délai cible | **Compte rendu + horodatage** | ✅ **2 min 24 s** |
| Sauvegarde / PBS | Lancer une sauvegarde puis tester une restauration | Sauvegarde exploitable et restauration réussie | Journal de sauvegarde + preuve de restauration | À faire |
| Supervision / Zabbix | Vérifier la remontée et déclencher une alerte | Les 30 postes visibles, alerte remontée | Capture/export Zabbix + journal | À faire |
| IaC / Ansible | Déployer ou reconfigurer une machine de test, puis rejouer le playbook | Configuration identique et standardisée, sans action manuelle | Playbook + sortie d'exécution + état final | À faire |

> La recette vérifie chaque brique **séparément puis leur fonctionnement conjoint**, et les tests sont réalisés sur l'**environnement de validation avant mise en production**.

---

## Annexe A — Preuves brutes horodatées

> Cette annexe constitue la **preuve horodatée** exigée par la recette. Les relevés sont reproduits tels quels, sans retraitement.

### A.1 Relevé de la surveillance du service témoin

Surveillance automatique, interrogée chaque seconde. Extrait du journal de mesure :

```
SURVEILLANCE 11:37:41
COUPURE : 11:38:40
RETOUR DU SERVICE : 11:41:04
DUREE INTERRUPTION : 144 secondes
```

**Lecture :** la coupure est détectée à 11:38:40, le service répond de nouveau à 11:41:04, soit **144 secondes d'indisponibilité**.

### A.2 Journal du gestionnaire de disponibilité

Extrait du journal du gestionnaire, relevé sur le nœud survivant :

```
Oct 05 11:38:46  node 'pve-a': state changed from 'online' => 'unknown'
Oct 05 11:39:36  service 'vm:100': state changed from 'started' to 'fence'
Oct 05 11:39:36  node 'pve-a': state changed from 'unknown' => 'fence'
Oct 05 11:40:46  node 'pve-a': state changed from 'fence' => 'unknown'
Oct 05 11:40:46  service 'vm:100': state changed from 'fence' to 'recovery'
Oct 05 11:40:46  recover service 'vm:100' from fenced node 'pve-a' to node 'pve-b'
Oct 05 11:40:46  service 'vm:100': state changed from 'recovery' to 'started'  (node = pve-b)
```

**Lecture :** le nœud est détecté injoignable en 6 secondes. La ressource est déclarée perdue puis la reprise est engagée et aboutie sans intervention manuelle.

### A.3 État du cluster pendant la panne

```
Quorum information
------------------
Nodes:            3
Quorum:           2
Flags:            Quorate

Membership information
----------------------
   Nodeid      Votes Name
        1          1 pve-a
        2          1 pve-b
        3          1 pve-c
```

**Lecture :** trois nœuds déclarés, majorité requise de 2 votes, état **quorate** maintenu pendant l'indisponibilité d'un nœud.

### A.4 Réponses du service témoin, avant et après la reprise

**Avant la panne :**

```
<h1>vm-test-ha</h1>
<p>Boot: 2026-10-05 09:26:17</p>
<p>Repondu le: 2026-10-05 09:37:32 UTC</p>
<p>Uptime: up 11 minutes</p>
```

**Après la reprise :**

```
<h1>vm-test-ha</h1>
<p>Boot: 2026-10-05 09:40:56</p>
<p>Repondu le: 2026-10-05 09:42:55 UTC</p>
<p>Uptime: up 1 minute</p>
```

**Lecture :** l'horodatage de démarrage passe de **09:26:17** à **09:40:56**, ce qui atteste d'un redémarrage effectif. L'ancienneté passe de 11 minutes à 1 minute, cohérente avec le nouvel horodatage. Le service répond, ce qui prouve que la configuration a survécu à la reprise.

### A.5 État de la ressource après la reprise

```
service vm:100 (pve-b, started)
     VMID NAME                 STATUS     MEM(MB)    BOOTDISK(GB) PID
      100 vm-test-ha           running    1024               8.00 26922
```

**Lecture :** la ressource est gérée par le mécanisme de disponibilité, la machine tourne sur le nœud survivant avec un identifiant de processus neuf.

### A.6 Synchronisation forcée avant la coupure

```
JobID      Enabled    Target          LastSync              NextSync   Duration   FailCount State
100-0      Yes        local/pve-b     2026-10-05_11:37:18   11:45:00   2.96 s     0         OK
```

**Lecture :** la synchronisation a été forcée immédiatement avant la coupure, avec `FailCount 0` et un état `OK`. C'est cette opération qui garantit que le service témoin se retrouve intact sur le nœud d'accueil.

---

_Source : cahier des charges Santélia, Bloc 2 AIS — Groupe 2._
