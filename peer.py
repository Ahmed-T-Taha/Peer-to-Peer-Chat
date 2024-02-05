from socket import *
import threading
import select


def print_above(msg):
    print("\u001B[s", end="")  # Save current cursor position
    print("\u001B[A", end="")  # Move cursor up one line
    print("\u001B[999D", end="")  # Move cursor to beginning of line
    print("\u001B[S", end="")  # Scroll up/pan window down 1 line
    print("\u001B[L", end="")  # Insert new line
    print(msg, end="")  # Print message sent to function
    print("\u001B[u", end="", flush=True)  # Jump back to saved cursor position


class PeerServer(threading.Thread):
    # Peer server initialization
    def __init__(self, username, peerServerPort):
        threading.Thread.__init__(self)
        self.username = username
        self.isChatting = False
        self.chatroom = None

        self.peerServerSocket = socket(AF_INET, SOCK_STREAM)
        self.peerServerHost = gethostbyname(gethostname())
        self.peerServerPort = peerServerPort
        self.peerServerSocket.bind((self.peerServerHost, self.peerServerPort))
        self.peerServerSocket.listen()

        self.inputs = [self.peerServerSocket]
        self.connectedPeers = []

    # main method of the peer server thread
    def run(self):
        while self.username:
            # monitors for the incoming connections
            readable, writable, exceptional = select.select(self.inputs + self.connectedPeers, [], [], 1)
            for sock in readable:
                # if the socket that is receiving the connection is the tcp socket of the peer's server, enters here
                if sock is self.peerServerSocket:
                    # accepts the connection, and adds its connection socket to the connected peers list
                    connectedPeerSocket, addr = sock.accept()
                    self.connectedPeers.append(connectedPeerSocket)

                # if the socket that receives the data is used to communicate with a connected peer, then enters here
                else:
                    try:
                        message = sock.recv(1024).decode().split("\n")
                    except:
                        sock.close()
                        if sock in self.connectedPeers:
                            self.connectedPeers.remove(sock)
                        if self.chatroom == None:
                            self.isChatting = False
                        continue

                    if len(message) == 0:
                        sock.close()
                        if sock in self.connectedPeers:
                            self.connectedPeers.remove(sock)

                    else:
                        match message[0]:
                            case "chat-request":
                                if self.isChatting:
                                    if self.chatroom:
                                        sock.send(f"user-chatting\n{self.chatroom}".encode())
                                    else:
                                        sock.send(f"user-chatting".encode())
                                else:
                                    self.isChatting = True
                                    print_above(f"Receiving chat request from {message[1]}")
                                    print_above("Would you like to accept (y/n)")

                            case "chatroom-join":
                                if message[1] == self.chatroom:
                                    print_above(f"{message[2]} has joined the chatroom.")
                                    sock.send("welcome".encode())
                                else:
                                    sock.send("user-not-in-chatroom".encode())

                            case "chatroom-leave":
                                print_above(f"{message[1]} has left the chatroom.")
                                sock.close()
                                if sock in self.connectedPeers:
                                    self.connectedPeers.remove(sock)

                            case "chat-end":
                                print_above(f"{message[1]} has ended the chat.")
                                self.isChatting = False
                                sock.close()
                                if sock in self.connectedPeers:
                                    self.connectedPeers.remove(sock)

                            case "chat-message":
                                username = message[1]
                                content = "\n".join(message[2:])
                                print_above(f"{username} -> {content}")

        if self.peerServerSocket:
            self.peerServerSocket.close()


class PeerClient(threading.Thread):
    def __init__(
        self,
        peerServer,
        peersToConnect=None,
        chatroom=None,
    ):
        threading.Thread.__init__(self)
        self.peerServer = peerServer
        self.peerServer.chatroom = chatroom
        self.peerServer.isChatting = True

        if peersToConnect:
            for peer in peersToConnect:
                peer = peer.split(":")
                sock = socket(AF_INET, SOCK_STREAM)
                sock.connect((peer[0], int(peer[1])))

                if chatroom:
                    sock.send(f"chatroom-join\n{chatroom}\n{self.peerServer.username}".encode())
                    response = sock.recv(1024).decode()
                    if response == "welcome":
                        self.peerServer.connectedPeers.append(sock)

                else:
                    sock.send(f"chat-request\n{self.peerServer.username}".encode())
                    response = sock.recv(1024).decode().split("\n")
                    match response[0]:
                        case "user-chatting":
                            self.peerServer.isChatting = False
                            if len(response) == 1:
                                print("User is already in a private chat")
                            else:
                                print(f"User is in chatroom: {response[1]}")

                        case "chat-request-reject":
                            print("User has rejected the chat request")
                            self.peerServer.isChatting = False

                        case "chat-request-accept":
                            self.peerServer.connectedPeers.append(sock)
                            print("User has accepted the chat.")

    # main method of the peer client thread
    def run(self):
        if self.peerServer.isChatting:
            if self.peerServer.chatroom:
                print("Chatroom joined Successfully.")
            print("Start typing to send a message. Send ':quit' to leave the chatroom.")

        while self.peerServer.isChatting:
            content = input("You -> ")

            if content == ":quit":
                if self.peerServer.chatroom == None:
                    message = f"chat-end\n{self.peerServer.username}"
                else:
                    message = f"chatroom-leave\n{self.peerServer.username}"
            else:
                message = f"chat-message\n{self.peerServer.username}\n{content}"

            for sock in self.peerServer.connectedPeers:
                sock.send(message.encode())

            if content == ":quit":
                self.peerServer.isChatting = False
                self.peerServer.chatroom = None
                for sock in self.peerServer.connectedPeers:
                    sock.close()
                self.peerServer.connectedPeers = []


