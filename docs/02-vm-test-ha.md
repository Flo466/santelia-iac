# Santélia — VM critique `vm-test-ha` : construction et provisionnement

> Document rendable — décrit la mise en place de la machine de test de la brique HA.
> Les mesures de disponibilité et le compte rendu de recette sont dans le document « Santélia — Test de recette HA : simulation de panne de nœud ».
> TP Bloc 2 AIS, Groupe 2 (Florent, Youcef, Robin)

---

## 1. Objet de ce document

Ce document décrit la **construction** d'une machine virtuelle minimale destinée à servir d'objet de test pour la brique de haute disponibilité.

Il ne traite ni des mesures ni du compte rendu de recette, qui font l'objet d'un document distinct.

Le cahier des charges répartit les rôles ainsi : Proxmox VE HA traite la continuité des VM, Proxmox Backup Server la sauvegarde et la restauration, Zabbix la supervision, et Ansible l'automatisation et la standardisation. La préparation de la HA et l'intégration des VM critiques constituent la phase 2 du planning, avec pour jalon une **HA opérationnelle sur l'environnement cible**.

**Pourquoi une machine minimale plutôt que le service réel :** elle permet de valider le mécanisme complet sans introduire d'autres variables. Une fois le mécanisme prouvé, le contenu pourra être remplacé par le service réel sans retoucher au mécanisme.

---

## 2. Approche retenue : image cloud et provisionnement automatique

Plutôt qu'une installation interactive depuis une image d'installation, une **image cloud** et un mécanisme de **provisionnement automatique** ont été utilisés.

| | Image d'installation | Image cloud |
| --- | --- | --- |
| Nature | Support d'installation | Disque système **déjà installé** |
| Format | `.iso` | `.qcow2` |
| Au démarrage | Un programme d'installation pose des questions | Le système démarre directement |
| Utilisateur, réseau | Configurés manuellement | Définis par **données de configuration** |
| Reproductibilité | Faible | **Élevée** |

### Principe du provisionnement automatique

Un service embarqué dans l'image s'exécute au **premier démarrage**. Il lit des instructions fournies par l'hyperviseur et les applique : création de l'utilisateur, dépôt d'une clé d'authentification, configuration réseau. Il ne s'exécute **qu'une seule fois**, puis se marque comme terminé.

Côté hyperviseur, ces instructions ne sont pas rédigées à la main : elles se renseignent sous forme d'**options dans la configuration de la machine**, et un petit périphérique de type CD-ROM est généré automatiquement pour les transporter jusqu'à l'invité.

**Intérêt pour le projet :** la machine est décrite en **données** plutôt que configurée manuellement. C'est la même démarche que l'automatisation attendue en phase de standardisation, où les configurations des serveurs et des applications doivent être automatisées et documentées.

---

## 3. Vérifications préalables

Trois contrôles avant toute création.

| Contrôle | Objet |
| --- | --- |
| Adresse réseau disponible | Vérifier qu'aucune machine ne répond, et que l'adresse est hors de la plage d'attribution automatique |
| Clé d'authentification présente sur le nœud | C'est elle qui sera injectée dans la machine |
| Numéro de machine libre | Dans un cluster, les numéros sont **uniques à l'échelle du cluster**, pas par nœud |

> Les numéros déjà attribués à d'autres projets hébergés sur le même hôte physique doivent être évités. Prévoir des plages distinctes par projet.

---

## 4. Création de la machine

### 4.1 Récupération de l'image cloud

L'image est récupérée depuis les dépôts officiels de la distribution.

**Contrôle :** le fichier doit faire **plusieurs centaines de mégaoctets**. Une taille de quelques kilo-octets indique une page d'erreur et non une image.

### 4.2 Création de la coquille

Une machine est créée **sans disque**, avec les paramètres suivants.

| Paramètre | Justification |
| --- | --- |
| Mémoire fixe, gestion dynamique **désactivée** | La gestion mémoire dynamique est erratique dans un hyperviseur lui-même virtualisé |
| Interface réseau sur un pont **existant sur tous les nœuds** | Indispensable pour que la machine puisse redémarrer sur un autre nœud après une reprise |
| Agent invité activé | Ouvre le canal de communication avec l'agent (voir § 6) |
| Démarrage automatique activé | La machine revient après un redémarrage de l'hôte |

À ce stade, la machine est une **coquille vide** : aucun disque, aucune image de démarrage.

### 4.3 Import de l'image comme disque

L'image est importée puis **raccordée** à la machine.

> Le retour de l'import indique que le disque est **importé mais pas encore raccordé**. C'est une étape intermédiaire volontaire.

### 4.4 Agrandissement du disque

Les images cloud sont volontairement **minuscules** — deux à trois gigaoctets — afin que la taille finale soit choisie au déploiement.

> **L'agrandissement est obligatoire.** Sans lui, la machine démarre mais toute installation de paquet échoue rapidement par manque d'espace.

Taille retenue : **8 Gio**, avec option de récupération de l'espace libéré activée.

### 4.5 Disque d'amorçage, ordre de démarrage et console série

| Option | Rôle |
| --- | --- |
| Disque de provisionnement en position secondaire | Crée le périphérique qui transporte les instructions jusqu'à la machine |
| Ordre de démarrage forcé sur le disque | Sans disque au moment de la création, l'hyperviseur place le réseau en premier |
| Console série activée | **Les images cloud n'ont pas d'affichage graphique.** Elles écrivent sur la console série : sans cette option, la console reste noire et on croit à une panne |

### 4.6 Renseignement de la configuration

