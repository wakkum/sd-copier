"""
SD Card Video Backup Tool

Copies video files from an SD card into a dated, structured folder on an
external hard drive:

    {HDD}/{YYYY_MM_DD}/{NN}_EVENT_{name}_{YYYY_MM_DD}/{Button camera|PB}/

Designed to be used by someone with no technical background: pick the SD
card, pick the hard drive, fill in a short form, click Copy. The interface
language is chosen from the dropdown in the top right corner; see LANGUAGES
below for the ones currently available.

Works on Windows and macOS using only the Python standard library.
"""

import hashlib
import json
import os
import re
import shutil
import string
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
import webbrowser
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

APP_VERSION = "1.3.0"

# Public GitHub repo used by "Check for Updates" (reads the latest Release
# via GitHub's public API - no auth token needed or embedded). Left blank,
# "Check for Updates" just tells the user it isn't configured - no network
# calls are made.
UPDATE_REPO = "wakkum/sd-copier"

CONFIG_PATH = Path.home() / ".sd_video_backup_config.json"
REGISTRY_FILENAME = ".sd_backup_registry.json"

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".m4v", ".avi", ".mts", ".m2ts",
    ".wmv", ".flv", ".mkv", ".3gp", ".3gpp",
}

CAMERA_FOLDER_NAMES = {
    "Button": "Button camera",
    "Powerbank": "PB",
}

MASTER_LOG_NAME = "All_Descriptions.txt"

# ---------------------------------------------------------------------------
# Translations - every piece of user-facing text lives here. Camera names
# ("Button" / "Powerbank") are left untranslated on purpose: they're the
# camera nicknames used to name the folders on disk, not generic words.
# ---------------------------------------------------------------------------

LANGUAGES = {
    "en": "English", "el": "Ελληνικά", "fr": "Français", "de": "Deutsch", "it": "Italiano",
}

