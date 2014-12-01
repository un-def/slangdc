# -*-coding: UTF-8 -*-
import webbrowser
import urllib.parse
import re
import time
import threading
from datetime import datetime
from tkinter import *
from tkinter.messagebox import askyesno
import slangdc
import conf


def recursive_destroy(widget):
    for child in widget.winfo_children():
        recursive_destroy(child)
    widget.destroy()


class Gui:

    def __init__(self):
        root = Tk()
        root.title("slangdc.Tk")
        root.protocol('WM_DELETE_WINDOW', root.iconify)
        root.geometry('800x600+10+10')
        self.root = root
        main_frame = Frame(root, padx=5, pady=5)
        main_frame.pack(expand=YES, fill=BOTH)
        # menu
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
        # tabbar, tab
        self.tabbar = TabBar(main_frame, side=TOP, height=25, select_callback=self.tab_select_cb, close_callback=self.tab_close_cb)
        self.tab_frame = Frame(main_frame)
        self.tab_frame.pack(side=TOP, expand=YES, fill=BOTH)
        #
        self.hub_tabs = {}      # {имя_хаб_таба: инстанс, …}
        self.pm_tabs = {}       # {имя_хаб_таба: {имя_PM_таба: инстанс, …}, …}
        self.current_tab = {'type_': None, 'name': None}
        self.root.after(1000, self.statusbar_update)

    ### gui methods ###

    def mainloop(self):
        self.root.mainloop()

    def statusbar_update(self, loop=True):
        current_tab = self.tab_instance(parent=True, **self.current_tab)
        if current_tab:
            for var, value in current_tab.statusbar.items():
                self.statusbar.set(var, value)
        else:
            self.statusbar.clear()
        if loop: self.root.after(1000, self.statusbar_update)

    def connect(self, dc_settings=None):
        ''' без аргументов - (пере)подключается в выбранной вкладке (всегда);
            переданы dc_settings - открывает новую вкладку и коннектится или
            активирует вкладку, если уже открыта (в этом случае не реконнектит)
        '''
        if dc_settings:
            name = dc_settings['address']
            if not name in self.hub_tabs:
                self.tab_add_hub(name, dc_settings)
                self.tab_connect(name)
            self.tab_select('hub', name)
        elif self.current_tab['type_'] == 'hub':
            self.tab_connect(self.current_tab['name'])

    def disconnect(self):
        if self.current_tab['type_'] == 'hub':
            self.tab_disconnect(self.current_tab['name'])

    def quick_connect(self, event=None):
        address = config.trim_address(self.quick_address.get())
        if address:
            self.quick_address.delete(0, END)
            self.quick_address.insert(0, address)
            dc_settings = config.make_dc_settings(address)
            self.connect(dc_settings)

    def bookmark_connect(self, bm_number):
        dc_settings = config.make_dc_settings_from_bm(bm_number)
        if dc_settings: self.connect(dc_settings)

    def show_settings(self):
        try:
            self.settings_window.focus_set()
        except Exception:   # workaround - AttribureError, _tkinter.TclError
            self.settings_window = SettingsWindow()

    def quit(self):
        if askyesno("Quit confirmation", "Really quit?"):
            for tab in self.hub_tabs:
                self.tab_disconnect(tab)
            self.root.quit()

    ### tabs methods ###

    def tab_add_hub(self, name, dc_settings):
        tab = HubTab(   name=name,
                        parent_widget=self.tab_frame,
                        dc_settings=dc_settings,
                        tab_update_callback=self.tab_update,
                        tab_pm_callback=self.tab_pm_get_cb)
        self.tabbar.add_tab(name=self.make_tb_tab_name('hub', name))
        self.hub_tabs[name] = tab
        return tab

    def tab_add_pm(self, name, state, pm_send_callback):
        # name - (имя_хаб_таба, имя_PM_таба)
        tab = PMTab(    name=name,
                        state=state,
                        parent_widget=self.tab_frame,
                        tab_update_callback=self.tab_update,
                        pm_send_callback=self.tab_pm_send_cb)
        self.tabbar.add_tab(name=self.make_tb_tab_name('pm', name))
        if not name[0] in self.pm_tabs:
            self.pm_tabs[name[0]] = {}
        self.pm_tabs[name[0]][name[1]] = tab
        return tab

    def tab_select(self, type_, name):
        # через коллбэк таббара вызывает tab_select_cb
        self.tabbar.select_tab(self.make_tb_tab_name(type_, name))

    def tab_update(self, type_, name):
        if type_ == 'hub':
            label = name
        elif type_ == 'pm':
            label = "PM: " + name[1]
        tab = self.tab_instance(type_, name)
        state = tab.state
        label = label if tab.unread == 0 else "({}) {}".format(tab.unread, label)
        self.tabbar.update_tab(self.make_tb_tab_name(type_, name), label, state)

    def tab_connect(self, name):
        # только для хаб-табов
        self.hub_tabs[name].connect()

    def tab_disconnect(self, name):
        # только для хаб-табов
        self.hub_tabs[name].disconnect()

    def tab_instance(self, type_, name, parent=False):
        ''' возвращает ссылку на экземпляр таба (по его типу и имени)
            parent=True (для PM-табов) - вернуть ссылку не на PM таб,
            а на родительский (хаб) таб
        '''
        try:
            if type_ == 'hub':
                return self.hub_tabs[name]
            elif type_ == 'pm':
                if parent:
                    return self.hub_tabs[name[0]]
                else:
                    return self.pm_tabs[name[0]][name[1]]
        except KeyError:
            return None

    def make_tb_tab_name(self, type_, name):
        if type_ == 'hub':
            tb_tab_name = 'hub|' + name
        elif type_ == 'pm':
            tb_tab_name = '|'.join(('pm', name[0], name[1]))
        return tb_tab_name

    def split_tb_tab_name(self, tb_tab_name):
        name_split = tb_tab_name.split('|')
        type_ = name_split[0]
        if type_ == 'hub':
            name = name_split[1]
        elif type_ == 'pm':
            name = (name_split[1], name_split[2])
        return (type_, name)

    ### callbacks ###

    def tab_select_cb(self, tb_tab_name):
        # коллбэк для инстанса TabBar
        type_, name = self.split_tb_tab_name(tb_tab_name)
        current_tab = self.tab_instance(**self.current_tab)
        if current_tab:
            current_tab.hide()
        self.tab_instance(type_, name).show()
        self.current_tab['type_'] = type_
        self.current_tab['name'] = name
        self.statusbar_update(loop=False)

    def tab_close_cb(self, tb_tab_name):
        # коллбэк для инстанса TabBar
        type_, name = self.split_tb_tab_name(tb_tab_name)
        tab = self.tab_instance(type_, name)
        tab.close()
        if type_ == 'hub':
            del self.hub_tabs[name]
        elif type_ == 'pm':
            del self.pm_tabs[name[0]][name[1]]

    def tab_pm_get_cb(self, name=None, add_new=False, select=False):
        ''' коллбэк для хаб-таба - возвращает ссылку на объект PM-таба или
            все дочерние PM-табы в виде словаря
            name=(имя_хаб_таба, имя_PM_таба) - вернуть ссылку на один таб
            name=имя_хаб_таба - вернуть ссылку на словарь всех PM-табов
            {имя_PM_таба: инстанс, …}
            если PM-таб(ы) не существует(-ют), возвращает None
            если add_new=True и name=(имя_хаб_таба, имя_PM_таба), то при
            отсутствии PM-таба он будет создан
            select=True - переключиться на PM-таб
        '''
        if isinstance(name, str):
            return self.pm_tabs.get(name)
        else:
            tab = self.tab_instance('pm', name)
            if not tab and add_new:
                tab = self.tab_add_pm(name, 1, 'pm_send_callback')
            if select:
                self.tab_select('pm', name)
            return tab

    def tab_pm_send_cb(self, name, message):
        ''' мост между PM и хаб табами для отправки личных
            сообщений: PM таб вызывает этот коллбэк, передавая своё
            имя - кортеж (имя_хаб_таба, имя_PM_таба), коллбэк
            отыскивает родительский хаб таб в self.hub_tabs
            и вызывает его метод pm_send(recipient, message)
            если хаб таба нет (закрыт, а вкладка с личкой осталась),
            возвращает False, иначе возвращает то, что возвращает
            pm_send (True или False)
        '''
        hub_tab = self.tab_instance(type_='pm', name=name, parent=True)
        if not hub_tab:
            return False
        else:
            return hub_tab.pm_send(name[1], message)
        pm_send(self, recipient, message)


