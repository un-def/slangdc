# -*-coding: UTF-8 -*-
from tkinter import *
import slangdc
import conf
from example import PrintThread, DCThread


class TestGui(Frame):

    def __init__(self, root=None):
        Frame.__init__(self, root)
        self.root = root
        self.dc = None
        self.pack(expand=YES)
        self.make_widgets()

    def make_widgets(self):
        ftop = Frame(self)
        ftop.pack()
        self.address_entry = Entry(ftop)
        self.address_entry.insert(0, 'allavtovo.ru')
        self.address_entry.pack(side=LEFT)
        self.address_entry.bind('<Return>', self.connect)
        Button(ftop, text="connect", command=self.connect).pack(side=LEFT)
        Button(ftop, text="disconnect", command=self.disconnect).pack(side=LEFT)
        Button(ftop, text="settings", command=self.show_settings).pack(side=LEFT)
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
                self.dc = slangdc.DCClient(address=address, **config.settings)
                PrintThread(self.dc).start()
                DCThread(self.dc).start()

    def disconnect(self):
        if self.dc:
            self.dc.disconnect()
            self.dc = None

    def quit(self):
        self.disconnect()
        self.__class__.__base__.quit(self)   # можно и просто Frame.quit(self)

    def show_settings(self):
        try:
            self.settings_window.focus_set()
        except Exception:   # workaround - AttribureError, _tkinter.TclError
            self.settings_window = SettingsWindow()

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

class SettingsWindow(Toplevel):

    def __init__(self, root=None):
        Toplevel.__init__(self, root)
        self.title("settings")
        self.protocol('WM_DELETE_WINDOW', self.close)
        # (field_name, field_type, field_text)
        fields = (
            ('nick', 'str', 'nick'),
            ('desc', 'str', 'description'),
            ('email', 'str', 'e-mail'),
            ('share', 'int', 'share'),
            ('slots', 'int', 'slots'),
            ('encoding', 'str', 'encoding'),
            ('timeout', 'int', 'receive timeout')
        )
        self.entry_vars = {}
        for field_name, field_type, field_text in fields:
            row = Frame(self)
            row.pack(expand=YES, fill=X)
            Label(row, width=12, text=field_text, anchor=W).pack(side=LEFT)
            self.entry_vars[field_name] = (StringVar(), field_type)
            self.entry_vars[field_name][0].set(config.settings[field_name])
            Entry(row, textvariable=self.entry_vars[field_name][0]).pack(expand=YES, fill=X, side=RIGHT)
        Button(self, text="cancel", command=self.close).pack(side=RIGHT)
        Button(self, text="save", command=self.save).pack(side=RIGHT)

    def save(self):
        new_settings = {}
        for field_name, (entry_var, field_type) in self.entry_vars.items():
            val = entry_var.get()
            if field_type == 'int':
                try:
                    val = int(val)
                except ValueError:   # валидации форм нет, поэтому вместо недопустимых значений берём дефолтные
                    val = config.default_settings[field_name]
            new_settings[field_name] = val
        config.update_settings(new_settings)
        self.close()

    def close(self):
        self.destroy()


config = conf.Config()
root = Tk()
root.title("slangdc.Tk")
gui = TestGui(root)
root.protocol('WM_DELETE_WINDOW', gui.quit)
root.mainloop()
