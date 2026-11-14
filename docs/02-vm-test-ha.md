# Santélia — Machine critique : construction et provisionnement

> Brique 01 — socle du service rendu par la haute disponibilité.
> Construite comme banc de test, elle est désormais la machine de production du service.

---

## 1. Ce que produit ce document

Une machine virtuelle minimale, apte à servir d'objet de test à la haute disponibilité.

**Pourquoi une machine minimale.** Elle valide le mécanisme complet sans introduire d'autres variables. Une fois le mécanisme prouvé, le contenu est remplacé sans retoucher au mécanisme : le dispositif s'appuie sur l'**identifiant** de la machine, pas sur son nom.

---

## 2. Image cloud plutôt qu'installation

| | Image d'installation | Image cloud |
| --- | --- | --- |
| Nature | Support d'installation | Disque système **déjà installé** |
| Format | `.iso` | `.qcow2` |
| Au démarrage | Un programme pose des questions | Le système démarre directement |
| Utilisateur, réseau | Configurés à la main | Définis par **données de configuration** |
| Reproductibilité | Faible | **Élevée** |

Un service embarqué s'exécute au **premier démarrage**, lit les instructions fournies par l'hyperviseur et les applique : utilisateur, clé d'authentification, réseau. Il ne s'exécute **qu'une fois**.

Côté hyperviseur, ces instructions sont des **options de configuration**. Un petit périphérique de type CD-ROM est généré automatiquement pour les transporter.

**La machine est décrite en données, pas configurée à la main.** C'est déjà la démarche attendue en phase de standardisation.

---

## 3. Vérifications préalables

| Contrôle | Objet |
| --- | --- |
| Adresse réseau disponible | Aucune réponse, et hors plage d'attribution automatique |
| Clé d'authentification sur le nœud | C'est elle qui sera injectée |
| Numéro de machine libre | **Unique à l'échelle du cluster**, pas par nœud |

---

## 4. Construction

| Étape | Opération | Point déterminant |
| --- | --- | --- |
| 1 | Récupération de l'image cloud | Le fichier doit peser **plusieurs centaines de mégaoctets**. Quelques kilo-octets = page d'erreur |
| 2 | Création de la coquille, **sans disque** | Pont réseau **présent sur tous les nœuds**, sinon la reprise ailleurs est impossible |
| 3 | Import de l'image, puis raccordement | L'import seul ne raccorde pas le disque : étape intermédiaire volontaire |
| 4 | Agrandissement du disque | **Obligatoire.** Sans lui, toute installation de paquet échoue par manque d'espace |
| 5 | Disque d'amorçage et ordre de démarrage | Sans disque à la création, l'hyperviseur place le réseau en premier |
| 6 | Console série | **Les images cloud n'ont pas d'affichage graphique.** Sans elle, la console reste noire et on croit à une panne |
| 7 | Configuration de provisionnement | Utilisateur, chemin du fichier de clés autorisées, adresse statique, serveur de noms |

| Paramètre de la machine | Valeur | Raison |
| --- | --- | --- |
| Mémoire dynamique | **Désactivée** | Erratique dans un hyperviseur déjà virtualisé |
| Agent invité | Activé | Ouvre le canal de communication |
| Démarrage automatique | Activé | Retour après redémarrage de l'hôte |
| Récupération des blocs libérés | Activée | Le stockage thin récupère l'espace |

Taille retenue : **8 Gio**.

---

## 5. Contrôles après démarrage

Compter **30 à 60 secondes** au premier démarrage, le temps que le provisionnement crée l'utilisateur, dépose la clé et applique le réseau.

| Vérification | Résultat obtenu | Interprétation |
| --- | --- | --- |
| Réponse réseau | 2 à 4 ms | La machine communique |
| Connexion à distance | réussie **sans mot de passe** | Utilisateur créé **et** clé injectée |
| Empreinte de la clé d'hôte | aucune autre machine sous cette adresse | Identité propre |
| Espace disque | **7,7 Gio** sur la racine | Agrandissement et extension de partition appliqués |
| État du provisionnement | terminé, sans erreur | Configuration appliquée intégralement |
| Agent invité | **installé et actif** | Voir § 6 |

**Déploiement sans aucune installation interactive : validé.** Aucune question posée, aucune intervention en console.

---

## 6. Point de vigilance — agent invité

