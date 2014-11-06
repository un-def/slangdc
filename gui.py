# -*-coding: UTF-8 -*-
import time
import re
import threading
from datetime import datetime
from tkinter import *
import slangdc
import conf


class Gui:

    def __init__(self, root=None):
        self.root = root
        self.dc = None
        self.chat_addr_sep = ':'   # разделитель при обращении к пользователю в чате
        main_frame = Frame(root)
        main_frame.pack(expand=YES, fill=BOTH)
        # address entry, connect, disconnect, settings, quit buttons
        ftop = Frame(main_frame)
        ftop.pack(side=TOP, fill=X)
        address_entry = Entry(ftop)
        address_entry.insert(0, 'allavtovo.ru')
        address_entry.pack(side=LEFT)
        address_entry.bind('<Return>', self.connect)
        self.address_entry = address_entry
        Button(ftop, text="connect", command=self.connect).pack(side=LEFT)
        Button(ftop, text="disconnect", command=self.disconnect).pack(side=LEFT)
        Button(ftop, text="quit", command=self.quit).pack(side=RIGHT)
        Button(ftop, text="settings", command=self.show_settings).pack(side=RIGHT)
        # message entry, send button
        fbottom = Frame(main_frame)
        fbottom.pack(side=BOTTOM, fill=X)
        msg_entry = Entry(fbottom, width=50)
        msg_entry.pack(side=LEFT, expand=YES, fill=X)
        msg_entry.bind('<Return>', self.send)
        self.msg_entry = msg_entry
        Button(fbottom, text="send", command=self.send).pack(side=RIGHT)
        # chat
        self.chat = Chat(main_frame, side=TOP, doubleclick_callback=self.insert_nick)

    def get_pass(self):
        pass_window = PassWindow(self.root)
        pass_window.wait_window()
        return pass_window.password.get()

    def insert_nick(self, check_nick):
        if self.dc and check_nick != self.dc.nick and self.dc.nicklist:
            if check_nick in self.dc.nicklist:
                if self.msg_entry.index('insert') == 0:   # если курсор стоит в начале поля ввода,
                    check_nick = check_nick + self.chat_addr_sep + ' '   # то вставляем ник как обращение
                self.msg_entry.insert('insert', check_nick)
                self.msg_entry.focus_set()
                return True

    def connect(self, event=None):
        if not self.dc or not self.dc.connecting:   # если ещё не подключались или не подключаемся в данный момент
            address = self.address_entry.get().strip()
            if address:
                self.disconnect()   # отключимся, если уже подключены
                self.dc = slangdc.DCClient(address=address, **config.settings)
                self.run_chat_loop(self.dc.message_queue)
                DCThread(self.dc, pass_callback=self.get_pass).start()

    def disconnect(self):
        if self.dc and self.dc.connected:
            self.dc.disconnect()
            self.dc = None

    def quit(self):
        self.disconnect()
        self.root.quit()

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

    def run_chat_loop(self, message_queue):
        message = message_queue.mget()
        if message:
            if message['type'] == slangdc.MSGEND:
                message_queue = False
            else:
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
        if message_queue:
            self.root.after(10, self.run_chat_loop, message_queue)


class Chat(Frame):

    def __init__(self, parent=None, side=TOP, doubleclick_callback=None):
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
        # http://stackoverflow.com/questions/9957810/how-do-you-modify-the-current-selection-length-in-a-tkinter-text-widget
        chat.bind('<Double-1>', lambda e: self.after(20, self.doubleclick))
        self.chat = chat
        self.doubleclick_callback = doubleclick_callback
        self.first_line = True   # используем флаг вместо извлечения текста из виджета
        self.lock = threading.RLock()

    def doubleclick(self, event=None):
        ''' пытается извлечь из выделенного по двойному клику текста и его
            окружения ник:
            при клике в строке '<user.nick> text' по 'nick' будет выделен
            только фрагмент 'nick' ("слово" в понимании Tk)
            метод проверяет окружающий текст, извлекает часть, похожую на ник
            и передаёт её коллбэку, указанному при инициализации Chat
            коллбэк должен вернуть True, если есть пользователь с таким ником,
            в этом случае метод выделит ник ('user.nick')
            NB: на некоторых системах при клике выделяется весь текст между
            whitespace ('<user.nick>'), в этом случае используем воркэраунд
        '''
        line_begin, col_begin = self.chat.index('sel.first').split('.')
        line_end, col_end = self.chat.index('sel.last').split('.')
        if line_begin == line_end:   # только если выделена одна строка
            line = line_begin
            full_line = self.chat.get(line + '.0', line + '.end')
            col_begin = int(col_begin)
            col_end = int(col_end)
            sel = full_line[col_begin:col_end]
            modified = False
            if col_begin:
                around = re.search('[^ \r\n\t\<]+$', full_line[:col_begin])
                if around:
                    sel = around.group(0) + sel
                    col_begin = col_begin - len(around.group(0))
                    modified = True
            if col_end < len(full_line):
                around = re.search('^[^ \r\n\t\:,\>]+', full_line[col_end:])
                if around:
                    sel = sel + around.group(0)
                    col_end = col_end + len(around.group(0))
                    modified = True
            if not modified:   # workaround - см. NB в docstring; с изменением выделения не будем париться, только стрипнем ник
                sel_strip = re.search('[^\<\>\:,]+', sel)
                if sel_strip:
                    sel = sel_strip.group(0)
            if self.doubleclick_callback:
                is_nick = self.doubleclick_callback(sel)
                if is_nick:
                    self.chat.tag_add('sel', '{}.{}'.format(line, col_begin), '{}.{}'.format(line, col_end))

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
        grid_frame = Frame(self)
        grid_frame.pack(padx=5, pady=5)
        for row, (field_name, field_type, field_text) in enumerate(fields):
            self.entry_vars[field_name] = (StringVar(), field_type)
            self.entry_vars[field_name][0].set(config.settings[field_name])
            Label(grid_frame, width=12, text=field_text, anchor=W).grid(row=row, column=0)
            Entry(grid_frame, width=20, textvariable=self.entry_vars[field_name][0]).grid(row=row, column=1)
        Button(self, text="cancel", width=8, command=self.close).pack(side=RIGHT, padx=5, pady=3)
        Button(self, text="save", width=8, command=self.save).pack(side=RIGHT)

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
gui = Gui(root)
root.protocol('WM_DELETE_WINDOW', gui.quit)
root.mainloop()
