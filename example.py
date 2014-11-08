#!/usr/bin/env python
# -*- coding: utf-8 -*-
import threading
from datetime import datetime
import time
import re
import slangdc

settings = {
    'address': 'allavtovo.ru',
    #'nick': 'slangdc',
    #'password': 'psswrd',
    #'email': 'un.def@ya.ru',
    'desc': 'git',
    'slots': 10,
    'encoding': 'windows-1251',
    'timeout': 900
}

class DCThread(threading.Thread):

    def __init__(self, dc):
        self.dc = dc
        threading.Thread.__init__(self)

    def run(self):
        self.dc.connect(nicklist=True)
        while self.dc.connected:
            self.dc.receive(raise_exc=False)


class PrintThread(threading.Thread):

    disconnect_countdown = 10

    def __init__(self, dc):
        self.dc = dc
        threading.Thread.__init__(self)

    def run(self):
        while True:
            message = self.dc.message_queue.mget()
            if message:
                if message['type'] == slangdc.MSGEND:
                    return
                elif message['type'] == slangdc.MSGCHAT:
                    if not message['me']:
                        pref = "<" + message['nick'] + ">"
                    else:
                        pref = "* " + message['nick']
                elif message['type'] == slangdc.MSGPM:
                    if 'sender' in message:   # если это входящее сообщение
                        pref = "PM from " + message['sender'] + ":"
                        if message['nick']:
                            if not message['me']:
                                pref = pref + " <" + message['nick'] + ">"
                            else:
                                pref = pref + " * " + message['nick']
                    else:   # если исходящее сообщение
                        pref = "PM to " + message['recipient'] + ":"
                        if not message['me']:
                            pref = pref + " <" + self.dc.nick + ">"
                        else:
                            pref = pref + " * " + self.dc.nick
                elif message['type'] == slangdc.MSGERR:
                    pref = "xxx"
                elif message['type'] == slangdc.MSGINFO:
                    pref = "***"
                else:
                    pass   # joins/parts
                timestamp = datetime.fromtimestamp(message['time']).strftime('[%H:%M:%S]')
                print("{0} {1} {2}".format(timestamp, pref, message['text']))
            time.sleep(0.01)


class InputThread(threading.Thread):

    def __init__(self, dc):
        self.dc = dc
        threading.Thread.__init__(self)
        self.daemon = True

    def run(self):
        while True:
            message = input()
            if message:
                pm = re.fullmatch('/pm (.+?) (.+)', message)
                if pm:
                    dc.pm_send(pm.group(1), pm.group(2))
                elif message == '/quit':
                    self.dc.disconnect()
                    return
                elif message == '/usercount':
                    print("users: ", len(dc.nicklist))
                elif message == '/nicklist':
                    for nmb, nick in enumerate(sorted(dc.nicklist), 1):
                        print("{0: 4d} {1}".format(nmb, nick))
                elif message == '/oplist':
                    oplist_str = " ".join(dc.nicklist.ops) if dc.nicklist.ops else "none"
                    print("ops:", oplist_str)
                elif message == '/botlist':
                    botlist_str = " ".join(dc.nicklist.bots) if dc.nicklist.bots else "none"
                    print("bots:", botlist_str)
                else:
                    dc.chat_send(message)

if __name__ == '__main__':
    dc = slangdc.DCClient(**settings)
    PrintThread(dc).start()
    InputThread(dc).start()
    dcthread = DCThread(dc)
    dcthread.start()
    dcthread.join()
    time.sleep(0.1)
