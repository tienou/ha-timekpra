# Timekpra - Contr\u00f4le Parental pour Home Assistant

Int\u00e9gration Home Assistant pour g\u00e9rer [Timekpr-nExT](https://mjasnik.gitlab.io/timekpr-next/) (contr\u00f4le parental Linux) \u00e0 distance via SSH.

## Fonctionnalit\u00e9s

- **Limites quotidiennes** : slider par jour de la semaine (en minutes)
- **Limite hebdomadaire / mensuelle** : en heures
- **Plage horaire** : heure de d\u00e9but et fin d'acc\u00e8s autoris\u00e9
- **Jours autoris\u00e9s** : toggle par jour
- **Type de verrouillage** : lock / suspend / shutdown
- **Suivi du temps inactif** : on/off
- **Capteurs** : temps utilis\u00e9 aujourd'hui, cette semaine
- **Statut** : ordinateur en ligne / hors ligne
- **File d'attente offline** : les modifications sont mises en attente si l'ordinateur est \u00e9teint et appliqu\u00e9es automatiquement au rallumage (persistant entre red\u00e9marrages HA)

## Installation

### Via HACS (recommand\u00e9)

1. Ouvrir HACS dans Home Assistant
2. Cliquer sur **Int\u00e9grations** > **\u22ee** (menu) > **D\u00e9p\u00f4ts personnalis\u00e9s**
3. Ajouter l'URL du d\u00e9p\u00f4t : `https://github.com/tienou/ha-timekpra`
4. Cat\u00e9gorie : **Int\u00e9gration**
5. Installer **Timekpra - Contr\u00f4le Parental**
6. Red\u00e9marrer Home Assistant

### Manuelle

Copier le dossier `custom_components/timekpra/` dans le r\u00e9pertoire `config/custom_components/` de votre Home Assistant.

## Configuration

### Pr\u00e9requis sur la machine de l'enfant (Ubuntu / Linux)

- **Timekpr-nExT** install\u00e9 (`sudo apt install timekpr-next`)
- **SSH** activ\u00e9 (`sudo apt install openssh-server`)
- Un compte utilisateur avec acc\u00e8s **sudo** (ex: `parents`)

**Option A** - Sudo avec mot de passe (plus simple) :

Remplissez les champs *Utilisateur admin* et *Mot de passe admin* dans la configuration. Le mot de passe sera utilis\u00e9 automatiquement pour les commandes sudo.

**Option B** - Sudo sans mot de passe :

Cr\u00e9er `/etc/sudoers.d/timekpra-ha` :

```
VOTRE_USER ALL=(ALL) NOPASSWD: /usr/bin/timekpra, /bin/cat /etc/timekpr/*, /bin/cat /var/lib/timekpr/*, /bin/test *
```

### Ajout dans Home Assistant

1. **Param\u00e8tres** > **Appareils et services** > **Ajouter une int\u00e9gration**
2. Chercher **Timekpra**
3. Remplir :
   - **H\u00f4te SSH** : IP de la machine de l'enfant
   - **Port SSH** : 22
   - **Utilisateur SSH** : un compte avec acc\u00e8s SSH
   - **Mot de passe SSH** : son mot de passe
   - **Utilisateur Timekpra** : le login de l'enfant (ex: `camille`)
   - **Utilisateur admin** *(optionnel)* : compte admin (ex: `parents`)
   - **Mot de passe admin** *(optionnel)* : mot de passe du compte admin

## Carte Lovelace

Un fichier `lovelace-card.yaml` est fourni dans le dossier de l'int\u00e9gration. Pour l'utiliser :

1. Dashboard > **Modifier** > **Ajouter une carte** > **Manuel**
2. Coller le contenu de `lovelace-card.yaml`
3. Ajuster les `entity_id` si n\u00e9cessaire

## Entit\u00e9s cr\u00e9\u00e9es

| Type | Entit\u00e9s |
|------|---------|
| **Number** | Limite Lundi\u2026Dimanche, Limite hebdo, Limite mensuelle, Heure d\u00e9but/fin |
| **Switch** | Jour autoris\u00e9 Lundi\u2026Dimanche, Compter le temps inactif |
| **Select** | Action fin de temps (lock/suspend/shutdown) |
| **Sensor** | Temps utilis\u00e9 aujourd'hui, Temps utilis\u00e9 cette semaine, Ordinateur (en ligne/hors ligne), Modifications en attente |

## Licence

MIT
