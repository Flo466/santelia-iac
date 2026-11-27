# Pile de supervision

Supervision centralisée, déployée hors de l'infrastructure surveillée :
un serveur posé sur la machine qu'il surveille disparaît avec elle.

## Déploiement

    git clone https://github.com/Flo466/santelia-iac.git
    cd santelia-iac/stacks/zabbix
    cp .env.example .env
    # renseigner DB_PASSWORD dans .env
    chmod 600 .env
    docker compose up -d

## Mise à jour

    git pull
    docker compose up -d

## Ports

| Port | Usage |
| --- | --- |
| 8087 | Interface web |
| 10051 | Écoute des agents |

La base occupe un volume nommé `zabbix-db-data`, jamais un montage de
répertoire : PostgreSQL impose la correspondance des identifiants système.

## Réserve connue

Le service de mise à jour automatique de la machine passe sans lire le label
`watchtower.enable`. Une mise à jour de la pile peut donc survenir sans
action. En cas d'interface indisponible après une mise à jour :

    docker compose pull && docker compose up -d
