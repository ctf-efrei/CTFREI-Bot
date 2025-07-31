# CTFREI Discord Bot

Ceci est un simple bot Discord en Python pour la création et la gestion d'événements CTFs (majoritairement venus de CTFTIME).

Ce bot a été fait pour l'association CTFREI, l'association de CTF de l'EFREI. Les mises à jour ne sont pas constantes et se font majoritairement quand j'ai du temps et des idées de modification.

# Installation

Tout le paramétrage se fait dans le fichier `conf.json`. Il permet la définition de différents paramètres qui seront expliqués plus bas, ainsi que l'ajout du TOKEN du bot et des différents salons et catégories nécessaires.

Une fois le bot lancé pour la première fois, il faudra écrire un message sur le serveur Discord (dans un salon que le bot peut voir) `/setup-ctfrei` (ce n'est pas une commande reconnue par Discord donc elle ne sera pas proposée).

Cela créera tous les dossiers et fichiers nécessaires au fonctionnement du bot. De là, vous pouvez lancer `/sync` pour la synchronisation avec le serveur si ce n'est pas déjà fait.

**INFORMATION IMPORTANTE** : le bot n'est **pas encore** capable de totalement gérer plusieurs serveurs Discord. Il reste un peu de travail à faire, notamment au niveau de l'ID Discord, mais il peut presque le gérer.

## Explication des paramètres `conf.json`

`"DISCORD_TOKEN"` : Ceci est le TOKEN du bot Discord sur lequel vous voulez lancer le bot (string)

`"DISCORD_GUILD_ID"` : Ceci est l'ID du serveur Discord sur lequel le bot fonctionnera (int)

`"INTERACTION_SAVE_FILE"` : Ceci est le fichier dans lequel les informations des interactions (les boutons sur les messages) seront sauvegardées pour permettre de les faire refonctionner après un redémarrage


`"UPCOMING_CTFTIME_FILE"` : Ceci est le fichier dans lequel les informations sur les prochains CTF seront stockées (un fichier cache)

`"EVENT_LOG_FILE"` : Ceci est un simple fichier de log pour suivre les activités sur le bot

`"CURRENT_CTF_DIR"` : Ceci est le dossier dans lequel les événements en cours seront stockés (sous format JSON)

`"PAST_CTF_DIR"` : Ceci est le dossier dans lequel les événements passés seront stockés (sous format JSON)


`"WEIGHT_RANGE_GENERAL"` : La marge pour la recherche de difficulté (lorsqu'une recherche est faite par rapport à la difficulté des événements). Ceci permet un éventail de choix

`"WEIGHT_START_RECOMMENDATION"` : Difficulté de base pour la recherche de CTFs de recommandation (tous les mercredis)

`"WEIGHT_RANGE_RECOMMENDATION"` : Marge pour la recherche des recommandations

`"WEEKS_RANGE_RECOMMENDATION"` : Définition de la durée avant un événement pour le rendre éligible aux recommandations (si par exemple 8, alors un événement dans plus de 8 semaines ne pourra pas être recommandé)

`"DISABLE_ZERO_WEIGHT_RECOMMENDATION"` : Si 0, autorise les CTFs avec un weight de 0 (soit ceux inconnus ou non mesurables selon CTFTIME) à être recommandés

`"NUMBER_OF_RECOMMENDATIONS"` : Le nombre maximal de recommandations à faire (un message par recommandation)

`"MAX_EVENT_LIMIT"` : Le nombre d'événements qui peut être envoyé au maximum lors d'une réponse du bot. Pour des limites liées à Discord, ce nombre doit rester entre 1 et 25


`"CTF_CHANNEL_CATEGORY_ID"` : {"NOM DE VOTRE SERVEUR DISCORD": ID DE LA CATÉGORIE CTF (pour la création des salons)},

`"CTF_JOIN_CHANNEL"` : {"NOM DE VOTRE SERVEUR DISCORD": ID DE LA CATÉGORIE CTF (pour la création des salons)},

`"CTF_ANNOUNCE_CHANNEL"` : {"NOM DE VOTRE SERVEUR DISCORD": {"channel\_id": ID DE VOTRE SALON POUR LES ANNONCES, "role\_id": ID DU RÔLE À PING LORS DES ANNONCES}},

`"ARCHIVE_CATEGORY"` : {"NOM DE VOTRE SERVEUR DISCORD": ID DE LA CATÉGORIE ARCHIVE (où envoyer les salons CTFs quand ils sont finis)},


## Explication des commandes

Pour l'explication des commandes, vous pouvez utiliser `/help {la commande}`

Voici les 3 commandes les plus importantes :

`/search {int ou string}` : permet de rechercher un ou plusieurs CTF soit par un éventail de difficulté (votre difficulté entre 0 et 99 qui utilisera ensuite la marge `WEIGHT_RANGE_GENERAL`), soit par un nom/mot.

`/quickadd {nom du rôle} {nom du CTF}` : permet d'ajouter des CTF au serveur. Le premier paramètre permet de définir le nom du rôle à utiliser et, par conséquent, le nom du salon pour ce CTF (qui sera sous le format 🚩-nomdurole). Le deuxième est simplement une entrée qui pointera vers **un seul** CTF (si aucun ou plusieurs CTF sont trouvés, alors la commande échoue). Le mécanisme de recherche est exactement le même que pour `/search`.

`/upcoming {int}` : permet de lister les X prochains CTFs dans l'ordre chronologique avec quelques informations. Le paramètre n'est pas obligatoire et sa valeur de base est égale à `MAX_EVENT_LIMIT`.

# Prochains objectifs :

- Ajouter une possibilité d'ajout silencieux pour les CTFs quickadd

- Retravailler entièrement /vote

- Peut-être un /recommend (mais personnel)

- Système utilisant une API CTFd pour récupérer les challenges présents et automatiser le processus de création de threads avec des commandes pour la gestion de ceux-ci

- /add pour pouvoir ajouter de manière plus simple des CTFs qui ne sont pas sur CTFTIME (nécéssitera une réécriture de /quickadd 😔)
