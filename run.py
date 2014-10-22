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

    def __init__(self, queue):
        self.queue = queue
        threading.Thread.__init__(self)

    def run(self):
        global flag_
        prefixes = {
            slangdc.MSGINFO: "***",
            slangdc.MSGERR: "xxx",
            slangdc.MSGCHAT: "",
            slangdc.MSGPM: "## PM ##"
        }
        while flag_:
            message = self.queue.mget()
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
        global flag_
        while flag_:
            message = input()
            if message == '!!quit':
                flag_ = False
            elif message:
                dc.chat_send(message)
        print("@close Typer")



flag_ = True

dc = slangdc.DCClient(**settings)

printer = Printer(dc.message_queue)
printer.start()

connected = dc.connect()

if not connected:
    time.sleep(1)
    flag_ = False
else:
    typer = Typer(dc)
    typer.start()
    while flag_:
        success = dc.receive()
        if not success:
            time.sleep(0.5)
            flag_ = False
    print("@close main")
