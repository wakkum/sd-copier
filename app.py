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
import logging
import os
import re
import shutil
import ssl
import string
import subprocess
import sys
import threading
import time
import tkinter as tk
import traceback
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import zipfile
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

APP_VERSION = "1.5.4"

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
        "update_install_msg": "A newer version is available: {version} (you have {current}).\n\n"
                              "Download and install it now? The app will close and reopen by "
                              "itself when it's done.",
        "update_downloading": "Downloading update... {pct}%",
        "update_installing": "Installing the update. The app will close and reopen in a moment.",
        "update_install_failed": "The update could not be installed:\n{error}\n\n"
                                 "Nothing has been changed - the app still works as before.",
        "update_busy": "Please wait until the copy has finished before updating.",
        "confirm_missing_both": "You haven't filled in an event name or a description.\n\n"
                                "These are what make this backup easy to find and understand "
                                "later. Copy anyway?",
        "confirm_missing_name": "You haven't filled in an event name.\n\n"
                                "Without one the folder will just be called \"Event\". "
                                "Copy anyway?",
        "confirm_missing_desc": "You haven't written a description.\n\n"
                                "The description is what you'll read later to remember what "
                                "these videos show. Copy anyway?",
        "help_button": "Help / How to use",
        "help_title": "How to use SD Video Backup",
        "help_close": "Close",
        "report_button": "Report a Problem",
        "report_saved": "A report has been saved to your Desktop:\n\n{path}\n\nSend that file to whoever set this app up. It lists what the app did and any errors, so they can see what went wrong. It does not contain your videos.",
        "report_failed": "The report could not be saved: {error}",
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
        "update_install_msg": "Υπάρχει νεότερη έκδοση διαθέσιμη: {version} (έχετε {current}).\n\n"
                              "Να γίνει λήψη και εγκατάσταση τώρα; Η εφαρμογή θα κλείσει και θα "
                              "ανοίξει ξανά μόνη της.",
        "update_downloading": "Λήψη ενημέρωσης... {pct}%",
        "update_installing": "Εγκατάσταση της ενημέρωσης. Η εφαρμογή θα κλείσει και θα ανοίξει "
                             "ξανά σε λίγο.",
        "update_install_failed": "Η ενημέρωση δεν εγκαταστάθηκε:\n{error}\n\n"
                                 "Δεν άλλαξε τίποτα - η εφαρμογή λειτουργεί όπως πριν.",
        "update_busy": "Περιμένετε να ολοκληρωθεί η αντιγραφή πριν την ενημέρωση.",
        "confirm_missing_both": "Δεν έχετε συμπληρώσει ούτε όνομα συμβάντος ούτε περιγραφή.\n\n"
                                "Αυτά είναι που κάνουν αυτό το αντίγραφο ασφαλείας εύκολο να "
                                "το βρείτε και να το καταλάβετε αργότερα. Να γίνει ούτως ή "
                                "άλλως αντιγραφή;",
        "confirm_missing_name": "Δεν έχετε συμπληρώσει όνομα συμβάντος.\n\n"
                                "Χωρίς αυτό ο φάκελος θα ονομαστεί απλώς \"Event\". "
                                "Να γίνει ούτως ή άλλως αντιγραφή;",
        "confirm_missing_desc": "Δεν έχετε γράψει περιγραφή.\n\n"
                                "Η περιγραφή είναι αυτό που θα διαβάσετε αργότερα για να "
                                "θυμηθείτε τι δείχνουν αυτά τα βίντεο. Να γίνει ούτως ή άλλως "
                                "αντιγραφή;",
        "help_button": "Βοήθεια / Οδηγίες χρήσης",
        "help_title": "Οδηγίες χρήσης του SD Video Backup",
        "help_close": "Κλείσιμο",
        "report_button": "Αναφορά Προβλήματος",
        "report_saved": "Μια αναφορά αποθηκεύτηκε στην Επιφάνεια Εργασίας:\n\n{path}\n\nΣτείλτε αυτό το αρχείο σε όποιον έστησε την εφαρμογή. Δείχνει τι έκανε η εφαρμογή και τυχόν σφάλματα, ώστε να δει τι πήγε στραβά. Δεν περιέχει τα βίντεό σας.",
        "report_failed": "Η αναφορά δεν αποθηκεύτηκε: {error}",
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
        "update_install_msg": "Une nouvelle version est disponible : {version} (vous avez "
                              "{current}).\n\nLa télécharger et l'installer maintenant ? "
                              "L'application se fermera et se rouvrira toute seule.",
        "update_downloading": "Téléchargement de la mise à jour... {pct} %",
        "update_installing": "Installation de la mise à jour. L'application va se fermer et se "
                             "rouvrir dans un instant.",
        "update_install_failed": "La mise à jour n'a pas pu être installée :\n{error}\n\n"
                                 "Rien n'a été modifié - l'application fonctionne comme avant.",
        "update_busy": "Veuillez attendre la fin de la copie avant de mettre à jour.",
        "confirm_missing_both": "Vous n'avez saisi ni nom d'événement ni description.\n\n"
                                "Ce sont eux qui rendront cette sauvegarde facile à retrouver "
                                "et à comprendre plus tard. Copier quand même ?",
        "confirm_missing_name": "Vous n'avez pas saisi de nom d'événement.\n\n"
                                "Sans nom, le dossier s'appellera simplement « Event ». "
                                "Copier quand même ?",
        "confirm_missing_desc": "Vous n'avez pas écrit de description.\n\n"
                                "C'est la description que vous relirez plus tard pour vous "
                                "rappeler ce que montrent ces vidéos. Copier quand même ?",
        "help_button": "Aide / Mode d'emploi",
        "help_title": "Mode d'emploi de SD Video Backup",
        "help_close": "Fermer",
        "report_button": "Signaler un Problème",
        "report_saved": "Un rapport a été enregistré sur votre Bureau :\n\n{path}\n\nEnvoyez ce fichier à la personne qui a installé l'application. Il indique ce que l'application a fait et les erreurs éventuelles, pour qu'elle puisse voir ce qui s'est passé. Il ne contient pas vos vidéos.",
        "report_failed": "Le rapport n'a pas pu être enregistré : {error}",
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
        "update_install_msg": "Eine neuere Version ist verfügbar: {version} (Sie haben "
                              "{current}).\n\nJetzt herunterladen und installieren? Die App "
                              "schließt sich und öffnet sich danach von selbst wieder.",
        "update_downloading": "Update wird heruntergeladen... {pct} %",
        "update_installing": "Das Update wird installiert. Die App schließt sich und öffnet sich "
                             "gleich wieder.",
        "update_install_failed": "Das Update konnte nicht installiert werden:\n{error}\n\n"
                                 "Es wurde nichts verändert - die App funktioniert wie zuvor.",
        "update_busy": "Bitte warten Sie, bis das Kopieren abgeschlossen ist, bevor Sie "
                       "aktualisieren.",
        "confirm_missing_both": "Sie haben weder einen Ereignisnamen noch eine Beschreibung "
                                "eingegeben.\n\nGenau die machen diese Sicherung später "
                                "leicht auffindbar und verständlich. Trotzdem kopieren?",
        "confirm_missing_name": "Sie haben keinen Ereignisnamen eingegeben.\n\n"
                                "Ohne Namen heißt der Ordner einfach „Event“. "
                                "Trotzdem kopieren?",
        "confirm_missing_desc": "Sie haben keine Beschreibung eingegeben.\n\n"
                                "Die Beschreibung ist das, was Sie später lesen, um sich zu "
                                "erinnern, was diese Videos zeigen. Trotzdem kopieren?",
        "help_button": "Hilfe / Anleitung",
        "help_title": "Anleitung für SD Video Backup",
        "help_close": "Schließen",
        "report_button": "Problem melden",
        "report_saved": "Ein Bericht wurde auf Ihrem Desktop gespeichert:\n\n{path}\n\nSenden Sie diese Datei an die Person, die die App eingerichtet hat. Sie zeigt, was die App getan hat, und eventuelle Fehler, damit sie sehen kann, was schiefgelaufen ist. Ihre Videos sind nicht enthalten.",
        "report_failed": "Der Bericht konnte nicht gespeichert werden: {error}",
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
        "update_install_msg": "È disponibile una versione più recente: {version} (hai la "
                              "{current}).\n\nScaricarla e installarla adesso? L'app si "
                              "chiuderà e si riaprirà da sola.",
        "update_downloading": "Download dell'aggiornamento... {pct}%",
        "update_installing": "Installazione dell'aggiornamento. L'app si chiuderà e si riaprirà "
                             "tra poco.",
        "update_install_failed": "Non è stato possibile installare l'aggiornamento:\n{error}\n\n"
                                 "Non è stato modificato nulla - l'app funziona come prima.",
        "update_busy": "Attendi il termine della copia prima di aggiornare.",
        "confirm_missing_both": "Non hai inserito né un nome dell'evento né una "
                                "descrizione.\n\nSono questi a rendere il backup facile da "
                                "ritrovare e da capire in futuro. Copiare lo stesso?",
        "confirm_missing_name": "Non hai inserito un nome dell'evento.\n\n"
                                "Senza nome la cartella si chiamerà semplicemente \"Event\". "
                                "Copiare lo stesso?",
        "confirm_missing_desc": "Non hai scritto una descrizione.\n\n"
                                "La descrizione è ciò che leggerai in futuro per ricordare "
                                "cosa mostrano questi video. Copiare lo stesso?",
        "help_button": "Aiuto / Istruzioni",
        "help_title": "Istruzioni per SD Video Backup",
        "help_close": "Chiudi",
        "report_button": "Segnala un Problema",
        "report_saved": "Un rapporto è stato salvato sulla Scrivania:\n\n{path}\n\nInvia questo file a chi ha configurato l'app. Mostra che cosa ha fatto l'app ed eventuali errori, così può capire che cosa è andato storto. Non contiene i tuoi video.",
        "report_failed": "Non è stato possibile salvare il rapporto: {error}",
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
# Logging. When something goes wrong on the user's machine there is otherwise
# nothing to look at: they are not technical, there is no console, and the
# dialog they saw is gone by the time they describe it. Everything lands in
# one file next to the config, which "Report a Problem" then hands over.
# ---------------------------------------------------------------------------

