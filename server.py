import socket

HOST = "localhost"
PORT = 3000

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen()
print("Aguardando conexão...")

conn, addr = server.accept()
print(f"Conectado por {addr}")

dados = conn.recv(1024).decode()
tipo_operacao, tamanho_maximo = dados.split(",")
print(
    f"Configurações recebidas do cliente: Modo de operação = {tipo_operacao}, Tamanho máximo = {tamanho_maximo}"
)

conn.sendall("Configurações aplicadas com sucesso".encode())

conn.close()
server.close()