| Sans agent | Avec agent |
| --- | --- |
| L'hyperviseur ignore l'adresse réseau de la machine | Adresse remontée automatiquement |
| Les arrêts aboutissent à un délai d'attente dépassé | Arrêt propre fiable |
| La supervision n'exploite aucune information invitée | Inventaire et mesures disponibles |

**Activer l'agent dans la configuration ouvre le canal, il n'installe pas le logiciel.** L'image cloud de la distribution ne l'embarque pas : l'état inactif constaté après démarrage vient de là.

**Mesure appliquée.** Installation et activation dans l'invité, puis contrôle depuis l'hyperviseur que la communication est établie et que les informations système remontent.

**Non bloquant** pour un redémarrage sur un autre nœud, qui fonctionne avec ou sans agent. **Nécessaire** aux arrêts propres et à la supervision.

---

## 7. Dispositif témoin

Pour que la vérification porte sur **le service rendu** et non sur l'état de la machine.

| Choix | Pourquoi |
| --- | --- |
| Service **réel** plutôt qu'un script isolé | État vérifiable, comportement de production |
| Activation au démarrage | Sans elle, le service ne revient pas après reprise et la vérification perd sa valeur |
| Page **dynamique** plutôt que statique | Elle relit l'état réel à chaque requête : démarrage, heure de réponse, ancienneté. Une page statique afficherait indéfiniment la même valeur |

**L'hyperviseur considère une machine démarrée bien avant que le service rendu ne le soit.** C'est la distinction sur laquelle repose toute la mesure de recette.

---

## 8. Reproductibilité

| Élément | Comportement constaté |
| --- | --- |
| Clé d'authentification | Injectée au provisionnement |
| Identifiant machine | Dérivé de l'identifiant matériel exposé par l'hyperviseur. **Unique par construction au clonage** |
| Configuration réseau | Appliquée par le provisionnement |
| Disque | Raccordé et agrandi selon la taille choisie |

**Clonage.** L'opération régénère l'identifiant matériel, donc chaque clone dispose du sien dès le premier démarrage. La régénération de l'identifiant machine y est une **ceinture de sécurité**.

**Restauration.** Elle recopie la configuration, identifiant matériel compris. La machine restaurée porte donc l'identifiant machine de l'originale : la régénération devient une **obligation**, et doit être précédée du changement de l'identifiant matériel.

> Constaté en conditions réelles : la machine restaurée et son originale portaient le même identifiant machine, hérité de la configuration recopiée.

---

## 9. Du banc de test au service réel

La construction a été menée sous le nom `vm-test-ha`, pour valider le mécanisme sans introduire d'autres variables. La machine est **désormais la machine de production** du service, et non plus un objet de démonstration.

| Élément | État |
| --- | --- |
| Nom de la machine | `srv-dpi-santelia` |
| Mémoire | 2 Gio, plus 2 Gio de mémoire d'échange |
| Clés d'hôte et identifiant machine | régénérés |
| Groupe de disponibilité, réplication, sauvegarde | **aucune reconfiguration**, ils s'appuient sur l'identifiant |
| Contenu applicatif | **à déployer** : environnement de conteneurs, application de gestion de patients, base de données |

**Ce que cette bascule démontre.** Le dispositif de continuité est indifférent à ce que la machine héberge. Renommer, redimensionner et régénérer l'identité n'a demandé aucune intervention sur la réplication ni sur la sauvegarde : c'est le principe du **remplacement progressif du contenu**.

**Ce qu'elle ne démontre pas encore.** La machine est un socle préparé, pas encore un service rendu. Tant que l'application n'est pas déployée, la chaîne complète — démarrage du système, démarrage des conteneurs, disponibilité de la base — n'a pas été mesurée.

**Conséquence sur les 2 min 24 s.** La mesure porte sur une machine minimale, dont le système redémarre en quelques secondes. Elle reste valable pour le **mécanisme**. Elle ne préjuge pas du démarrage applicatif, qui s'y ajoutera. Une nouvelle campagne est à prévoir après déploiement, avec le même protocole et les mêmes horodatages.

**Pourquoi la mesure reste défendable dans l'intervalle.** La cible est de 5 à 10 minutes pour un rétablissement constaté de 2 min 24 s : la marge absorbe le temps de démarrage applicatif. C'est ce que la nouvelle mesure devra confirmer.

---

*Source : cahier des charges Santélia, Bloc 2 AIS — Groupe 2.*
