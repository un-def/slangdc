# -*-coding: UTF-8 -*-
import time
import re
import threading
from datetime import datetime
from tkinter import *
from tkinter.messagebox import askyesno
import slangdc
import conf


class Gui:

    def __init__(self):
        self.dc = None
        self.dc_settings = None
        self.reconnect_callback_id = None
        self.userlist_callback_id = None
        root = Tk()
        root.title("slangdc.Tk")
        root.protocol('WM_DELETE_WINDOW', root.iconify)
        self.root = root
        main_frame = Frame(root, padx=5, pady=5)
        main_frame.pack(expand=YES, fill=BOTH)
        # меню
        menu = Menu(root, borderwidth=0)
        root.config(menu=menu)
        menu_bookmarks = Menu(menu, tearoff=False)
        if config.bookmarks:
            for bm_number, bookmark in enumerate(config.bookmarks):
                menu_bookmarks.add_command(label=bookmark['name'], command=lambda n=bm_number: self.bookmark_connect(n))
        else:
            menu_bookmarks.add_command(label="Empty", state=DISABLED)
        menu.add_cascade(label="Bookmarks", menu=menu_bookmarks)
        menu_buttons = (
            ('Connect', self.connect),
            ('Disconnect', self.disconnect),
            ('Settings', self.show_settings),
            ('Quit', self.quit)
        )
        for btn_txt, btn_cmd in menu_buttons:
            menu.add_command(label=btn_txt, command=btn_cmd)
        # address entry, quick connect button
        quick_frame = Frame(main_frame, pady=3)
        quick_frame.pack(side=TOP, fill=X)
        quick_address = Entry(quick_frame)
        quick_address.pack(side=LEFT)
        quick_address.bind('<Return>', self.quick_connect)
        self.quick_address = quick_address
        Button(quick_frame, text="Quick connect", command=self.quick_connect).pack(side=LEFT)
        # statusbar
        self.statusbar = StatusBar(main_frame, side=BOTTOM)
        # message box, send button
        self.message_box = MessageBox(main_frame, side=BOTTOM, fill=X, submit_callback=self.send)
        # chat, userlist
        chat_users_frame = Frame(main_frame)
        chat_users_frame.pack(side=TOP, expand=YES, fill=BOTH)
        self.userlist = UserList(chat_users_frame, side=RIGHT, expand=NO, fill=Y, doubleclick_callback=self.insert_nick)
        self.chat = Chat(chat_users_frame, side=LEFT, expand=YES, fill=BOTH, doubleclick_callback=self.insert_nick)
        self.root.after(1000, self.userlist_loop)

    def mainloop(self):
        self.root.mainloop()

    def get_pass(self):
        pass_window = PassWindow(self.root)
        self.root.after(50)   # workaround - без этого иногда PassWindow блокируется
        pass_window.wait_window()
        return pass_window.password.get()

    def insert_nick(self, check_nick):
        if self.dc and check_nick != self.dc.nick and self.dc.userlist and check_nick in self.dc.userlist:
                if self.message_box.message_text.index(INSERT) == '1.0':   # если курсор стоит в начале поля ввода,
                    check_nick = check_nick + config.settings['chat_addr_sep'] + ' '   # то вставляем ник как обращение
                self.message_box.message_text.insert(INSERT, check_nick)
                self.message_box.message_text.focus_set()
                return True

    def connect(self):
        self.disconnect()
        self._reconnect = True if config.settings['reconnect'] and config.settings['reconnect_delay'] > 0 else False
        if self.dc_settings and (not self.dc or not self.dc.connecting):   # если ещё не подключались или не подключаемся в данный момент
            self.dc = slangdc.DCClient(**self.dc_settings)
            self.userlist.clear()
            self.chat_loop(self.dc)
            self.userlist_callback_id = self.root.after(100, self.userlist_loop)
            DCThread(self.dc, pass_callback=self.get_pass, onclose_callback=self.reconnect).start()

    def disconnect(self):
        self._reconnect = False
        if self.dc and self.dc.connected:
            self.dc.disconnect()
            self.dc = None
            self.statusbar.set('hubname', '')
            self.statusbar.set('hubtopic', '')
            self.statusbar.set('usercount', '')
            self.userlist.clear()
        self.cancel_reconnect_callback()
        if self.userlist_callback_id:
            self.root.after_cancel(self.userlist_callback_id)

    def reconnect(self):
        if self._reconnect:
            try:
                self.reconnect_callback_id = self.root.after(config.settings['reconnect_delay']*1000, self.connect)
            except RuntimeError:   # main thread is not in main loop при закрытии приложения
                pass

    def cancel_reconnect_callback(self):
        if self.reconnect_callback_id:
            self.root.after_cancel(self.reconnect_callback_id)
            self.reconnect_callback_id = None

    def quick_connect(self, event=None):
        address = self.quick_address.get().strip().rstrip('/').split('//')[-1]
        if address:
            self.quick_address.delete(0, END)
            self.quick_address.insert(0, address)
            self.dc_settings = config.make_dc_settings(address)
            self.connect()

    def bookmark_connect(self, bm_number):
        self.dc_settings = config.make_dc_settings_from_bm(bm_number)
        self.connect()

    def quit(self):
        if askyesno("Quit confirmation", "Really quit?"):
            self.disconnect()
            self.root.quit()

    def show_settings(self):
        try:
            self.settings_window.focus_set()
        except Exception:   # workaround - AttribureError, _tkinter.TclError
            self.settings_window = SettingsWindow(self.root)

    def send(self, message):
        if self.dc and self.dc.connected:
            if message.startswith('/pm '):
                nick, text = message[4:].split(' ', 1)
                self.dc.pm_send(nick, text)
            else:
                self.dc.chat_send(message)
            return True
        else:
            return False

    def userlist_loop(self):
        if self.dc and (self.dc.connecting or self.dc.connected):
            if self.dc.userlist:
                ### копировать надо бы с локом
                bots = self.dc.userlist.bots.copy()
                ops = self.dc.userlist.ops - bots
                users = (self.dc.userlist - ops - bots)
                self.userlist.update_list(ops, bots, users)
                self.statusbar.set('usercount', len(self.dc.userlist))
            self.userlist_callback_id = self.root.after(1000, self.userlist_loop)
        else:
            self.userlist.clear()
            self.statusbar.set('usercount', '')

    def chat_loop(self, dc):
        ''' небольшой трюк - ссылку на инстанс DCClient передаём не через
            атрибуты (self.dc), а через аргумент функции; после дисконнекта
            (self.dc = None) инстанс продолжит существовать, пока передаётся
            ссылка на него (т.е. пока не заберём все сообщения из очереди и
            не завершим chat_loop)
        '''
        message = dc.message_queue.mget()
        if message:
            if message['type'] == slangdc.MSGEND:
                return
            else:
                if message['type'] == slangdc.MSGCHAT:
                    message['text'] = message['text'].replace('\r', '')
                    nick_tag = 'user_nick'
                    if self.dc:
                        if message['nick'] == dc.nick:
                            nick_tag = 'own_nick'
                        else:
                            nick_role = self.check_user_role(message['nick'])
                            if nick_role:
                                nick_tag = nick_role + '_nick'
                    if not message['me']:
                        msg = ('text', "<", nick_tag, message['nick'], 'text', "> " + message['text'])
                    else:
                        msg = ('text', "* ", nick_tag, message['nick'], 'text', " " + message['text'])
                elif message['type'] == slangdc.MSGPM:
                    message['text'] = message['text'].replace('\r', '')
                    if 'sender' in message:   # если это входящее сообщение
                        pref = "PM from " + message['sender']
                    else:   # если исходящее сообщение
                        pref = "PM to " + message['recipient']
                    msg = ('info', pref)
                elif message['type'] == slangdc.MSGERR:
                    msg = ('error', "*** " + message['text'])
                elif message['type'] == slangdc.MSGINFO:
                    msg = ('info', "*** " + message['text'])
                    if message['text'].startswith('HubName: '):
                        self.statusbar.set('hubname', self.dc.hubname)
                    elif message['text'].startswith('HubTopic: '):
                        self.statusbar.set('hubtopic', self.dc.hubtopic)
                elif message['type'] == slangdc.MSGNICK:
                    if config.settings['show_joins'] and isinstance(message['nick'], str):
                        msg = ('info', "*** {0}s: {1}".format(message['state'], message['nick']))
                    else:
                        msg = None
                if msg:
                    timestamp = datetime.fromtimestamp(message['time']).strftime('[%H:%M:%S] ')
                    self.chat.add_message(('timestamp', timestamp) + msg)
        self.root.after(10, self.chat_loop, dc)

    def check_user_role(self, nick):
        if self.dc and self.dc.userlist:
            if nick in self.dc.userlist.bots:
                return 'bot'
            elif nick in self.dc.userlist.ops:
                return 'op'
            elif nick in self.dc.userlist:
                return 'user'
        return False


