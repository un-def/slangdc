# -*-coding: UTF-8 -*-
# python 3.3+
import socket
import random
import string
import re

version = '0.0.5'

class DCError(Exception):
    def __init__(self, error, close=None):
        """ error="текст ошибки"
            close=<socket object>, который надо закрыть, или None
        """
        self.error = error
        if close:
            close.close()   # закрываем сокет
    def __str__(self):
        return self.error

class DCSocketError(DCError):
    pass

class DCHubError(DCError):
    pass

class DCClient:

    timeout = None
    debug = False

    def __init__(self, address, nick=None, password=None, encoding='utf-8', timeout=None):
        """ address='dchub.com[:port]'
                стандартный порт (411) можно не указывать
            nick='nick'
                если не указывать, будет рандомный вида 'sldc[A-Z]{6}'
            password='password'
                можно не указывать, если не требуется
            encoding='enc'
                кодировка хаба, по умолчанию windows-1251
            timeout=sec
                таймаут получения данных из сокета в секундах; по таймауту
                recv() возбуждает DCError
                по умолчанию __class__.timeout=None -->
                http://docs.python.org/3.4/library/socket.html#socket-timeouts
        """
        host, _, port = address.partition(':')
        try:
            port = int(port)
        except ValueError:
            port = 411
        self.address = (host, port)
        self.nick = nick if nick else 'sldc' + ''.join(random.choice(string.ascii_uppercase) for n in range(6))
        self.password = password
        self.encoding = encoding
        if timeout: self.timeout = timeout
        self.recv_list = []

    def connect(self):
        """ подключиться к хабу
            при ошибках сокета возбуждает DCSocketError
            при ошибках на уровне протокола (нужен пароль, неправильный
            пароль, etc.) - DCHubError
        """
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(self.timeout)
        try:
            self.socket.connect(self.address)
        except socket.timeout:
            raise DCSocketError("connection timeout ({} s)".format(self.timeout), close=self.socket)
        except OSError as err:
            raise DCSocketError(err.strerror, close=self.socket)
        data = self.recv(encoding=False)   # $Lock получаем без декодирования (bytes)
        lock_received = re.search(b'^\$Lock (.+) Pk=.+$', data)
        if not lock_received:
            raise DCHubError("$Lock is not received", close=self.socket)
        lock = lock_received.group(1)
        if lock.startswith(b'EXTENDEDPROTOCOL'):   # EXTENDEDPROTOCOL - поддерживаются расширения протокола
            supports = '$Supports HubTopic'
        else:
            supports = ''
        key = self.lock2key(lock)
        self.send(supports, b'$Key ' + key, '$ValidateNick ' + self.nick)
        tries = 10
        lastdata = None
        while tries:
            try:
                data = self.recv()
            except DCSocketError as err:
                if lastdata:
                   err = "{0} | {1}".format(err, lastdata)
                raise DCSocketError(err)
            lastdata = data
            if data == '$GetPass':
                if not self.password:
                    raise DCHubError("need a password", close=self.socket)
                else:
                    self.send('$MyPass ' + self.password)
            elif data == '$BadPass':
                raise DCHubError("wrong password", close=self.socket)
            elif data.startswith('$HubName'):
                pass
            elif data.startswith('$Supports'):
                pass
            elif data.startswith('$Hello'):
                break
            else:
                tries -= 1
        else:   # если вышли не по break (т.е. не получили Hello)
            raise DCHubError("$Hello not received | " + data, close=self.socket)
        self.send('$Version 1,0091', '$MyINFO $ALL {0} desc<slangdc V:{1},M:P,H:0/1/0,S:1>$ $100 $email$0$'.format(self.nick, version))

    def disconnect(self):
        self.socket.close()

    def recv(self, encoding=None):
        """ recv([encoding=False|'enc'])
            возвращает одну команду DC без конечного '|':
                хаб отправил 'hello|bye|'
                recv() --> 'hello'
                recv() --> 'bye'

            возвращает str или bytearray (в зависимости от
            encoding) или False в случае ошибки или таймаута

            encoding=
                False - вернуть без декодирования (bytearray)
                'enc' - декодировать как 'enc'
                None (по умолчанию) - кодировка по умолчанию
        """
        if not self.recv_list:
            recv = bytearray()
            while True:
                try:
                    chunk = self.socket.recv(1024)
                except socket.timeout:
                    raise DCSocketError("receive timeout ({} s)".format(self.timeout), close=self.socket)
                except OSError as err:
                    raise DCSocketError(err.strerror, close=self.socket)
                if not chunk:   # len(recv) == 0 --> удаленный сокет закрыт
                    raise DCSocketError("closed", close=self.socket)
                recv.extend(chunk)
                if chunk.endswith(b'|'):
                    break
            if self.debug: print("<--", recv)
            self.recv_list = recv.rstrip(b'|').split(b'|')
        data = self.recv_list.pop(0)
        if encoding is None: encoding = self.encoding   # кодировка по умолчанию
        if not encoding:   # если encoding=False
            return data
        else:
            return data.decode(encoding=encoding, errors='replace')

    def send(self, *commands, encoding=None):
        """ send(command1, command2, …, [encoding='enc'])
            отправить в сокет b'command1|command2|…|'

            commandN может быть
                str - энкодится в указанную кодировку
                bytes|bytearray - как есть
                пустые объекты игнорируются:
                send('hello', '', b'bye') --> b'hello|bye|'

            encoding=
                'enc' - декодировать строки как 'enc'
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
            self.socket.send(data)
        except OSError as err:
            raise DCSocketError(err.strerror, close=self.socket)

    def chat_send(self, message, encoding=None):
        self.send('<{0}> {1}'.format(self.nick, message), encoding=encoding)

    def pm_send(self, to, message, encoding=None):
        self.send('$To: {0} From: {1} $<{1}> {2}'.format(to, self.nick, message), encoding=encoding)

    @staticmethod
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