class Tab:

    def __init__(self, name, parent_widget):
        self.name = name
        self.parent_widget = parent_widget
        self.visible = False
        self.unread = 0
        self.frame = Frame(parent_widget)

    def update(self):
        self.tab_update_callback(type_=self.type_, name=self.name)

    def set_state(self, state):
        self.state = state
        self.update()

    def show(self):
        self.visible = True
        self.unread = 0
        self.update()
        self.frame.pack(expand=YES, fill=BOTH)

    def hide(self):
        self.visible = False
        self.frame.pack_forget()


class HubTab(Tab):

    def __init__(self, name, parent_widget, dc_settings, tab_update_callback, tab_pm_callback):
        super().__init__(name, parent_widget)
        self.type_ = 'hub'
        self.state = 0
        self.dc = None
        self.dc_settings = dc_settings
        self.tab_update_callback = tab_update_callback
        self.tab_pm_callback = tab_pm_callback
        self.queue_loop_running = False
        self.userlist_loop_running = False
        self.connect_loop_running = False
        self.do_connect = False
        self.statusbar_clear()
        self.pass_event = PassEvent()   # эвент для коммуникации между тредами (получения пароля)
        self.message_box = MessageBox(self.frame, side=BOTTOM, expand=NO, fill=X, submit_callback=self.chat_send)
        chat_ul_frame = Frame(self.frame)
        chat_ul_frame.pack(side=TOP, expand=YES, fill=BOTH)
        self.userlist = UserList(chat_ul_frame, side=RIGHT, expand=NO, fill=Y, nick_callback=self.nick_action)
        self.chat = Chat(chat_ul_frame, side=LEFT, expand=YES, fill=BOTH, nick_callback=self.nick_action)

    def close(self):
        self.disconnect()
        self.hide()
        self.set_state_pm_tabs(0)
        recursive_destroy(self.frame)

    def set_state(self, state):
        self.state = state
        self.update()

    def set_state_pm_tabs(self, state, nicks=None):
        ''' обновляет статус всех (nicks=None) PM табов или только тех,
            ники которых присутствуют в nicks
        '''
        pm_tabs = self.tab_pm_callback(name=self.name)   # получаем словарь всех дочерних табов (или None)
        if pm_tabs:
            timestamp = self.timestamp()
            for tab_name, tab_instance in pm_tabs.items():
                if nicks is None or tab_name in nicks:
                    tab_instance.set_state(state, timestamp)

    def connect(self):
        if not self.connect_loop_running:
            if self.dc and (self.dc.connected or self.dc.connecting):
                self.disconnect()
                self.frame.after(200, self.connect)
            else:
                self.do_connect = True
                self.connect_loop_running = True
                self.connect_loop()

    def disconnect(self):
        self.do_connect = False
        self.pass_event.password = None   # сбросим пароль, введённый вручную
        if self.dc and self.dc.connected:
            self.dc.disconnect()

    def statusbar_clear(self):
        self.statusbar = {
            'hubname': '',
            'hubtopic': '',
            'usercount': ''
        }

    def nick_action(self, nick, action):
        if self.dc and nick != self.dc.nick and self.dc.userlist and nick in self.dc.userlist:
            if action == 'insert':   # вставить ник в чат
                if self.message_box.message_text.index(INSERT) == '1.0':   # если курсор стоит в начале поля ввода,
                    nick = nick + config.settings['chat_addr_sep'] + ' '   # то вставляем ник как обращение
                self.message_box.message_text.insert(INSERT, nick)
                self.message_box.message_text.focus_set()
            elif action == 'pm':
                self.tab_pm_callback(name=(self.name, nick), add_new=True, select=True)
            return True

    def timestamp(self, unix_time=None):
        if not unix_time: unix_time = time.time()
        return datetime.fromtimestamp(unix_time).strftime('[%H:%M:%S]')

    def format_message(self, nick, text, me):
        if config.settings['detect_utf8'] and self.dc_settings['encoding'].lower() not in ('utf-8', 'utf8'):
            try:
                text = text.encode(self.dc_settings['encoding']).decode('utf-8')
            except UnicodeDecodeError:
                pass
        text = text.replace('\r\n', '\n')
        repl = '\n' if config.settings['cr2lf'] else ' '
        text = text.replace('\r', repl)
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

    def chat_send(self, message):
        if self.dc and self.dc.connected:
            self.dc.chat_send(message)
            return True
        else:
            return False

    def pm_send(self, recipient, message):
        if self.dc and self.dc.connected and recipient in self.dc.userlist:
            self.dc.pm_send(recipient, message)
            return True
        else:
            return False

    def check_loop(self):
        if not (self.dc.connecting or self.dc.connected):
            self.set_state(0)
            self.set_state_pm_tabs(0)
            self.userlist.clear()
            self.statusbar_clear()
            if self.do_connect and config.settings['reconnect'] and config.settings['reconnect_delay'] > 0:
                self.connect_loop_running = True
                self.frame.after(config.settings['reconnect_delay']*1000, self.connect_loop)
        else:
            if not self.state and self.dc.connected:
                self.state = 1
                self.update()
            if not self.pass_event.is_set():   # если сброшен, значит, DC-тред ждёт пароль
                pass_window = PassWindow()
                pass_window.wait_window()
                self.pass_event.password = pass_window.password.get()   # передамим в DC-тред через атрибут эвента
                self.pass_event.set()   # устанавливаем обратно в True (информируем DC-тред, что пароль получен)
            self.frame.after(100, self.check_loop)

    def connect_loop(self):
        if self.queue_loop_running or self.userlist_loop_running:
            self.frame.after(100, self.connect_loop)
        else:
            if self.do_connect:
                self.dc = slangdc.DCClient(**self.dc_settings)
                DCThread(self.dc, self.pass_event).start()
                self.queue_loop_running = True
                self.chat_userlist_running = True
                self.frame.after(100, self.queue_loop)
                self.frame.after(100, self.userlist_loop)
                self.frame.after(100, self.check_loop)
            self.frame.after(2000, self.reset_connect_loop_flag)   # 2 секунды игнорируем повторные попытки подключиться

    def reset_connect_loop_flag(self):   # lambda - это вам не function() {...}
        self.connect_loop_running = False   # поэтому тривиальное действие приходится выносить в отдельную функцию

    def queue_loop(self):
        message = self.dc.message_queue.mget()
        if message:
            if message['type'] == slangdc.MSGEND:
                self.queue_loop_running = False
                return
            else:
                timestamp = self.timestamp(message['time'])
                tab = self   # или дочерняя PM вкладка
                if message['type'] == slangdc.MSGCHAT:
                    msg = self.format_message(message['nick'], message['text'], message['me'])
                elif message['type'] == slangdc.MSGPM:
                    if 'sender' in message:   # входящее сообщение
                        nick = message['nick'] if message['nick'] else message['sender']
                        tab_pm_name = (self.name, message['sender'])
                    else:   # исходящее сообщение
                        nick = self.dc.nick
                        tab_pm_name = (self.name, message['recipient'])
                    tab = self.tab_pm_callback(name=tab_pm_name, add_new=True)
                    msg = self.format_message(nick, message['text'], message['me'])
                elif message['type'] == slangdc.MSGERR:
                    msg = ('error', "*** " + message['text'])
                elif message['type'] == slangdc.MSGINFO:
                    msg = ('info', "*** " + message['text'])
                    if message['text'].startswith('HubName: '):
                        self.statusbar['hubname'] = self.dc.hubname
                    elif message['text'].startswith('HubTopic: '):
                        self.statusbar['hubtopic'] = self.dc.hubtopic
                elif message['type'] == slangdc.MSGNICK:
                    if config.settings['show_joins'] and isinstance(message['nick'], str):
                        msg = ('info', "*** {0}s: {1}".format(message['state'], message['nick']))
                    else:
                        msg = None
                        if self.tab_pm_callback(name=self.name):   # если PM табов нет, не будем впустую вызывать
                            if isinstance(message['nick'], str):
                                nicks = (message['nick'],)
                            else:
                                nicks = message['nick']
                            state = 1 if message['state'] == 'join' else 0
                            self.set_state_pm_tabs(state, nicks)
                if msg:
                    tab.chat.add_message('timestamp', timestamp, 'text', " ", *msg)
                    # обновим счётчик непрочитанных (только для сообщий чата и PM, информационные
                    # и прочие сообщения игнорируем)
                    if not tab.visible and message['type'] in (slangdc.MSGCHAT, slangdc.MSGPM):
                        tab.unread += 1
                        tab.update()
        self.frame.after(10, self.queue_loop)

    def userlist_loop(self):
        if self.dc.connecting or self.dc.connected:
            if self.visible and self.dc.userlist:   # не обновляем список, пока таб не выбран
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
                self.statusbar['usercount'] = count
            self.frame.after(1000, self.userlist_loop)
        else:
            self.userlist_loop_running = False


