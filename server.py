import socket
from dataclasses import dataclass

HOST = "localhost"
PORT = 3000


@dataclass
class Package:
    message: str
    seq: int
    bytesData: int
    checksum: bytes


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
    chunk = conn.recv(1024).decode()

    if chunk == "END":
        print("Fim da transmissão.")

    chunk = chunk.split("|")

    if len(chunk) < 3:
        return ""

    message = chunk[0].strip()
    seq = chunk[1].strip()
    bytesData = chunk[2].strip()

    print(f"Message: {message}")
    print(f"Sequência: {seq}")
    print(f"Bytes Data: {bytesData}")

    ackNumber = int(seq) + int(bytesData)
    print(f"Enviando ACK = {ackNumber}")
    conn.sendall(f"ACK = {ackNumber}".encode())
    return message


def main():

    server, conn = handShake()

    wholeChunks = []
    while True:
        response = reciveMessage(conn)

        wholeChunks.append(response)
        
        if wholeChunks[-1] == "":
            print(f"c: {"".join(wholeChunks)}")
            wholeChunks = []

        if "".join(wholeChunks).endswith("exit"):
            break

    conn.close()
    server.close()


if __name__ == "__main__":
    main()
