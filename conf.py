# -*-coding: UTF-8 -*-
import json

class Config:

    default_settings = {
        'nick': '',
        'desc': 'slangdc',
        'email': '',
        'share': 0,
        'slots': 1,
        'encoding': 'windows-1251',
        'timeout': 900,
        'reconnect': True,
        'reconnect_delay': 10
    }

    def __init__(self):
        self.settings_filename = 'settings.json'
        self.bookmarks_filename = 'bookmarks.json'
        self.settings = self.load_settings()

    def load_file(self, file, default=None, save=False):
        modified = False
        conf = None
        try:
            fo = open(file)
        except FileNotFoundError:
            if not default is None:
                conf = default.copy()
                modified = True
        else:
            try:
                conf = json.load(fo)
            except ValueError:
                fo.close()
                if not default is None:
                    conf = default.copy()
                    modified = True
            else:
                fo.close()
                if default and not modified:
                    for k in default:
                        if k not in conf:
                            conf[k] = default[k]
                            modified = True
        if save and modified:
            self.save_file(file, conf)
        return conf

    def save_file(self, file, conf):
        fo = open(file, 'w')
        json.dump(conf, fo, indent=4, sort_keys=True)
        fo.close()

    def load_settings(self):
        self.settings = self.load_file(self.settings_filename, default=self.default_settings, save=True)

    def save_settings(self, settings):
        self.settings = settings
        self.save_file(self.settings_filename, settings)

    def load_bookmarks(self):
        self.bookmarks = self.load_file(self.bookmarks_filename, default=[], save=False)

    def save_bookmarks(self, bookmarks):
        self.bookmarks = bookmarks
        self.save_file(self.bookmarks_filename, bookmarks)