class PMTab(Tab):

    def __init__(self, name, state, parent_widget, tab_update_callback, pm_send_callback):
        super().__init__(name, parent_widget)
        self.type_ = 'pm'
        self.state = state
        self.tab_update_callback = tab_update_callback
        self.message_box = MessageBox(self.frame, side=BOTTOM, expand=NO, fill=X, submit_callback=lambda message:pm_send_callback(self.name, message))
        self.chat = Chat(self.frame, side=TOP, expand=YES, fill=BOTH, nick_callback=None)
        Label(self.frame, text='PM: {} @ {}'.format(name[1], name[0]), anchor=W).pack(side=TOP, expand=NO, fill=X)

    def close(self):
        self.hide()
        recursive_destroy(self.frame)

    def set_state(self, state, timestamp):
        # timestamp - отформатированная строка
        prev_state = self.state
        self.state = state
        self.update()
        if prev_state != state:   # не выводим одинаковые сообщения подряд
            self.chat.add_message('timestamp', timestamp, 'text', " ", 'info', "*** User went {}".format(('offline', 'online')[state]))

    def set_pm_send_callback(self, pm_send_callback):
        self.message_box.submit_callback = pm_send_callback


class AppMenu(Menu):

    def __init__(self, root):
        super().__init__(root, borderwidth=0)
        root.config(menu=self)

    def add_bookmarks(self, bookmarks, action):
        menu_bookmarks = Menu(self, tearoff=False)
        if bookmarks:
            for bm_number, bookmark in enumerate(bookmarks):
                if 'name' in bookmark:
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
    font_unsel = ('Helvetica', 9, 'normal')
    font_sel = ('Helvetica', 10, 'bold')

    def __init__(self, parent, side, select_callback, close_callback, height=30):
        super().__init__(parent, height=height)
        self.select_callback = select_callback
        self.close_callback = close_callback
        self.pack(side=side, expand=NO, fill=X)
        self.tabs = []
        self.selected = None   # name выбранной вкладки
        self.prev = None   # name предыдущей выбранной вкладки

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

    def add_tab(self, name, label='', state=0):
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
        if name == self.selected:   # если закрываем выбранную вкладку, выберем предыдущую или первую
            self.selected = None
            if self.tabs:
                if self.tab_index(self.prev) == -1: self.prev = self.tabs[0]['name']
                self.select_tab(self.prev)
            else:
                self.prev = None

    def draw_tabs(self):
        width = self.calculate_width()
        if width:
            relx = 0
            for tab in self.tabs:
                relh = 1 if tab['name'] == self.selected else 0.8
                tab['button'].place(relx=relx, rely=1, relheight=relh, relwidth=width, anchor='sw')
                relx += width

    def select_tab(self, name):
        if self.selected == name: return
        index = self.tab_index(name)
        if index == -1: return False
        if self.selected:
            sel_index = self.tab_index(self.selected)
            if not sel_index == -1:
                self.tabs[sel_index]['label'].config(font=self.font_unsel)
                self.prev = self.selected
            else:
                self.prev = None
        self.selected = name
        self.tabs[index]['label'].config(font=self.font_sel)
        self.draw_tabs()
        self.select_callback(name)

    def update_tab(self, name, label=None, state=None):
        index = self.tab_index(name)
        if index == -1: return False
        if not label is None:
            self.tabs[index]['label'].config(text=label)
        if not state is None:
            self.tabs[index]['state'] = int(state)
            bg = self.color_on if state else self.color_off
            self.tabs[index]['button'].config(bg=bg)
            self.tabs[index]['label'].config(bg=bg)


