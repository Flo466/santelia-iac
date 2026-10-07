# Cahier des charges technique & fonctionnel

> Dossier de référence du projet — Groupe Santélia
> Modernisation, automatisation, disponibilité et sécurisation de l'infrastructure

| | |
|---|---|
| **Client** | Groupe Santélia |
| **Périmètre** | Évry, Corbeil-Essonnes, Ris-Orangis |
| **Budget / délai** | 15 000 € max / 2 à 3 mois |
| **Groupe** | Groupe 2 |

---

## 1. Contexte du projet

Le groupe Santélia exploite trois cliniques privées situées à Évry, Corbeil-Essonnes et Ris-Orangis. Une panne survenue au mois de mars a bloqué la prise de rendez-vous pendant plus de six heures sur le site d'Évry. Cet incident met en évidence le besoin de renforcer la continuité de service et de réduire les interventions manuelles sur les serveurs.

**Audit / échéance :** le projet doit être stabilisé dans un délai de 2 à 3 mois afin de laisser une marge avant l'audit prévu à M+4.

Aujourd'hui, les serveurs sont configurés manuellement, au cas par cas. Santélia souhaite une infrastructure plus standardisée, supervisée et automatisée, tout en conservant l'Active Directory existant pour la gestion des accès.

**Objectif global :** améliorer la disponibilité du DPI (Dossier Patient Informatisé), accélérer le rétablissement en cas d'incident et automatiser les opérations récurrentes.

---

## 2. Périmètre du projet

### 2.1 Périmètre et services concernés

- 3 établissements : cliniques d'Évry, de Corbeil-Essonnes et de Ris-Orangis.
- Services critiques : DPI, prise de rendez-vous et services nécessaires à leur fonctionnement.
- Postes supervisés : les 30 postes mentionnés dans le besoin client.
- Accès / identités : conservation de l'Active Directory existant.

### 2.2 Socle technologique retenu

| Brique / outil | Solution retenue | Rôle & justification |
|---|---|---|
| **IaC / Automatisation** | Ansible | Automatiser et standardiser les configurations des serveurs et des applications ; utiliser Ansible Vault pour les secrets. |
| **Virtualisation / HA** | Proxmox VE HA | Héberger les VM critiques dans une architecture de haute disponibilité afin de limiter les interruptions. |
| **Sauvegarde / 3-2-1** | Proxmox Backup Server | Centraliser les sauvegardes et prévoir une copie secondaire afin de répondre à la stratégie 3-2-1. |
| **Supervision** | Zabbix | Centraliser la supervision, les seuils et les alertes, notamment pour les 30 postes concernés. |

### 2.3 Inclus / hors périmètre

- **Inclus :** configuration, intégration, tests, recette, documentation et transmission à l'équipe technique ; mise à disposition d'un environnement de test avant production.
- **Hors périmètre :** migration complète vers un cloud public, refonte complète de l'Active Directory et reconstruction globale du réseau au-delà des besoins nécessaires aux 4 briques.

---

## 3. Exigences fonctionnelles

Le système doit faire ce qui suit. Chaque exigence est priorisée selon la méthode MoSCoW demandée dans la séance 3.

| # | Exigence | Priorité (MoSCoW) |
|---|---|---|
| 1 | Permettre l'accès continu au DPI grâce à une architecture de haute disponibilité des VM critiques. | **Must** |
| 2 | Réaliser et restaurer les sauvegardes selon une stratégie 3-2-1 avec Proxmox Backup Server, tout en maintenant l'accès aux données pendant la sauvegarde. | **Must** |
| 3 | Automatiser et standardiser la configuration des serveurs et des applications avec Ansible, avec protection des secrets via Ansible Vault. | **Must** |
| 4 | Superviser en temps réel les équipements et les 30 postes concernés, avec remontée d'alertes dans Zabbix. | **Should** |
| 5 | Conserver l'Active Directory existant pour les identités et les droits, et assurer la traçabilité des accès. | **Should** |
| 6 | Mettre à disposition un environnement de test / validation avant la mise en production. | **Should** |
| 7 | Prévoir, en option, un tableau de bord synthétique destiné à la direction. | **Could** |

---

## 4. Exigences non-fonctionnelles

Ces exigences décrivent le comportement attendu et sont formulées avec des critères mesurables conformément aux consignes du TP.

