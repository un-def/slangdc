# -*-coding: UTF-8 -*-
import webbrowser
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
        self.chat_loop_running = False
        self.userlist_loop_running = False
        self.connect_loop_running = False
        self.do_connect = False
        self.connected = False
        self.tabs = {}
        self.pass_event = PassEvent()   # эвент для коммуникации между тредами (получения пароля)
        root = Tk()
        root.title("slangdc.Tk")
        root.protocol('WM_DELETE_WINDOW', root.iconify)
        root.geometry('800x600+10+10')
        self.root = root
        main_frame = Frame(root, padx=5, pady=5)
        main_frame.pack(expand=YES, fill=BOTH)
        # меню
        menu = AppMenu(root)
        menu.add_bookmarks(config.bookmarks, self.bookmark_connect)
        buttons = (
            ('Connect', self.connect),
            ('Disconnect', self.disconnect),
            ('Settings', self.show_settings),
            ('Quit', self.quit)
        )
        menu.add_buttons(buttons)
        self.menu = menu
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
        # tabbar
        tabbar = TabBar(main_frame, side=TOP, height=25, select_callback=lambda n: None, close_callback=lambda n: None)
        tabbar.add_tab(name='hub', label='…', state=0)
        self.tabbar = tabbar
        self.tabs['hub'] = True
        self.tabbar.select_tab('hub')
        # chat, userlist
        chat_users_frame = Frame(main_frame)
        chat_users_frame.pack(side=TOP, expand=YES, fill=BOTH)
        self.userlist = UserList(chat_users_frame, side=RIGHT, expand=NO, fill=Y, doubleclick_callback=self.insert_nick)
        self.chat = Chat(chat_users_frame, side=LEFT, expand=YES, fill=BOTH, nick_callback=self.insert_nick)

    def mainloop(self):
        self.root.mainloop()

    def quit(self):
        if askyesno("Quit confirmation", "Really quit?"):
            self.disconnect()
            self.root.quit()

    def show_settings(self):
        try:
            self.settings_window.focus_set()
        except Exception:   # workaround - AttribureError, _tkinter.TclError
            self.settings_window = SettingsWindow(self.root)

    def insert_nick(self, check_nick):
        if self.dc and check_nick != self.dc.nick and self.dc.userlist and check_nick in self.dc.userlist:
                if self.message_box.message_text.index(INSERT) == '1.0':   # если курсор стоит в начале поля ввода,
                    check_nick = check_nick + config.settings['chat_addr_sep'] + ' '   # то вставляем ник как обращение
                self.message_box.message_text.insert(INSERT, check_nick)
                self.message_box.message_text.focus_set()
                return True

    def format_message(self, nick, text, me):
        text = text.replace('\r', '')
        nick_tag = 'user_nick'
        if self.dc:
            if nick == self.dc.nick:
                nick_tag = 'own_nick'
            else:
                nick_role = self.check_user_role(nick)
                if nick_role:
                    nick_tag = nick_role + '_nick'
        if not me:
            msg = ['text', "<", nick_tag, nick, 'text', "> "]
        else:
            msg = ['text', "* ", nick_tag, nick, 'text', " "]
        tags = ('text', 'link')
        cur_tag = 0
        text_splitted = re.split('((?:http|ftp)s?://[^\s]+)', text)
        for part in text_splitted:
            if part: msg.extend((tags[cur_tag], part))
            cur_tag = 1 - cur_tag
        return msg

    def check_user_role(self, nick):
        if self.dc and self.dc.userlist:
            if nick in self.dc.userlist.bots:
                return 'bot'
            elif nick in self.dc.userlist.ops:
                return 'op'
            elif nick in self.dc.userlist:
                return 'user'
        return False

    def connect(self):
        if not self.connect_loop_running:
            if self.dc and (self.dc.connected or self.dc.connecting):
                self.disconnect()
                self.root.after(200, self.connect)
            elif self.dc_settings:
                self.tabbar.set_tab_label('hub', self.dc_settings['address'])
                self.do_connect = True
                self.connect_loop_running = True
                self.connect_loop()

    def disconnect(self):
        self.do_connect = False
        self.pass_event.password = None   # сбросим пароль, введённый вручную
        if self.dc and self.dc.connected:
            self.dc.disconnect()

    def quick_connect(self, event=None):
        if not self.connect_loop_running:
            address = self.quick_address.get().strip().rstrip('/').split('//')[-1]
            if address:
                self.quick_address.delete(0, END)
                self.quick_address.insert(0, address)
                self.dc_settings = config.make_dc_settings(address)
                self.connect()

    def bookmark_connect(self, bm_number):
        if not self.connect_loop_running:
            self.dc_settings = config.make_dc_settings_from_bm(bm_number)
            self.connect()

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

    def check_loop(self):
        if not (self.dc.connecting or self.dc.connected):
            self.connected = False
            self.userlist.clear()
            self.statusbar.clear()
            for tab in self.tabs:
                self.tabbar.update_tab(tab, state=0)
            if self.do_connect and config.settings['reconnect'] and config.settings['reconnect_delay'] > 0:
                self.connect_loop_running = True
                self.root.after(config.settings['reconnect_delay']*1000, self.connect_loop)
        else:
            if not self.connected and self.dc.connected:
                self.connected = True
                self.tabbar.update_tab('hub', state=1)
            if not self.pass_event.is_set():   # если сброшен, значит, DC-тред ждёт пароль
                pass_window = PassWindow(self.root)
                pass_window.wait_window()
                self.pass_event.password = pass_window.password.get()   # передамим в DC-тред через атрибут эвента
                self.pass_event.set()   # устанавливаем обратно в True (информируем DC-тред, что пароль получен)
            self.root.after(100, self.check_loop)

    def connect_loop(self):
        if self.chat_loop_running or self.userlist_loop_running:
            self.root.after(100, self.connect_loop)
        else:
            if self.do_connect:
                self.dc = slangdc.DCClient(**self.dc_settings)
                DCThread(self.dc, self.pass_event).start()
                self.chat_loop_running = True
                self.chat_userlist_running = True
                self.root.after(100, self.chat_loop)
                self.root.after(100, self.userlist_loop)
                self.root.after(100, self.check_loop)
            self.root.after(2000, self.reset_connect_loop_flag)   # 2 секунды игнорируем повторные попытки подключиться

    def reset_connect_loop_flag(self):   # lambda - это вам не function() {...}
        self.connect_loop_running = False   # поэтому тривиальное действие приходится выносить в отдельную функцию

    def chat_loop(self):
        message = self.dc.message_queue.mget()
        if message:
            if message['type'] == slangdc.MSGEND:
                self.chat_loop_running = False
                return
            else:
                if message['type'] == slangdc.MSGCHAT:
                    msg = self.format_message(message['nick'], message['text'], message['me'])
                elif message['type'] == slangdc.MSGPM:
                    if 'sender' in message:   # входящее сообщение
                        nick = message['nick'] if message['nick'] else message['sender']
                        msg = ['info', "*** PM from {}:".format(message['sender']), 'text', " "]
                        if not 'pm|' + message['sender'] in self.tabs:
                            self.tabbar.add_tab('pm|' + message['sender'], label=message['sender'], state=1)
                            self.tabs['pm|' + message['sender']] = True
                    else:   # исходящее сообщение
                        nick = self.dc.nick
                        msg = ['info', "*** PM to {}:".format(message['recipient']), 'text', " "]
                    msg.extend(self.format_message(nick, message['text'], message['me']))
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
                    if isinstance(message['nick'], str):
                        nicks = (message['nick'],)
                    else:
                        nicks = message['nick']
                    for nick in nicks:
                        if 'pm|'+nick in self.tabs:
                            state = 1 if message['state'] == 'join' else 0
                            self.tabbar.update_tab('pm|'+nick, state=state)
                if msg:
                    timestamp = datetime.fromtimestamp(message['time']).strftime('[%H:%M:%S]')
                    self.chat.add_message('timestamp', timestamp, 'text', " ", *msg)
        self.root.after(10, self.chat_loop)

    def userlist_loop(self):
        if self.dc.connecting or self.dc.connected:
            if self.dc.userlist:
                ### копировать надо бы с локом
                bots = self.dc.userlist.bots.copy()
                ops = self.dc.userlist.ops - bots
                users = (self.dc.userlist - ops - bots)
                count_all = sum(map(len, (bots, ops, users)))   # не len(self.dc.userlist), т.к. он может измениться в процессе
                self.userlist.update_list(ops, bots, users)
                count_filter = self.userlist.len()
                if count_filter != count_all:
                    count = "{0:d}/{1:d}".format(count_filter, count_all)
                else:
                    count = str(count_all)
                self.statusbar.set('usercount', count)
            self.root.after(1000, self.userlist_loop)
        else:
            self.userlist_loop_running = False