class Chat(Frame):

    max_lines = 500

    def __init__(self, parent, side, expand, fill, doubleclick_callback=None):
        Frame.__init__(self, parent)
        self.pack(side=side, expand=expand, fill=fill)
        font_family = 'Helvetica'
        font_size = 12
        font_normal = (font_family, font_size, 'normal')
        font_bold = (font_family, font_size, 'bold')
        tools_frame = Frame(self, height=30)
        tools_frame.pack_propagate(0)
        tools_frame.pack(side=BOTTOM, expand=NO, fill=BOTH)
        Button(tools_frame, text='Clear chat', command=self.clear).place(x=0, rely=0.5, anchor=W)
        self.autoscroll = BooleanVar()
        self.autoscroll.set(True)
        Checkbutton(tools_frame, text='Autoscroll', variable=self.autoscroll).place(x=100, rely=0.5, anchor=W)
        chat = Text(self, wrap=WORD)
        scroll = Scrollbar(self)
        scroll.config(command=chat.yview)
        scroll.pack(side=RIGHT, fill=Y)
        chat.config(yscrollcommand=scroll.set)
        chat.pack(side=LEFT, expand=YES, fill=BOTH)
        tags = (
            ('timestamp', font_normal, 'gray'),
            ('text', font_normal, 'black'),
            ('own_nick', font_bold, 'green'),
            ('user_nick', font_bold, 'black'),
            ('op_nick', font_bold, 'red'),
            ('bot_nick', font_bold, 'magenta'),
            ('error', font_normal, 'red'),
            ('info', font_normal, 'blue')
        )
        for tag, font, color in tags:
            chat.tag_config(tag, font=font, foreground=color)
        # http://stackoverflow.com/questions/9957810/how-do-you-modify-the-current-selection-length-in-a-tkinter-text-widget
        chat.bind('<Double-1>', lambda e: self.after(20, self.doubleclick))
        chat.bind('<Control-c>', self.text_copy)
        chat.bind('<Key>', lambda e: 'break')
        self.chat = chat
        self.empty = True
        self.doubleclick_callback = doubleclick_callback
        self.lock = threading.Lock()

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

    def add_message(self, msg_list):
        ''' msg_list - одно сообщение в виде списка/кортежа
            (tag1, text1, tag2, text2, ...)
        '''
        with self.lock:
            if self.empty:
                self.empty = False
            else:
                self.chat.insert(END, '\n', 'text')
            msg_list_iter = iter(msg_list)   # fuck tha itertools!
            for tag in msg_list_iter:
                text = next(msg_list_iter)
                self.chat.insert(END, text, tag)
            chat_lines = int(self.chat.index('end-1c').split('.')[0])
            if chat_lines > self.max_lines:
                del_to = str(chat_lines-self.max_lines+1) + '.0'
                self.chat.delete('1.0', del_to)
            if self.autoscroll.get():
                self.chat.see(END)

    def clear(self):
        with self.lock:
            self.chat.delete('1.0', END)
            self.empty = True

    def text_copy(self, event):
        if self.chat.tag_ranges(SEL):
            self.clipboard_clear()
            self.clipboard_append(self.chat.get('sel.first', 'sel.last'))
        return 'break'