STRINGS = {
    "en": {
        "app_title": "SD Card Video Backup",
        "language_label": "Language:",
        "source_group": "1. SD Card (source)",
        "dest_group": "2. External Hard Drive (destination)",
        "browse": "Browse...",
        "detected_label": "Detected:",
        "no_drives": "No external drives detected - use Browse.",
        "refresh_drives": "Refresh detected drives",
        "details_group": "3. Recording details",
        "date_label": "Date of recording:",
        "date_hint": "(YYYY-MM-DD)",
        "camera_label": "Camera:",
        "event_name_label": "Event name:",
        "event_name_hint": "(e.g. Birthday party, Beach day - leave blank to just call it \"Event\")",
        "description_label": "Description:",
        "important_check": "Mark this day as VERY IMPORTANT",
        "copy_button": "Copy videos now",
        "status_scanning": "Scanning SD card for video files...",
        "status_copying": "Copying file {i} of {total}: {name}",
        "status_verifying": "Verifying file {i} of {total}: {name}",
        "status_done": "Done. Copied and verified {copied} of {total} files to:\n{folder}",
        "status_done_problems": "Done with problems: {copied} of {total} files copied and "
                                 "verified. {problems} file(s) had issues - see info.txt in "
                                 "the destination folder.",
        "err_select_sd": "Please select a valid SD card folder.",
        "err_select_hdd": "Please select a valid destination hard drive folder.",
        "err_date": "Please enter the date as YYYY-MM-DD.",
        "err_read_sd": "Could not read the SD card:\n{error}",
        "err_no_videos": "No video files were found on that SD card.",
        "err_create_folder": "Could not create the destination folder:\n{error}",
        "dlg_browse_sd_title": "Select the SD card",
        "dlg_browse_hdd_title": "Select the external hard drive",
        "msg_success": "Success! Copied and verified {copied} video file(s).\n\nEvery file was "
                        "checked byte-for-byte against the original on the SD card.\n\n"
                        "Saved to:\n{folder}",
        "msg_warning_failed": "{n} file(s) failed to copy.",
        "msg_warning_unverified": "{n} file(s) copied but didn't match the original (possible "
                                   "SD card read error or bad connection) - try again.",
        "msg_warning_body": "{copied} of {total} files copied and verified successfully.\n\n"
                             "{details}\n\nSee info.txt in:\n{folder}",
        "msg_warning_metadata": "The videos copied, but the notes/log files could not be "
                                  "written to the hard drive (was it unplugged?). Your description "
                                  "may not have been saved.",
        "not_enough_space": "Not enough free space on the hard drive.\n\nNeeded: {needed}\n"
                             "Available: {available}",
        "duplicate_card_msg": "This SD card looks like it was already copied here before:\n\n"
                               "{folder}\n(on {when})\n\nCopy it again anyway?",
        "same_event_button": "Add Another Camera to This Event",
        "same_event_hint": "Uses the same date, name and description as the last backup - "
                            "just plug in the other camera's SD card and click the button above.",
        "same_event_hint_disabled": "This lights up after your first successful copy, so you can "
                                     "add the second camera's footage to the very same event.",
        "history_button": "View Backup History",
        "history_title": "Backup History",
        "history_search_label": "Search:",
        "history_empty": "No backups found yet on this hard drive.",
        "history_close": "Close",
        "eject_button": "Eject SD Card & Hard Drive",
        "eject_confirm": "Eject both the SD card and the hard drive now?\n\nMake sure any copy "
                          "has finished first.",
        "eject_ok": "Ejected safely - you can now unplug it.",
        "eject_fail": "Could not eject - you may need to eject it manually.",
        "update_check_button": "Check for Updates",
        "update_not_configured": "Update checking isn't set up yet.",
        "update_check_failed": "Could not check for updates (no internet connection?).",
        "update_none": "You're using the latest version ({version}).",
        "update_available_msg": "A newer version is available: {version} (you have {current}).\n\n"
                                 "Open the download page?",
    },
    "el": {
        "app_title": "Αντίγραφο Ασφαλείας Βίντεο SD",
        "language_label": "Γλώσσα:",
        "source_group": "1. Κάρτα SD (πηγή)",
        "dest_group": "2. Εξωτερικός Σκληρός Δίσκος (προορισμός)",
        "browse": "Αναζήτηση...",
        "detected_label": "Εντοπίστηκαν:",
        "no_drives": "Δεν εντοπίστηκαν εξωτερικοί δίσκοι - χρησιμοποιήστε την Αναζήτηση.",
        "refresh_drives": "Ανανέωση εντοπισμένων δίσκων",
        "details_group": "3. Στοιχεία εγγραφής",
        "date_label": "Ημερομηνία εγγραφής:",
        "date_hint": "(ΕΕΕΕ-ΜΜ-ΗΗ)",
        "camera_label": "Κάμερα:",
        "event_name_label": "Όνομα συμβάντος:",
        "event_name_hint": "(π.χ. Πάρτι γενεθλίων, Μέρα στην παραλία - αφήστε το κενό για να ονομαστεί απλώς \"Event\")",
        "description_label": "Περιγραφή:",
        "important_check": "Σήμανση αυτής της ημέρας ως ΠΟΛΥ ΣΗΜΑΝΤΙΚΗ",
        "copy_button": "Αντιγραφή βίντεο τώρα",
        "status_scanning": "Σάρωση της κάρτας SD για αρχεία βίντεο...",
        "status_copying": "Αντιγραφή αρχείου {i} από {total}: {name}",
        "status_verifying": "Έλεγχος αρχείου {i} από {total}: {name}",
        "status_done": "Ολοκληρώθηκε. Αντιγράφηκαν και ελέγχθηκαν {copied} από {total} αρχεία στο:\n{folder}",
        "status_done_problems": "Ολοκληρώθηκε με προβλήματα: {copied} από {total} αρχεία αντιγράφηκαν και ελέγχθηκαν. {problems} αρχείο(α) είχαν πρόβλημα - δείτε το info.txt στον φάκελο προορισμού.",
        "err_select_sd": "Παρακαλώ επιλέξτε έναν έγκυρο φάκελο κάρτας SD.",
        "err_select_hdd": "Παρακαλώ επιλέξτε έναν έγκυρο φάκελο εξωτερικού σκληρού δίσκου.",
        "err_date": "Παρακαλώ εισάγετε την ημερομηνία ως ΕΕΕΕ-ΜΜ-ΗΗ.",
        "err_read_sd": "Δεν ήταν δυνατή η ανάγνωση της κάρτας SD:\n{error}",
        "err_no_videos": "Δεν βρέθηκαν αρχεία βίντεο σε αυτή την κάρτα SD.",
        "err_create_folder": "Δεν ήταν δυνατή η δημιουργία του φακέλου προορισμού:\n{error}",
        "dlg_browse_sd_title": "Επιλέξτε την κάρτα SD",
        "dlg_browse_hdd_title": "Επιλέξτε τον εξωτερικό σκληρό δίσκο",
        "msg_success": "Επιτυχία! Αντιγράφηκαν και ελέγχθηκαν {copied} αρχείο(α) βίντεο.\n\nΚάθε αρχείο ελέγχθηκε byte-προς-byte σε σχέση με το πρωτότυπο στην κάρτα SD.\n\nΑποθηκεύτηκε στο:\n{folder}",
        "msg_warning_failed": "{n} αρχείο(α) απέτυχαν να αντιγραφούν.",
        "msg_warning_unverified": "{n} αρχείο(α) αντιγράφηκαν αλλά δεν ταίριαζαν με το πρωτότυπο (πιθανό σφάλμα ανάγνωσης της κάρτας SD ή κακή σύνδεση) - δοκιμάστε ξανά.",
        "msg_warning_body": "{copied} από {total} αρχεία αντιγράφηκαν και ελέγχθηκαν με επιτυχία.\n\n{details}\n\nΔείτε το info.txt στο:\n{folder}",
        "msg_warning_metadata": "Τα βίντεο αντιγράφηκαν, αλλά τα αρχεία σημειώσεων/ιστορικού δεν ήταν δυνατό να γραφτούν στον σκληρό δίσκο (μήπως αποσυνδέθηκε;). Η περιγραφή σας ίσως να μην αποθηκεύτηκε.",
        "not_enough_space": "Δεν υπάρχει αρκετός ελεύθερος χώρος στον σκληρό δίσκο.\n\nΑπαιτούνται: {needed}\nΔιαθέσιμα: {available}",
        "duplicate_card_msg": "Αυτή η κάρτα SD φαίνεται να έχει ήδη αντιγραφεί εδώ:\n\n{folder}\n(στις {when})\n\nΝα αντιγραφεί ξανά;",
        "same_event_button": "Προσθήκη Άλλης Κάμερας σε Αυτό το Συμβάν",
        "same_event_hint": "Χρησιμοποιεί την ίδια ημερομηνία, όνομα και περιγραφή με το τελευταίο αντίγραφο - απλώς συνδέστε την κάρτα SD της άλλης κάμερας και πατήστε το κουμπί παραπάνω.",
        "same_event_hint_disabled": "Ενεργοποιείται μετά το πρώτο επιτυχημένο αντίγραφο, ώστε να προσθέσετε το υλικό της δεύτερης κάμερας στο ίδιο συμβάν.",
        "history_button": "Προβολή Ιστορικού Αντιγράφων",
        "history_title": "Ιστορικό Αντιγράφων",
        "history_search_label": "Αναζήτηση:",
        "history_empty": "Δεν βρέθηκαν ακόμα αντίγραφα σε αυτόν τον σκληρό δίσκο.",
        "history_close": "Κλείσιμο",
        "eject_button": "Αποσύνδεση Κάρτας SD & Σκληρού Δίσκου",
        "eject_confirm": "Αποσύνδεση και της κάρτας SD και του σκληρού δίσκου τώρα;\n\nΒεβαιωθείτε ότι κάθε αντιγραφή έχει ολοκληρωθεί.",
        "eject_ok": "Αποσυνδέθηκε με ασφάλεια - μπορείτε τώρα να το αφαιρέσετε.",
        "eject_fail": "Δεν ήταν δυνατή η αποσύνδεση - ίσως χρειαστεί να το αφαιρέσετε χειροκίνητα.",
        "update_check_button": "Έλεγχος για Ενημερώσεις",
        "update_not_configured": "Ο έλεγχος ενημερώσεων δεν έχει ρυθμιστεί ακόμα.",
        "update_check_failed": "Δεν ήταν δυνατός ο έλεγχος για ενημερώσεις (πρόβλημα σύνδεσης στο διαδίκτυο;).",
        "update_none": "Χρησιμοποιείτε την πιο πρόσφατη έκδοση ({version}).",
        "update_available_msg": "Υπάρχει νεότερη έκδοση διαθέσιμη: {version} (έχετε {current}).\n\nΆνοιγμα της σελίδας λήψης;",
    },
    "fr": {
        "app_title": "Sauvegarde Vidéo Carte SD",
        "language_label": "Langue :",
        "source_group": "1. Carte SD (source)",
        "dest_group": "2. Disque Dur Externe (destination)",
        "browse": "Parcourir...",
        "detected_label": "Détecté :",
        "no_drives": "Aucun disque externe détecté - utilisez Parcourir.",
        "refresh_drives": "Actualiser les disques détectés",
        "details_group": "3. Détails de l'enregistrement",
        "date_label": "Date de l'enregistrement :",
        "date_hint": "(AAAA-MM-JJ)",
        "camera_label": "Caméra :",
        "event_name_label": "Nom de l'événement :",
        "event_name_hint": "(ex. Fête d'anniversaire, Journée à la plage - laissez vide pour l'appeler "
                            "simplement \"Event\")",
        "description_label": "Description :",
        "important_check": "Marquer ce jour comme TRÈS IMPORTANT",
        "copy_button": "Copier les vidéos maintenant",
        "status_scanning": "Recherche de fichiers vidéo sur la carte SD...",
        "status_copying": "Copie du fichier {i} sur {total} : {name}",
        "status_verifying": "Vérification du fichier {i} sur {total} : {name}",
        "status_done": "Terminé. {copied} fichiers sur {total} copiés et vérifiés dans :\n{folder}",
        "status_done_problems": "Terminé avec des problèmes : {copied} fichiers sur {total} copiés et "
                                 "vérifiés. {problems} fichier(s) ont posé problème - voir info.txt dans "
                                 "le dossier de destination.",
        "err_select_sd": "Veuillez sélectionner un dossier de carte SD valide.",
        "err_select_hdd": "Veuillez sélectionner un dossier de disque dur de destination valide.",
        "err_date": "Veuillez saisir la date au format AAAA-MM-JJ.",
        "err_read_sd": "Impossible de lire la carte SD :\n{error}",
        "err_no_videos": "Aucun fichier vidéo trouvé sur cette carte SD.",
        "err_create_folder": "Impossible de créer le dossier de destination :\n{error}",
        "dlg_browse_sd_title": "Sélectionnez la carte SD",
        "dlg_browse_hdd_title": "Sélectionnez le disque dur externe",
        "msg_success": "Succès ! {copied} fichier(s) vidéo copié(s) et vérifié(s).\n\nChaque fichier a "
                        "été vérifié octet par octet par rapport à l'original sur la carte SD.\n\n"
                        "Enregistré dans :\n{folder}",
        "msg_warning_failed": "{n} fichier(s) n'ont pas pu être copiés.",
        "msg_warning_unverified": "{n} fichier(s) copiés mais ne correspondaient pas à l'original "
                                   "(erreur de lecture de la carte SD ou mauvaise connexion possible) - "
                                   "réessayez.",
        "msg_warning_body": "{copied} fichiers sur {total} copiés et vérifiés avec succès.\n\n{details}"
                             "\n\nVoir info.txt dans :\n{folder}",
        "msg_warning_metadata": "Les vidéos ont été copiées, mais les fichiers de notes/journal "
                                  "n'ont pas pu être écrits sur le disque dur (a-t-il été débranché ?). "
                                  "Votre description n'a peut-être pas été enregistrée.",
        "not_enough_space": "Espace libre insuffisant sur le disque dur.\n\nNécessaire : {needed}\n"
                             "Disponible : {available}",
        "duplicate_card_msg": "Cette carte SD semble avoir déjà été copiée ici auparavant :\n\n{folder}"
                               "\n(le {when})\n\nLa copier à nouveau quand même ?",
        "same_event_button": "Ajouter une Autre Caméra à cet Événement",
        "same_event_hint": "Utilise la même date, le même nom et la même description que la dernière "
                            "sauvegarde - branchez simplement la carte SD de l'autre caméra et cliquez "
                            "sur le bouton ci-dessus.",
        "same_event_hint_disabled": "Ce bouton s'active après votre première copie réussie, afin que "
                                     "vous puissiez ajouter les vidéos de la seconde caméra au même "
                                     "événement.",
        "history_button": "Voir l'Historique des Sauvegardes",
        "history_title": "Historique des Sauvegardes",
        "history_search_label": "Recherche :",
        "history_empty": "Aucune sauvegarde trouvée pour l'instant sur ce disque dur.",
        "history_close": "Fermer",
        "eject_button": "Éjecter la Carte SD et le Disque Dur",
        "eject_confirm": "Éjecter maintenant la carte SD et le disque dur ?\n\nAssurez-vous d'abord que "
                          "toute copie est terminée.",
        "eject_ok": "Éjecté en toute sécurité - vous pouvez maintenant le débrancher.",
        "eject_fail": "Impossible d'éjecter - vous devrez peut-être l'éjecter manuellement.",
        "update_check_button": "Vérifier les Mises à Jour",
        "update_not_configured": "La vérification des mises à jour n'est pas encore configurée.",
        "update_check_failed": "Impossible de vérifier les mises à jour (pas de connexion internet ?).",
        "update_none": "Vous utilisez déjà la dernière version ({version}).",
        "update_available_msg": "Une nouvelle version est disponible : {version} (vous avez {current})."
                                 "\n\nOuvrir la page de téléchargement ?",
    },
    "de": {
        "app_title": "SD-Karte Video-Backup",
        "language_label": "Sprache:",
        "source_group": "1. SD-Karte (Quelle)",
        "dest_group": "2. Externe Festplatte (Ziel)",
        "browse": "Durchsuchen...",
        "detected_label": "Erkannt:",
        "no_drives": "Keine externen Laufwerke erkannt - bitte Durchsuchen verwenden.",
        "refresh_drives": "Erkannte Laufwerke aktualisieren",
        "details_group": "3. Aufnahmedetails",
        "date_label": "Aufnahmedatum:",
        "date_hint": "(JJJJ-MM-TT)",
        "camera_label": "Kamera:",
        "event_name_label": "Ereignisname:",
        "event_name_hint": "(z. B. Geburtstagsfeier, Strandtag - leer lassen, um es einfach \"Event\" "
                            "zu nennen)",
        "description_label": "Beschreibung:",
        "important_check": "Diesen Tag als SEHR WICHTIG markieren",
        "copy_button": "Videos jetzt kopieren",
        "status_scanning": "SD-Karte wird nach Videodateien durchsucht...",
        "status_copying": "Kopiere Datei {i} von {total}: {name}",
        "status_verifying": "Überprüfe Datei {i} von {total}: {name}",
        "status_done": "Fertig. {copied} von {total} Dateien kopiert und überprüft nach:\n{folder}",
        "status_done_problems": "Fertig mit Problemen: {copied} von {total} Dateien kopiert und "
                                 "überprüft. {problems} Datei(en) hatten Probleme - siehe info.txt im "
                                 "Zielordner.",
        "err_select_sd": "Bitte wählen Sie einen gültigen SD-Kartenordner aus.",
        "err_select_hdd": "Bitte wählen Sie einen gültigen Zielordner auf der Festplatte aus.",
        "err_date": "Bitte geben Sie das Datum im Format JJJJ-MM-TT ein.",
        "err_read_sd": "Die SD-Karte konnte nicht gelesen werden:\n{error}",
        "err_no_videos": "Auf dieser SD-Karte wurden keine Videodateien gefunden.",
        "err_create_folder": "Der Zielordner konnte nicht erstellt werden:\n{error}",
        "dlg_browse_sd_title": "SD-Karte auswählen",
        "dlg_browse_hdd_title": "Externe Festplatte auswählen",
        "msg_success": "Erfolg! {copied} Videodatei(en) kopiert und überprüft.\n\nJede Datei wurde Byte "
                        "für Byte mit dem Original auf der SD-Karte verglichen.\n\nGespeichert unter:\n"
                        "{folder}",
        "msg_warning_failed": "{n} Datei(en) konnten nicht kopiert werden.",
        "msg_warning_unverified": "{n} Datei(en) wurden kopiert, stimmten aber nicht mit dem Original "
                                   "überein (möglicher Lesefehler der SD-Karte oder schlechte "
                                   "Verbindung) - bitte erneut versuchen.",
        "msg_warning_body": "{copied} von {total} Dateien erfolgreich kopiert und überprüft.\n\n"
                             "{details}\n\nSiehe info.txt in:\n{folder}",
        "msg_warning_metadata": "Die Videos wurden kopiert, aber die Notiz-/Protokolldateien "
                                  "konnten nicht auf die Festplatte geschrieben werden (wurde sie "
                                  "abgezogen?). Ihre Beschreibung wurde möglicherweise nicht gespeichert.",
        "not_enough_space": "Nicht genügend freier Speicherplatz auf der Festplatte.\n\nBenötigt: "
                             "{needed}\nVerfügbar: {available}",
        "duplicate_card_msg": "Diese SD-Karte scheint bereits hierher kopiert worden zu sein:\n\n"
                               "{folder}\n(am {when})\n\nTrotzdem erneut kopieren?",
        "same_event_button": "Weitere Kamera zu diesem Ereignis hinzufügen",
        "same_event_hint": "Verwendet dasselbe Datum, denselben Namen und dieselbe Beschreibung wie die "
                            "letzte Sicherung - einfach die SD-Karte der anderen Kamera einstecken und "
                            "die Schaltfläche oben klicken.",
        "same_event_hint_disabled": "Wird nach Ihrer ersten erfolgreichen Kopie aktiviert, damit Sie "
                                     "das Material der zweiten Kamera zum selben Ereignis hinzufügen "
                                     "können.",
        "history_button": "Sicherungsverlauf anzeigen",
        "history_title": "Sicherungsverlauf",
        "history_search_label": "Suche:",
        "history_empty": "Auf dieser Festplatte wurden noch keine Sicherungen gefunden.",
        "history_close": "Schließen",
        "eject_button": "SD-Karte & Festplatte auswerfen",
        "eject_confirm": "Jetzt sowohl die SD-Karte als auch die Festplatte auswerfen?\n\nStellen Sie "
                          "sicher, dass jede Kopie abgeschlossen ist.",
        "eject_ok": "Sicher ausgeworfen - Sie können es jetzt abziehen.",
        "eject_fail": "Auswerfen nicht möglich - Sie müssen es möglicherweise manuell auswerfen.",
        "update_check_button": "Nach Updates suchen",
        "update_not_configured": "Die Update-Prüfung ist noch nicht eingerichtet.",
        "update_check_failed": "Es konnte nicht nach Updates gesucht werden (keine Internetverbindung?).",
        "update_none": "Sie verwenden bereits die neueste Version ({version}).",
        "update_available_msg": "Eine neuere Version ist verfügbar: {version} (Sie haben {current})."
                                 "\n\nDownload-Seite öffnen?",
    },
    "it": {
        "app_title": "Backup Video Scheda SD",
        "language_label": "Lingua:",
        "source_group": "1. Scheda SD (origine)",
        "dest_group": "2. Disco Rigido Esterno (destinazione)",
        "browse": "Sfoglia...",
        "detected_label": "Rilevati:",
        "no_drives": "Nessun disco esterno rilevato - usa Sfoglia.",
        "refresh_drives": "Aggiorna dischi rilevati",
        "details_group": "3. Dettagli della registrazione",
        "date_label": "Data della registrazione:",
        "date_hint": "(AAAA-MM-GG)",
        "camera_label": "Videocamera:",
        "event_name_label": "Nome evento:",
        "event_name_hint": "(es. Festa di compleanno, Giornata al mare - lascia vuoto per chiamarlo "
                            "semplicemente \"Event\")",
        "description_label": "Descrizione:",
        "important_check": "Contrassegna questo giorno come MOLTO IMPORTANTE",
        "copy_button": "Copia i video ora",
        "status_scanning": "Ricerca di file video sulla scheda SD in corso...",
        "status_copying": "Copia del file {i} di {total}: {name}",
        "status_verifying": "Verifica del file {i} di {total}: {name}",
        "status_done": "Completato. {copied} di {total} file copiati e verificati in:\n{folder}",
        "status_done_problems": "Completato con problemi: {copied} di {total} file copiati e "
                                 "verificati. {problems} file hanno avuto problemi - vedi info.txt "
                                 "nella cartella di destinazione.",
        "err_select_sd": "Seleziona una cartella valida per la scheda SD.",
        "err_select_hdd": "Seleziona una cartella di destinazione valida sul disco rigido.",
        "err_date": "Inserisci la data nel formato AAAA-MM-GG.",
        "err_read_sd": "Impossibile leggere la scheda SD:\n{error}",
        "err_no_videos": "Nessun file video trovato su questa scheda SD.",
        "err_create_folder": "Impossibile creare la cartella di destinazione:\n{error}",
        "dlg_browse_sd_title": "Seleziona la scheda SD",
        "dlg_browse_hdd_title": "Seleziona il disco rigido esterno",
        "msg_success": "Successo! {copied} file video copiati e verificati.\n\nOgni file è stato "
                        "controllato byte per byte rispetto all'originale sulla scheda SD.\n\n"
                        "Salvato in:\n{folder}",
        "msg_warning_failed": "{n} file non sono stati copiati.",
        "msg_warning_unverified": "{n} file copiati ma non corrispondenti all'originale (possibile "
                                   "errore di lettura della scheda SD o connessione instabile) - "
                                   "riprova.",
        "msg_warning_body": "{copied} di {total} file copiati e verificati con successo.\n\n{details}"
                             "\n\nVedi info.txt in:\n{folder}",
        "msg_warning_metadata": "I video sono stati copiati, ma i file di note/cronologia non "
                                  "sono stati scritti sul disco rigido (è stato scollegato?). La tua "
                                  "descrizione potrebbe non essere stata salvata.",
        "not_enough_space": "Spazio libero insufficiente sul disco rigido.\n\nNecessario: {needed}\n"
                             "Disponibile: {available}",
        "duplicate_card_msg": "Questa scheda SD sembra essere già stata copiata qui in precedenza:\n\n"
                               "{folder}\n(il {when})\n\nCopiarla di nuovo comunque?",
        "same_event_button": "Aggiungi un'Altra Videocamera a Questo Evento",
        "same_event_hint": "Usa la stessa data, nome e descrizione dell'ultimo backup - collega "
                            "semplicemente la scheda SD dell'altra videocamera e premi il pulsante "
                            "sopra.",
        "same_event_hint_disabled": "Si attiva dopo la prima copia riuscita, così puoi aggiungere il "
                                     "materiale della seconda videocamera allo stesso evento.",
        "history_button": "Visualizza Cronologia Backup",
        "history_title": "Cronologia Backup",
        "history_search_label": "Cerca:",
        "history_empty": "Nessun backup trovato finora su questo disco rigido.",
        "history_close": "Chiudi",
        "eject_button": "Espelli Scheda SD e Disco Rigido",
        "eject_confirm": "Espellere ora sia la scheda SD che il disco rigido?\n\nAssicurati prima che "
                          "ogni copia sia terminata.",
        "eject_ok": "Espulso in sicurezza - ora puoi scollegarlo.",
        "eject_fail": "Impossibile espellere - potrebbe essere necessario espellerlo manualmente.",
        "update_check_button": "Controlla Aggiornamenti",
        "update_not_configured": "Il controllo degli aggiornamenti non è ancora configurato.",
        "update_check_failed": "Impossibile controllare gli aggiornamenti (nessuna connessione "
                                "internet?).",
        "update_none": "Stai già usando l'ultima versione ({version}).",
        "update_available_msg": "È disponibile una nuova versione: {version} (hai {current}).\n\n"
                                 "Aprire la pagina di download?",
    },
}


