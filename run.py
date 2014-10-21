#!/usr/bin/env python
# -*- coding: utf-8 -*-
import threading
from datetime import datetime
import time
import slangdc

settings = {
    'address': 'dc.zet',
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
        while flag_:
            if self.queue:
                message = self.queue.pop(0)
                print(datetime.today().strftime('[%H:%M:%S]'), message)
            time.sleep(0.01)
        print("@close Printer")


class Typer(threading.Thread):

    def __init__(self, hub):
        self.hub = hub
        threading.Thread.__init__(self)

    def run(self):
        global flag_
        while flag_:
            message = input()
            if message == '!!quit':
                flag_ = False
            else:
                hub.chat_send(message)
        print("@close Typer")



flag_ = True

hub = slangdc.DCClient(**settings)

printer = Printer(hub.message_queue)
printer.start()

connected = hub.connect()

if not connected:
    time.sleep(1)
    flag_ = False
else:
    typer = Typer(hub)
    typer.start()
    while flag_:
        success = hub.chat_recv()
        if not success:
            time.sleep(0.5)
            flag_ = False
    print("@close main")
