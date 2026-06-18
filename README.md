# Timekpra - Contrôle Parental pour Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Intégration Home Assistant pour gérer [Timekpr-nExT](https://mjasnik.gitlab.io/timekpr-next/) (contrôle parental Linux) à distance via SSH.

Contrôlez le temps d'écran de vos enfants directement depuis votre dashboard Home Assistant, même quand leur ordinateur est éteint.

![Carte Timekpra](images/screenshot.png)

## Fonctionnalités

- **Profils prédéfinis** : basculez en un clic entre des configurations complètes (École, Vacances, Chez Papi Mamie...) — changement instantané dans l'interface
- **Profils personnalisés** : créez, modifiez et supprimez vos propres profils depuis la carte Lovelace
- **Déblocage temporaire** : profil intégré pour bypasser toutes les restrictions d'un clic
- **Limites quotidiennes** : réglables par jour (Lun-Dim), avec boutons +/- directement dans la carte
- **Limite hebdomadaire / mensuelle** : en heures, avec affichage "Illimité" quand désactivé
- **Plage horaire** : heure de début et fin d'accès autorisé
- **Jours autorisés** : toggle par jour de la semaine
- **Type de verrouillage** : lock / suspend / shutdown (menu déroulant)
- **Suivi du temps inactif** : on/off
- **Capteurs** : temps utilisé aujourd'hui et cette semaine
- **Statut** : ordinateur en ligne / hors ligne
- **File d'attente offline** : les modifications sont mises en attente si l'ordinateur est éteint et appliquées automatiquement au rallumage (persistant entre redémarrages HA)
- **Carte Lovelace intégrée** : carte personnalisée installée automatiquement avec contrôles interactifs

## Installation

### Via HACS (recommandé)

1. Ouvrir HACS dans Home Assistant
2. Cliquer sur **Intégrations** > **⋮** (menu) > **Dépôts personnalisés**
3. Ajouter l'URL du dépôt : `https://github.com/tienou/ha-timekpra`
4. Catégorie : **Intégration**
5. Installer **Timekpra - Contrôle Parental**
6. Redémarrer Home Assistant

### Manuelle

Copier le dossier `custom_components/timekpra/` dans le répertoire `config/custom_components/` de votre Home Assistant, puis redémarrer.

## Configuration

### Prérequis sur la machine de l'enfant (Ubuntu / Linux)

- **Timekpr-nExT** installé (`sudo apt install timekpr-next`)
- **SSH** activé (`sudo apt install openssh-server`)
- Un compte utilisateur avec accès **sudo** (ex: `parents`)

> **Astuce** : En authentification par mot de passe, le mot de passe SSH est utilisé automatiquement pour les commandes `sudo`. Pas besoin de configuration sudoers spéciale. Pour l'authentification par clé SSH, voir la [section dédiée](#authentification-par-clé-ssh).

### Ajout dans Home Assistant

1. **Paramètres** > **Appareils et services** > **Ajouter une intégration**
2. Chercher **Timekpra**
3. Remplir :
   - **Hôte SSH** : IP de la machine de l'enfant (ex: `192.168.1.50`)
   - **Hôte SSH (VPN)** : *(optionnel)* IP quand l'enfant est connecté au VPN (ex: `10.0.0.2`)
   - **Port SSH** : `22` (par défaut)
   - **Utilisateur SSH** : compte avec accès sudo (ex: `parents`)
   - **Méthode d'authentification** : `Mot de passe` ou `Clé SSH`
   - **Mot de passe SSH** : mot de passe du compte *(si méthode = mot de passe)*
   - **Clé privée SSH** : la clé privée complète à coller *(si méthode = clé — voir ci-dessous)*
   - **Phrase secrète de la clé** : *(optionnel)* si la clé est protégée par une passphrase
   - **Mot de passe sudo** : *(optionnel)* mot de passe pour `sudo` sur la machine distante ; à laisser vide si `sudo` est en `NOPASSWD`
   - **Utilisateur Timekpra** : le login de l'enfant (ex: `camille`)

> Le formulaire affiche tous les champs en même temps : ne remplissez que ceux de la méthode choisie. Les identifiants non pertinents ne sont pas enregistrés.

### Authentification par clé SSH

L'authentification par clé évite de stocker un mot de passe et est recommandée. Comme la clé sert uniquement à ouvrir la session SSH (pas à `sudo`), il faut décider comment `sudo` s'authentifie :

**Option A — `sudo` sans mot de passe (`NOPASSWD`, recommandé)** : laissez le champ **Mot de passe sudo** vide. Les commandes utiliseront `sudo -n`.