class AppMenu(Menu):

    def __init__(self, root):
        super().__init__(root, borderwidth=0)
        root.config(menu=self)

    def add_bookmarks(self, bookmarks, action):
        menu_bookmarks = Menu(self, tearoff=False)
        if bookmarks:
            for bm_number, bookmark in enumerate(bookmarks):
                menu_bookmarks.add_command(label=bookmark['name'], command=lambda n=bm_number: action(n))
        else:
            menu_bookmarks.add_command(label="Empty", state=DISABLED)
        self.add_cascade(label="Bookmarks", menu=menu_bookmarks)

    def add_buttons(self, buttons):
        for btn_txt, btn_cmd in buttons:
            self.add_command(label=btn_txt, command=btn_cmd)


class TabBar(Frame):

    tab_max_width = 0.2
    color_on = '#99FF99'
    color_off = '#FF9999'
    color_sel = '#9999FF'
    font_unsel = ('Helvetica', 9, 'normal')
    font_sel = ('Helvetica', 9, 'bold')

    def __init__(self, parent, side, select_callback, close_callback, height=30):
        super().__init__(parent, height=height)
        self.select_callback = select_callback
        self.close_callback = close_callback
        self.pack(side=side, expand=NO, fill=X)
        self.tabs = []
        self.selected = None   # name выбранной вкладки

    def calculate_width(self):
        if len(self.tabs) > 0:
            width = 1 / len(self.tabs)
            if width > self.tab_max_width: width = self.tab_max_width
            return width
        else:
            return False

    def tab_index(self, name):
        for index, tab in enumerate(self.tabs):
            if tab['name'] == name: return index
        return -1

    def add_tab(self, name, label, state=0):
        tab = {'name': name}
        bg = self.color_on if state else self.color_off
        button = Frame(self, bg=bg, bd=1, relief=RAISED, padx=3)
        label = Label(button, bg=bg, text=label, font=self.font_unsel, anchor=NW)
        close_ = Label(button, font=('Helvetica', 5, 'bold'), bg='red', fg='white', text=' X ')
        close_.pack(side=RIGHT)
        label.pack(side=LEFT, expand=YES, fill=BOTH)
        close_.bind('<Button-1>', lambda e: self.close_tab(name))
        label.bind('<Button-1>', lambda e: self.select_tab(name))
        tab['button'] = button
        tab['label'] = label
        tab['state'] = state
        self.tabs.append(tab)
        self.draw_tabs()

    def close_tab(self, name):
        index = self.tab_index(name)
        if index == -1: return False
        tab = self.tabs.pop(index)
        tab['button'].place_forget()
        tab['button'].destroy()
        self.close_callback(name)
        self.draw_tabs()
        if self.selected == name:   # если закрываем выбранную вкладку, выберем первую
            if self.tabs:
                self.selected = self.tabs[0]['name']
                self.select_tab(self.selected)
            else:
                self.selected = None

    def draw_tabs(self):
        width = self.calculate_width()
        if width:
            relx = 0
            for tab in self.tabs:
                relh = 1 if tab['name'] == self.selected else 0.8
                tab['button'].place(relx=relx, rely=1, relheight=relh, relwidth=width, anchor='sw')
                relx += width

    def select_tab(self, name):
        index = self.tab_index(name)
        if index == -1: return False
        if self.selected:
            self.tabs[self.tab_index(self.selected)]['label'].config(font=self.font_unsel)
        self.selected = name
        self.tabs[index]['label'].config(font=self.font_sel)
        self.draw_tabs()
        self.select_callback(name)

    def set_tab_label(self, name, label):
        index = self.tab_index(name)
        if index == -1: return False
        self.tabs[index]['label'].config(text=label)

    def update_tab(self, name, state):
        index = self.tab_index(name)
        if index == -1: return False
        self.tabs[index]['state'] = int(state)
        bg = self.color_on if state else self.color_off
        self.tabs[index]['button'].config(bg=bg)
        self.tabs[index]['label'].config(bg=bg)


