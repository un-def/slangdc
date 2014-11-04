# -*-coding: UTF-8 -*-
import time
import threading
from datetime import datetime
from tkinter import *
import slangdc
import conf


class TestGui(Frame):

    def __init__(self, root=None):
        Frame.__init__(self, root)
        self.root = root
        self.dc = None
        self.pack(expand=YES, fill=BOTH)
        # address entry, connect, disconnect, settings, quit buttons
        ftop = Frame(self)
        ftop.pack(side=TOP, fill=X)
        self.address_entry = Entry(ftop)
        self.address_entry.insert(0, 'allavtovo.ru')
        self.address_entry.pack(side=LEFT)
        self.address_entry.bind('<Return>', self.connect)
        Button(ftop, text="connect", command=self.connect).pack(side=LEFT)
        Button(ftop, text="disconnect", command=self.disconnect).pack(side=LEFT)
        Button(ftop, text="quit", command=self.quit).pack(side=RIGHT)
        Button(ftop, text="settings", command=self.show_settings).pack(side=RIGHT)
        # message entry, send button
        fbottom = Frame(self)
        fbottom.pack(side=BOTTOM, fill=X)
        self.msg_entry = Entry(fbottom, width=50)
        self.msg_entry.pack(side=LEFT, expand=YES, fill=X)
        self.msg_entry.bind('<Return>', self.send)
        Button(fbottom, text="send", command=self.send).pack(side=RIGHT)
        # chat
        self.chat = Chat(self, side=TOP)

    def get_pass(self):
        pass_window = PassWindow(self.root)
        time.sleep(0.1)   # по непонятной причине без этого костыля окно пароля блокируется почти всегда
        pass_window.wait_window()
        return pass_window.password.get()

    def connect(self, event=None):
        if not self.dc or not self.dc.connecting:   # если ещё не подключались или не подключаемся в данный момент
            address = self.address_entry.get().strip()
            if address:
                self.disconnect()   # отключимся, если уже подключены
                self.dc = slangdc.DCClient(address=address, **config.settings)
                ChatThread(self.dc, self.chat).start()
                DCThread(self.dc, pass_callback=self.get_pass).start()

    def disconnect(self):
        if self.dc and self.dc.connected:
            self.dc.disconnect()
            self.dc = None

    def quit(self):
        self.disconnect()
        self.__class__.__base__.quit(self)   # можно и просто Frame.quit(self)

    def show_settings(self):
        try:
            self.settings_window.focus_set()
        except Exception:   # workaround - AttribureError, _tkinter.TclError
            self.settings_window = SettingsWindow(self.root)

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


class Chat(Frame):

    def __init__(self, parent=None, side=TOP):
        Frame.__init__(self, parent)
        self.pack(expand=YES, fill=BOTH, side=side)
        scroll = Scrollbar(self)
        chat = Text(self, font='TkTextFont', wrap=WORD, state=DISABLED)
        scroll.config(command=chat.yview)
        chat.config(yscrollcommand=scroll.set)
        scroll.pack(side=RIGHT, fill=Y)
        chat.pack(side=LEFT, expand=YES, fill=BOTH)
        self.chat = chat

    def add_string(self, string):
        string = string.replace('\r', '')
        self.chat.config(state=NORMAL)
        self.chat.insert(END, string + '\n')
        self.chat.config(state=DISABLED)
        self.chat.see(END)


class SettingsWindow(Toplevel):

    def __init__(self, root=None):
        Toplevel.__init__(self, root)
        self.title("settings")
        self.resizable(width=FALSE, height=FALSE)
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


class PassWindow(Toplevel):

    def __init__(self, root=None):
        Toplevel.__init__(self, root)
        self.title("password")
        self.resizable(width=FALSE, height=FALSE)
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.transient()
        self.focus_set()
        self.grab_set()
        Label(self, text='password', anchor=W).pack(side=LEFT)
        self.password = StringVar()
        pass_entry = Entry(self, show='*', textvariable=self.password)
        pass_entry.pack(side=LEFT, expand=YES, fill=X)
        pass_entry.bind('<Return>', self.confirm)
        Button(self, text="ok", command=self.confirm).pack(side=RIGHT)

    def close(self):
        self.password.set('')
        self.destroy()

    def confirm(self, event=None):
        if self.password.get():
            self.destroy()


class ChatThread(threading.Thread):

    def __init__(self, dc, chat):
        self.dc = dc
        self.chat = chat
        threading.Thread.__init__(self, name=self.__class__.__name__, daemon=True)

    def run(self):
        while True:
            message = self.dc.message_queue.mget()
            if message:
                if message['type'] == slangdc.MSGCHAT:
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
                else:
                    pref = "***"
                timestamp = datetime.fromtimestamp(message['time']).strftime('[%H:%M:%S]')
                self.chat.add_string("{0} {1} {2}".format(timestamp, pref, message['text']))
                if message['type'] == slangdc.MSGINFO and message['text'] == 'disconnected':
                    break
            time.sleep(0.01)


class DCThread(threading.Thread):

    def __init__(self, dc, pass_callback=None):
        self.dc = dc
        self.pass_callback=pass_callback
        threading.Thread.__init__(self, name=self.__class__.__name__)

    def run(self):
        self.dc.connect(get_nicks=True, pass_callback=self.pass_callback)
        while self.dc.connected:
            self.dc.receive(raise_exc=False)


config = conf.Config()
root = Tk()
root.title("slangdc.Tk")
gui = TestGui(root)
root.protocol('WM_DELETE_WINDOW', gui.quit)
root.mainloop()
