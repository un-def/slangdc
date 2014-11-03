# -*-coding: UTF-8 -*-
# python 3.3+
import socket
import queue
import random
import string
import re
import time
from threading import RLock

version = '0.1.0'

MSGINFO = 0
MSGERR = 1
MSGCHAT = 2
MSGPM = 3

def dcescape(text):
    return text.replace('$', '&#36;').replace('|', '&#124;')

def dcunescape(text):
    return text.replace('&#36;', '$').replace('&#124;', '|')

def lock2key(lock):   # http://wiki.mydc.ru/Lock2Key
    """ вычисляет key из lock
        key - bytes или bytearray
        lock - byrearray
    """
    keylist = [lock[0] ^ lock[-1] ^ lock[-2] ^ 5]
    keylist.extend(x1 ^ x2 for x1, x2 in zip(lock, lock[1:]))
    escaping = (0, 5, 36, 96, 124, 126)
    key = bytearray()
    for x in keylist:
        x = ((x << 4) & 240) | ((x >> 4) & 15)
        if x in escaping:
            key.extend(bytes('/%DCN{:03d}%/'.format(x), 'ascii'))
        else:
            key.append(x)
    return key


class DCSocketError(Exception):

    def __init__(self, error, close=None):
        """ error="текст ошибки"
            close=экземпляр DCClient, если нужно закрыть сокет и установить
                атрибут connected в False
        """
        self.error = error
        if close:
            close.connected = False
            close.socket_close()

        def __str__(self):
            return self.error


class MsgQueue(queue.Queue):
    """ класс для хранения всех отображаемых сообщений
        в виде очереди (подкласс queue.Queue)
        сообщения хранятся в виде словарей
        структура - как указано в методе mput()
        + ключ 'time' (Unix time)
    """
    def mput(self, **item):
        """ MSGCHAT:
                mput(type=MSGCHAT, nick='…', text='…', me=False|True)

            MSGINFO, MSGERR:
                mput(type=MSGINFO|MSGERR, text='…')

            MSGPM:
                входящее сообщение:
                mput(type=MSGPM, sender='…', nick='…', text='…', me=False|True)
                sender и nick теоретически могут быть разными:
                '$To: … From: sender $<nick> [/me] text'
                если текст сообщения не соответствует шаблону
                ('<nick> [/me] text' или '*[*] nick text') - возможно, хаб
                может отправлять такие сообщения - то DCClient.receive()
                передаёт такие аргументы:
                    sender - sender из команды ('From: …')
                    nick   - None
                    text   - весь текст сообщения (часть команды после второго $)
                    me     - False

                исходящее сообщение:
                mput(type=MSGPM, recipient='…', text='…', me=False|True)
        """
        item['time'] = time.time()
        self.put(item, block=False)

    def mget(self):
        try:
            item = self.get(block=False)
        except queue.Empty:
            return False
        else:
            return item


class NickList(set):
    """ подкласс set; всегда True, даже если пуст

        методами add и remove можно добавлять как один ник, так и
        несколько - в виде списка/кортежа/множества

        имеет два дополнительный атрибута - ops и bots - подмножества
        операторов/ботов, наполняются при обработке команд
        $OpList/$BotList в DCClient.receive()
    """
    def __init__(self):
        self.ops = set()
        self.bots = set()
        set.__init__(self)

    def __bool__(self):
        return True

    def add(self, nicks, list_type=None):
        """ добавляет пользователя/нескольких пользователей
            в основной список и, если указан list_type='OpList|BotList',
            в список опов/ботов соответственно
            по умолчанию list_type=None (эквивалентно 'NickList')
        """
        if list_type == 'NickList': list_type = None
        if not isinstance(nicks, (list, tuple, set, frozenset)):
            nicks = (nicks,)   # если не коллекция, сделаем коллекцией
        self.update(nicks)
        if list_type:
            # ссылка на self.ops или self.bots
            ops_bots = self.ops if list_type == 'OpList' else self.bots
            ops_bots.update(nicks)

    def remove(self, nicks):
        """ удаляет пользователя/нескольких пользователей
            из всех трёх списков (основной, боты, операторы)
            попытка удалить несуществующий ник игнорируется
        """
        if isinstance(nicks, (list, tuple, set, frozenset)):
            self.difference_update(nicks)
            self.ops.difference_update(nicks)
            self.bots.difference_update(nicks)
        else:
            self.discard(nicks)
            self.ops.discard(nicks)
            self.bots.discard(nicks)