class Chat(Frame):

    max_lines = 500

    def __init__(self, parent, side, expand, fill, nick_callback):
        Frame.__init__(self, parent)
        self.pack(side=side, expand=expand, fill=fill)
        font_family = 'Helvetica'
        font_size = 12
        font_normal = (font_family, font_size, 'normal')
        font_bold = (font_family, font_size, 'bold')
        font_underline = (font_family, font_size, 'normal underline')
        tools_frame = Frame(self, height=30)
        tools_frame.pack_propagate(0)
        tools_frame.pack(side=BOTTOM, expand=NO, fill=BOTH)
        Button(tools_frame, text='Clear chat', command=self.clear).place(x=0, rely=0.5, anchor=W)
        self.autoscroll = BooleanVar()
        self.autoscroll.set(True)
        Checkbutton(tools_frame, text='Autoscroll', variable=self.autoscroll).place(x=100, rely=0.5, anchor=W)
        chat = Text(self, wrap=WORD, cursor='xterm')
        scroll = Scrollbar(self)
        scroll.config(command=chat.yview)
        scroll.pack(side=RIGHT, fill=Y)
        chat.config(yscrollcommand=scroll.set)
        chat.pack(side=LEFT, expand=YES, fill=BOTH)
        tags_styles = (
            ('timestamp', font_normal, 'gray'),
            ('text', font_normal, 'black'),
            ('link', font_underline, 'blue'),
            ('own_nick', font_bold, 'green'),
            ('user_nick', font_bold, 'black'),
            ('op_nick', font_bold, 'red'),
            ('bot_nick', font_bold, 'magenta'),
            ('error', font_normal, 'red'),
            ('info', font_normal, 'blue')
        )
        tags_bindings = (
            ('text', ('<Button-3>', self.extract_nick)),
            ('link',    ('<Button-1>', self.link_click),
                        ('<Enter>', self.link_enter),
                        ('<Leave>', self.link_leave)
            ),
            ('user_nick', ('<Button-3>', self.nick_click)),
            ('op_nick', ('<Button-3>', self.nick_click)),
            ('bot_nick', ('<Button-3>', self.nick_click)),
        )
        for tag, font, color in tags_styles:
            chat.tag_config(tag, font=font, foreground=color)
        for tag, *bindings in tags_bindings:
            for bind in bindings:
                chat.tag_bind(tag, bind[0], lambda e, c=bind[1], t=tag: c(t, e))
        chat.bind('<Control-c>', self.text_copy)
        chat.bind('<Control-C>', self.text_copy)
        chat.bind('<Key>', self.nav_keys)
        self.chat = chat
        self.empty = True
        self.nick_callback = nick_callback
        self.lock = threading.Lock()

    def _get_tag_range(self, tag, event):
        index = self.chat.index('@{},{}'.format(event.x, event.y))
        tag_range = self.chat.tag_prevrange(tag, index)
        if not tag_range or self.chat.compare(tag_range[1], '<', index):
            tag_range = self.chat.tag_nextrange(tag, index)
        return (index, tag_range)

    def _get_tag_text(self, tag, event):
        _, tag_range = self._get_tag_range(tag, event)
        return self.chat.get(*tag_range)

    def _split_index(self, index):
        return tuple(map(int, index.split('.')))

    def extract_nick(self, tag, event):
        # пытается извлечь из текста под курсором ник
        index, tag_range = self._get_tag_range(tag, event)
        tag_text = self.chat.get(*tag_range)
        begin_line, begin_col = self._split_index(tag_range[0])
        index_line, index_col = self._split_index(index)
        line_text = tag_text.splitlines()[index_line-begin_line]
        if index_line == begin_line:
            index_col = index_col - begin_col
        if index_col < len(line_text):
            around = re.search('^[^\s\<\>\$\|]+', line_text[index_col:])
            if around:
                nick = around.group(0)
                if index_col > 0:
                    around = re.search('[^\s\<\>\$\|]+$', line_text[:index_col])
                    if around:
                        nick = around.group(0) + nick
                # '.' не отсекаем, т.к. ник может заканчиваться на неё (может и на ',', но гораздо реже)
                if nick[-1] in ':,': nick = nick[:-1]
                if len(nick) > 2:   # вряд ли распространены ники короче 3 символов
                    self.nick_callback(nick)

    def nick_click(self, tag, event):
        nick = self._get_tag_text(tag, event)
        self.nick_callback(nick)

    def link_click(self, tag, event):
        link = self._get_tag_text(tag, event)
        webbrowser.open(link)

    def link_enter(self, tag, event):
        self.chat.config(cursor='hand2')

    def link_leave(self, tag, event):
        self.chat.config(cursor='xterm')

    def add_message(self, *msg_list):
        ''' add_message(tag1, text1, tag2, text2, ...)
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

    def nav_keys(self, event):
        if not event.keysym in ('Home', 'End', 'Prior', 'Next', 'Up', 'Down', 'Left', 'Right'):
            return 'break'


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

    def len(self):
        return sum((self.op_len, self.bot_len, self.user_len))

    def add(self, index, user, role):
        self.userlist.insert(index, " " + user)
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
            nick = self.userlist.get(ACTIVE)[1:]
            self.doubleclick_callback(nick)


class MessageBox(Frame):

    def __init__(self, parent, side, expand=NO, fill=X, submit_callback=None):
        Frame.__init__(self, parent)
        self.pack(side=side, expand=expand, fill=fill)
        Button(self, text="Send", command=self.submit).pack(side=RIGHT, fill=Y)
        message_text = Text(self, height=2, font = 'Helvetica', undo=1)
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

    def clear(self):
        for var_name in self._vars:
            self.set(var_name, '')


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


class PassEvent(threading.Event):
    ''' по умолчанию True, сбрасывается, когда DC-тред ждёт пароль,
        устанавливается обратно, когда основной тред получил пароль
        хранит пароль в атрибуте password
    '''
    def __init__(self):
        super().__init__()
        self.set()
        self.password = None


class DCThread(threading.Thread):

    def __init__(self, dc, pass_event):
        self.dc = dc
        self.pass_event = pass_event
        threading.Thread.__init__(self, name=self.__class__.__name__)

    def run(self):
        self.dc.connect(userlist=True, msgnick=True, pass_callback=self.pass_callback)
        while self.dc.connected:
            self.dc.receive(raise_exc=False)

    def pass_callback(self):
        ''' однажды введённый пароль храним в атрибуте эвента, пока не будет
            нажата кнопка Disconnect или инициировано новое подключение через
            закладки или Quick connect (тоже вызывают disconnect(), который
            сбрасывает pass_event.password в None)
        '''
        if not self.pass_event.password:
            self.pass_event.clear()   # сбрасываем эвент (False) (по умолчанию было True)
            self.pass_event.wait()   # ждём, пока в главном потоке выставят обратно в True (когда будет получен пароль)
        return self.pass_event.password


config = conf.Config()
config.load_settings()
config.load_bookmarks()
Gui().mainloop()
