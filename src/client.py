import socket

# connect to server
s = socket.socket()
s.connect(('127.0.0.1', 8080))

# # send a manual HTTP request
# request = "GET / HTTP/1.1\r\nHost: localhost\r\n\r\n"
# s.sendall(request.encode())

# print response
print(s.recv(4096).decode())
s.close()