| # | Exigence | Critère de mesure |
|---|---|---|
| 1 | Disponibilité du service critique | *à confirmer* |
| 2 | Rétablissement en cas d'incident | Retour du service critique dans un délai cible de 5 à 10 minutes. |
| 3 | Supervision en temps réel | Les 30 postes concernés sont visibles dans Zabbix et leurs informations remontent correctement. |
| 4 | Délai de mise en œuvre | Solution déployée et opérationnelle dans un délai maximal de 2 à 3 mois. |
| 5 | Traçabilité des accès | *à confirmer* |
| 6 | Continuité d'alimentation | Les équipements critiques sont protégés par les onduleurs prévus dans l'architecture. |

> Les critères des lignes 1 et 5 n'ont pas été récupérés lors de l'extraction du document d'origine. À compléter depuis le PDF source avant publication.

---

## 5. Contraintes techniques et budgétaires

| Contrainte | Valeur / impact |
|---|---|
| **Budget maximal** | 15 000 € pour l'ensemble du projet. |
| **Délai** | Déploiement prévu sur 2 à 3 mois maximum. |
| **Compétences internes** | Équipe principalement composée de techniciens ; la solution doit rester simple, exploitable et documentée. |
| **Existant** | Active Directory déjà en place pour la gestion des accès. |
| **Données de santé** | Le projet concerne des données sensibles ; le cadre réglementaire et les exigences de sécurité applicables doivent être respectés. |
| **Continuité de service** | L'architecture doit limiter l'impact d'une panne et atteindre le temps de rétablissement demandé. |

---

## 6. Critères d'acceptation / recette

La recette vérifie chaque brique séparément puis leur fonctionnement conjoint. Les tests sont réalisés sur l'environnement de validation avant la mise en production.

| Brique | Test de recette | Résultat attendu | Preuve |
|---|---|---|---|
| **HA / Proxmox VE** | Simuler l'indisponibilité d'un nœud hébergeant une VM critique. | Le service reste disponible ou est rétabli dans le délai cible. | Compte rendu + horodatage. |
| **Sauvegarde / PBS** | Lancer une sauvegarde puis tester une restauration sur une VM ou un jeu de données de test. | Sauvegarde exploitable et restauration réussie. | Journal de sauvegarde + preuve de restauration. |
| **Supervision / Zabbix** | Vérifier la remontée et déclencher une alerte sur un équipement ou service de test. | Les 30 postes concernés sont visibles et l'alerte remonte correctement. | Capture / export Zabbix + journal. |
| **IaC / Ansible** | Déployer ou reconfigurer une machine de test à partir d'un playbook puis rejouer le playbook. | Configuration identique et standardisée, sans action manuelle supplémentaire. | Playbook + sortie d'exécution + état final. |

### 6.1 Indicateurs complémentaires proposés — à valider avec le client

Les indicateurs ci-dessous reprennent des idées de précision technique apportées lors des échanges de groupe. Ils sont proposés pour la recette et ne sont pas présentés comme des exigences client déjà validées.

| Domaine | Indicateur proposé | Cible de recette à valider |
|---|---|---|
| Sauvegarde | RPO (perte de données) | Cible proposée : < 15 min. |
| Sauvegarde | Temps de restauration | Cible proposée : restauration d'une VM critique < 30 min. |
| Ansible | Temps de déploiement / reconfiguration | Cible proposée : nouvelle configuration appliquée < 15 min. |
| Zabbix | Réactivité des alertes | Cible proposée : alerte envoyée à la DSI < 2 min. |

---

## 7. Planning prévisionnel de mise en œuvre

Le planning reste compatible avec la contrainte de 2 à 3 mois et prévoit une phase de tests et de recette avant la mise en production.

| Phase | Contenu | Période | Livrable / jalon |
|---|---|---|---|
| **1. Cadrage & conception** | Validation du besoin, architecture cible et dépendances entre les 4 briques. | S1 – S2 | Architecture et plan d'action validés. |
| **2. Haute disponibilité** | Préparation de la HA Proxmox VE et intégration des VM critiques. | S2 – S4 | HA opérationnelle sur l'environnement cible. |
| **3. Sauvegarde** | Mise en place de Proxmox Backup Server et stratégie 3-2-1. | S3 – S5 | Sauvegardes + premier test de restauration. |
| **4. Supervision** | Déploiement de Zabbix, intégration des équipements et des 30 postes. | S4 – S6 | Supervision centralisée et alertes. |
| **5. IaC** | Écriture des playbooks Ansible et standardisation des configurations. | S5 – S8 | Playbooks validés et documentés. |
| **6. Intégration & recette** | Tests croisés, sécurité, documentation, formation et corrections. | S8 – S10 | PV de recette + dossier d'exploitation. |
| **7. Mise en production** | Déploiement final et accompagnement de l'équipe. | S10 – S12 | Solution en production dans le délai maximal. |

