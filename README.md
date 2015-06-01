slangdc
=======

A (very) simple Direct Connect library and Tk-based GUI client. Chat/private messages/userlist features only, no file sharing or any other p2p stuff.


## Requirements

* Python 3.3+
* Tk (gui.py)


## Files

* `slangdc.py` — DC library
* `example.py` — DC library usage example (sort of console client)
* `gui.py` — Tk-based GUI client
* `conf.py` — json-configs (settings, bookmarks, styles) support module for gui.py


## GUI client

![slangdc.Tk](https://i.imgur.com/pLFb8vM.png)

### Key and mouse bindings

*Global*
* **Ctrl+Tab** — next tab
* **Ctrl+Shitf+Tab** — previous tab

*Message text box*
* **Enter** — send message
* **Ctrl+Enter** — new line
* **Shift+Enter** — replace all '\n' with '\r' and send

*Chat and userlist*
* **Left button double-click** — insert nick
* **Right button double-click** — send PM

### Slash commands

*(currently available in main chat only)*

* **/connect** — connect to hub or reconnect if already connected
* **/disconnect** — disconnect from hub
* **/clear** — clear chat
* **/pm {nick} {message}** — send PM
* **/utf8 {message}** — send UTF-8-encoded message to chat (ignore current global/bookmark encoding)

### bookmarks.json format

[{bookmark1}, {bookmark2}, …]

bookmark object keys:

* **name** — bookmark name (in Bookmarks menu) (required)
* **address** — hub address (required)
* **autoconnect** — autoconnect to hub at startup (0 or 1) (optional)
* **nick**, **desc**, **email**, **share**, **slots**, **encoding**, **timeout** — override settings.json values (optional)