# ---------------------------------------------------------------------------
# Config (remembers the last-used destination drive and language between runs)
# ---------------------------------------------------------------------------

def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_config(cfg: dict) -> None:
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Drive detection
# ---------------------------------------------------------------------------

def list_candidate_drives() -> list[str]:
    """Return a list of plausible removable/external drive root paths."""
    drives = []

    if sys.platform == "darwin":
        volumes = Path("/Volumes")
        if volumes.exists():
            for entry in sorted(volumes.iterdir()):
                if entry.is_dir():
                    drives.append(str(entry))

    elif sys.platform.startswith("win"):
        import ctypes

        DRIVE_REMOVABLE = 2
        DRIVE_FIXED = 3
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for i, letter in enumerate(string.ascii_uppercase):
            if not (bitmask >> i) & 1:
                continue
            root = f"{letter}:\\"
            try:
                drive_type = ctypes.windll.kernel32.GetDriveTypeW(root)
            except Exception:
                continue
            # C: is always fixed/local - skip it, everything else external
            # is fair game (removable card readers and external HDDs both
            # report as DRIVE_REMOVABLE or DRIVE_FIXED depending on the
            # reader/enclosure).
            if letter == "C":
                continue
            if drive_type in (DRIVE_REMOVABLE, DRIVE_FIXED):
                drives.append(root)

    else:  # Linux fallback, e.g. /media/<user>/<label>
        for base in (Path("/media"), Path("/mnt")):
            if base.exists():
                for user_dir in base.iterdir():
                    if user_dir.is_dir():
                        for entry in user_dir.iterdir() if user_dir.is_dir() else []:
                            drives.append(str(entry))

    return drives