class Chat(Frame):

    max_lines = 500

    def __init__(self, parent, side, expand, fill, nick_callback=None):
        Frame.__init__(self, parent)
        self.pack(side=side, expand=expand, fill=fill)
        font_family = 'Helvetica'
        font_size = 12
        font_normal = (font_family, font_size, 'normal')
        font_bold = (font_family, font_size, 'bold')
        font_underline = (font_family, font_size, 'normal underline')
        tools_frame = Frame(self, height=36)
        tools_frame.pack_propagate(0)
        tools_frame.pack(side=BOTTOM, expand=NO, fill=BOTH)
        Button(tools_frame, text='Clear chat', command=self.clear).pack(side=LEFT)
        self.autoscroll = BooleanVar()
        self.autoscroll.set(True)
        Checkbutton(tools_frame, text='Autoscroll', variable=self.autoscroll).pack(side=LEFT)
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
            ('text',    ('<Double-1>', self.extract_nick, 'insert'),
                        ('<Double-3>', self.extract_nick, 'pm')),
            ('link',    ('<Button-1>', self.link_click),
                        ('<Enter>', self.link_enter),
                        ('<Leave>', self.link_leave)),
            ('user_nick',   ('<Double-1>', self.nick_click, 'insert'),
                            ('<Double-3>', self.nick_click, 'pm')),
            ('op_nick',     ('<Double-1>', self.nick_click, 'insert'),
                            ('<Double-3>', self.nick_click, 'pm')),
            ('bot_nick',    ('<Double-1>', self.nick_click, 'insert'),
                            ('<Double-3>', self.nick_click, 'pm')),
        )
        for tag, font, color in tags_styles:
            chat.tag_config(tag, font=font, foreground=color)
        for tag, *bindings in tags_bindings:
            for event, callback, *args in bindings:
                args.insert(0, tag)
                cb = lambda e, c=callback, a=args: c(e, *a)
                chat.tag_bind(tag, event, cb)
        chat.bind('<Control-c>', self.text_copy)
        chat.bind('<Control-C>', self.text_copy)
        chat.bind('<Key>', self.nav_keys)
        self.chat = chat
        self.empty = True
        self.links = {}
        self.link_index = 1   # индекс для тегов ссылок ('link-%d')
        self.nick_callback = nick_callback
        self.lock = threading.Lock()

    def _get_index(self, event):
        return self.chat.index('@{},{}'.format(event.x, event.y))

    def _get_tag_range(self, index, tag):
        tag_range = self.chat.tag_prevrange(tag, index)
        if not tag_range or self.chat.compare(tag_range[1], '<', index):
            tag_range = self.chat.tag_nextrange(tag, index)
        return tag_range

    def _get_tag_text(self, index, tag):
        tag_range = self._get_tag_range(index, tag)
        return self.chat.get(*tag_range)

    def _split_index(self, index):
        return tuple(map(int, index.split('.')))

    def extract_nick(self, event, tag, action):
        if self.nick_callback:
            # пытается извлечь из текста под курсором ник
            index = self._get_index(event)
            tag_range = self._get_tag_range(index, tag)
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
                        self.nick_callback(nick, action)

    def nick_click(self, event, tag, action):
        if self.nick_callback:
            index = self._get_index(event)
            nick = self._get_tag_text(index, tag)
            self.nick_callback(nick, action)

    def link_click(self, event, tag):
        index = self._get_index(event)
        link_tag = self.chat.tag_names(index)[1]
        webbrowser.open(self.links[link_tag])

    def link_enter(self, event, tag):
        self.chat.config(cursor='hand2')

    def link_leave(self, event, tag):
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
                if tag == 'link':
                    link_tag = 'link-' + str(self.link_index)
                    self.link_index += 1
                    self.links[link_tag] = text
                    tag = ('link', link_tag)
                    text = urllib.parse.unquote_plus(text)
                self.chat.insert(END, text, tag)
            chat_lines = int(self.chat.index('end-1c').split('.')[0])
            if chat_lines > self.max_lines:
                del_to = str(chat_lines-self.max_lines+1) + '.0'
                from_ = '1.0'
                while True:   # удаляем ссылки, выходящие за пределы max_lines
                    link_range = self.chat.tag_nextrange('link', from_, del_to)
                    if not link_range: break
                    link_tag = self.chat.tag_names(index=link_range[0])[1]   # 0 - link, 1 - link-%d (в том же порядке, как при insert)
                    del self.links[link_tag]
                    self.chat.tag_delete(link_tag)   # тег тоже удаляем (может, и не надо, не знаю, как они хранятся в Tk)
                    from_ = link_range[1]
                self.chat.delete('1.0', del_to)
            if self.autoscroll.get():
                self.chat.see(END)

    def clear(self):
        with self.lock:
            self.chat.delete('1.0', END)
            self.empty = True
            self.links.clear()
            for i in range(1, self.link_index):
                self.chat.tag_delete('link-' + str(i))
            self.link_index = 1

    def text_copy(self, event):
        if self.chat.tag_ranges(SEL):
            self.clipboard_clear()
            self.clipboard_append(self.chat.get('sel.first', 'sel.last'))
        return 'break'

    def nav_keys(self, event):
        if not event.keysym in ('Home', 'End', 'Prior', 'Next', 'Up', 'Down', 'Left', 'Right'):
            return 'break'


