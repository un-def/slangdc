# -*-coding: UTF-8 -*-
import json
settings_filename = 'settings.json'
bookmarks_filename = 'bookmarks.json'
default_settings = {
    'nick': '',
    'desc': 'slangdc',
    'email': '',
    'share': 0,
    'slots': 1,
    'timeout': 900,
    'encoding': 'windows-1251'
}

def load_settings():
    save_it = False
    try:
        settings_fo = open(settings_filename)
    except FileNotFoundError:
        settings = default_settings.copy()
        save_it = True
    else:
        try:
            settings = json.load(settings_fo)
        except ValueError:
            settings_fo.close()
            settings = default_settings.copy()
            save_it = True
        else:
            settings_fo.close()
            for k in default_settings:
                if k not in settings:
                    settings[k] = default_settings[k]
                    save_it = True
    if save_it:
        save_settings(settings)
    return settings

def save_settings(settings):
    settings_fo = open(settings_filename, 'w')
    json.dump(settings, settings_fo, indent=4, sort_keys=True)
    settings_fo.close()


