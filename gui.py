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
                chat_thread = ChatThread(self.dc, self.chat)
                chat_thread.start()
                DCThread(self.dc, pass_callback=self.get_pass, onclose=chat_thread.close).start()

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
        font_family = 'Helvetica'
        font_size = 12
        font_normal = (font_family, font_size, 'normal')
        font_bold = (font_family, font_size, 'bold')
        chat = Text(self, wrap=WORD, state=DISABLED)
        scroll.config(command=chat.yview)
        chat.config(yscrollcommand=scroll.set)
        scroll.pack(side=RIGHT, fill=Y)
        chat.pack(side=LEFT, expand=YES, fill=BOTH)
        chat.tag_config('timestamp', font=font_normal, foreground='gray')
        chat.tag_config('text', font=font_normal, foreground='black')
        chat.tag_config('nick', font=font_bold, foreground='black')
        chat.tag_config('own_nick', font=font_bold, foreground='green')
        chat.tag_config('op_nick', font=font_bold, foreground='red')
        chat.tag_config('bot_nick', font=font_bold, foreground='red')
        chat.tag_config('error', font=font_normal, foreground="red")
        chat.tag_config('info', font=font_normal, foreground="blue")
        for tag in ('nick', 'op_nick', 'bot_nick'):
            chat.tag_bind(tag, '<Double-1>', lambda e: print(e))
        self.chat = chat
        self.first_line = True   # используем флаг вместо извлечения текста из виджета
        self.lock = threading.RLock()

    def add_string(self, str_list):
        ''' str_list - одна строка в виде списка/кортежа
            (tag1, text1, tag2, text2, ...)
        '''
        with self.lock:
            self.chat.config(state=NORMAL)
            str_list_iter = iter(str_list)   # fuck tha itertools!
            if self.first_line:
                self.first_line = False
            else:
                self.chat.insert(END, '\n', 'text')
            for tag in str_list_iter:
                text = next(str_list_iter)
                self.chat.insert(END, text, tag)
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
        self._close = False
        threading.Thread.__init__(self, name=self.__class__.__name__, daemon=True)

    def run(self):
        counter = 50
        while not self._close or counter:
            message = self.dc.message_queue.mget()
            if message:
                message['text'] = message['text'].replace('\r', '')
                if message['type'] == slangdc.MSGCHAT:
                    nick_tag = 'nick'
                    if message['nick'] == self.dc.nick:
                        nick_tag = 'own_nick'
                    elif self.dc.nicklist:
                        if message['nick'] in self.dc.nicklist.ops:
                            nick_tag = 'op_nick'
                        elif message['nick'] in self.dc.nicklist.bots:
                            nick_tag = 'bot_nick'
                    if not message['me']:
                        msg = ('text', "<", nick_tag, message['nick'], 'text', "> " + message['text'])
                    else:
                        msg = ('text', "* ", nick_tag, message['nick'], 'text', " " + message['text'])
                elif message['type'] == slangdc.MSGPM:
                    if 'sender' in message:   # если это входящее сообщение
                        pref = "PM from " + message['sender']
                    else:   # если исходящее сообщение
                        pref = "PM to " + message['recipient']
                    msg = ('info', pref)
                elif message['type'] == slangdc.MSGERR:
                    msg = ('error', "*** " + message['text'])
                else:
                    msg = ('info', "*** " + message['text'])
                timestamp = datetime.fromtimestamp(message['time']).strftime('[%H:%M:%S] ')
                self.chat.add_string(('timestamp', timestamp) + msg)
            if self._close:
                counter -= 1
            time.sleep(0.01)

    def close(self):
        self._close = True


class DCThread(threading.Thread):

    def __init__(self, dc, pass_callback=None, onclose=None):   # onclose - коллбэк, вызываемый при завершении треда (прибиваем другой тред)
        self.dc = dc
        self.pass_callback=pass_callback
        self.onclose = onclose
        threading.Thread.__init__(self, name=self.__class__.__name__)

    def run(self):
        self.dc.connect(get_nicks=True, pass_callback=self.pass_callback)
        while self.dc.connected:
            self.dc.receive(raise_exc=False)
        if self.onclose:
            self.onclose()


config = conf.Config()
root = Tk()
root.title("slangdc.Tk")
gui = TestGui(root)
root.protocol('WM_DELETE_WINDOW', gui.quit)
root.mainloop()