---

## 8. Synthèse des solutions et justification

Les quatre briques sont complémentaires. Le choix porte sur une architecture cohérente : Proxmox VE HA traite la continuité des VM, Proxmox Backup Server la sauvegarde et la restauration, Zabbix la supervision et Ansible l'automatisation / standardisation.

| Solution | Rôle dans le projet | Justification par rapport au besoin |
|---|---|---|
| **Proxmox VE HA** | Haute disponibilité des VM | Répond à l'objectif de continuité de service du DPI et à la réduction du temps d'interruption. |
| **Proxmox Backup Server** | Sauvegarde / restauration | Centralise les sauvegardes et permet de structurer la stratégie 3-2-1 avec une copie secondaire. |
| **Zabbix** | Supervision / alertes | Centralise la visibilité sur les équipements et les 30 postes concernés. |
| **Ansible** | IaC / automatisation | Réduit la configuration manuelle et standardise les déploiements sur les environnements concernés. |

> **Point technique important :** Ansible ne remplace pas la HA, la sauvegarde ou la supervision ; il automatise leur déploiement et leur configuration lorsqu'il est utilisé à cette fin.

---

## 9. Réponse synthétique à l'appel d'offres — bonus

En nous plaçant du côté du prestataire, nous répondons en priorité aux exigences Must et vérifions que les options proposées restent compatibles avec l'enveloppe maximale de 15 000 €.

| # | Exigence reçue | Priorité | Réponse | Justification courte |
|---|---|---|---|---|
| 1 | Accès continu au DPI via haute disponibilité des VM | Must | **Couvert** | Proxmox VE HA est retenu comme brique de continuité de service. |
| 2 | Sauvegarde 3-2-1 et restauration | Must | **Couvert** | PBS + copie secondaire prévue dans la stratégie de sauvegarde. |
| 3 | Supervision centralisée des 30 postes | Should | **Couvert** | Zabbix est retenu pour la supervision et les alertes. |
| 4 | Automatisation des serveurs et applications | Must | **Couvert** | Ansible automatise et standardise les configurations via des playbooks. |

---

## 10. Préparation de la restitution orale — 5 minutes

Le support de séance demande une restitution en trois points : contexte en une phrase, 2 à 3 exigences clés avec leur priorité MoSCoW, puis prochaine étape.

**Pitch proposé**

> Santélia exploite trois cliniques et a subi une panne de plus de six heures sur le site d'Évry, alors que les serveurs sont aujourd'hui configurés manuellement. Notre cahier des charges vise à renforcer la continuité de service et à automatiser l'administration des infrastructures.

> Les exigences clés sont : l'accès continu au DPI grâce à la haute disponibilité — Must ; la sauvegarde 3-2-1 et la restauration — Must ; et l'automatisation de la configuration des serveurs avec Ansible — Must. La supervision Zabbix est classée Should pour centraliser la visibilité et les alertes.

> La prochaine étape est l'intégration des quatre briques, puis les tests de recette : panne contrôlée sur une VM, restauration d'une sauvegarde, vérification de la supervision et exécution des playbooks Ansible.

---

## 11. Grille de relecture croisée

| Critère | OK / À revoir | Commentaire |
|---|---|---|
| Toutes les rubriques sont complétées | OK | Sections 1 à 12 renseignées. |
| Document clair et bien structuré | OK | Titres, tableaux et priorités lisibles. |
| Toutes les exigences fonctionnelles ont une priorité MoSCoW | OK | Chaque ligne du tableau est classée. |
| Les exigences non fonctionnelles sont mesurables | OK | Disponibilité, rétablissement, supervision, délai et traçabilité sont vérifiables. |
| Cohérence avec les séances 1-2 | OK | Les besoins repris correspondent au besoin Santélia consolidé. |

---

## 12. Conclusion

Le cahier des charges formalise les besoins de Santélia autour de quatre briques complémentaires. Proxmox VE HA vise à limiter les interruptions des VM critiques ; Proxmox Backup Server structure la sauvegarde et la restauration ; Zabbix apporte la supervision ; et Ansible automatise et standardise l'administration. L'ensemble doit respecter un budget maximal de 15 000 € et un délai de 2 à 3 mois, avec une recette permettant de démontrer objectivement la conformité aux exigences.
