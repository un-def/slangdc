#!/usr/bin/env python
# -*- coding: utf-8 -*-
from datetime import datetime
import slangdc

settings = {
    'address': 'allavtovo.ru',
    'nick': 'slangdc',
    'encoding': 'windows-1251',
    'timeout': 300
}

def printline(string, *args):
    if args:
        string = string.format(*args)
    print(datetime.today().strftime('[%H:%M:%S]'), string)

printline('*** slangdc v{}', slangdc.version)

hub = slangdc.DCClient(**settings)
#hub.debug = True
printline('*** connecting to {}', settings['address'])
try:
    hub.connect()
except slangdc.DCSocketError as err:
    printline('*** socket error: {}', err)
except slangdc.DCHubError as err:
    printline('*** hub error: {}', err)
else:
    printline('*** connected to {}', settings['address'])
    while True:
        try:
            data = hub.recv()
        except slangdc.DCSocketError as err:
            printline('*** socket error: {}', err)
            break
        if data and not data.startswith('$'):
            printline(data)
hub.disconnect()
