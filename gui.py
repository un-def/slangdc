# -*-coding: UTF-8 -*-
from tkinter import *
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
        self.disconnect()   # в случае реконнекта
        self.dc = slangdc.DCClient(**self.settings)
        PrintThread(self.dc).start()
        self.dc.connect(get_nicks=True)
        if self.dc.connected:
            DCThread(self.dc).start()

    def disconnect(self):
        if self.dc and self.dc.connected:
            print("### already connected ###")
            self.dc.disconnect()

    def quit(self):
        self.disconnect()
        print("### closing ###")
        
wrapper = Wrapper()
root = Tk()
root.title("slangdc.Tk")
button_connect = Button(root, text="connect", command=wrapper.connect)
button_connect.pack()
button_disconnect = Button(root, text="disconnect", command=wrapper.disconnect)
button_disconnect.pack()
button_quit = Button(root, text="quit", command=wrapper.quit)
button_quit.pack()
root.mainloop()
