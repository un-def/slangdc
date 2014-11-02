# -*-coding: UTF-8 -*-
from tkinter import *
import slangdc
from example import PrintThread, DCThread


class TestGui(Frame):

    def __init__(self, parent=None):
        self.settings = {
            'address': 'allavtovo.ru',
            'encoding': 'windows-1251',
            'timeout': 900
        }
        self.dc = None
        Frame.__init__(self, parent)
        self.pack(expand=YES)
        self.make_widgets()

    def make_widgets(self):
        ftop = Frame(self)
        ftop.pack()
        self.address_entry = Entry(ftop)
        self.address_entry.insert(0, self.settings['address'])
        self.address_entry.pack(side=LEFT)
        self.address_entry.bind('<Return>', self.connect)
        Button(ftop, text="connect", command=self.connect).pack(side=LEFT)
        Button(ftop, text="disconnect", command=self.disconnect).pack(side=LEFT)
        Button(ftop, text="quit", command=self.quit).pack(side=LEFT)
        fbottom = Frame(self)
        fbottom.pack()
        self.msg_entry = Entry(fbottom, width=50)
        self.msg_entry.pack(side=LEFT)
        self.msg_entry.bind('<Return>', self.send)
        Button(fbottom, text="send", command=self.send).pack(side=LEFT)

    def connect(self, event=None):
        if not self.dc or not self.dc.connecting:   # если ещё не подключались или не подключаемся в данный момент
            address = self.address_entry.get().strip()
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
        self.__class__.__base__.quit(self)   # можно и просто Frame.quit(self)

    def send(self, event=None):
        if self.dc and self.dc.connected:
            etext = self.msg_entry.get()
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
                self.msg_entry.delete(0, END)


root = Tk()
root.title("slangdc.Tk")
gui = TestGui(root)
root.protocol('WM_DELETE_WINDOW', gui.quit)
root.mainloop()
