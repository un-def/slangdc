# -*-coding: UTF-8 -*-
import os
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
        'reconnect_delay': 10,
        'show_joins': False,
        'chat_addr_sep': ':',
        'detect_utf8': False,
        'cr2lf': False
    }

    def __init__(self):
        self.path = (os.path.abspath(os.path.dirname(__file__)))
        self.settings_filename = os.path.join(self.path, 'settings.json')
        self.bookmarks_filename = os.path.join(self.path, 'bookmarks.json')
        self.load_settings()
        self.load_bookmarks()

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

    def make_dc_settings(self, address=None):
        ''' возвращает словарь аргументов для DCClient.connect из текущих
            настроек (Config.settings) и адреса, если он передан
        '''
        dc_settings = {s: self.settings[s] for s in ('nick', 'desc', 'email', 'share', 'slots', 'encoding', 'timeout')}
        if address:
            dc_settings['address'] = address
        return dc_settings

    def make_dc_settings_from_bm(self, bm_number):
        ''' возвращает словарь аргументов для DCClient.connect из указанной
            закладки; недостающие в закладке поля берутся из текущих настроек
            (Config.settings)
        '''
        address = self.trim_address(self.bookmarks[bm_number].get('address', ''))
        if not address: return False
        dc_settings = self.make_dc_settings()
        dc_settings.update(self.bookmarks[bm_number])
        dc_settings['address'] = address
        dc_settings.pop('name')
        return dc_settings

    def trim_address(self, address):
        address = address.strip().rstrip('/').split('//')[-1]
        return address[:-4] if address.endswith(':411') else address
