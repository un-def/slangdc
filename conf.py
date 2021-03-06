# -*-coding: UTF-8 -*-
import os
import json
import copy


class DNDict(dict):
    ''' словарь с точечной нотацией доступа к элементам
    '''
    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError
        return self[name]


class Config:

    default_settings = DNDict({
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
        'cr2lf': False,
        'max_lines': 500
    })

    default_styles = DNDict({
        'window_size': (800, 600),
        'chat': DNDict({
            'bg': '#FEFEFE',
            'font': ('Helvetica', 11),
            'styles': DNDict({
                'timestamp': ('normal', 'gray'),
                'text': ('normal', 'black'),
                'link': ('normal underline', 'blue'),
                'broken_link': ('normal underline', 'gray'),
                'own_nick': ('bold', 'green'),
                'user_nick': ('bold', 'black'),
                'op_nick': ('bold', 'red'),
                'bot_nick': ('bold', 'magenta'),
                'error': ('normal', 'red'),
                'info': ('normal', 'blue')
            })
        }),
        'userlist': DNDict({
            'bg': 'white',
            'font': ('Helvetica', 10, 'normal'),
            'color_user': 'black',
            'color_op': 'red',
            'color_bot': 'magenta'
        }),
        'tabs': DNDict({
            'color_on': '#D0D0D0',
            'color_off': '#FF9999',
            'font_unsel': ('Helvetica', 9, 'normal'),
            'font_sel': ('Helvetica', 10, 'bold')
        }),
        'message': DNDict({
            'bg': 'white',
            'font': ('Helvetica', 11, 'normal'),
            'color': 'black',
            'height': 3
        })
    })

    def __init__(self):
        self.path = (os.path.abspath(os.path.dirname(__file__)))
        self.settings_filename = os.path.join(self.path, 'settings.json')
        self.styles_filename = os.path.join(self.path, 'styles.json')
        self.bookmarks_filename = os.path.join(self.path, 'bookmarks.json')
        self.load_settings()
        self.load_styles()
        self.load_bookmarks()


    def load_file(self, file, default=None, save=False):
        modified = False
        conf = None
        try:
            fo = open(file)
        except FileNotFoundError:
            if not default is None:
                conf = copy.deepcopy(default)
                modified = True
        else:
            try:
                conf = json.load(fo, object_hook=lambda d: DNDict(d))
            except ValueError:
                fo.close()
                if not default is None:
                    conf = copy.deepcopy(default)
                    modified = True
            else:
                fo.close()
                if default and not modified:
                    modified, conf = self.check_config(conf, default)
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

    def load_styles(self):
        self.styles = self.load_file(self.styles_filename, default=self.default_styles, save=True)

    def load_bookmarks(self):
        self.bookmarks = self.load_file(self.bookmarks_filename, default=[], save=False)

    def save_bookmarks(self, bookmarks):
        self.bookmarks = bookmarks
        self.save_file(self.bookmarks_filename, bookmarks)

    def make_dc_settings(self, address=None):
        ''' возвращает словарь аргументов для DCClient.connect из текущих
            настроек (Config.settings) и адреса, если он передан
        '''
        dc_settings = {s: self.settings[s] for s in ('nick', 'desc', 'email', 'share', 'slots', 'encoding', 'timeout', 'detect_utf8')}
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
        dc_settings.pop('autoconnect', None)
        return dc_settings

    def check_config(self, conf, default, modified=False):
        ''' сравнивает конфиги conf и default и при необходимости копирует
            недостающие элементы из default (рекурсивно)
        '''
        for k in default:
            if k not in conf:
                conf[k] = default[k]
                modified = True
            elif isinstance(default[k], dict):
                modified, conf[k] = self.check_config(conf[k], default[k], modified)
        return modified, conf

    @staticmethod
    def trim_address(address):
        address = address.strip().rstrip('/').split('//')[-1]
        return address[:-4] if address.endswith(':411') else address