class peerMain:
    # peer initializations
    def __init__(self):
        # connection initialization
        self.tcpClientSocket = socket(AF_INET, SOCK_STREAM)
        self.registryPort = 15600

        while True:
            try:
                self.registryName = input("Enter IP address of registry: ")
                self.tcpClientSocket.connect((self.registryName, self.registryPort))
                break
            except:
                print("Invalid registry IP address. Try again")

        # peer info
        self.username = None
        self.peerServerPort = None
        self.peerServer = None
        self.peerClient = None

        # timer and UDP socket for hello
        self.udpClientSocket = socket(AF_INET, SOCK_DGRAM)
        self.registryUDPPort = 15500
        self.timer = None

        self.run()

    def run(self):
        # main loop for program
        while True:
            # in case that the user is not yet logged in
            if self.username == None:
                choice = input("\nOptions: \n\tCreate account: 1 \n\tLogin: 2 \nChoice: ")

                match choice:
                    # if choice is 1, creates an account with entered username, password
                    case "1":
                        while True:
                            username = input("Username: ")
                            if len(username) < 4:
                                print("Username must be at least 4 characters long")
                            else:
                                break

                        while True:
                            password = input("Password: ")
                            if len(password) < 8:
                                print("Password must be at least 8 characters long")
                            else:
                                break

                        self.createAccount(username, password)

                    # if choice is 2 and user is not logged in, logs in with entered username, password
                    case "2":
                        username = input("Username: ")
                        password = input("Password: ")
                        while True:
                            port = input("Port to receive messages: ")
                            if port.isdigit() == False:
                                print("Port number must be integer between 1024 and 65535")
                            else:
                                port = int(port)
                                if port < 1024 or port > 65535:
                                    print("Port number must be integer between 1024 and 65535")
                                else:
                                    break
                        self.login(username, password, port)

                    case _:
                        print("Invalid input. Please try again")

            # otherwise if user is already logged in
            else:
                if choice == "invalid":
                    choice = input("Invalid input, please try again.\nChoice: ")
                else:
                    choice = input(
                        "\nOptions: \n\tLogout: 1 \n\tSearch for User: 2 \n\tActive Users: 3"
                        + "\n\tJoin Chatroom: 4 \n\tShow Chatrooms: 5 \n\tCreate Chatroom: 6"
                        + "\nChoice: "
                    )

                if (self.peerServer.isChatting and choice not in ["y", "n"]) or (
                    not self.peerServer.isChatting and choice not in ["1", "2", "3", "4", "5", "6"]
                ):
                    choice = "invalid"
                    continue

                match choice:
                    # if choice is 1 user is logged out
                    case "1":
                        self.logout()

                    # if choice is 2 user is asked for username to search
                    case "2":
                        username = input("Username to be searched: ")
                        self.searchUser(username)

                    # if choice is 3 prints list of online users
                    case "3":
                        self.userList()

                    # if choice is 4 joins chatroom
                    case "4":
                        name = input("Chatroom name: ")
                        self.chatroomJoin(name)

                    # if choice is 5 shows available chatrooms
                    case "5":
                        self.chatroomList()

                    # if choice is 6 creates chatroom
                    case "6":
                        while True:
                            name = input("Chatroom name: ")
                            if len(name) < 4:
                                print("Chatroom name must be at least 4 characters long")
                            else:
                                self.chatroomCreate(name)
                                break

                    case "y":
                        sock = self.peerServer.connectedPeers[0]
                        sock.send("chat-request-accept".encode())
                        self.peerClient = PeerClient(self.peerServer)
                        self.peerClient.start()
                        self.peerClient.join()

                    case "n":
                        sock = self.peerServer.connectedPeers[0]
                        sock.send("chat-request-reject".encode())
                        sock.close()
                        if sock in self.peerServer.connectedPeers:
                            self.peerServer.connectedPeers.remove(sock)
                        self.peerServer.isChatting = False

                    case _:
                        choice = "invalid"
                        print("Invalid input. Please try again")

    def createAccount(self, username, password):
        message = f"register-request\n{username}\n{password}"
        self.tcpClientSocket.send(message.encode())
        response = self.tcpClientSocket.recv(1024).decode()

        match response:
            case "register-success":
                print("Account created successfully.")
            case "register-username-exist":
                print("Username already exists.")

    def login(self, username, password, peerServerPort):
        message = f"login-request\n{username}\n{password}\n{peerServerPort}"
        self.tcpClientSocket.send(message.encode())
        response = self.tcpClientSocket.recv(1024).decode()

        match response:
            case "login-fail":
                print("Wrong username or password.")
            case "login-user-online":
                print("Account is already online.")

            case "login-success":
                print("Logged in successfully.")
                self.username = username
                self.peerServerPort = peerServerPort
                self.peerServer = PeerServer(self.username, self.peerServerPort)
                self.peerServer.start()
                self.sendHelloMessage()

    def logout(self):
        self.username = None
        self.tcpClientSocket.send("logout".encode())

        if self.peerServer:
            self.peerServer.username = None
            for sock in self.peerServer.connectedPeers:
                sock.close()
            self.peerServer = None

        if self.peerClient:
            self.peerClient = None

        if self.timer:
            self.timer.cancel()

        print("Logged out successfully")

    def searchUser(self, username):
        message = f"search-request\n{username}"
        self.tcpClientSocket.send(message.encode())
        response = self.tcpClientSocket.recv(1024).decode().split("\n")

        match response[0]:
            case "search-not-online":
                print(f"{username} is not online.")
            case "search-not-found":
                print(f"{username} was not found.")
            case "search-success":
                print(f"{username} is logged in -> {response[1]} : {response[2]}")
                while True:
                    chatStart = input("Would you like to start a chat with this user (y/n): ")
                    match chatStart:
                        case "y":
                            peer = [f"{response[1]}:{response[2]}"]
                            self.peerClient = PeerClient(peerServer=self.peerServer, peersToConnect=peer)
                            self.peerClient.start()
                            self.peerClient.join()
                            # This section will only run after user quits the chat
                            self.peerClient = None
                            break
                        case "n":
                            break
                        case _:
                            print("Response must be 'y' or 'n': ")

    def userList(self):
        message = "users-list-request"
        self.tcpClientSocket.send(message.encode())
        response = self.tcpClientSocket.recv(1024).decode().split("\n")

        if response[0] == "users-list":
            print("Online Users:")
            for user in response[1:]:
                print(f"\n\t{user}")

    def chatroomJoin(self, name):
        message = f"chatroom-join-request\n{name}"
        self.tcpClientSocket.send(message.encode())
        response = self.tcpClientSocket.recv(1024).decode().split("\n")

        match response[0]:
            case "chatroom-not-found":
                print("No chatroom exists with this name.")
            case "chatroom-join-success":
                if len(response) == 1:
                    peers = None
                else:
                    peers = response[1:]
                self.peerClient = PeerClient(peerServer=self.peerServer, chatroom=name, peersToConnect=peers)
                self.peerClient.start()
                self.peerClient.join()

                # This section will only run after user quits the chatroom
                self.tcpClientSocket.send("chatroom-leave-request".encode())
                self.peerClient = None

    def chatroomList(self):
        message = "chatroom-list-request"
        self.tcpClientSocket.send(message.encode())
        response = self.tcpClientSocket.recv(1024).decode().split("\n")

        if response[0] == "chatroom-list":
            print("Available Chatrooms:")
            for chatroom in response[1:]:
                print(f"\n\t{chatroom} users connected")

    def chatroomCreate(self, name):
        message = f"chatroom-creation-request\n{name}"
        self.tcpClientSocket.send(message.encode())
        response = self.tcpClientSocket.recv(1024).decode()

        match response:
            case "chatroom-name-exists":
                print("There already exists a chatroom with this name.")
            case "chatroom-creation-success":
                print("Chatroom created successfully")
                self.chatroomJoin(name)

    def sendHelloMessage(self):
        message = f"hello\n{self.username}"
        self.udpClientSocket.sendto(message.encode(), (self.registryName, self.registryUDPPort))
        self.timer = threading.Timer(1, self.sendHelloMessage)
        self.timer.start()


# peer is started
main = peerMain()