```bash
# Sur la machine de l'enfant, en tant qu'admin :

# 1. Depuis Home Assistant (ou votre poste), générer une clé dédiée
ssh-keygen -t ed25519 -f ~/.ssh/timekpra -C "timekpra-ha"

# 2. Copier la clé publique sur le compte sudo de la machine de l'enfant
ssh-copy-id -i ~/.ssh/timekpra.pub parents@192.168.1.50

# 3. Autoriser le compte à utiliser sudo sans mot de passe (NOPASSWD)
echo "parents ALL=(ALL) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/timekpra
sudo chmod 440 /etc/sudoers.d/timekpra
```

> Pour durcir, vous pouvez restreindre `NOPASSWD` aux seules commandes utilisées par l'intégration (`timekpra`, `test`, `cat`, `find`) au lieu de `ALL` — pensez à vérifier les chemins réels sur votre distribution (`which timekpra`), sinon `sudo` redemandera un mot de passe et les commandes échoueront.

Collez ensuite le contenu de la **clé privée** (`~/.ssh/timekpra`, en entier, lignes `-----BEGIN…` à `-----END…` comprises) dans le champ **Clé privée SSH** du formulaire.

**Option B — `sudo` avec mot de passe** : renseignez le champ **Mot de passe sudo** avec le mot de passe du compte SSH. Aucune ligne sudoers n'est nécessaire.

> **Sécurité** : la clé d'hôte SSH du serveur est épinglée à la première connexion (*Trust On First Use*, comme le client `ssh`). Si elle change ensuite (réinstallation de l'OS, ou tentative d'interception), la connexion est **refusée** et un message d'erreur est journalisé — supprimez puis ré-ajoutez l'intégration pour ré-épingler la nouvelle clé.

### Modifier la configuration

Pour changer les identifiants SSH (ou basculer entre mot de passe et clé) après l'installation :
**Paramètres** > **Appareils et services** > **Timekpra** > **Configurer**

## Carte Lovelace

La carte est installée automatiquement. Pour l'ajouter à un dashboard :

1. Dashboard > **Modifier** > **Ajouter une carte**
2. Chercher **Timekpra** dans la liste des cartes
3. La carte affiche tous les contrôles avec des boutons **+/-** pour modifier les valeurs directement

### Fonctionnalités de la carte

- **Sélecteur de profil** : menu déroulant pour basculer instantanément entre les profils
- **Gestion des profils** : boutons pour créer, modifier et supprimer des profils personnalisés
- **Limites quotidiennes** : boutons ±15 min par jour, affiche "Illimité" à 1440 min
- **Limite hebdomadaire** : boutons ±1h, affiche "Illimité" à 168h
- **Limite mensuelle** : boutons ±1h, affiche "Illimité" à 744h
- **Plage horaire** : boutons ±1h pour début et fin
- **Jours autorisés** : toggles on/off
- **Type de verrouillage** : menu déroulant (lock/suspend/shutdown)
- **Statut en temps réel** : en ligne/hors ligne + commandes en attente

## Entités créées

| Type | Entités |
|------|---------|
| **Number** | Limite Lundi…Dimanche, Limite hebdo, Limite mensuelle, Heure début/fin |
| **Switch** | Jour autorisé Lundi…Dimanche, Compter le temps inactif, Limites quotidiennes on/off, Limite hebdo on/off, Limite mensuelle on/off, Déblocage temporaire |
| **Select** | Action fin de temps (lock/suspend/shutdown), Profil actif |
| **Sensor** | Temps utilisé aujourd'hui, Temps utilisé cette semaine, Ordinateur (en ligne/hors ligne), Modifications en attente |

## Fonctionnement technique

- Connexion SSH via `asyncssh`, authentification par **mot de passe** ou **clé privée** (au choix)
- **Clé d'hôte épinglée** (*Trust On First Use*) : refus de connexion si la clé du serveur change
- `sudo` authentifié par mot de passe (`sudo -S`) ou sans mot de passe (`sudo -n` / `NOPASSWD`)
- **Fallback VPN** : si l'IP locale est injoignable et une IP VPN est configurée, la connexion est tentée automatiquement sur l'IP VPN
- Lecture de la config depuis `/var/lib/timekpr/config/timekpr.{user}.conf`
- Écriture via la CLI `timekpra` (ex: `timekpra --settimelimits`)
- Rafraîchissement toutes les 5 minutes (configurable)
- File d'attente persistante pour les commandes quand la machine cible est hors ligne
- Vérification du code retour : une commande qui échoue sur la machine (mauvais mot de passe sudo, règle NOPASSWD manquante, erreur `timekpra`…) est journalisée et signalée via « Modifications en attente » au lieu d'être silencieusement ignorée

## Licence

MIT
