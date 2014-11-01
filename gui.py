# -*-coding: UTF-8 -*-
from tkinter import *
import sys
import slangdc
from example import PrintThread, DCThread

class Wrapper:

    def __init__(self):
        self.settings = {
            'encoding': 'windows-1251',
            'timeout': 900
        }
        self.dc = None

    def connect(self, entry):
        if not self.dc or not self.dc.connecting:   # если ещё не подключались или не подключаемся в данный момент
            address = entry.get().strip()
            if address:
                self.disconnect()   # отключимся, если уже подключены
                self.settings['address'] = address
                self.dc = slangdc.DCClient(**self.settings)
                PrintThread(self.dc).start()
                DCThread(self.dc).start()

    def disconnect(self):
        if self.dc:
            self.dc.disconnect()
            self.dc = None

    def quit(self):
        self.disconnect()
        sys.exit()

    def send(self, entry):
        if self.dc and self.dc.connected:
            etext = entry.get()
            if etext:
                if etext.startswith('/pm '):
                    nick, text = etext[4:].split(' ', 1)
                    self.dc.pm_send(nick, text)
                if etext.startswith('/user '):
                    nick = etext[6:]
                    print("user", nick, "is", "online" if nick in self.dc.nicklist else "offline")
                elif etext == '/oplist':
                    print("ops:", " ".join(sorted(self.dc.nicklist.ops)))
                elif etext == '/botlist':
                    print("bots:", " ".join(sorted(self.dc.nicklist.bots)))
                elif etext == '/usercount':
                    print("usercount:", len(self.dc.nicklist))
                elif etext == '/quit':
                    self.quit()
                elif not etext.startswith('/') or etext.startswith('/me '):
                    self.dc.chat_send(etext)
                entry.delete(0, END)


wrapper = Wrapper()
root = Tk()
root.title("slangdc.Tk")
ftop = Frame(root)
ftop.pack()
address_entry = Entry(ftop)
address_entry.insert(0, "allavtovo.ru")
address_entry.pack(side=LEFT)
address_entry.bind('<Return>', lambda e: wrapper.connect(address_entry))
Button(ftop, text="connect", command=lambda: wrapper.connect(address_entry)).pack(side=LEFT)
Button(ftop, text="disconnect", command=wrapper.disconnect).pack(side=LEFT)
Button(ftop, text="quit", command=wrapper.quit).pack(side=LEFT)
fbottom = Frame(root)
fbottom.pack()
msg_entry = Entry(fbottom, width=50)
msg_entry.pack(side=LEFT)
msg_entry.bind('<Return>', lambda e: wrapper.send(msg_entry))
Button(fbottom, text="send", command=lambda: wrapper.send(msg_entry)).pack(side=LEFT)
root.mainloop()
