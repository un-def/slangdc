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
        print("### closing ###")
        sys.exit()

    def test(self):
        if self.dc and self.dc.connected:
            self.dc.chat_send("test")
        
wrapper = Wrapper()
root = Tk()
root.title("slangdc.Tk")
button_connect = Button(root, text="connect", command=wrapper.connect)
button_connect.pack()
button_disconnect = Button(root, text="disconnect", command=wrapper.disconnect)
button_disconnect.pack()
button_test = Button(root, text="test", command=wrapper.test)
button_test.pack()
button_quit = Button(root, text="quit", command=wrapper.quit)
button_quit.pack()
root.mainloop()