LOG_PATH = Path.home() / ".sd_video_backup.log"
LOG_MAX_BYTES = 512 * 1024

log = logging.getLogger("sd_video_backup")


def setup_logging():
    """Start logging to LOG_PATH, trimming it first if it has grown large.

    Deliberately not a RotatingFileHandler: a single file is easier for the
    user to find and send, and this keeps the recent half rather than
    discarding everything.
    """
    try:
        if LOG_PATH.exists() and LOG_PATH.stat().st_size > LOG_MAX_BYTES:
            tail = LOG_PATH.read_text(encoding="utf-8", errors="replace")[-LOG_MAX_BYTES // 2:]
            LOG_PATH.write_text("(earlier entries trimmed)\n" + tail, encoding="utf-8")
        handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    except OSError:
        # Never let logging itself stop the app from starting.
        handler = logging.NullHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s"))
    log.setLevel(logging.INFO)
    log.handlers = [handler]
    log.propagate = False

    log.info("-" * 60)
    log.info("started  version=%s  platform=%s  frozen=%s  python=%s",
             APP_VERSION, sys.platform, getattr(sys, "frozen", False),
             sys.version.split()[0])


def log_exception(where: str, exc: BaseException):
    log.error("%s: %s: %s", where, type(exc).__name__, exc)
    log.error("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip())


# ---------------------------------------------------------------------------
# In-app help. The printed guide (HOW_TO_USE.pdf) exists only in English and
# Greek, so this is the only help a French, German or Italian user gets. It
# lives in the app so it ships with every build and follows the language
# dropdown. Keep it in step with the UI when behaviour changes.
# ---------------------------------------------------------------------------

HELP_TEXT = {
    "en": """WHAT YOU NEED

  - The SD card from the camera
  - The external hard drive
  - This laptop

OPENING THE APP

On Windows the app lives inside a folder called "SD Video Backup". Open
that folder and double-click "SD Video Backup" inside it. Keep the folder
together exactly as it is: the other files next to the app are part of it,
and moving the app out on its own will stop it opening. If you want it on
the Desktop, ask for a shortcut rather than dragging the app out.

On Mac the app is in the Applications folder.

The first time you open it the computer may warn that it does not
recognise the app. That is expected. On Windows click "More info" and then
"Run anyway"; on Mac right-click the app and choose "Open". Once only.

STEP BY STEP

  1. Plug in both the SD card and the external hard drive. Wait a few
     seconds for them to be recognised.

  2. Choose the SD card in the list under "Detected", or press "Browse..."
     and pick it yourself. Each drive shows its size, which is the quickest
     way to tell them apart: the card is the small one (usually tens of
     GB), the hard drive is much bigger (often 1 TB or more). On Windows
     the drive letter is shown too, for example E: or F:.

  3. Choose the external hard drive the same way, in the section below it.
     It is the larger of the two.

  4. Fill in the details:
       - Date of recording, as YYYY-MM-DD (e.g. 2026-09-14).
       - Camera: "Button" or "Powerbank", whichever recorded the video.
       - Event name: a short name for what happened, e.g. "Birthday
         party". Optional; left blank the folder is called "Event".
       - Description: a short note about what happens in the videos.
       - Tick "Mark this day as VERY IMPORTANT" if it is a special day.

     If you click Copy with the event name or description empty, the app
     asks whether to continue. It is only a reminder and you can say yes,
     but the description is the one thing that cannot be worked out again
     from the videos later, so it is worth writing something.

  5. Click the green "Copy videos now" button at the bottom. If the window
     is too small to show the whole form, the green button stays at the
     bottom and the form scrolls above it.

  6. Wait while the files copy and are checked. Do NOT remove the SD card
     or the hard drive while this is happening.

  7. When it finishes you are told how many files were copied, and the
     folder opens so you can look at it. You can then disconnect both.

ADDING A SECOND CAMERA TO THE SAME EVENT

After a copy, "Add Another Camera to This Event" becomes available. It
keeps the same date, event name and description, switches to the other
camera and clears the card field, so the second camera's footage lands in
the same event folder instead of making a new one.

IF SOMETHING GOES WRONG

Click "Report a Problem". The app saves a file on your Desktop called
SD_Backup_Report_ followed by today's date, and opens the folder so you
can see it. Send that file to whoever set the app up: it records what the
app did and any errors, which is usually enough to work out what
happened. It does not contain your videos.

The version number is shown next to the title at the top of the window.
Worth mentioning whenever you report something.

KEEPING THE APP UP TO DATE

Click "Check for Updates" at the bottom right. On Windows the app can
download and install a newer version itself: it closes and reopens on the
new version, and there is nothing else to do. On Mac it opens the download
page instead. Do not update in the middle of a copy; the app will tell you
to wait. If an update cannot be downloaded, nothing is changed and the
version you have keeps working.

GOOD TO KNOW

  - Every description you write is also collected in one file called
    "All_Descriptions.txt" at the top of the hard drive. "View Backup
    History" shows the same thing inside the app.

  - Never delete anything from the SD card yourself. Copy first, and only
    clear the card once you are sure the backup worked.

  - Nothing is ever overwritten. If a file with the same name is already
    there, the new copy is saved alongside it, not on top of it.

  - Your videos are read from the card, never changed or deleted.

  - If some files report a problem, the SD card is untouched. Just try
    "Copy videos now" again.

  - The app remembers the hard drive you used last time.
""",

    "el": """ΤΙ ΧΡΕΙΑΖΕΣΤΕ

  - Την κάρτα SD από την κάμερα
  - Τον εξωτερικό σκληρό δίσκο
  - Αυτό το laptop

ΑΝΟΙΓΜΑ ΤΗΣ ΕΦΑΡΜΟΓΗΣ

Στα Windows η εφαρμογή βρίσκεται μέσα σε έναν φάκελο με το όνομα "SD Video
Backup". Ανοίξτε τον φάκελο και κάντε διπλό κλικ στο "SD Video Backup" που
είναι μέσα. Κρατήστε τον φάκελο ακριβώς όπως είναι: τα υπόλοιπα αρχεία
δίπλα στην εφαρμογή αποτελούν μέρος της, και αν βγάλετε την εφαρμογή μόνη
της δεν θα ανοίγει. Αν τη θέλετε στην Επιφάνεια Εργασίας, ζητήστε μια
συντόμευση αντί να σύρετε την εφαρμογή έξω.

Σε Mac η εφαρμογή βρίσκεται στον φάκελο Applications.

Την πρώτη φορά ο υπολογιστής μπορεί να προειδοποιήσει ότι δεν αναγνωρίζει
την εφαρμογή. Είναι φυσιολογικό. Στα Windows πατήστε "More info" και μετά
"Run anyway". Σε Mac κάντε δεξί κλικ και επιλέξτε "Open". Μόνο μία φορά.

ΒΗΜΑ-ΒΗΜΑ

  1. Συνδέστε και την κάρτα SD και τον εξωτερικό σκληρό δίσκο. Περιμένετε
     λίγα δευτερόλεπτα μέχρι να αναγνωριστούν.

  2. Επιλέξτε την κάρτα SD στη λίστα κάτω από το "Detected", ή πατήστε
     "Browse..." και επιλέξτε την εσείς. Κάθε δίσκος δείχνει το μέγεθός
     του, που είναι ο πιο γρήγορος τρόπος να τους ξεχωρίσετε: η κάρτα
     είναι η μικρή (συνήθως μερικές δεκάδες GB), ο σκληρός δίσκος πολύ
     μεγαλύτερος (συχνά 1 TB ή περισσότερο). Στα Windows εμφανίζεται και
     το γράμμα του δίσκου, π.χ. E: ή F:.

  3. Επιλέξτε τον εξωτερικό σκληρό δίσκο με τον ίδιο τρόπο, στην ενότητα
     από κάτω. Είναι ο μεγαλύτερος από τους δύο.

  4. Συμπληρώστε τα στοιχεία:
       - Ημερομηνία εγγραφής, στη μορφή ΕΕΕΕ-ΜΜ-ΗΗ (π.χ. 2026-09-14).
       - Κάμερα: "Button" ή "Powerbank", όποια κατέγραψε το βίντεο.
       - Όνομα συμβάντος: ένα σύντομο όνομα για το τι έγινε, π.χ. "Πάρτι
         γενεθλίων". Προαιρετικό. Αν μείνει κενό, ο φάκελος θα ονομαστεί
         "Event".
       - Περιγραφή: λίγα λόγια για το τι δείχνουν τα βίντεο.
       - Επιλέξτε "Mark this day as VERY IMPORTANT" αν είναι ξεχωριστή
         μέρα.

     Αν πατήσετε Αντιγραφή με κενό το όνομα συμβάντος ή την περιγραφή, η
     εφαρμογή θα ρωτήσει αν θέλετε να συνεχίσετε. Είναι απλώς υπενθύμιση
     και μπορείτε να απαντήσετε ναι, όμως η περιγραφή είναι το μόνο που
     δεν μπορεί να βρεθεί ξανά από τα ίδια τα βίντεο, οπότε αξίζει να
     γράψετε κάτι.

  5. Πατήστε το πράσινο κουμπί "Copy videos now" στο κάτω μέρος. Αν το
     παράθυρο είναι μικρό, το πράσινο κουμπί παραμένει κάτω και η φόρμα
     κυλάει από πάνω του.

  6. Περιμένετε όσο αντιγράφονται και ελέγχονται τα αρχεία. ΜΗΝ αφαιρέσετε
     την κάρτα SD ή τον σκληρό δίσκο όσο διαρκεί η διαδικασία.

  7. Όταν ολοκληρωθεί, θα δείτε πόσα αρχεία αντιγράφηκαν και ο φάκελος θα
     ανοίξει για να τον ελέγξετε. Μετά μπορείτε να τα αποσυνδέσετε.

ΠΡΟΣΘΗΚΗ ΔΕΥΤΕΡΗΣ ΚΑΜΕΡΑΣ ΣΤΟ ΙΔΙΟ ΣΥΜΒΑΝ

Μετά από μια αντιγραφή ενεργοποιείται το "Add Another Camera to This
Event". Κρατά την ίδια ημερομηνία, όνομα και περιγραφή, αλλάζει στην άλλη
κάμερα και καθαρίζει το πεδίο της κάρτας, ώστε το υλικό της δεύτερης
κάμερας να μπει στον ίδιο φάκελο συμβάντος αντί να δημιουργηθεί νέος.

ΑΝ ΚΑΤΙ ΠΑΕΙ ΣΤΡΑΒΑ

Πατήστε "Report a Problem". Η εφαρμογή αποθηκεύει στην Επιφάνεια Εργασίας
ένα αρχείο με όνομα SD_Backup_Report_ και τη σημερινή ημερομηνία, και
ανοίγει τον φάκελο για να το δείτε. Στείλτε αυτό το αρχείο σε όποιον
έστησε την εφαρμογή: καταγράφει τι έκανε η εφαρμογή και τυχόν σφάλματα,
που συνήθως αρκούν για να βρεθεί τι συνέβη. Δεν περιέχει τα βίντεό σας.

Ο αριθμός έκδοσης εμφανίζεται δίπλα στον τίτλο, στο πάνω μέρος του
παραθύρου. Αξίζει να τον αναφέρετε όποτε δηλώνετε κάτι.

ΔΙΑΤΗΡΩΝΤΑΣ ΤΗΝ ΕΦΑΡΜΟΓΗ ΕΝΗΜΕΡΩΜΕΝΗ

Πατήστε "Check for Updates" κάτω δεξιά. Στα Windows η εφαρμογή μπορεί να
κατεβάσει και να εγκαταστήσει μόνη της τη νεότερη έκδοση: κλείνει και
ανοίγει ξανά με τη νέα έκδοση, χωρίς να χρειάζεται να κάνετε τίποτα. Σε
Mac ανοίγει τη σελίδα λήψης. Μην κάνετε ενημέρωση στη μέση μιας
αντιγραφής. Αν η ενημέρωση δεν κατέβει, δεν αλλάζει τίποτα και η έκδοση
που έχετε συνεχίζει να λειτουργεί.

ΚΑΛΟ ΕΙΝΑΙ ΝΑ ΞΕΡΕΤΕ

  - Κάθε περιγραφή που γράφετε συγκεντρώνεται και σε ένα αρχείο με το
    όνομα "All_Descriptions.txt" στην κορυφή του σκληρού δίσκου. Το "View
    Backup History" δείχνει το ίδιο μέσα από την εφαρμογή.

  - Μην διαγράφετε ποτέ τίποτα από την κάρτα SD μόνοι σας. Αντιγράψτε
    πρώτα, και αδειάστε την κάρτα μόνο αφού βεβαιωθείτε ότι πέτυχε.

  - Τίποτα δεν αντικαθίσταται ποτέ. Αν υπάρχει ήδη αρχείο με το ίδιο
    όνομα, το νέο αποθηκεύεται δίπλα του, όχι πάνω του.

  - Τα βίντεό σας διαβάζονται από την κάρτα, δεν αλλάζουν και δεν
    διαγράφονται ποτέ.

  - Αν κάποια αρχεία εμφανίσουν πρόβλημα, η κάρτα SD παραμένει ανέπαφη.
    Απλώς δοκιμάστε ξανά το "Copy videos now".

  - Η εφαρμογή θυμάται τον σκληρό δίσκο που χρησιμοποιήσατε την
    τελευταία φορά.
""",

    "fr": """CE QU'IL VOUS FAUT

  - La carte SD de la caméra
  - Le disque dur externe
  - Cet ordinateur portable

OUVRIR L'APPLICATION

Sous Windows, l'application se trouve dans un dossier nommé "SD Video
Backup". Ouvrez ce dossier et double-cliquez sur "SD Video Backup" à
l'intérieur. Gardez le dossier tel quel : les autres fichiers à côté de
l'application en font partie, et si l'application en est sortie seule elle
ne s'ouvrira plus. Si vous la voulez sur le Bureau, demandez un raccourci
plutôt que de la faire glisser hors du dossier.

Sur Mac, l'application se trouve dans le dossier Applications.

La première fois, l'ordinateur peut avertir qu'il ne reconnaît pas
l'application. C'est normal. Sous Windows, cliquez sur « Informations
complémentaires » puis « Exécuter quand même » ; sur Mac, faites un clic
droit sur l'application et choisissez « Ouvrir ». Une seule fois.

ÉTAPE PAR ÉTAPE

  1. Branchez la carte SD et le disque dur externe. Patientez quelques
     secondes le temps qu'ils soient reconnus.

  2. Choisissez la carte SD dans la liste sous « Detected », ou appuyez
     sur « Browse... » pour la sélectionner vous-même. Chaque disque
     affiche sa taille, le moyen le plus rapide de les distinguer : la
     carte est la petite (quelques dizaines de Go en général), le disque
     dur est bien plus grand (souvent 1 To ou plus). Sous Windows, la
     lettre du lecteur est également affichée, par exemple E: ou F:.

  3. Choisissez le disque dur externe de la même façon, dans la section
     en dessous. C'est le plus grand des deux.

  4. Remplissez les informations :
       - Date de l'enregistrement, au format AAAA-MM-JJ (ex. 2026-09-14).
       - Caméra : « Button » ou « Powerbank », celle qui a filmé.
       - Nom de l'événement : un nom court de ce qui s'est passé, par
         exemple « Anniversaire ». Facultatif ; laissé vide, le dossier
         s'appellera « Event ».
       - Description : quelques mots sur ce que montrent les vidéos.
       - Cochez « Mark this day as VERY IMPORTANT » si la journée est
         particulière.

     Si vous cliquez sur Copier en laissant le nom de l'événement ou la
     description vide, l'application demande si vous voulez continuer.
     Ce n'est qu'un rappel et vous pouvez répondre oui, mais la
     description est la seule chose qui ne pourra pas être retrouvée plus
     tard à partir des vidéos : cela vaut la peine d'écrire quelque chose.

  5. Cliquez sur le bouton vert « Copy videos now » en bas. Si la fenêtre
     est trop petite pour afficher tout le formulaire, le bouton vert
     reste en bas et le formulaire défile au-dessus.

  6. Patientez pendant la copie et la vérification des fichiers. NE
     RETIREZ PAS la carte SD ni le disque dur pendant ce temps.

  7. À la fin, le nombre de fichiers copiés s'affiche et le dossier
     s'ouvre pour que vous puissiez le voir. Vous pouvez alors tout
     débrancher.

AJOUTER UNE DEUXIÈME CAMÉRA AU MÊME ÉVÉNEMENT

Après une copie, « Add Another Camera to This Event » devient disponible.
La date, le nom de l'événement et la description sont conservés,
l'application passe à l'autre caméra et vide le champ de la carte, afin
que les images de la deuxième caméra arrivent dans le même dossier
d'événement au lieu d'en créer un nouveau.

EN CAS DE PROBLÈME

Cliquez sur « Report a Problem ». L'application enregistre sur votre
Bureau un fichier nommé SD_Backup_Report_ suivi de la date du jour, et
ouvre le dossier pour que vous le voyiez. Envoyez ce fichier à la
personne qui a installé l'application : il indique ce que l'application a
fait et les erreurs éventuelles, ce qui suffit en général à comprendre ce
qui s'est passé. Il ne contient pas vos vidéos.

Le numéro de version est affiché à côté du titre, en haut de la fenêtre.
Il est utile de le mentionner quand vous signalez quelque chose.

GARDER L'APPLICATION À JOUR

Cliquez sur « Check for Updates » en bas à droite. Sous Windows,
l'application peut télécharger et installer elle-même une version plus
récente : elle se ferme et se rouvre sur la nouvelle version, sans rien
d'autre à faire. Sur Mac, elle ouvre la page de téléchargement. Ne faites
pas de mise à jour au milieu d'une copie ; l'application vous demandera
d'attendre. Si une mise à jour ne peut pas être téléchargée, rien n'est
modifié et la version que vous avez continue de fonctionner.

BON À SAVOIR

  - Chaque description que vous écrivez est aussi rassemblée dans un
    fichier « All_Descriptions.txt » à la racine du disque dur. « View
    Backup History » montre la même chose depuis l'application.

  - Ne supprimez jamais rien de la carte SD vous-même. Copiez d'abord, et
    ne videz la carte qu'une fois certain que la sauvegarde a réussi.

  - Rien n'est jamais écrasé. Si un fichier du même nom existe déjà, la
    nouvelle copie est enregistrée à côté, pas par-dessus.

  - Vos vidéos sont lues depuis la carte, jamais modifiées ni supprimées.

  - Si des fichiers signalent un problème, la carte SD reste intacte.
    Réessayez simplement « Copy videos now ».

  - L'application se souvient du disque dur utilisé la dernière fois.
""",

    "de": """WAS SIE BRAUCHEN

  - Die SD-Karte aus der Kamera
  - Die externe Festplatte
  - Diesen Laptop

DIE APP ÖFFNEN

Unter Windows liegt die App in einem Ordner namens "SD Video Backup".
Öffnen Sie diesen Ordner und doppelklicken Sie auf "SD Video Backup"
darin. Lassen Sie den Ordner genau so, wie er ist: die übrigen Dateien
neben der App gehören dazu, und wenn die App allein herausgenommen wird,
lässt sie sich nicht mehr öffnen. Wenn Sie sie auf dem Desktop haben
möchten, lassen Sie eine Verknüpfung anlegen, statt die App aus dem Ordner
zu ziehen.

Auf dem Mac liegt die App im Ordner "Programme".

Beim ersten Öffnen warnt der Computer möglicherweise, dass er die App
nicht kennt. Das ist normal. Unter Windows klicken Sie auf „Weitere
Informationen“ und dann „Trotzdem ausführen“; auf dem Mac klicken Sie mit
der rechten Maustaste auf die App und wählen „Öffnen“. Nur einmal nötig.

SCHRITT FÜR SCHRITT

  1. Schließen Sie die SD-Karte und die externe Festplatte an. Warten Sie
     ein paar Sekunden, bis beide erkannt werden.

  2. Wählen Sie die SD-Karte in der Liste unter „Detected“, oder klicken
     Sie auf „Browse...“ und wählen Sie sie selbst aus. Zu jedem Laufwerk
     wird die Größe angezeigt, das ist der schnellste Weg, sie zu
     unterscheiden: die Karte ist die kleine (meist einige zehn GB), die
     Festplatte ist deutlich größer (oft 1 TB oder mehr). Unter Windows
     wird außerdem der Laufwerksbuchstabe angezeigt, etwa E: oder F:.

  3. Wählen Sie die externe Festplatte auf dieselbe Weise im Abschnitt
     darunter. Sie ist die größere der beiden.

  4. Füllen Sie die Angaben aus:
       - Aufnahmedatum im Format JJJJ-MM-TT (z. B. 2026-09-14).
       - Kamera: „Button“ oder „Powerbank“, je nachdem, welche gefilmt
         hat.
       - Ereignisname: ein kurzer Name für das Geschehen, z. B.
         „Geburtstag“. Optional; bleibt er leer, heißt der Ordner
         „Event“.
       - Beschreibung: ein paar Worte dazu, was die Videos zeigen.
       - Haken Sie „Mark this day as VERY IMPORTANT“ an, wenn es ein
         besonderer Tag ist.

     Wenn Sie auf Kopieren klicken und Ereignisname oder Beschreibung leer
     sind, fragt die App, ob Sie wirklich fortfahren möchten. Das ist nur
     eine Erinnerung und Sie können mit Ja antworten, aber die
     Beschreibung ist das Einzige, was sich später nicht aus den Videos
     selbst wiederherstellen lässt. Es lohnt sich, etwas zu schreiben.

  5. Klicken Sie unten auf die grüne Schaltfläche „Copy videos now“. Ist
     das Fenster zu klein für das ganze Formular, bleibt die grüne
     Schaltfläche unten und das Formular scrollt darüber.

  6. Warten Sie, während die Dateien kopiert und geprüft werden. Entfernen
     Sie in dieser Zeit WEDER die SD-Karte NOCH die Festplatte.

  7. Am Ende wird angezeigt, wie viele Dateien kopiert wurden, und der
     Ordner öffnet sich zur Kontrolle. Danach können Sie beide Geräte
     abziehen.

EINE ZWEITE KAMERA ZUM SELBEN EREIGNIS HINZUFÜGEN

Nach einem Kopiervorgang wird „Add Another Camera to This Event“
verfügbar. Datum, Ereignisname und Beschreibung bleiben erhalten, die App
wechselt zur anderen Kamera und leert das Feld für die Karte, damit das
Material der zweiten Kamera im selben Ereignisordner landet, statt einen
neuen anzulegen.

WENN ETWAS SCHIEFGEHT

Klicken Sie auf „Report a Problem“. Die App speichert auf Ihrem Desktop
eine Datei namens SD_Backup_Report_ mit dem heutigen Datum und öffnet den
Ordner, damit Sie sie sehen. Senden Sie diese Datei an die Person, die
die App eingerichtet hat: sie hält fest, was die App getan hat, und
eventuelle Fehler, was meist genügt, um herauszufinden, was passiert ist.
Ihre Videos sind nicht enthalten.

Die Versionsnummer steht oben im Fenster neben dem Titel. Es lohnt sich,
sie bei jeder Meldung anzugeben.

DIE APP AKTUELL HALTEN

Klicken Sie unten rechts auf „Check for Updates“. Unter Windows kann die
App eine neuere Version selbst herunterladen und installieren: sie
schließt sich und öffnet sich mit der neuen Version wieder, mehr ist nicht
zu tun. Auf dem Mac wird stattdessen die Download-Seite geöffnet.
Aktualisieren Sie nicht mitten in einem Kopiervorgang; die App bittet Sie
dann zu warten. Lässt sich ein Update nicht laden, wird nichts verändert
und Ihre bisherige Version funktioniert weiter.

GUT ZU WISSEN

  - Jede Beschreibung, die Sie schreiben, wird zusätzlich in einer Datei
    namens „All_Descriptions.txt“ oben auf der Festplatte gesammelt. „View
    Backup History“ zeigt dasselbe innerhalb der App.

  - Löschen Sie nie selbst etwas von der SD-Karte. Kopieren Sie zuerst,
    und leeren Sie die Karte erst, wenn die Sicherung sicher geklappt hat.

  - Es wird nie etwas überschrieben. Gibt es bereits eine Datei mit
    demselben Namen, wird die neue Kopie daneben gespeichert, nicht
    darüber.

  - Ihre Videos werden von der Karte gelesen, nie verändert oder
    gelöscht.

  - Melden einzelne Dateien ein Problem, bleibt die SD-Karte unberührt.
    Versuchen Sie einfach erneut „Copy videos now“.

  - Die App merkt sich die zuletzt verwendete Festplatte.
""",

    "it": """CHE COSA SERVE

  - La scheda SD della videocamera
  - Il disco rigido esterno
  - Questo portatile

APRIRE L'APP

Su Windows l'app si trova dentro una cartella chiamata "SD Video Backup".
Apri quella cartella e fai doppio clic su "SD Video Backup" al suo
interno. Tieni la cartella esattamente com'è: gli altri file accanto
all'app ne fanno parte, e se l'app viene spostata da sola non si aprirà
più. Se la vuoi sul Desktop, fai creare un collegamento invece di
trascinare l'app fuori dalla cartella.

Su Mac l'app si trova nella cartella Applicazioni.

La prima volta il computer potrebbe avvisare che non riconosce l'app. È
normale. Su Windows fai clic su "Maggiori informazioni" e poi "Esegui
comunque"; su Mac fai clic destro sull'app e scegli "Apri". Solo una
volta.

PASSO DOPO PASSO

  1. Collega sia la scheda SD sia il disco rigido esterno. Aspetta qualche
     secondo che vengano riconosciuti.

  2. Scegli la scheda SD nell'elenco sotto "Detected", oppure premi
     "Browse..." e selezionala tu. Ogni unità mostra la propria
     dimensione, il modo più rapido per distinguerle: la scheda è quella
     piccola (di solito qualche decina di GB), il disco rigido è molto più
     grande (spesso 1 TB o più). Su Windows viene mostrata anche la
     lettera dell'unità, per esempio E: o F:.

  3. Scegli il disco rigido esterno allo stesso modo, nella sezione
     sottostante. È il più grande dei due.

  4. Compila i dati:
       - Data della ripresa, nel formato AAAA-MM-GG (es. 2026-09-14).
       - Videocamera: "Button" o "Powerbank", quella che ha ripreso.
       - Nome dell'evento: un nome breve di quello che è successo, per
         esempio "Festa di compleanno". Facoltativo; se lo lasci vuoto la
         cartella si chiamerà "Event".
       - Descrizione: due righe su cosa mostrano i video.
       - Spunta "Mark this day as VERY IMPORTANT" se è un giorno
         speciale.

     Se premi Copia lasciando vuoto il nome dell'evento o la descrizione,
     l'app chiede se vuoi continuare. È solo un promemoria e puoi
     rispondere di sì, ma la descrizione è l'unica cosa che non si potrà
     più ricavare dai video in futuro: vale la pena scrivere qualcosa.

  5. Premi il pulsante verde "Copy videos now" in basso. Se la finestra è
     troppo piccola per mostrare tutto il modulo, il pulsante verde resta
     in basso e il modulo scorre sopra di esso.

  6. Aspetta mentre i file vengono copiati e verificati. NON rimuovere la
     scheda SD né il disco rigido durante questa fase.

  7. Al termine vedrai quanti file sono stati copiati e la cartella si
     aprirà per un controllo. Dopo puoi scollegare entrambi.

AGGIUNGERE UNA SECONDA VIDEOCAMERA ALLO STESSO EVENTO

Dopo una copia diventa disponibile "Add Another Camera to This Event".
Mantiene la stessa data, lo stesso nome evento e la stessa descrizione,
passa all'altra videocamera e svuota il campo della scheda, così le
riprese della seconda videocamera finiscono nella stessa cartella
dell'evento invece di crearne una nuova.

SE QUALCOSA VA STORTO

Premi "Report a Problem". L'app salva sulla Scrivania un file chiamato
SD_Backup_Report_ seguito dalla data di oggi e apre la cartella perché tu
lo veda. Invia quel file a chi ha configurato l'app: registra che cosa ha
fatto l'app ed eventuali errori, di solito abbastanza per capire che cosa
è successo. Non contiene i tuoi video.

Il numero di versione è mostrato accanto al titolo, in alto nella
finestra. Vale la pena indicarlo ogni volta che segnali qualcosa.

TENERE L'APP AGGIORNATA

Premi "Check for Updates" in basso a destra. Su Windows l'app può
scaricare e installare da sola una versione più recente: si chiude e si
riapre sulla nuova versione, senza che tu debba fare altro. Su Mac apre
invece la pagina di download. Non aggiornare nel mezzo di una copia; l'app
ti dirà di aspettare. Se un aggiornamento non può essere scaricato non
viene modificato nulla e la versione che hai continua a funzionare.

BUONO A SAPERSI

  - Ogni descrizione che scrivi viene raccolta anche in un unico file
    chiamato "All_Descriptions.txt" sulla radice del disco rigido. "View
    Backup History" mostra la stessa cosa dentro l'app.

  - Non cancellare mai nulla dalla scheda SD da solo. Copia prima, e
    svuota la scheda solo quando sei sicuro che il backup è riuscito.

  - Niente viene mai sovrascritto. Se esiste già un file con lo stesso
    nome, la nuova copia viene salvata accanto, non sopra.

  - I tuoi video vengono letti dalla scheda, mai modificati né
    cancellati.

  - Se alcuni file segnalano un problema, la scheda SD resta intatta.
    Riprova semplicemente con "Copy videos now".

  - L'app ricorda il disco rigido usato l'ultima volta.
""",

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


def windows_volume_name(root: str) -> str:
    """The user-visible label of a Windows volume, e.g. "SDCARD" for E:\\.

    Empty string when the drive has no label or the call fails - callers fall
    back to showing just the letter.
    """
    import ctypes

    name = ctypes.create_unicode_buffer(261)
    fs = ctypes.create_unicode_buffer(261)
    try:
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(root), name, 261, None, None, None, fs, 261
        )
    except Exception:
        return ""
    return name.value.strip() if ok else ""


def drive_label(path: str) -> str:
    """Button text for a detected drive.

    A bare "E:\\" tells the user nothing about which stick it is, so the
    label carries the volume name and the total capacity too: the SD card and
    the backup drive are usually an order of magnitude apart in size, which
    makes the size the quickest way to tell them apart.
    """
    if sys.platform.startswith("win"):
        letter = path[:2] if len(path) >= 2 and path[1] == ":" else path
        volume = windows_volume_name(path)
        base = f"{letter}  {volume}" if volume else letter
    else:
        base = Path(path).name or path

    try:
        total = shutil.disk_usage(path).total
    except OSError:
        return base
    return f"{base}  ({format_bytes(total)})"


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

def ssl_context() -> ssl.SSLContext:
    """Build an SSL context with a CA bundle we can count on.

    A PyInstaller-frozen app carries its own OpenSSL, which has no trust
    store of its own: ssl.get_default_verify_paths().cafile is None inside
    the bundle, so every HTTPS request fails verification and the update
    check silently reports "couldn't check". certifi ships the CA bundle
    that fixes this and is pulled in at build time. Falling back to the
    stock context keeps app.py runnable as a plain script on a machine
    where certifi isn't installed.
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


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
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None
    tag = str(data.get("tag_name", "")).strip()
    html_url = data.get("html_url", "")
    if not tag or not html_url:
        return None

    # The Windows build can install itself, so pick out that asset. Matching
    # on the platform word rather than a fixed filename keeps this working if
    # the release naming ever changes.
    asset_url, asset_size, asset_name = "", 0, ""
    want = "windows" if sys.platform.startswith("win") else "mac"
    for asset in data.get("assets", []):
        name = str(asset.get("name", ""))
        if name.lower().endswith(".zip") and want in name.lower():
            asset_url = asset.get("browser_download_url", "")
            asset_size = int(asset.get("size", 0) or 0)
            asset_name = name
            break

    return {"version": tag.lstrip("v"), "url": html_url,
            "asset_url": asset_url, "asset_size": asset_size, "asset_name": asset_name}



# ---------------------------------------------------------------------------
# Self-update (Windows only)
#
# A running .exe cannot overwrite itself, but the app is a onedir build - a
# folder - so the new version can be unpacked beside it and a small detached
# script can swap the two once this process has exited. Everything lives
# under the user's own profile, so no admin rights are involved, and the old
# folder is kept until the swap succeeds so a failure can roll back.
# ---------------------------------------------------------------------------

# A release asset URL comes from GitHub's API over a verified connection, but
# the host is still checked before anything is downloaded and run.
ALLOWED_DOWNLOAD_HOSTS = ("github.com", "www.github.com")


def is_allowed_download_url(url: str) -> bool:
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and (
        host in ALLOWED_DOWNLOAD_HOSTS or host.endswith(".githubusercontent.com")
    )


def update_work_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("TEMP") or str(Path.home())
    return Path(base) / "SDVideoBackup" / "update"


def download_update(url: str, dest: Path, expected_size: int = 0,
                    progress_cb=None, timeout: float = 30.0) -> Path:
    """Stream a release asset to dest, reporting progress as a 0-100 int."""
    if not is_allowed_download_url(url):
        raise ValueError(f"refusing to download from an unexpected host: {url}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "sd-video-backup"})
    with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as resp:
        total = int(resp.headers.get("Content-Length") or expected_size or 0)
        done = 0
        with dest.open("wb") as f:
            while True:
                chunk = resp.read(COPY_CHUNK_SIZE)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress_cb and total:
                    progress_cb(min(100, int(done * 100 / total)))

    if expected_size and dest.stat().st_size != expected_size:
        dest.unlink(missing_ok=True)
        raise ValueError("the downloaded file was incomplete")
    return dest


def extract_update(zip_path: Path, staging: Path, exe_name: str) -> Path:
    """Unpack the archive and return the folder holding the new app."""
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            # A zip can name entries outside the destination; refuse those
            # rather than letting an archive write anywhere on disk.
            if name.startswith("/") or ".." in name.split("/"):
                raise ValueError(f"unsafe path in update archive: {info.filename}")
        zf.extractall(staging)

    if (staging / exe_name).exists():
        root = staging
    else:
        subdirs = [p for p in staging.iterdir() if p.is_dir()]
        root = subdirs[0] if len(subdirs) == 1 else staging
    if not (root / exe_name).exists():
        raise ValueError("the update does not contain the application")
    return root


SWAP_SCRIPT = """@echo off
setlocal enabledelayedexpansion
set "APP={app}"
set "NEW={new}"
set "OLD={old}"
set "EXE={exe}"

rem Wait for the app to close before touching its folder. ping is used to
rem pause because timeout needs a console and this runs without one.
set /a tries=0
:wait
tasklist /FI "PID eq {pid}" /NH 2>nul | find /i "{exe}" >nul
if errorlevel 1 goto ready
set /a tries+=1
if !tries! GEQ 60 goto ready
ping -n 2 127.0.0.1 >nul
goto wait

:ready
if exist "%OLD%" rmdir /s /q "%OLD%"
move "%APP%" "%OLD%" >nul 2>&1
if errorlevel 1 goto restart_only
move "%NEW%" "%APP%" >nul 2>&1
if errorlevel 1 goto rollback
rmdir /s /q "%OLD%" >nul 2>&1
start "" "%APP%\\%EXE%"
goto done

:rollback
if exist "%APP%" rmdir /s /q "%APP%"
move "%OLD%" "%APP%" >nul 2>&1
start "" "%APP%\\%EXE%"
goto done

:restart_only
start "" "%APP%\\%EXE%"

:done
(goto) 2>nul & del "%~f0"
"""


def launch_swap_script(app_dir: Path, new_root: Path, exe_name: str) -> Path:
    """Write the swap script and start it detached, so it outlives this app."""
    work = update_work_dir()
    work.mkdir(parents=True, exist_ok=True)
    script = work / "apply_update.bat"
    script.write_text(
        SWAP_SCRIPT.format(app=app_dir, new=new_root, old=str(app_dir) + ".old",
                           exe=exe_name, pid=os.getpid()),
        encoding="utf-8",
    )

    CREATE_NO_WINDOW = 0x08000000
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    subprocess.Popen(
        ["cmd", "/c", str(script)],
        cwd=str(work),  # never inside the folder about to be renamed
        creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )
    return script


def can_self_update() -> bool:
    """Only a frozen Windows build can replace itself this way."""
    return sys.platform.startswith("win") and getattr(sys, "frozen", False)


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.geometry("640x760")
        # Deliberately short: the form scrolls, so a small laptop screen is
        # allowed to shrink the window rather than clip the Copy button.
        self.minsize(560, 480)

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

        # Tk prints callback errors to a console nobody has and carries on,
        # so route them into the log as well.
        self.report_callback_exception = self._log_tk_exception

        self._build_ui()
        self._apply_language()
        self._refresh_drive_suggestions()
        self._size_to_content()

    @staticmethod
    def _log_tk_exception(exc_type, exc_value, exc_tb):
        log_exception("unhandled error in the interface", exc_value)

    # -- Translation helper ---------------------------------------------------

    def t(self, key: str, **kwargs) -> str:
        text = STRINGS[self.lang][key]
        return text.format(**kwargs) if kwargs else text

    # -- UI construction ---------------------------------------------------

    def _build_ui(self):
        pad = {"padx": 12, "pady": 6}

        top_row = tk.Frame(self)
        top_row.pack(side="top", fill="x", **pad)
        self.header = tk.Label(top_row, font=("Helvetica", 16, "bold"))
        self.header.pack(side="left")
        self.version_label = tk.Label(top_row, font=("Helvetica", 10), fg="gray")
        self.version_label.pack(side="left", padx=(8, 0), pady=(6, 0))

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

        # Packed before the form and anchored to the bottom edge, so it claims
        # its space first. Windows draws the system font larger than macOS
        # does, which pushed the form past the bottom of the window - and pack
        # simply drops whatever no longer fits, so the green Copy button was
        # silently not rendered at all.
        self._build_action_area(pad)

        # The form itself scrolls, so a window shorter than the form stays
        # usable instead of hiding the widgets that did not fit.
        form = self._build_scrollable_form()

        # Source
        self.src_frame = tk.LabelFrame(form)
        self.src_frame.pack(fill="x", **pad)
        self.source_browse_btn = self._build_path_row(self.src_frame, self.source_path, self._browse_source)
        self.source_suggestions = tk.Frame(self.src_frame)
        self.source_suggestions.pack(fill="x", padx=8, pady=(0, 8))

        # Destination
        self.dst_frame = tk.LabelFrame(form)
        self.dst_frame.pack(fill="x", **pad)
        self.dest_browse_btn = self._build_path_row(self.dst_frame, self.dest_path, self._browse_dest)
        self.dest_suggestions = tk.Frame(self.dst_frame)
        self.dest_suggestions.pack(fill="x", padx=8, pady=(0, 8))

        utility_row = tk.Frame(form)
        utility_row.pack(fill="x", padx=12)
        self.refresh_btn = tk.Button(utility_row, command=self._refresh_drive_suggestions)
        self.refresh_btn.pack(side="left")
        self.history_button = tk.Button(utility_row, command=self._open_history)
        self.history_button.pack(side="left", padx=(8, 0))
        # Deliberately in the scrolling form rather than the pinned strip at
        # the bottom, which is kept as short as it can be.
        self.help_button = tk.Button(utility_row, command=self._open_help)
        self.help_button.pack(side="left", padx=(8, 0))
        self.report_button = tk.Button(utility_row, command=self._save_report)
        self.report_button.pack(side="left", padx=(8, 0))

        # Details
        self.details_frame = tk.LabelFrame(form)
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

    def _build_action_area(self, pad):
        """The controls pinned to the bottom of the window.

        Packed bottom-up, so the visual order top to bottom ends up:
        same-event button, Copy, progress bar, status line, eject/update row.
        """
        bottom_row = tk.Frame(self)
        bottom_row.pack(side="bottom", fill="x", padx=12, pady=(0, 10))
        self.eject_button = tk.Button(bottom_row, command=self._eject_drives)
        self.eject_button.pack(side="left")
        self.update_button = tk.Button(bottom_row, command=self._check_for_updates)
        self.update_button.pack(side="right")

        self.status_label = tk.Label(self, text="", anchor="w", justify="left", wraplength=600)
        self.status_label.pack(side="bottom", fill="x", padx=12, pady=8)

        self.progress = ttk.Progressbar(self, mode="determinate")
        self.progress.pack(side="bottom", fill="x", padx=12, pady=(4, 0))

        action_frame = tk.Frame(self)
        action_frame.pack(side="bottom", fill="x", **pad)
        self.copy_button = tk.Button(
            action_frame, font=("Helvetica", 12, "bold"),
            bg="#2e7d32", fg="white",
            activebackground="#1b5e20", activeforeground="white",
            command=self._start_copy,
        )
        self.copy_button.pack(fill="x", ipady=8)

        self.same_event_frame = same_event_frame = tk.Frame(self)
        same_event_frame.pack(side="bottom", fill="x", padx=12, pady=(0, 4))
        self.same_event_button = tk.Button(
            same_event_frame, state="disabled", command=self._use_same_event,
        )
        self.same_event_button.pack(fill="x", ipady=4)
        self.same_event_hint_label = tk.Label(
            same_event_frame, fg="gray", anchor="w", justify="left", wraplength=600,
        )
        self.same_event_hint_label.pack(fill="x", pady=(2, 0))

        self.action_frame = action_frame
        # The pinned strip costs the form its height, and on a small screen
        # that was swallowing close to half the window. Nothing here is
        # usable before the first copy, so none of it is shown until it is:
        # the same-event button does nothing until an event exists, and an
        # empty progress bar and status line say nothing at all.
        self.same_event_frame.pack_forget()
        self._hide_progress_area()

    def _show_progress_area(self):
        """Reveal the progress bar and status line, in their original order.

        `before` is what keeps them in place: re-packing a bottom-side widget
        without it would drop the row at the top of the pinned stack instead
        of back where it belongs.
        """
        if not self.progress.winfo_manager():
            self.progress.pack(side="bottom", fill="x", padx=12, pady=(4, 0),
                               before=self.action_frame)
        if not self.status_label.winfo_manager():
            self.status_label.pack(side="bottom", fill="x", padx=12, pady=8,
                                   before=self.progress)

    def _hide_progress_area(self):
        self.progress.pack_forget()
        self.status_label.pack_forget()

    def _show_same_event(self):
        """Show the same-event row once there is an event to add a camera to."""
        if not self.same_event_frame.winfo_manager():
            # Must land before the form container in the pack order, or it
            # takes its slab from above the form instead of just above Copy.
            self.same_event_frame.pack(side="bottom", fill="x", padx=12, pady=(0, 4),
                                       before=self._form_container)

    def _build_scrollable_form(self):
        """Create the scrolling container and return the frame to build into."""
        self._form_container = container = tk.Frame(self)
        container.pack(side="top", fill="both", expand=True)

        canvas = tk.Canvas(container, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        inner = tk.Frame(canvas)
        window = canvas.create_window((0, 0), window=inner, anchor="nw")

        def on_inner_configure(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_configure(event):
            # Keep the form as wide as the canvas, otherwise it sits in a
            # narrow column when the window is widened.
            canvas.itemconfigure(window, width=event.width)

        inner.bind("<Configure>", on_inner_configure)
        canvas.bind("<Configure>", on_canvas_configure)

        def on_mousewheel(event):
            # Let the description box keep its own scrolling.
            under_pointer = self.winfo_containing(event.x_root, event.y_root)
            if isinstance(under_pointer, tk.Text):
                return
            if event.num == 5 or getattr(event, "delta", 0) < 0:
                canvas.yview_scroll(1, "units")
            elif event.num == 4 or getattr(event, "delta", 0) > 0:
                canvas.yview_scroll(-1, "units")

        # Windows and macOS send <MouseWheel>; X11 sends Button-4/Button-5.
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            canvas.bind_all(sequence, on_mousewheel)

        self._form_canvas = canvas
        self._form_inner = inner
        return inner

    def _size_to_content(self):
        """Open large enough for the whole form, but never taller than the screen.

        The canvas has no natural height of its own, so it is told the form's
        required height before measuring the window. Whatever is left over on
        a short screen becomes scrollable rather than clipped.
        """
        self.update_idletasks()
        self._form_canvas.configure(height=self._form_inner.winfo_reqheight())
        self.update_idletasks()
        width = max(640, self.winfo_reqwidth())
        height = min(self.winfo_reqheight(), self.winfo_screenheight() - 120)
        self.geometry(f"{width}x{height}")

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
        # The version goes in the title bar and beside the heading: without
        # it the only way to find out which version is running is to click
        # "Check for Updates", which is no use when asking someone remotely
        # what they have, or when confirming an update actually took.
        self.title(f"{self.t('app_title')}  -  {APP_VERSION}")
        self.header.config(text=self.t("app_title"))
        self.version_label.config(text=f"v{APP_VERSION}")
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
        self.help_button.config(text=self.t("help_button"))
        self.report_button.config(text=self.t("report_button"))
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

        # One full-width button per drive rather than a row of small ones:
        # the labels now carry a volume name and a size, which overflowed the
        # window when packed side by side.
        labels = [(d, drive_label(d)) for d in drives]

        for frame, var in ((self.source_suggestions, self.source_path),
                           (self.dest_suggestions, self.dest_path)):
            tk.Label(frame, text=self.t("detected_label"), fg="gray").pack(anchor="w")
            for d, label in labels:
                tk.Button(frame, text=label, anchor="w",
                          command=lambda d=d, v=var: v.set(d)).pack(fill="x", pady=1)

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

        # Catch the common slip of hitting Copy before filling in what the
        # footage actually is. Both fields are optional as far as the copy
        # is concerned, so this asks rather than blocks - and it reads the
        # raw entry, because event_name has already been sanitised to
        # "Event" by this point and would never look empty.
        missing_name = not self.event_name_var.get().strip()
        missing_desc = not description
        if missing_name or missing_desc:
            if missing_name and missing_desc:
                key = "confirm_missing_both"
            elif missing_name:
                key = "confirm_missing_name"
            else:
                key = "confirm_missing_desc"
            if not messagebox.askyesno(self.t("app_title"), self.t(key), default="no"):
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

        log.info("copy starting: date=%s camera=%s event=%r important=%s",
                 date_str, camera, event_name, important)
        log.info("  source=%s", source)
        log.info("  destination=%s", dest_root)
        self._set_busy(True)
        self._show_progress_area()
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
                log.error("copy failed: %s: %s", src_file.name, e)
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
                log.error("verification failed: %s", src_file.name)
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

        log.info("copy finished: %s of %s verified, %s failed, %s unverified, metadata_ok=%s",
                 copied, total, len(failed), len(unverified), metadata_ok)
        log.info("  into %s", event_folder)
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
                self._show_same_event()
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

    # The help text is stored as plain paragraphs; these turn it into
    # something that reads like a document rather than a dumped text file.
    HELP_STEP_RE = re.compile(r"^ {2}(\d+)\.\s+(.*)$")
    HELP_BULLET_RE = re.compile(r"^(\s*)-\s+(.*)$")

    @classmethod
    def _parse_help(cls, raw: str):
        """Group the raw text into (kind, text) blocks.

        Wrapped lines are rejoined into one block so the Text widget can do
        the wrapping itself at whatever width the window happens to be,
        rather than keeping the hard line breaks the source was typed with.
        """
        blocks, kind, buf, num = [], None, [], None

        def flush():
            nonlocal kind, buf, num
            if buf:
                blocks.append((kind, num, " ".join(buf)))
            kind, buf, num = None, [], None

        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                flush()
                continue

            # Unindented and entirely upper case is a section heading. This
            # holds for Greek and for accented Latin, both checked.
            if not line.startswith(" ") and stripped == stripped.upper():
                flush()
                blocks.append(("h1", None, stripped))
                continue

            step = cls.HELP_STEP_RE.match(line)
            if step:
                flush()
                kind, num, buf = "step", step.group(1), [step.group(2)]
                continue

            bullet = cls.HELP_BULLET_RE.match(line)
            if bullet:
                flush()
                kind = "sub" if len(bullet.group(1)) >= 6 else "bullet"
                buf = [bullet.group(2)]
                continue

            if kind is None:
                kind = "indented" if line.startswith("     ") else "body"
            buf.append(stripped)

        flush()
        return blocks

    def _render_help(self, text):
        base = ("Helvetica", 12)
        text.tag_config("h1", font=("Helvetica", 13, "bold"), foreground="#2e7d32",
                        spacing1=16, spacing3=7)
        text.tag_config("body", font=base, spacing3=9, lmargin1=2, lmargin2=2)
        text.tag_config("indented", font=base, spacing3=9, lmargin1=26, lmargin2=26)
        text.tag_config("step", font=base, spacing3=7, lmargin1=20, lmargin2=38)
        text.tag_config("stepnum", font=("Helvetica", 12, "bold"), foreground="#2e7d32")
        text.tag_config("bullet", font=base, spacing3=6, lmargin1=20, lmargin2=34)
        text.tag_config("sub", font=base, spacing3=4, lmargin1=44, lmargin2=58)

        for kind, num, body in self._parse_help(HELP_TEXT.get(self.lang, HELP_TEXT["en"])):
            if kind == "h1":
                text.insert("end", body + "\n", ("h1",))
            elif kind == "step":
                text.insert("end", f"{num}.  ", ("stepnum", "step"))
                text.insert("end", body + "\n", ("step",))
            elif kind in ("bullet", "sub"):
                text.insert("end", "\u2022  ", (kind,))
                text.insert("end", body + "\n", (kind,))
            else:
                text.insert("end", body + "\n", (kind,))

    def _save_report(self):
        """Put the log somewhere the user can actually find and send.

        Asking a non-technical person for a file in a dotted path in their
        home folder does not work, so it is copied to the Desktop with a
        dated name and the folder is opened on it.
        """
        stamp = time.strftime("%Y-%m-%d_%H%M")
        desktop = Path.home() / "Desktop"
        target = (desktop if desktop.is_dir() else Path.home()) / f"SD_Backup_Report_{stamp}.txt"

        header = [
            "SD Card Video Backup - problem report",
            f"Written:   {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Version:   {APP_VERSION}",
            f"Platform:  {sys.platform}  (packaged app: {bool(getattr(sys, 'frozen', False))})",
            f"Language:  {self.lang}",
            f"SD card:   {self.source_path.get().strip() or '(none selected)'}",
            f"Hard disk: {self.dest_path.get().strip() or '(none selected)'}",
            "",
            "--- log ---",
            "",
        ]
        try:
            body = LOG_PATH.read_text(encoding="utf-8", errors="replace") \
                if LOG_PATH.exists() else "(no log file yet)"
            target.write_text("\n".join(header) + body, encoding="utf-8")
        except OSError as e:
            log_exception("saving the report", e)
            messagebox.showerror(self.t("app_title"), self.t("report_failed", error=e))
            return

        log.info("problem report written to %s", target)
        open_in_file_manager(target.parent)
        messagebox.showinfo(self.t("app_title"), self.t("report_saved", path=target))

    def _open_help(self):
        """Show the guide for the language the interface is set to."""
        win = tk.Toplevel(self)
        win.title(self.t("help_title"))
        win.geometry("720x640")
        win.minsize(460, 340)
        win.configure(bg="#ffffff")

        header = tk.Frame(win, bg="#ffffff")
        header.pack(fill="x", padx=22, pady=(18, 0))
        tk.Label(header, text=self.t("help_title"), bg="#ffffff", fg="#1a1a1a",
                 font=("Helvetica", 16, "bold"), anchor="w").pack(fill="x")
        tk.Frame(header, height=1, bg="#dddddd").pack(fill="x", pady=(10, 0))

        body = tk.Frame(win, bg="#ffffff")
        body.pack(fill="both", expand=True, padx=22, pady=(6, 0))
        scrollbar = ttk.Scrollbar(body, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        text = tk.Text(body, wrap="word", yscrollcommand=scrollbar.set,
                       bg="#ffffff", fg="#1a1a1a", relief="flat", highlightthickness=0,
                       padx=0, pady=8, cursor="arrow", spacing2=3)
        text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=text.yview)

        self._render_help(text)
        text.config(state="disabled")

        footer = tk.Frame(win, bg="#ffffff")
        footer.pack(fill="x", padx=22, pady=(8, 16))
        tk.Button(footer, text=self.t("help_close"), command=win.destroy,
                  width=12).pack(side="right")

        def wheel(event):
            text.yview_scroll(1 if (event.num == 5 or getattr(event, "delta", 0) < 0)
                              else -1, "units")
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            text.bind(seq, wheel)
        win.bind("<Escape>", lambda _e: win.destroy())

        win.transient(self)
        text.focus_set()

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
        if str(self.copy_button.cget("state")) == "disabled":
            messagebox.showinfo(self.t("app_title"), self.t("update_busy"))
            return
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
        if version_tuple(info["version"]) <= version_tuple(APP_VERSION):
            messagebox.showinfo(self.t("app_title"), self.t("update_none", version=APP_VERSION))
            return

        # Where the app can replace itself, offer to do the whole thing.
        # Everywhere else, fall back to opening the download page.
        if can_self_update() and info.get("asset_url"):
            if messagebox.askyesno(
                self.t("app_title"),
                self.t("update_install_msg", version=info["version"], current=APP_VERSION),
            ):
                self._install_update(info)
            return

        if messagebox.askyesno(
            self.t("app_title"),
            self.t("update_available_msg", version=info["version"], current=APP_VERSION),
        ):
            webbrowser.open(info["url"])

    def _install_update(self, info):
        """Download the new version, unpack it, and hand over to the swap
        script. The app closes itself so its folder can be replaced."""
        self._set_busy(True)
        self.update_button.config(state="disabled")
        self._show_progress_area()
        self._set_progress_max(100)
        self._set_progress(0)
        self._set_status(self.t("update_downloading", pct=0))

        def worker():
            try:
                work = update_work_dir()
                archive = work / (info.get("asset_name") or "update.zip")
                download_update(
                    info["asset_url"], archive, info.get("asset_size", 0),
                    progress_cb=lambda pct: self.after(
                        0, lambda p=pct: (self._set_progress(p),
                                          self._set_status(self.t("update_downloading", pct=p)))),
                )
                exe_name = Path(sys.executable).name
                new_root = extract_update(archive, work / "staged", exe_name)
                self.after(0, lambda: self._set_status(self.t("update_installing")))
                log.info("update: installing %s over %s", new_root, Path(sys.executable).parent)
                launch_swap_script(Path(sys.executable).parent, new_root, exe_name)
            except Exception as e:
                log_exception("update failed", e)
                self.after(0, lambda e=e: self._update_failed(e))
                return
            # Give the swap script a moment to start waiting on this PID.
            self.after(800, self._quit_for_update)

        threading.Thread(target=worker, daemon=True).start()

    def _update_failed(self, error):
        self._set_busy(False)
        self.update_button.config(state="normal")
        self._set_progress(0)
        self._set_status("")
        messagebox.showerror(self.t("app_title"),
                             self.t("update_install_failed", error=error))

    def _quit_for_update(self):
        self.destroy()


def main():
    setup_logging()
    sys.excepthook = lambda t, v, tb: log_exception("unhandled error", v)
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
