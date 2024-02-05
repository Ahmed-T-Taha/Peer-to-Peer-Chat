from socket import *
import threading
import select
import bcrypt
import database


class ClientThread(threading.Thread):
    def __init__(self, host, port, tcpClientSocket):
        threading.Thread.__init__(self)
        # host, port, socket of connected peer
        self.host = host
        self.port = port
        self.tcpClientSocket = tcpClientSocket

        # username, current chatrooms, udp server of connected peer
        self.username = None
        self.chatroom = None
        self.udpServer = None
        print(f"New thread started for {self.host} : {self.port}")

    # main of peer thread
    def run(self):
        self.lock = threading.Lock()
        print(f"Connection from: {self.host} : {self.port}")

        while True:
            try:
                message_bytes = self.tcpClientSocket.recv(1024).decode()
                if message_bytes == b"":
                    break
                message_str = message_bytes
                message = message_str.split("\n")

                match message[0]:
                    case "register-request":
                        self.register(message[1], message[2])
                    case "login-request":
                        self.login(message[1], message[2], message[3])
                    case "logout":
                        self.logout()

                    case "search-request":
                        self.search(message[1])
                    case "users-list-request":
                        self.userList()

                    case "chatroom-join-request":
                        self.chatroomJoin(message[1])
                    case "chatroom-list-request":
                        self.chatroomList()
                    case "chatroom-creation-request":
                        self.chatroomCreate(message[1])
                    case "chatroom-leave-request":
                        self.chatroomLeave()

            except OSError:
                break

    def register(self, username, password):
        if db.is_account_exist(username):
            response = "register-username-exist"
        else:
            hashedPass = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
            db.register(username, hashedPass)
            response = "register-success"

        self.tcpClientSocket.send(response.encode())

    def login(self, username, password, port):
        if not db.is_account_exist(username):
            response = "login-fail"

        elif username in onlinePeers:
            response = "login-user-online"

        else:
            retrievedPass = db.get_password(username)
            password = password.encode()
            if retrievedPass == None:
                response = "login-fail"
            else:
                if bcrypt.checkpw(password, retrievedPass):
                    self.username = username
                    self.lock.acquire()
                    try:
                        tcpThreads[self.username] = self
                    finally:
                        self.lock.release()

                        onlinePeers[username] = {"host": self.host, "port": port}
                        self.udpServer = UDPServer(self.username, self.tcpClientSocket)
                        self.udpServer.start()
                        self.udpServer.timer.start()
                        print(f"{self.username} is logged in")
                        response = "login-success"

                else:
                    response = "login-fail"

        self.tcpClientSocket.send(response.encode())

    def logout(self):
        if self.username in onlinePeers:
            del onlinePeers[self.username]

        if self.udpServer:
            self.udpServer.timer.cancel()
            self.udpServer = None

        if self.chatroom:
            self.chatroomLeave()
        if self.username:
            print(f"{self.username} is logged out")
            self.username = None

    def search(self, username):
        if db.is_account_exist(username):
            if username in onlinePeers.keys():
                peer_info = onlinePeers[username]
                if peer_info:
                    response = f"search-success\n{peer_info['host']}\n{peer_info['port']}"
                else:
                    response = "search-not-online"

            else:
                response = "search-not-online"

        # enters if username does not exist
        else:
            response = "search-not-found"

        self.tcpClientSocket.send(response.encode())

    def userList(self):
        users = "\n".join(onlinePeers.keys())
        response = f"users-list\n{users}"
        self.tcpClientSocket.send(response.encode())

    def chatroomJoin(self, name):
        if name not in chatrooms.keys():
            response = "chatroom-not-found"
        else:
            response = "chatroom-join-success"
            for user in chatrooms[name]:
                response = f"{response}\n{onlinePeers[user]["host"]}:{onlinePeers[user]["port"]}"
            chatrooms[name].append(self.username)
            self.chatroom = name
        self.tcpClientSocket.send(response.encode())

    def chatroomList(self):
        response = "chatroom-list"
        for key in chatrooms.keys():
            response = f"{response}\n{key} : {len(chatrooms[key])}"
        self.tcpClientSocket.send(response.encode())

    def chatroomCreate(self, name):
        if name in chatrooms.keys():
            response = "chatroom-name-exists"
        else:
            chatrooms[name] = []
            response = "chatroom-creation-success"
        self.tcpClientSocket.send(response.encode())

    def chatroomLeave(self):
        chatrooms[self.chatroom].remove(self.username)
        self.chatroom = None


# implementation of the udp server thread for clients
class UDPServer(threading.Thread):
    # udp server thread initializations
    def __init__(self, username, clientSocket):
        threading.Thread.__init__(self)
        self.username = username
        # timer thread for the udp server is initialized
        self.timer = threading.Timer(3, self.waitHelloMessage)
        self.tcpClientSocket = clientSocket

    # if hello message is not received before timeout
    # then peer is disconnected
    def waitHelloMessage(self):
        if self.username in onlinePeers:
            del onlinePeers[self.username]
        if self.username in tcpThreads:
            del tcpThreads[self.username]
        if len(chatrooms.keys()) > 0:
            for key in chatrooms.keys():
                if self.username in chatrooms[key]:
                    chatrooms[key].remove(self.username)
        print(f"Removed {self.username} from online peers")
        self.username = None

    # resets the timer for udp server
    def resetTimer(self):
        self.timer.cancel()
        self.timer = threading.Timer(3, self.waitHelloMessage)
        self.timer.start()


# server port initialization
print("Registy started...")
port = 15600
portUDP = 15500

# db initialization
db = database.DB()

# gets the ip address of the registry
host = gethostbyname(gethostname())
print(f"Registry IP address: {host}")
print(f"Registry port number: {port}")

# threads for active connections and dict of online peers and chatrooms
tcpThreads = {}
onlinePeers = {}
chatrooms = {}

# socket initialization
tcpSocket = socket(AF_INET, SOCK_STREAM)
tcpSocket.bind((host, port))
tcpSocket.listen()
udpSocket = socket(AF_INET, SOCK_DGRAM)
udpSocket.bind((host, portUDP))
inputs = [tcpSocket, udpSocket]


print("Listening for incoming connections...")
# as long as at least a socket exists to listen to, the registry runs
while tcpSocket:
    readable, writable, exceptional = select.select(inputs, [], [])

    # monitors for the incoming connections
    for sock in readable:
        # if the message received comes to the tcp socket, accept connection & start thread
        if sock is tcpSocket:
            (tcpClientSocket, addr) = tcpSocket.accept()
            newThread = ClientThread(addr[0], addr[1], tcpClientSocket)
            newThread.start()

        # if the message received comes to the udp socket, check hello
        elif sock is udpSocket:
            (message, clientAddress) = sock.recvfrom(1024)
            message = message.decode().split("\n")

            # checks if it is a hello message
            if message[0] == "hello":
                # checks if the account that sent this hello message is online
                if message[1] in tcpThreads:
                    # resets the timeout for that peer
                    tcpThreads[message[1]].udpServer.resetTimer()


# registry tcp socket is closed
tcpSocket.close()
