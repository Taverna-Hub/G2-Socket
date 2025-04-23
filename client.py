import socket

HOST = "localhost"
PORT = 3000


def handShake():
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((HOST, PORT))

    tipo_operacao = input("Digite o modo de operação: ")
    tamanho_maximo = input("Digite o tamanho máximo: ")

    client.sendall(f"{tipo_operacao},{tamanho_maximo}".encode())

    resposta = client.recv(1024).decode()
    print(f"Resposta do servidor: {resposta}")

    return client

def sendMessage(client):

    message = input("c: ")
    chunks = [message[i:i+3] for i in range(0, len(message), 3)]

    for chunk in chunks:
        print(chunk)
        client.sendall(f"{chunk}".encode())

    client.sendall('END'.encode())

    print(chunks)

    return message    


def recieveMessage(client):

    buffer = []

    chunk = client.recv(1024).decode()

        # if not chunk :
        #     break

    buffer.append(chunk)
    print(f"s: {''.join(buffer)}")


def main():

    client = handShake()

    print(f"A conversa entre você e o servidor começa aqui :D")

    while True:
        message = sendMessage(client)
        recieveMessage(client)

        if message == 'exit':
            break

    client.close()

if __name__ == '__main__':
    main()