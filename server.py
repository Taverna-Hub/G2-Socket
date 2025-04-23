import socket

HOST = "localhost"
PORT = 3000


def handShake():
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

    return server, conn

def reciveMessage(conn):

    buffer = []

    while True:
    # for i in range(2):

        chunk = conn.recv(3).decode()

        if not chunk :
            break    

        buffer.append(chunk)
        print(f"buffer: {buffer}")
    
    return ''.join(buffer)


def sendMessage(conn, clientResp):

    if clientResp == 'exit':
        response = "Fechando conexão..."
    else: 
        response = input("s: ")
    
    conn.sendall(f"{response}".encode())


def main():

    server, conn = handShake()

    # while True: 
    response = reciveMessage(conn)

    sendMessage(conn, response)

        # if response == 'exit':
            # break

    conn.close()
    server.close()

if __name__ == '__main__':
    main()