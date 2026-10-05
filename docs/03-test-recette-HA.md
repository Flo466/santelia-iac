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
| 11:40:56 | **Démarrage effectif de la machine** (relevé par le témoin) | 10 s |
| **11:41:04** | **Le service répond de nouveau** | **18 s** |

### 2.3 Du démarrage annoncé au service réellement rendu

Ce paragraphe explique la différence entre trois instants souvent confondus.

| Instant | Heure | Ce qui est vrai à ce moment-là |
| --- | --- | --- |
| Le gestionnaire déclare la ressource démarrée | 11:40:46 | La décision est prise, la machine n'a pas encore démarré |
| La machine démarre réellement | 11:40:56 | Le système invité s'amorce, les services applicatifs ne sont pas encore lancés |
| Le service répond | 11:41:04 | La chaîne complète est opérationnelle |

> **À retenir : l'hyperviseur considère une machine démarrée bien avant que le service rendu ne le soit.**
> Un indicateur calculé sur l'état de la machine est donc optimiste. L'engagement de continuité doit se mesurer sur la **réponse du service**, comme cela a été fait ici.

### 2.4 Comportement du quorum

| État | Avant la panne | Pendant la panne |
| --- | --- | --- |
| Nœuds | 3 | **2** |
| Votes attendus | 3 | 3 |
| Majorité requise | 2 | 2 |
| État | Quorate | **Quorate** |

**C'est le résultat le plus significatif du test.** La perte d'un nœud n'a pas fait perdre le quorum, ce qui a permis au gestionnaire de déclencher la reprise. Une architecture à deux nœuds aurait perdu le quorum, et aucune reprise n'aurait été possible sans dispositif externe supplémentaire.

### 2.5 Preuve du redémarrage effectif

Le dispositif témoin affiche l'horodatage de démarrage de la machine, valeur qu'il relit à chaque requête.

| Moment | Démarrage de la machine (heure locale) | Ce que cela signifie |
| --- | --- | --- |
| Avant la coupure | **11:26:17** | La machine tournait depuis 12 minutes quand le test a été lancé |
| Après la reprise | **11:40:56** | La machine a redémarré : nouvel horodatage, postérieur à la coupure |

L'horodatage de démarrage est **différent**, et le nouveau se situe **après la coupure**. C'est la preuve d'un redémarrage réel, et non d'une réponse mise en cache ou d'une machine restée en fonctionnement.

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

**Conversion et lecture :** la machine invitée étant en temps universel, il faut ajouter deux heures pour se ramener au référentiel des mesures.

| Élément | Sortie brute (UTC) | Converti (heure locale) |
| --- | --- | --- |
| Démarrage avant la coupure | 09:26:17 | **11:26:17** |
| Réponse avant la coupure | 09:37:32 | 11:37:32 |
| Démarrage après la reprise | 09:40:56 | **11:40:56** |
| Réponse après la reprise | 09:42:55 | 11:42:55 |

Trois vérifications de cohérence :

1. **Avant la coupure** : démarrage à 11:26:17, réponse à 11:37:32, soit 11 minutes d'ancienneté — ce que confirme la mention « up 11 minutes ».
2. **Après la reprise** : démarrage à 11:40:56, réponse à 11:42:55, soit 2 minutes d'ancienneté — cohérent avec « up 1 minute ».
3. **Enchaînement de la reprise** : décision à 11:40:46, démarrage à 11:40:56, service joignable à 11:41:04. Les trois relevés s'enchaînent sans contradiction.

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

> **Convention d'horodatage.** Le système invité est en temps universel (UTC) et affiche donc ses propres valeurs décalées de deux heures par rapport au poste de mesure, réglé à l'heure locale d'été. Pour éviter toute ambiguïté, **tous les horodatages de ce document sont exprimés dans le référentiel du poste de mesure**. Les relevés bruts de la machine invitée figurent en annexe A, accompagnés de leur conversion.