| Élément | Valeur |
| --- | --- |
| Utilisateur invité | Compte d'administration non privilégié |
| Clé d'authentification | Injectée depuis le fichier de clés autorisées du nœud |
| Adresse réseau | Adresse statique du réseau d'administration |
| Serveur de noms | Passerelle du réseau |

L'utilisation du chemin vers le fichier de clés autorisées évite de recopier une clé à la main : l'hyperviseur lit le fichier et l'injecte.

### 4.7 Contrôle de la configuration

Le contrôle consiste à vérifier que figurent bien : le disque **avec sa taille finale** — preuve que l'agrandissement a été appliqué —, le périphérique de provisionnement, l'ordre de démarrage, la console série, l'utilisateur et l'adresse réseau.

---

## 5. Contrôles après démarrage

Un délai de **30 à 60 secondes** est nécessaire au premier démarrage, le temps que le provisionnement automatique crée l'utilisateur, dépose la clé et applique la configuration réseau.

| Vérification | Résultat obtenu | Interprétation |
| --- | --- | --- |
| Réponse réseau | Réponses en 2 à 4 ms | La machine communique |
| Connexion à distance | Réussie **sans mot de passe** | L'utilisateur a été créé **et** la clé injectée |
| Empreinte de la clé d'hôte | Aucune autre machine connue sous cette adresse | Identité propre, aucun partage |
| Espace disque | **7,7 Gio** sur la partition racine | L'agrandissement et l'extension de partition ont fonctionné |
| État du provisionnement | Terminé, sans erreur | Configuration appliquée intégralement |
| Agent invité | **Inactif** | ⚠️ Voir § 6 |

**Conclusion :** le déploiement d'une machine virtuelle **sans aucune installation interactive** est validé. Aucune question posée, aucune intervention dans la console.

---

## 6. Point de vigilance — agent invité

**Constat.** L'activation de l'agent dans la configuration de la machine ouvre le **canal** de communication, mais **n'installe pas le logiciel dans l'invité**. L'image cloud de la distribution ne l'embarque pas par défaut, d'où un état inactif constaté après démarrage.

**Conséquence.**

| Sans agent | Avec agent |
| --- | --- |
| L'hyperviseur ne connaît pas l'adresse réseau de la machine | L'adresse est remontée automatiquement |
| Les arrêts de la machine peuvent aboutir à un délai d'attente dépassé | Arrêt propre fiable |
| La supervision ne peut pas exploiter les informations invitées | Inventaire et mesures disponibles |

**Mesure appliquée.** Installation et activation du logiciel dans l'invité, puis vérification depuis l'hyperviseur que la communication est établie et que les informations système remontent.

**Réserve.** Non bloquant pour un redémarrage sur un autre nœud, qui fonctionne avec ou sans agent, mais **nécessaire** pour les opérations d'arrêt propre et pour la supervision.

---

## 7. Dispositif témoin installé dans la machine

Pour que la vérification de disponibilité porte sur **le service rendu** et non sur l'état de la machine, un serveur web minimal est installé, accompagné d'une **page dynamique**.

| Point | Pourquoi |
| --- | --- |
| Service **réel** plutôt qu'un script isolé | Il possède un état vérifiable et un comportement de production |
| Activation au démarrage | **Sans cette activation, le service ne redémarrerait pas après une reprise et la vérification perdrait sa valeur** |
| Page **dynamique** plutôt que statique | La page lit l'état réel de la machine à chaque requête : horodatage de démarrage, heure de réponse, ancienneté. Une page statique afficherait indéfiniment la même valeur et ne prouverait rien |

> C'est une distinction essentielle pour un engagement de continuité : l'hyperviseur considère une machine démarrée bien avant que le service rendu ne le soit.

---

## 8. Reproductibilité de la construction

| Élément | Comportement constaté |
| --- | --- |
| Clé d'authentification | Injectée automatiquement au provisionnement |
| Identifiant machine | Dérivé de l'identifiant unique exposé par l'hyperviseur : **unique par construction** |
| Configuration réseau | Appliquée par le provisionnement automatique |
| Disque | Raccordé et agrandi selon la taille choisie |

Cette machine est **reproductible à l'identique** : les étapes décrites ici constituent déjà une configuration décrite en données, et non une suite d'opérations manuelles.

**Fait notable constaté pendant la mise au point :** une configuration appliquée manuellement dans la machine invitée, après coup, n'est **pas reproductible** et peut être perdue lors d'une reprise ou d'une synchronisation de disque. Ce constat est détaillé et exploité dans le document de recette associé.

---

## 9. Suite donnée

| Étape | Objet | Document |
| --- | --- | --- |
| Réplication vers un second nœud | Permettre au nœud survivant de retrouver le disque | Document de configuration du cluster |
| Déclaration en ressource haute disponibilité | Confier la surveillance de la machine au gestionnaire | Document de configuration du cluster |
| **Simulation de panne et mesure** | Vérifier la reprise et le délai de rétablissement du service | **Document « Test de recette HA »** |
| Standardisation | Reproduire cette construction par playbook plutôt qu'à la main | Phase de standardisation |

---

## 10. Situation dans le planning

| Phase | Contenu | Jalon | Statut |
| --- | --- | --- | --- |
| 2. Haute disponibilité | Préparation de la HA et intégration des VM critiques | **HA opérationnelle sur l'environnement cible** | ✅ Objet de test en place |
| 3. Sauvegarde | Proxmox Backup Server et stratégie 3-2-1 | Sauvegardes + premier test de restauration | À venir |
| 4. Supervision | Zabbix, équipements et les 30 postes | Supervision centralisée et alertes | À venir |
| 5. IaC | Playbooks Ansible et standardisation | Playbooks validés et documentés | À venir |

---

_Source : cahier des charges Santélia, Bloc 2 AIS — Groupe 2._