def find_video_files(root: Path) -> list[Path]:
    files = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if Path(name).suffix.lower() in VIDEO_EXTENSIONS:
                files.append(Path(dirpath) / name)
    return files


# ---------------------------------------------------------------------------
# Folder naming helpers
# ---------------------------------------------------------------------------

EVENT_RE = re.compile(r"^(\d{2})_EVENT_")


def next_event_number(date_folder: Path) -> int:
    """Look at existing NN_EVENT_... folders for this date and return the
    next free ordering number (starting at 1), regardless of what the event
    was named."""
    if not date_folder.exists():
        return 1
    highest = 0
    for entry in date_folder.iterdir():
        if entry.is_dir():
            m = EVENT_RE.match(entry.name)
            if m:
                highest = max(highest, int(m.group(1)))
    return highest + 1


def sanitize_event_name(name: str) -> str:
    """Turn free-form user text into a filesystem-safe folder name segment.
    Keeps letters and numbers from any of the alphabets the app supports
    (accented and non-Latin scripts included) and turns spaces into
    underscores; strips characters that aren't safe in Windows/Mac folder
    names. Falls back to "Event" if nothing usable is left."""
    name = name.strip()
    if not name:
        return "Event"
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^A-Za-z0-9_\-À-ÖØ-öø-ÿĀ-ſͰ-Ͽἀ-῿]", "", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name[:40] if name else "Event"


