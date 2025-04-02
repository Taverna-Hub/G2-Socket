import socket

HOST = "localhost"
PORT = 3000

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((HOST, PORT))

tipo_operacao = input("Digite o modo de operação: ")
tamanho_maximo = input("Digite o tamanho máximo: ")

client.sendall(f"{tipo_operacao},{tamanho_maximo}".encode())

resposta = client.recv(1024).decode()
print(f"Resposta do servidor: {resposta}")

client.close()