class UserList(Frame):

    def __init__(self, parent, side, expand, fill, nick_callback=None):
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
        userlist.bind('<Double-1>', lambda e: self.nick_action(e, 'insert'))
        userlist.bind('<Double-3>', lambda e: self.nick_action(e, 'pm'))
        self.userlist = userlist
        filter_frame = Frame(self, height=36)
        filter_frame.pack_propagate(0)
        filter_frame.pack(side=BOTTOM, expand=NO, fill=BOTH)
        self.filter_var = StringVar()
        filter_entry = Entry(filter_frame, textvariable=self.filter_var)
        filter_entry.pack(expand=YES, fill=X)
        self.colors = {
            'user': 'black',
            'op': 'red',
            'bot': 'magenta'
        }
        self.nick_callback = nick_callback
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

    def nick_action(self, event, action):
        if self.nick_callback:
            index = self.userlist.index('@{},{}'.format(event.x, event.y))
            self.userlist.activate(index)
            nick = self.userlist.get(index)[1:]
            self.nick_callback(nick, action)


class MessageBox(Frame):

    def __init__(self, parent, side, expand, fill, submit_callback=None):
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
            self._vars[var_name] = [var, label, None]
            self.set(var_name, '')

    def set(self, var, value):
        value = str(value)
        if not value == self._vars[var][2]:
            self._vars[var][0].set(self._vars[var][1] + ": " + value)
            self._vars[var][2] = value

    def clear(self):
        for var_name in self._vars:
            self.set(var_name, '')


class SettingsWindow(Toplevel):

    def __init__(self):
        super().__init__()
        self.title("Settings")
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
            ('chat_addr_sep', 'str', 'Chat address separator'),
            ('detect_utf8', 'bool', 'Force UTF-8 detection'),
            ('cr2lf', 'bool', 'Display CR as newline')
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
            if field_type in ('str', 'int'):
                val = val.strip()
            if field_type == 'int':
                try:
                    val = int(val)
                except ValueError:   # валидации форм нет, поэтому вместо недопустимых значений берём дефолтные
                    val = config.default_settings[field_name]
            new_settings[field_name] = val
        if new_settings != config.settings:
            config.save_settings(new_settings)
        self.close()

    def close(self):
        self.destroy()


class PassWindow(Toplevel):

    def __init__(self):
        super().__init__()
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
            нажата кнопка Disconnect
        '''
        if not self.pass_event.password:
            self.pass_event.clear()   # сбрасываем эвент (False) (по умолчанию было True)
            self.pass_event.wait()   # ждём, пока в главном потоке выставят обратно в True (когда будет получен пароль)
        return self.pass_event.password


config = conf.Config()
Gui().mainloop()