class DCClient:

    debug = False
    showjoins = False
    _connect_timeout = 30   # таймаут для попытки коннекта (socket.connect и recv при хендшейке)
    _real_timeout = 0.5   # "настоящий" таймаут для recv - вместо блокирующего чтения с заданным в настройках timeout будем много раз (timeout/_real_timeout) пытаться прочитать с маленьким таймаутом; можно было бы использовать select

    def __init__(self, address, nick=None, password=None, desc="", email="", share=0, slots=1, encoding='utf-8', timeout=600):
        """ address='dchub.com[:port]'
                стандартный порт (411) можно не указывать
            nick='nick'
                если не указывать, будет рандомный вида 'sldc[A-Z]{6}'
            password='password'
                можно не указывать, если не требуется
            encoding='enc'
                кодировка хаба, по умолчанию utf-8
            timeout=sec
                таймаут получения данных из сокета в секундах; по таймауту
                recv() возбуждает DCError
        """
        self.address = address
        host, _, port = address.partition(':')
        try:
            port = int(port)
        except ValueError:
            port = 411
        self._address = (host, port)
        self.nick = nick if nick else 'sldc' + ''.join(random.choice(string.ascii_uppercase) for n in range(6))
        self.password = password
        self.desc = desc
        self.email = email
        self.share = share
        self.slots = slots
        self.encoding = encoding
        self.timeout = timeout
        self.connected = False
        self.connecting = False   # флаг-индикатор процесса коннекта (до и после (не)успешного коннекта — False)
        self.socket = None   # None или socket object (False или True в логическом контексте соответственно)
        self.socket_lock = RLock()
        self.recv_list = []
        self.message_queue = MsgQueue()
        self.nicklist = None
        self.hubname = None
        self.hubtopic = None

    def connect(self, get_nicks=False, pass_callback=None):
        """ подключиться к хабу
            возвращает True или False

            get_nicks=True
                отправить команду $GetNickList

            pass_callback=<callable_object>
                коллбэк, вызываемый, если пароль не был указан, но хаб его
                запрашивает; должен возвращать str c паролем
                если возвращаемое значение в логическом контексте будет False
                ('', None, False) или коллбэк не задан, подключение будет
                прервано с ошибкой "нужен пароль"
        """
        def _connect(self):
            self.socket.settimeout(self._connect_timeout)   # настоящий блокирующий таймаут только для коннекта (не зависит от настроек)
            try:
                self.socket.connect(self._address)
            except socket.timeout:
                raise DCSocketError("connection timeout ({} s)".format(self._connect_timeout), close=self)
            except OSError as err:
                raise DCSocketError(err.strerror, close=self)
            self.socket.settimeout(self._real_timeout)   # ставим короткий таймаут для имитации неблокирующего режима при чтении
            data = self.recv(timeout=self._connect_timeout, encoding=False)   # $Lock получаем без декодирования (bytes)
            lock_received = re.fullmatch(b'\$Lock (.+) Pk=.+', data)
            if not lock_received:
                self.message_queue.mput(type=MSGERR, text="$Lock is not received")
                return False
            lock = lock_received.group(1)
            if lock.startswith(b'EXTENDEDPROTOCOL'):   # EXTENDEDPROTOCOL - поддерживаются расширения протокола
                supports = '$Supports HubTopic'
            else:
                supports = ''
            key = lock2key(lock)
            self.send(supports, b'$Key ' + key, '$ValidateNick ' + self.nick)
            attempts = 10
            while attempts:
                data = self.receive(timeout=self._connect_timeout, err_message=False)   # тут используем высокоуровневый метод
                if not data is None:   # None означает, что команда уже была обработана в receive()
                    if data == '$GetPass':
                        if not self.password and pass_callback:
                            self.password = pass_callback()
                        if not self.password:
                            self.message_queue.mput(type=MSGERR, text="need a password")
                            return False
                        else:
                            self.send('$MyPass ' + self.password)
                            self.message_queue.mput(type=MSGINFO, text="password has been sent")
                    elif data == '$BadPass':
                        self.message_queue.mput(type=MSGERR, text="wrong password")
                        return False
                    elif data.startswith('$ValidateDenide '):   # Verlihub шлёт эту команду после $Hello (!)
                        self.message_queue.mput(type=MSGERR, text="hub rejected your nick")
                        return False
                    elif data.startswith('$Supports '):
                        pass
                    elif data.startswith('$Hello '):
                        self.nick = data[7:]   # иногда хаб может выдавать другое имя
                        self.message_queue.mput(type=MSGINFO, text="Hello, {0}".format(self.nick))
                        break
                    else:
                        attempts -= 1
            else:   # если вышли не по break (т.е. не получили Hello)
                self.message_queue.mput(type=MSGERR, text="$Hello was not received")
                return False
            if get_nicks:
                getnicklist = '$GetNickList'
                self.nicklist = NickList()
            else:
                getnicklist = ''
                self.nicklist = None
            self.send('$Version 1,0091', getnicklist, '$MyINFO $ALL {0} {1}<slangdc V:{2},M:P,H:0/1/0,S:{3}>$ $100 ${4}${5}$'.format(self.nick, self.desc, version, self.slots, self.email, self.share))
            return True

        self.connecting = True
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.message_queue.mput(type=MSGINFO, text="connecting to {0}".format(self.address))
        try:
            self.connected = _connect(self)
        except DCSocketError as err:
            self.message_queue.mput(type=MSGERR, text="[socket] {0}".format(err))
        else:
            if not self.connected:
                self.socket_close()
            else:
                self.message_queue.mput(type=MSGINFO, text="connected")
        self.connecting = False
        return self.connected

    def socket_close(self):
        with self.socket_lock:
            if self.socket:
                self.socket.close()
                self.socket = None

    def disconnect(self):
        self.connected = False
        self.socket_close()
        self.message_queue.mput(type=MSGINFO, text="disconnected")

    def recv(self, timeout=None, encoding=None):
        """ recv([encoding=False|'enc'])
            возвращает одну команду DC без конечного '|':
                хаб отправил 'hello|bye|'
                recv() --> 'hello'
                recv() --> 'bye'

            возвращает str или bytearray (в зависимости от
            encoding) или False в случае ошибки или таймаута

            timeout=таймаут в секундах
                если не указан или None, то == self.timeout

            encoding=
                False - вернуть без декодирования (bytearray)
                'enc' - декодировать как 'enc'
                None (по умолчанию) - кодировка по умолчанию
        """
        def _recv(self, timeout):
            attempts = int(timeout / self._real_timeout)
            while attempts:
                if self.socket:
                    try:
                        data = self.socket.recv(1024)
                    except socket.timeout:
                        attempts -= 1
                    except OSError as err:
                        raise DCSocketError(err.strerror, close=self)
                    else:
                        if not data:   # len(data) == 0 --> удаленный сокет закрыт
                            raise DCSocketError("closed", close=self)
                        else:
                            return data
                else:
                    return False
            raise DCSocketError("receive timeout ({} s)".format(timeout), close=self)

        if not self.recv_list:
            recv_data = bytearray()
            if not timeout: timeout = self.timeout
            while True:
                with self.socket_lock:
                    chunk = _recv(self, timeout)
                if not chunk:   # если self.connected=False --> _recv() вернул False
                    chunk = b'|'   # recv_data = b'|' --> split --> [b'', b'']
                recv_data.extend(chunk)
                if chunk.endswith(b'|'):
                    break
            if self.debug: print("<--", recv_data)
            self.recv_list = recv_data.split(b'|')
            if not self.recv_list[-1]:   # обычно команды заканчиваются на |
                self.recv_list.pop()     # поэтому удаляем последний элемент
        data = self.recv_list.pop(0)
        if encoding is None: encoding = self.encoding   # кодировка по умолчанию
        if not encoding:   # если encoding=False
            return data
        else:
            return data.decode(encoding=encoding, errors='replace')

    def receive(self, timeout=None, raise_exc=True, err_message=True, encoding=None):
        """ высокоуровневая обёртка над recv()

            timeout=таймаут в секундах
            если не указан или None, то == self.timeout

            обрабатывает сообщения чата, PM, различные
            команды типа $HubName, выполняя соответствующие
            действия (кладёт в очереди, обновляет атрибуты)
            (в этом случае возвращает None)
            неизвестные команды возвращает как есть
            (т.е. ведёт себя аналогично более низкоуровневу
            recv c опциональной возможностью подавить
            исключение (см. ниже)

            перехватывает DCSocketError, после чего:
            raise_exc=True - заново возбуждает DCSocketError,
            чтобы передать его выше (по умолчанию)
            raise_exc=False - не возбуждает исключение,
            возвращает False (иными словами, подавляет
            исключение)

            если err_message=True (по умолчанию), то при
            исключении кладёт в очередь сообщений MSGERR
            c ошибкой ("[socket] ошибка")
        """
        def parse_msg(msg_string):
            """ пытается извлечь из строки ник, текст сообщения
                и флаг '/me' ("третьего лица") — понимает разные
                конструкции (см. ниже). Флаг me - True или False
                возвращает кортеж (nick, text, me) или False
            """
            # '<nick> text' или '<nick> /me text'
            msg = re.fullmatch('<([^\r\n]+?)> (.*)', msg_string, re.DOTALL)
            if msg:
                text = dcunescape(msg.group(2))
                if text.startswith('/me '):
                    text = text[4:]
                    me = True
                else:
                    me = False
                return (msg.group(1), text, me)
            # '*nick text' или '* nick text' c произвольным количеством *
            msg = re.fullmatch('\*+ ?([^\r\n]+?) (.*)', msg_string, re.DOTALL)
            if msg:
                text = dcunescape(msg.group(2))
                return (msg.group(1), text, True)
            return False

        try:
            data = self.recv(timeout=timeout, encoding=encoding)
        except DCSocketError as err:
            if err_message:
                self.message_queue.mput(type=MSGERR, text="[socket] {0}".format(err))
            if raise_exc:
                raise DCSocketError(str(err))
            else:
                return False
        else:
            if data:
                if not data.startswith('$'):
                    chat_msg = parse_msg(data)
                    if chat_msg:
                        self.message_queue.mput(type=MSGCHAT, nick=chat_msg[0], text=chat_msg[1], me=chat_msg[2])
                    else:
                        # любое другое сообщение, не начинающееся с $
                        self.message_queue.mput(type=MSGINFO, text=data)
                    return None
                elif data.startswith('$HubName '):
                    self.hubname = data[9:]
                    self.message_queue.mput(type=MSGINFO, text="HubName: {0}".format(self.hubname))
                    return None
                elif data.startswith('$HubTopic '):
                    self.hubtopic = data[10:]
                    self.message_queue.mput(type=MSGINFO, text="HubTopic: {0}".format(self.hubtopic))
                    return None
                elif self.nicklist and data.startswith('$Quit '):
                    nick = data[6:]
                    self.nicklist.remove(nick)
                    if self.showjoins:
                        self.message_queue.mput(type=MSGINFO, text="quit {0}".format(nick))
                    return None
                else:
                    pm = re.fullmatch('\$To: .+? From: (.+?) \$(.+)', data, flags=re.DOTALL)
                    if pm:
                        sender = pm.group(1)
                        # из PM тоже пытаемся извлечь ник, текст сообщения и me
                        pm_msg = parse_msg(pm.group(2))
                        if pm_msg:
                            nick, text, me = pm_msg
                        else:
                            nick, text, me = None, pm.group(2), False
                        self.message_queue.mput(type=MSGPM, sender=sender, nick=nick, text=text, me=me)
                        return None
                    if self.nicklist:
                        nicklist = re.fullmatch('\$(NickList|OpList|BotList) (.+)', data)
                        if nicklist:
                            list_type = nicklist.group(1)
                            list_ = nicklist.group(2)
                            # $OpList op1$$op2$$op3$$ или $OpList op4
                            if '$' in list_:
                                list_ = list_.split('$$')
                                list_.pop()
                            self.nicklist.add(list_, list_type)
                            return None
                        myinfo = re.match('\$MyINFO \$ALL (.+?) ', data)
                        if myinfo:
                            nick = myinfo.group(1)
                            if not nick in self.nicklist:
                                self.nicklist.add(nick)
                                if self.showjoins:
                                    self.message_queue.mput(type=MSGINFO, text="enter {0}".format(nick))
                            return None
            return data

    def send(self, *commands, encoding=None):
        """ send(command1, command2, …, [encoding='enc'])
            отправить в сокет b'command1|command2|…|'

            commandN может быть
                str - энкодится в указанную кодировку
                bytes|bytearray - как есть
                пустые объекты игнорируются:
                send('hello', '', b'bye') --> b'hello|bye|'

            encoding=
                'enc' - кодировать строки в 'enc'
                None (по умолчанию) - кодировка по умолчанию
        """
        data = bytearray()
        if encoding is None: encoding = self.encoding
        for command in commands:
            if command:
                if isinstance(command, str):
                    command = command.encode(encoding=encoding, errors='replace')
                data.extend(command + b'|')
        if self.debug: print("-->", data)
        try:
            return self.socket.send(data)
        except OSError as err:
            raise DCSocketError(err.strerror, close=self)
        except AttributeError:   # workaround - если в другом треде "убили" сокет socket_close()
            return False

    def chat_send(self, message, encoding=None):
        if not self.connected: return False
        return self.send('<{0}> {1}'.format(self.nick, dcescape(message)), encoding=encoding)

    def pm_send(self, recipient, message, encoding=None):
        if not self.connected: return False
        sent = self.send('$To: {0} From: {1} $<{1}> {2}'.format(recipient, self.nick, dcescape(message)), encoding=encoding)
        if message.startswith('/me '):
            message = message[4:]
            me = True
        else:
            me = False
        self.message_queue.mput(type=MSGPM, recipient=recipient, text=message, me=me)
        return sent
