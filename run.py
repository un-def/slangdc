#!/usr/bin/env python
# -*- coding: utf-8 -*-
import threading
from datetime import datetime
import time
import slangdc

settings = {
    'address': 'ozerki.org',
    #'nick': 'las.cifritas',
    #'password': 'psswrd',
    #'email': 'un.def@ya.ru',
    'desc': 'git',
    'slots': 10,
    'encoding': 'windows-1251',
    'timeout': 120
}

class Printer(threading.Thread):

    def __init__(self, dc):
        self.dc = dc
        threading.Thread.__init__(self)

    def run(self):
        prefixes = {
            slangdc.MSGINFO: "***",
            slangdc.MSGERR: "xxx",
            slangdc.MSGCHAT: "",
            slangdc.MSGPM: "## PM ##"
        }
        while True:
            message = self.dc.message_queue.mget()
            if message:
                sep = prefixes[message['type']]
                timestamp = datetime.fromtimestamp(message['time']).strftime('[%H:%M:%S]')
                print("{0} {1} {2}".format(timestamp, sep, message['text']))
            time.sleep(0.01)
        print("@close Printer")


class Typer(threading.Thread):

    def __init__(self, dc):
        self.dc = dc
        threading.Thread.__init__(self)

    def run(self):
        while self.dc.connected:
            message = input()
            if message == '!!quit':
                self.dc.disconnect()
            elif message == '!!showjoins':
                dc.showjoins = not dc.showjoins
                print("showjoins: ", dc.showjoins)
            elif message == '!!nickcount':
                print("users: ", len(dc.nicklist))
            elif message == '!!nicklist':
                for nmb, nick in enumerate(sorted(dc.nicklist), 1):
                    print("{0: 4d} {1}".format(nmb, nick))
            elif message:
                dc.chat_send(message)
        print("@close Typer")


dc = slangdc.DCClient(**settings)
printer = Printer(dc)
printer.start()

dc.connect(get_nicks=True)
if dc.connected:
    typer = Typer(dc)
    typer.start()
    while dc.connected:
        dc.receive(raise_exc=False)
time.sleep(0.5)
print("@close main")