class MessageBox(Frame):

    def __init__(self, parent, side, expand=NO, fill=X, submit_callback=None):
        Frame.__init__(self, parent)
        self.pack(side=side, expand=expand, fill=fill)
        Button(self, text="Send", command=self.submit).pack(side=RIGHT, fill=Y)
        message_text = Text(self, height=2, font = 'Helvetica')
        message_text.pack(side=LEFT, expand=YES, fill=X)
        # запускаем после небольшой задержки, чтобы наш биндинг отработал после системного (который вставляет \n)
        message_text.bind('<Return>', lambda e: self.submit())
        message_text.bind('<Shift-Return>', lambda e: self.submit(lf2cr=True))   # '\n' --> '\r'
        message_text.bind('<Control-Return>', lambda e: None)   # оверрайдим наш биндинг на Enter, передаём управление дальше системному (который вставит \n)
        self.message_text = message_text
        self.submit_callback = submit_callback

    def submit(self, lf2cr=False):   # lf2cr=True - преобразовать \n в \r
        message = self.message_text.get('1.0', 'end-1c')
        if message:
            if lf2cr: message = message.replace('\n', '\r')
            if self.submit_callback:
                sended = self.submit_callback(message)
                if sended:
                    self.message_text.delete('1.0', END)
        return 'break'   # отменяем системный биндинг