def open_in_file_manager(path: Path) -> None:
    """Open the given folder in Finder / Explorer / the default file manager."""
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        elif sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except OSError:
        pass


COPY_CHUNK_SIZE = 1024 * 1024


def copy_with_hash(src: Path, dest: Path) -> str:
    """Copy src to dest, returning the SHA-256 of the bytes read from the
    source. Hashing as the data streams through means the (often slow) SD
    card is read once rather than twice: verification afterwards only has
    to read back the freshly written destination file."""
    digest = hashlib.sha256()
    with src.open("rb") as fsrc, dest.open("wb") as fdst:
        while True:
            chunk = fsrc.read(COPY_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
            fdst.write(chunk)
    shutil.copystat(src, dest)
    return digest.hexdigest()


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(COPY_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unique_destination(dest_dir: Path, filename: str) -> Path:
    """Avoid clobbering an existing file with the same name."""
    candidate = dest_dir / filename
    if not candidate.exists():
        return candidate
    stem, suffix = Path(filename).stem, Path(filename).suffix
    n = 2
    while True:
        candidate = dest_dir / f"{stem}_{n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def format_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


# ---------------------------------------------------------------------------
# Duplicate-card detection - a lightweight fingerprint (filenames + sizes,
# not file contents) of what's on the card, remembered per hard drive so we
# can warn if the same card looks like it's already been backed up.
# ---------------------------------------------------------------------------

def fingerprint_source(files: list[Path], source_root: Path) -> str:
    parts = sorted(
        (str(f.relative_to(source_root)), f.stat().st_size) for f in files
    )
    return hashlib.sha256(repr(parts).encode("utf-8")).hexdigest()


def load_registry(dest_root: Path) -> dict:
    path = dest_root / REGISTRY_FILENAME
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_registry(dest_root: Path, registry: dict) -> bool:
    try:
        (dest_root / REGISTRY_FILENAME).write_text(
            json.dumps(registry, indent=2), encoding="utf-8"
        )
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Safe eject
# ---------------------------------------------------------------------------

def eject_drive(path: str) -> bool:
    try:
        if sys.platform == "darwin":
            r = subprocess.run(["diskutil", "eject", path], capture_output=True, timeout=20)
            return r.returncode == 0
        elif sys.platform.startswith("win"):
            drive_root = path[:2] + "\\" if len(path) >= 2 and path[1] == ":" else path
            # PowerShell parses -Command as source, so the path must never be
            # interpolated raw: pass it as a bound parameter instead. (Doubling
            # quotes would also work, but a real parameter can't be escaped out
            # of at all.)
            script = (
                "param($p) "
                "$s = New-Object -ComObject Shell.Application; "
                "$s.Namespace(17).ParseName($p).InvokeVerb('Eject')"
            )
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script, "-p", drive_root],
                capture_output=True, timeout=20,
            )
            return r.returncode == 0
        else:
            r = subprocess.run(["umount", path], capture_output=True, timeout=20)
            return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


# ---------------------------------------------------------------------------
# Update check - looks at a public GitHub repo's latest release. No network
# call happens unless UPDATE_REPO is set. See the auto-update note in
# README.md for why the repo needs to be public rather than private.
# ---------------------------------------------------------------------------

def version_tuple(v: str) -> tuple:
    try:
        return tuple(int(p) for p in v.strip().lstrip("v").split("."))
    except ValueError:
        return (0,)


