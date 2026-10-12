# Santélia — Sauvegarde et restauration

> Brique 02 — Proxmox Backup Server. Sauvegarde et restauration testées.
> Mise à jour : 08/10/2026

---

## 1. Objet

Le cahier des charges identifie la sauvegarde comme le second besoin du projet : centraliser les sauvegardes, prévoir une copie secondaire, et permettre la restauration des données.

Le test de recette consiste à lancer une sauvegarde, puis à restaurer. Les preuves attendues sont le journal de sauvegarde et la preuve de restauration.

Un point de vocabulaire, parce qu'il prête à confusion : cette brique ne traite pas la continuité de service. Celle-ci relève de la haute disponibilité, qui permet à une machine de redémarrer ailleurs. La sauvegarde répond à une autre question, revenir à un état antérieur connu.

---

## 2. Résultat

| Opération | Mesure |
| --- | --- |
| Sauvegarde | **12 secondes**, 8 Gio traités |
| Déduplication | **82 %** de données réutilisées |
| Restauration | **9,27 secondes** à 884 Mo/s |
| Cohérence | Applicative, agent invité sollicité |

La copie restaurée a été démarrée, puis le service témoin interrogé depuis plusieurs points du réseau. Elle est fonctionnelle.

Trois points à retenir.

**La sauvegarde s'est faite sans interrompre le service**, en mode instantané. C'est ce que le cahier des charges demande pour la sauvegarde des données.

**Elle est cohérente applicative.** Le journal mentionne l'appel à l'agent invité, qui gèle puis libère le système de fichiers avant et après la capture. Sans lui, la sauvegarde resterait utilisable mais serait comparable à un arrêt brutal.

**La restauration a réellement été exécutée**, vers une machine distincte de l'originale. Une sauvegarde qui n'a jamais été restaurée ne prouve rien.

---

## 3. Ce qui a été mis en place

Un serveur de sauvegarde dédié sur l'hôte, avec un entrepôt dédupliqué de 40 Go.

Deux choix d'architecture. Une machine virtuelle plutôt qu'un conteneur, parce que l'application nécessite un accès direct au stockage. Et le disque de données est ajouté après l'installation, pour que l'installateur n'ait qu'un seul disque à préparer.

### La stratégie 3-2-1

| Copie | Support | État |
| --- | --- | --- |
| **1** | Volumes du cluster | Donnée vivante, répliquée entre nœuds |
| **2** | Serveur de sauvegarde primaire | **En place** |
| **3** | Machine physique distincte | À mettre en place |

Le point qui fait la différence : un serveur de sauvegarde installé sur la machine qu'il protège ne protège de rien. Si l'hôte tombe, la donnée et sa sauvegarde disparaissent ensemble. C'est ce qui justifie la troisième copie sur une machine distincte.

### Sauvegarde et réplication, deux besoins distincts

La réplication entre nœuds apporte de la disponibilité. Elle ne protège pas de la perte de données, car elle réplique aussi les erreurs : une suppression ou une corruption se propage d'un nœud à l'autre.

La sauvegarde permet de revenir à un état antérieur connu. Les deux mécanismes sont complémentaires et ne se substituent pas l'un à l'autre.

---

## 4. Points de vigilance

Huit points relevés en conditions réelles. Forme courte.

| # | Point | Mesure appliquée |
| --- | --- | --- |
| 1 | Image téléchargée sans vérification du certificat | Contrôle systématique de l'empreinte |
| 2 | Protection du stockage désactivée par défaut | Extension automatique activée |
| 3 | Marge d'extension bornée | Espace réservé conservé |
| 4 | Identifiant de compte saisi avec un doublon de royaume | Suppression et recréation |
| 5 | Stockage déclaré sur le mauvais niveau | Déclaration corrigée au niveau du cluster |
| 6 | Identité réseau reprise après restauration | Extinction de l'originale, ou renumérotation |
| 7 | Arrêt arbitré par le gestionnaire de disponibilité | Passage par le gestionnaire |
| 8 | Adresse IPv6 globale exposée | Attribution à désactiver, ou filtrage explicite |

Deux d'entre eux méritent une phrase.

**Le point 6.** Une restauration restitue l'identité réseau de la machine, adresse matérielle comprise. Deux machines identiques sur le même segment provoquent un conflit, et le service devient injoignable sans aucun message d'erreur. Règle qui en découle : toute restauration exige une renumérotation avant mise en service simultanée.

**Le point 8.** Le système invité obtient automatiquement une adresse IPv6 publique, en plus de son adresse IPv4 privée. La traduction d'adresses qui protège IPv4 ne s'applique pas à IPv6. L'infrastructure semble protégée, alors qu'un second protocole contourne le mécanisme.

Ce dernier point illustre une fausse sensation de sécurité, et il constitue le principal enseignement de sécurité de cette brique.

---

## 5. Résultats de recette

| Indicateur | Mesure | Statut |
| --- | --- | --- |
| Sauvegarde exécutée | 12 secondes | Conforme |
| Restauration testée | 9,27 secondes | Conforme |
| Copie restaurée fonctionnelle | Service interrogé depuis deux chemins | Conforme |
| Cohérence de la sauvegarde | Agent invité sollicité | Conforme |
| Taux de déduplication | 82 % | Conforme |
| Copie secondaire présente | À mettre en place | En cours |
| Rétention configurée | À mettre en place | En cours |

---

## 6. Suite donnée

| Étape | Objet |
| --- | --- |
| Copie secondaire | Troisième copie du 3-2-1, sur une machine physique distincte |
| Job planifié | Sauvegarde automatique avec politique de rétention |
| Chiffrement de l'entrepôt | Protection des données au repos, clé conservée hors du serveur |

---

## 7. Journal des commandes

La séquence complète de mise en œuvre, environnement par environnement, est regroupée dans le document **Journal des commandes : sauvegarde**, qui accompagne celui-ci.

---

*Documentation publiée depuis le dépôt du projet — version du 08/10/2026.*