class StatusBar(Frame):

    def __init__(self, parent, side, expand=NO, fill=X):

        Frame.__init__(self, parent, height=24)
        self.pack(side=side, expand=expand, fill=fill)
        self._vars = {}
        labels = (
            ('Hub name', 0.4),
            ('Hub topic', 0.4),
            ('Usercount', 0.2)
        )
        relx=0
        for col, (label, width) in enumerate(labels):
            var = StringVar()
            Label(self, textvariable=var, anchor=W, padx=3, borderwidth=2, relief=GROOVE).place(relx=relx, rely=0.5, relwidth=width, anchor=W)
            relx += width
            var_name = label.replace(' ', '').lower()
            self._vars[var_name] = (var, label)
            self.set(var_name, '')

    def set(self, var, value):
        self._vars[var][0].set(self._vars[var][1] + ": " + str(value))


class UserList(Frame):

    def __init__(self, parent, side, expand, fill, doubleclick_callback=None):
        Frame.__init__(self, parent)
        self.pack(side=side, expand=expand, fill=fill)
        ul_frame = Frame(self)
        ul_frame.pack(side=TOP, expand=YES, fill=BOTH)
        font = ('Helvetica', 10, 'normal')
        userlist = Listbox(ul_frame, selectmode=SINGLE, activestyle=DOTBOX, width=25, font=font)
        scroll = Scrollbar(ul_frame)
        userlist.config(yscrollcommand=scroll.set)
        scroll.config(command=userlist.yview)
        userlist.pack(side=LEFT, expand=YES, fill=BOTH)
        scroll.pack(side=LEFT, fill=Y)
        userlist.bind('<Double-1>', self.doubleclick)
        self.userlist = userlist
        filter_frame = Frame(self, height=30)
        filter_frame.pack_propagate(0)
        filter_frame.pack(side=BOTTOM, expand=NO, fill=BOTH)
        self.filter_var = StringVar()
        filter_entry = Entry(filter_frame, textvariable=self.filter_var)
        filter_entry.place(relx=0.5, rely=0.5, relwidth=0.99, anchor=CENTER)
        self.colors = {
            'user': 'black',
            'op': 'red',
            'bot': 'magenta'
        }
        self.doubleclick_callback = doubleclick_callback
        self.clear()

    def add(self, index, user, role):
        self.userlist.insert(index, user)
        self.userlist.itemconfig(index, foreground=self.colors[role])

    def remove(self, index):
        self.userlist.delete(index)

    def clear(self):
        # очистка и (пере)инициализация
        self.prev_op = self.prev_bot = self.prev_user = None
        self.op_len = self.bot_len = self.user_len = 0
        self.userlist.delete(0, END)

    def update_list(self, *nicksets):
        ''' использование - update(ops, bots, users)
            ops, bots, users - множества
            users - множество _без_ опов и ботов
            не следует передавать множества, которые потом
            будут использоваться в вызывающем коде -
            метод хранит ссылки на них до следующегов вызова
        '''
        filter_ = self.filter_var.get().strip().lower()
        for ind, role in enumerate(('op', 'bot', 'user')):
            if filter_:
                nickset = {nick for nick in nicksets[ind] if filter_ in nick.lower()}
            else:
                nickset = nicksets[ind]
            self._update_role(nickset, role)

    def _update_role(self, nickset, role):

        def _sorted(set_, reverse=False):
            return sorted(sorted(set_, reverse=reverse), key=str.lower, reverse=reverse)

        prev = getattr(self, 'prev_'+role)
        if prev:
            parted = prev - nickset
            joined = nickset - prev
            if parted:
                prev_sorted = _sorted(prev)
                for nick in _sorted(parted, reverse=True):
                    index = prev_sorted.index(nick) + self._offset(role)
                    self.remove(index)
            if joined:
                nickset_sorted = _sorted(nickset)
                for nick in _sorted(joined):
                    index = nickset_sorted.index(nick) + self._offset(role)
                    self.add(index, nick, role)
        else:
            nickset_sorted = _sorted(nickset)
            for index, nick in enumerate(nickset_sorted, self._offset(role)):
                self.add(index, nick, role)
        setattr(self, 'prev_'+role, nickset)   # сохраняем для следующего вызова
        setattr(self, role+'_len', len(nickset))

    def _offset(self, role):
        if role == 'op':
            return 0
        elif role == 'bot':
            return self.op_len
        else:
            return self.op_len + self.bot_len

    def doubleclick(self, event=None):
        if self.doubleclick_callback:
            nick = self.userlist.get(ACTIVE)
            self.doubleclick_callback(nick)