def check_for_update(timeout: float = 4.0):
    if not UPDATE_REPO:
        return None
    url = f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"
    req = urllib.request.Request(
        url, headers={"Accept": "application/vnd.github+json", "User-Agent": "sd-video-backup"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None
    tag = str(data.get("tag_name", "")).strip()
    html_url = data.get("html_url", "")
    if not tag or not html_url:
        return None
    return {"version": tag.lstrip("v"), "url": html_url}


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.geometry("640x760")
        self.minsize(560, 700)

        self.config_data = load_config()
        self.lang = self.config_data.get("language", "en")
        if self.lang not in STRINGS:
            self.lang = "en"

        self.source_path = tk.StringVar()
        self.dest_path = tk.StringVar(value=self.config_data.get("last_destination", ""))
        self.date_var = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        self.camera_var = tk.StringVar(value="Button")
        self.event_name_var = tk.StringVar(value="")
        self.important_var = tk.BooleanVar(value=False)
        self.lang_display_var = tk.StringVar(value=LANGUAGES[self.lang])

        # Set after a successful copy so "Add Another Camera to This Event"
        # can reuse the same date/name/description/event-number.
        self.last_event_info = None
        self._pending_event_num = None

        self._build_ui()
        self._apply_language()
        self._refresh_drive_suggestions()

    # -- Translation helper ---------------------------------------------------

    def t(self, key: str, **kwargs) -> str:
        text = STRINGS[self.lang][key]
        return text.format(**kwargs) if kwargs else text

    # -- UI construction ---------------------------------------------------

    def _build_ui(self):
        pad = {"padx": 12, "pady": 6}

        top_row = tk.Frame(self)
        top_row.pack(fill="x", **pad)
        self.header = tk.Label(top_row, font=("Helvetica", 16, "bold"))
        self.header.pack(side="left")

        lang_box = tk.Frame(top_row)
        lang_box.pack(side="right")
        self.language_label = tk.Label(lang_box, font=("Helvetica", 10))
        self.language_label.pack(side="left", padx=(0, 4))
        self.lang_combo = ttk.Combobox(
            lang_box, textvariable=self.lang_display_var, state="readonly",
            values=list(LANGUAGES.values()), width=12,
        )
        self.lang_combo.pack(side="left")
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_language_change)

        # Source
        self.src_frame = tk.LabelFrame(self)
        self.src_frame.pack(fill="x", **pad)
        self.source_browse_btn = self._build_path_row(self.src_frame, self.source_path, self._browse_source)
        self.source_suggestions = tk.Frame(self.src_frame)
        self.source_suggestions.pack(fill="x", padx=8, pady=(0, 8))

        # Destination
        self.dst_frame = tk.LabelFrame(self)
        self.dst_frame.pack(fill="x", **pad)
        self.dest_browse_btn = self._build_path_row(self.dst_frame, self.dest_path, self._browse_dest)
        self.dest_suggestions = tk.Frame(self.dst_frame)
        self.dest_suggestions.pack(fill="x", padx=8, pady=(0, 8))

        utility_row = tk.Frame(self)
        utility_row.pack(fill="x", padx=12)
        self.refresh_btn = tk.Button(utility_row, command=self._refresh_drive_suggestions)
        self.refresh_btn.pack(side="left")
        self.history_button = tk.Button(utility_row, command=self._open_history)
        self.history_button.pack(side="left", padx=(8, 0))

        # Details
        self.details_frame = tk.LabelFrame(self)
        self.details_frame.pack(fill="x", **pad)

        row1 = tk.Frame(self.details_frame)
        row1.pack(fill="x", padx=8, pady=6)
        self.date_label = tk.Label(row1, width=18, anchor="w")
        self.date_label.pack(side="left")
        date_entry = tk.Entry(row1, textvariable=self.date_var, width=14)
        date_entry.pack(side="left")
        self.date_hint_label = tk.Label(row1, fg="gray")
        self.date_hint_label.pack(side="left", padx=6)

        row2 = tk.Frame(self.details_frame)
        row2.pack(fill="x", padx=8, pady=6)
        self.camera_label = tk.Label(row2, width=18, anchor="w")
        self.camera_label.pack(side="left")
        camera_menu = ttk.Combobox(
            row2, textvariable=self.camera_var, state="readonly",
            values=list(CAMERA_FOLDER_NAMES.keys()), width=20,
        )
        camera_menu.pack(side="left")

        row3 = tk.Frame(self.details_frame)
        row3.pack(fill="x", padx=8, pady=6)
        row3_entry_line = tk.Frame(row3)
        row3_entry_line.pack(fill="x")
        self.event_name_label = tk.Label(row3_entry_line, width=18, anchor="w")
        self.event_name_label.pack(side="left")
        event_name_entry = tk.Entry(row3_entry_line, textvariable=self.event_name_var, width=30)
        event_name_entry.pack(side="left", fill="x", expand=True)
        self.event_name_hint_label = tk.Label(row3, fg="gray", anchor="w", justify="left", wraplength=460)
        self.event_name_hint_label.pack(fill="x", padx=(140, 0), pady=(2, 0))

        row4 = tk.Frame(self.details_frame)
        row4.pack(fill="x", padx=8, pady=(6, 0))
        self.description_label = tk.Label(row4, width=18, anchor="nw")
        self.description_label.pack(side="left")
        self.description_text = tk.Text(row4, height=5, width=50, wrap="word")
        self.description_text.pack(side="left", fill="x", expand=True)

        row5 = tk.Frame(self.details_frame)
        row5.pack(fill="x", padx=8, pady=8)
        self.important_check = tk.Checkbutton(
            row5, variable=self.important_var, font=("Helvetica", 10, "bold"),
        )
        self.important_check.pack(side="left")

        # Same-event repeat (enabled after the first successful copy)
        same_event_frame = tk.Frame(self)
        same_event_frame.pack(fill="x", padx=12, pady=(0, 4))
        self.same_event_button = tk.Button(
            same_event_frame, state="disabled", command=self._use_same_event,
        )
        self.same_event_button.pack(fill="x", ipady=4)
        self.same_event_hint_label = tk.Label(
            same_event_frame, fg="gray", anchor="w", justify="left", wraplength=600,
        )
        self.same_event_hint_label.pack(fill="x", pady=(2, 0))

        # Action
        action_frame = tk.Frame(self)
        action_frame.pack(fill="x", **pad)
        self.copy_button = tk.Button(
            action_frame, font=("Helvetica", 12, "bold"),
            bg="#2e7d32", fg="white", command=self._start_copy,
        )
        self.copy_button.pack(fill="x", ipady=8)

        self.progress = ttk.Progressbar(self, mode="determinate")
        self.progress.pack(fill="x", padx=12, pady=(4, 0))

        self.status_label = tk.Label(self, text="", anchor="w", justify="left", wraplength=600)
        self.status_label.pack(fill="x", padx=12, pady=8)

        bottom_row = tk.Frame(self)
        bottom_row.pack(fill="x", padx=12, pady=(0, 10))
        self.eject_button = tk.Button(bottom_row, command=self._eject_drives)
        self.eject_button.pack(side="left")
        self.update_button = tk.Button(bottom_row, command=self._check_for_updates)
        self.update_button.pack(side="right")

    def _build_path_row(self, parent, var, browse_cmd):
        row = tk.Frame(parent)
        row.pack(fill="x", padx=8, pady=(8, 4))
        entry = tk.Entry(row, textvariable=var)
        entry.pack(side="left", fill="x", expand=True)
        browse = tk.Button(row, command=browse_cmd)
        browse.pack(side="left", padx=(6, 0))
        return browse

    # -- Language switching ---------------------------------------------------

    def _on_language_change(self, _event=None):
        display = self.lang_display_var.get()
        for code, label in LANGUAGES.items():
            if label == display:
                self.lang = code
                break
        self.config_data["language"] = self.lang
        save_config(self.config_data)
        self._apply_language()
        self._refresh_drive_suggestions()

    def _apply_language(self):
        self.title(self.t("app_title"))
        self.header.config(text=self.t("app_title"))
        self.language_label.config(text=self.t("language_label"))
        self.src_frame.config(text=self.t("source_group"))
        self.dst_frame.config(text=self.t("dest_group"))
        self.source_browse_btn.config(text=self.t("browse"))
        self.dest_browse_btn.config(text=self.t("browse"))
        self.refresh_btn.config(text=self.t("refresh_drives"))
        self.history_button.config(text=self.t("history_button"))
        self.details_frame.config(text=self.t("details_group"))
        self.date_label.config(text=self.t("date_label"))
        self.date_hint_label.config(text=self.t("date_hint"))
        self.camera_label.config(text=self.t("camera_label"))
        self.event_name_label.config(text=self.t("event_name_label"))
        self.event_name_hint_label.config(text=self.t("event_name_hint"))
        self.description_label.config(text=self.t("description_label"))
        self.important_check.config(text=self.t("important_check"))
        self.same_event_button.config(text=self.t("same_event_button"))
        self.same_event_hint_label.config(
            text=self.t("same_event_hint") if self.last_event_info else self.t("same_event_hint_disabled")
        )
        self.copy_button.config(text=self.t("copy_button"))
        self.eject_button.config(text=self.t("eject_button"))
        self.update_button.config(text=self.t("update_check_button"))

    # -- Drive suggestions ---------------------------------------------------

    def _refresh_drive_suggestions(self):
        for frame in (self.source_suggestions, self.dest_suggestions):
            for widget in frame.winfo_children():
                widget.destroy()

        drives = list_candidate_drives()
        if not drives:
            tk.Label(self.source_suggestions, text=self.t("no_drives"), fg="gray").pack(anchor="w")
            tk.Label(self.dest_suggestions, text=self.t("no_drives"), fg="gray").pack(anchor="w")
            return

        tk.Label(self.source_suggestions, text=self.t("detected_label"), fg="gray").pack(side="left")
        for d in drives:
            tk.Button(self.source_suggestions, text=Path(d).name or d,
                      command=lambda d=d: self.source_path.set(d)).pack(side="left", padx=3)

        tk.Label(self.dest_suggestions, text=self.t("detected_label"), fg="gray").pack(side="left")
        for d in drives:
            tk.Button(self.dest_suggestions, text=Path(d).name or d,
                      command=lambda d=d: self.dest_path.set(d)).pack(side="left", padx=3)

    def _browse_source(self):
        path = filedialog.askdirectory(title=self.t("dlg_browse_sd_title"))
        if path:
            self.source_path.set(path)

    def _browse_dest(self):
        path = filedialog.askdirectory(title=self.t("dlg_browse_hdd_title"))
        if path:
            self.dest_path.set(path)

    @staticmethod
    def _is_valid_date(s: str) -> bool:
        try:
            date.fromisoformat(s)
            return True
        except ValueError:
            return False

    # -- Copy logic -----------------------------------------------------------

    def _start_copy(self):
        source = self.source_path.get().strip()
        dest_root = self.dest_path.get().strip()
        date_str = self.date_var.get().strip()
        camera = self.camera_var.get()
        event_name = sanitize_event_name(self.event_name_var.get())
        description = self.description_text.get("1.0", "end").strip()
        important = self.important_var.get()

        if not source or not Path(source).is_dir():
            messagebox.showerror(self.t("app_title"), self.t("err_select_sd"))
            return
        if not dest_root or not Path(dest_root).is_dir():
            messagebox.showerror(self.t("app_title"), self.t("err_select_hdd"))
            return
        if not self._is_valid_date(date_str):
            messagebox.showerror(self.t("app_title"), self.t("err_date"))
            return

        # The pinned event number only belongs to the event it was pinned
        # from. If the user edited the date (or switched drives) afterwards,
        # reusing it would merge this footage into an unrelated event folder
        # on the new date, so fall back to normal auto-numbering.
        event_num_override = None
        if self._pending_event_num is not None:
            pinned = self._pending_event_num
            if pinned["date_str"] == date_str and pinned["dest_root"] == dest_root:
                event_num_override = pinned["event_num"]
        self._pending_event_num = None

        self._set_busy(True)
        self.status_label.config(text=self.t("status_scanning"))

        thread = threading.Thread(
            target=self._do_copy,
            args=(Path(source), Path(dest_root), date_str, camera, event_name, description,
                  important, event_num_override),
            daemon=True,
        )
        thread.start()

    def _ask_yesno_on_main_thread(self, kind: str, title: str, message: str) -> bool:
        """Block this background thread until the user answers a yes/no
        dialog shown on the main thread (Tk dialogs must run there)."""
        result = {}
        done = threading.Event()

        def ask():
            fn = messagebox.askyesno if kind == "yesno" else messagebox.showinfo
            result["v"] = fn(title, message)
            done.set()

        self.after(0, ask)
        done.wait()
        return bool(result.get("v"))

    def _do_copy(self, source: Path, dest_root: Path, date_str: str, camera: str,
                 event_name: str, description: str, important: bool,
                 event_num_override: int | None = None):
        try:
            files = find_video_files(source)
        except OSError as e:
            self._on_error(self.t("err_read_sd", error=e))
            return

        if not files:
            self._on_error(self.t("err_no_videos"))
            return

        registry = load_registry(dest_root)
        fingerprint = fingerprint_source(files, source)
        prior = registry.get(fingerprint)
        if prior:
            proceed = self._ask_yesno_on_main_thread(
                "yesno", self.t("app_title"),
                self.t("duplicate_card_msg", folder=prior.get("folder", "?"), when=prior.get("when", "?"))
            )
            if not proceed:
                self._on_cancelled()
                return

        total_bytes = sum(f.stat().st_size for f in files)
        free_bytes = shutil.disk_usage(dest_root).free
        if free_bytes < total_bytes * 1.02:
            self._on_error(self.t("not_enough_space", needed=format_bytes(total_bytes),
                                   available=format_bytes(free_bytes)))
            return

        folder_date = date_str.replace("-", "_")
        date_folder = dest_root / folder_date
        event_num = event_num_override if event_num_override is not None else next_event_number(date_folder)
        event_folder = date_folder / f"{event_num:02d}_EVENT_{event_name}_{folder_date}"
        camera_folder = event_folder / CAMERA_FOLDER_NAMES[camera]

        try:
            camera_folder.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self._on_error(self.t("err_create_folder", error=e))
            return

        total = len(files)
        self._set_progress_max(total)

        copied = 0
        failed = []
        unverified = []
        for i, src_file in enumerate(files, start=1):
            self._set_status(self.t("status_copying", i=i, total=total, name=src_file.name))
            try:
                dest_file = unique_destination(camera_folder, src_file.name)
                source_digest = copy_with_hash(src_file, dest_file)
            except OSError as e:
                failed.append((src_file.name, str(e)))
                self._set_progress(i)
                continue

            self._set_status(self.t("status_verifying", i=i, total=total, name=src_file.name))
            try:
                verified = hash_file(dest_file) == source_digest
            except OSError:
                verified = False
            if verified:
                copied += 1
            else:
                unverified.append(src_file.name)
            self._set_progress(i)

        # Track these separately: the videos themselves can copy perfectly
        # while the drive disappears before the notes/log land, and the user
        # must not be told "success" when their description was lost.
        metadata_ok = self._write_info_file(
            event_folder, camera_folder, date_str, camera, event_name, description,
            important, copied, failed, unverified)
        metadata_ok &= self._append_master_log(
            dest_root, event_folder, date_str, camera, event_name, description,
            important, copied, total)

        if important:
            try:
                (event_folder / "IMPORTANT").write_text(
                    "This event was marked as VERY IMPORTANT.\n"
                    f"Event: {event_name}\n"
                    f"Description: {description}\n",
                    encoding="utf-8",
                )
            except OSError:
                metadata_ok = False

        if copied > 0:
            registry[fingerprint] = {
                "folder": str(event_folder.relative_to(dest_root)),
                "when": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            metadata_ok &= save_registry(dest_root, registry)

        self.config_data["last_destination"] = str(dest_root)
        save_config(self.config_data)

        event_info = {
            "dest_root": str(dest_root), "date_str": date_str, "event_name": event_name,
            "description": description, "important": important, "event_num": event_num,
        } if copied > 0 else None

        self._on_done(copied, total, failed, unverified, event_folder, event_info, metadata_ok)

    @staticmethod
    def _write_info_file(event_folder: Path, camera_folder: Path, date_str: str, camera: str,
                          event_name: str, description: str, important: bool, copied: int,
                          failed: list, unverified: list) -> bool:
        info_path = event_folder / "info.txt"
        lines = [
            f"Date: {date_str}",
            f"Event: {event_name}",
            f"Camera: {camera} ({camera_folder.name})",
            f"Important: {'YES' if important else 'No'}",
            f"Files copied and verified: {copied}",
            f"Copied on: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "Description:",
            description if description else "(none provided)",
        ]
        if failed:
            lines += ["", "Files that FAILED to copy:"] + [f"  - {name}: {err}" for name, err in failed]
        if unverified:
            lines += ["", "Files copied but that FAILED verification (source and copy don't match - retry these):"]
            lines += [f"  - {name}" for name in unverified]
        try:
            existing = info_path.read_text(encoding="utf-8") if info_path.exists() else ""
            info_path.write_text(
                existing + ("\n\n---\n\n" if existing else "") + "\n".join(lines),
                encoding="utf-8",
            )
            return True
        except OSError:
            return False

    @staticmethod
    def _append_master_log(dest_root: Path, event_folder: Path, date_str: str, camera: str,
                            event_name: str, description: str, important: bool, copied: int,
                            total: int) -> bool:
        """Append this event's description to a single running log at the root
        of the hard drive, so there's one file with every recording's
        description in it, in the order they were added."""
        log_path = dest_root / MASTER_LOG_NAME
        entry = "\n".join([
            "=" * 60,
            f"Date: {date_str}" + ("   *** VERY IMPORTANT ***" if important else ""),
            f"Event: {event_name}",
            f"Camera: {camera}",
            f"Folder: {event_folder.relative_to(dest_root)}",
            f"Files: {copied} of {total} copied and verified",
            f"Logged on: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            description if description else "(no description provided)",
            "",
        ])
        try:
            with log_path.open("a", encoding="utf-8") as f:
                f.write(entry + "\n")
            return True
        except OSError:
            return False

    # -- Thread-safe UI updates ----------------------------------------------

    def _set_progress_max(self, value):
        self.after(0, lambda: self.progress.config(maximum=max(value, 1), value=0))

    def _set_progress(self, value):
        self.after(0, lambda: self.progress.config(value=value))

    def _set_status(self, text):
        self.after(0, lambda: self.status_label.config(text=text))

    def _set_busy(self, busy: bool):
        """Lock the controls that must not be touched mid-copy. Ejecting a
        drive while files are being written to it corrupts the copy, so the
        eject button is disabled for the duration rather than just warned
        about in its confirmation dialog."""
        state = "disabled" if busy else "normal"
        self.copy_button.config(state=state)
        self.eject_button.config(state=state)
        if busy:
            self.same_event_button.config(state="disabled")
        elif self.last_event_info:
            self.same_event_button.config(state="normal")

    def _on_error(self, message):
        def show():
            self._set_busy(False)
            self.status_label.config(text="")
            messagebox.showerror(self.t("app_title"), message)
        self.after(0, show)

    def _on_cancelled(self):
        def show():
            self._set_busy(False)
            self.status_label.config(text="")
        self.after(0, show)

    def _on_done(self, copied, total, failed, unverified, event_folder, event_info, metadata_ok=True):
        def show():
            self._set_busy(False)
            problems = len(failed) + len(unverified)

            if event_info:
                self.last_event_info = event_info
                self.same_event_button.config(state="normal")
                self.same_event_hint_label.config(text=self.t("same_event_hint"))

            if problems or not metadata_ok:
                detail_lines = []
                if failed:
                    detail_lines.append(self.t("msg_warning_failed", n=len(failed)))
                if unverified:
                    detail_lines.append(self.t("msg_warning_unverified", n=len(unverified)))
                if not metadata_ok:
                    detail_lines.append(self.t("msg_warning_metadata"))
                self.status_label.config(
                    text=self.t("status_done_problems", copied=copied, total=total,
                                problems=problems + (0 if metadata_ok else 1))
                )
                messagebox.showwarning(
                    self.t("app_title"),
                    self.t("msg_warning_body", copied=copied, total=total,
                           details="\n".join(detail_lines), folder=event_folder)
                )
            else:
                self.status_label.config(
                    text=self.t("status_done", copied=copied, total=total, folder=event_folder)
                )
                messagebox.showinfo(
                    self.t("app_title"),
                    self.t("msg_success", copied=copied, folder=event_folder)
                )

            open_in_file_manager(event_folder)

        self.after(0, show)

    # -- Same-event repeat (item 1) -------------------------------------------

    def _use_same_event(self):
        info = self.last_event_info
        if not info:
            return
        self.date_var.set(info["date_str"])
        self.event_name_var.set(info["event_name"])
        self.description_text.delete("1.0", "end")
        self.description_text.insert("1.0", info["description"])
        self.important_var.set(info["important"])
        self._pending_event_num = {
            "event_num": info["event_num"],
            "date_str": info["date_str"],
            "dest_root": info["dest_root"],
        }

        cameras = list(CAMERA_FOLDER_NAMES.keys())
        other = next((c for c in cameras if c != self.camera_var.get()), self.camera_var.get())
        self.camera_var.set(other)

        self.source_path.set("")
        self.status_label.config(text="")

    # -- History viewer (item 2) ----------------------------------------------

    def _open_history(self):
        dest_root = self.dest_path.get().strip()
        if not dest_root or not Path(dest_root).is_dir():
            messagebox.showerror(self.t("app_title"), self.t("err_select_hdd"))
            return
        log_path = Path(dest_root) / MASTER_LOG_NAME
        if not log_path.exists():
            messagebox.showinfo(self.t("app_title"), self.t("history_empty"))
            return
        try:
            content = log_path.read_text(encoding="utf-8")
        except OSError as e:
            messagebox.showerror(self.t("app_title"), str(e))
            return

        entries = [e.strip() for e in content.split("=" * 60) if e.strip()]

        win = tk.Toplevel(self)
        win.title(self.t("history_title"))
        win.geometry("620x520")

        search_row = tk.Frame(win)
        search_row.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(search_row, text=self.t("history_search_label")).pack(side="left")
        search_var = tk.StringVar()
        tk.Entry(search_row, textvariable=search_var).pack(side="left", fill="x", expand=True, padx=(6, 0))

        text_frame = tk.Frame(win)
        text_frame.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")
        text_widget = tk.Text(text_frame, wrap="word", yscrollcommand=scrollbar.set)
        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=text_widget.yview)

        def redraw(*_args):
            query = search_var.get().strip().lower()
            matched = [e for e in entries if query in e.lower()] if query else entries
            text_widget.config(state="normal")
            text_widget.delete("1.0", "end")
            text_widget.insert("1.0", ("\n\n" + "=" * 60 + "\n\n").join(reversed(matched)))
            text_widget.config(state="disabled")

        search_var.trace_add("write", redraw)
        redraw()

        tk.Button(win, text=self.t("history_close"), command=win.destroy).pack(pady=(0, 10))

    # -- Safe eject (item 5) ---------------------------------------------------

    def _eject_drives(self):
        targets = [p for p in (self.source_path.get().strip(), self.dest_path.get().strip()) if p]
        if not targets:
            return
        if not messagebox.askyesno(self.t("app_title"), self.t("eject_confirm")):
            return

        lines = []
        for path in targets:
            ok = eject_drive(path)
            lines.append(f"{path}\n{self.t('eject_ok') if ok else self.t('eject_fail')}")
            if ok:
                if path == self.source_path.get().strip():
                    self.source_path.set("")
                if path == self.dest_path.get().strip():
                    self.dest_path.set("")

        messagebox.showinfo(self.t("app_title"), "\n\n".join(lines))
        self._refresh_drive_suggestions()

    # -- Update check (item 8) -------------------------------------------------

    def _check_for_updates(self):
        if not UPDATE_REPO:
            messagebox.showinfo(self.t("app_title"), self.t("update_not_configured"))
            return
        self.update_button.config(state="disabled")

        def worker():
            info = check_for_update()
            self.after(0, lambda: self._show_update_result(info))

        threading.Thread(target=worker, daemon=True).start()

    def _show_update_result(self, info):
        self.update_button.config(state="normal")
        if not info:
            messagebox.showinfo(self.t("app_title"), self.t("update_check_failed"))
            return
        if version_tuple(info["version"]) > version_tuple(APP_VERSION):
            if messagebox.askyesno(
                self.t("app_title"),
                self.t("update_available_msg", version=info["version"], current=APP_VERSION),
            ):
                webbrowser.open(info["url"])
        else:
            messagebox.showinfo(self.t("app_title"), self.t("update_none", version=APP_VERSION))


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
