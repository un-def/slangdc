# -*-coding: UTF-8 -*-
from tkinter import *
import sys
import slangdc
from example import PrintThread, DCThread

class Wrapper:

    def __init__(self):
        self.settings = {
            'address': 'allavtovo.ru',
            #'nick': 'slangdc',
            #'password': 'psswrd',
            'encoding': 'windows-1251',
            'timeout': 900
        }
        self.dc = None

    def connect(self):
        if not self.dc or not self.dc.connecting:   # если ещё не подключались или не подключаемся в данный момент
            self.disconnect()   # отключимся, если уже подключены
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
            message = entry.get()
            if message:
                self.dc.chat_send(message)
                entry.delete(0, END)
        
wrapper = Wrapper()
root = Tk()
root.title("slangdc.Tk")
Button(root, text="connect", command=wrapper.connect).pack(side=LEFT)
Button(root, text="disconnect", command=wrapper.disconnect).pack(side=LEFT)
msg_entry = Entry(root, width=50)
msg_entry.pack(side=LEFT)
msg_entry.bind('<Return>', lambda e: wrapper.send(msg_entry))
Button(root, text="send", command=lambda: wrapper.send(msg_entry)).pack(side=LEFT)
Button(root, text="quit", command=wrapper.quit).pack(side=LEFT)
root.mainloop()