class SettingsWindow(Toplevel):

    def __init__(self, root=None):
        Toplevel.__init__(self, root)
        self.title("settings")
        self.resizable(width=FALSE, height=FALSE)
        self.protocol('WM_DELETE_WINDOW', self.close)
        # (field_name, field_type, field_text)
        fields = (
            ('nick', 'str', 'Nick'),
            ('desc', 'str', 'Description'),
            ('email', 'str', 'E-mail'),
            ('share', 'int', 'Share'),
            ('slots', 'int', 'Slots'),
            ('encoding', 'str', 'Encoding'),
            ('timeout', 'int', 'Receive timeout'),
            ('reconnect', 'bool', 'Reconnect'),
            ('reconnect_delay', 'int', 'Reconnect delay'),
            ('show_joins', 'bool', 'Show joins/parts in chat'),
            ('chat_addr_sep', 'str', 'Chat address separator')
        )
        self.entry_vars = {}
        grid_frame = Frame(self)
        grid_frame.pack(padx=5, pady=5)
        for row, (field_name, field_type, field_text) in enumerate(fields):
            Label(grid_frame, width=20, text=field_text, anchor=W).grid(row=row, column=0)
            if field_type == 'bool':
                var = BooleanVar()
                Checkbutton(grid_frame, variable=var).grid(row=row, column=1, sticky=W)
            else:
                var = StringVar()
                Entry(grid_frame, width=20, textvariable=var).grid(row=row, column=1)
            var.set(config.settings[field_name])
            self.entry_vars[field_name] = (var, field_type)
        Button(self, text="Cancel", width=8, command=self.close).pack(side=RIGHT, padx=5, pady=3)
        Button(self, text="Save", width=8, command=self.save).pack(side=RIGHT)

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
        config.save_settings(new_settings)
        self.close()

    def close(self):
        self.destroy()


class PassWindow(Toplevel):

    def __init__(self, root=None):
        Toplevel.__init__(self, root)
        self.title("Password")
        self.resizable(width=FALSE, height=FALSE)
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.transient()
        self.grab_set()
        pass_frame = Frame(self, padx=5, pady=5)
        pass_frame.pack(expand=YES, fill=BOTH)
        Label(pass_frame, text='Password', anchor=W).pack(side=LEFT)
        self.password = StringVar()
        pass_entry = Entry(pass_frame, show='*', textvariable=self.password)
        pass_entry.pack(side=LEFT, expand=YES, fill=X, padx=5)
        pass_entry.focus_set()
        pass_entry.bind('<Return>', self.confirm)
        Button(pass_frame, text="OK", command=self.confirm).pack(side=RIGHT)

    def close(self):
        self.password.set('')
        self.destroy()

    def confirm(self, event=None):
        if self.password.get():
            self.destroy()


class DCThread(threading.Thread):

    def __init__(self, dc, pass_callback=None, onclose_callback=None):
        self.dc = dc
        self.pass_callback=pass_callback
        self.onclose_callback=onclose_callback
        threading.Thread.__init__(self, name=self.__class__.__name__)

    def run(self):
        self.dc.connect(userlist=True, msgnick=True, pass_callback=self.pass_callback)
        while self.dc.connected:
            self.dc.receive(raise_exc=False)
        if self.onclose_callback:
            self.onclose_callback()


config = conf.Config()
config.load_settings()
config.load_bookmarks()
Gui().mainloop()
