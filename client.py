import socket
from dataclasses import dataclass


# Checklist
# ○ Soma de verificação (não feito)
# ○ Temporizador (não feito)
# ○ Número de sequência (feito)
# ○ Reconhecimento (feito)
# ○ Reconhecimento negativo (não feito - Entrega 3)
# ○ Janela, paralelismo (não feito)


@dataclass
class Package:
    message: str
    seq: int
    bytesData: int
    checksum: bytes


HOST = "localhost"
PORT = 3000


def calcChecksum(data: bytes) -> int:
    if len(data) % 2 != 0:
        data += b"\x00"

    checksum = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i + 1]
        checksum += word
        checksum = (checksum & 0xFFFF) + (checksum >> 16)

    checksum = ~checksum & 0xFFFF
    return checksum


def mountPackage(message, seq):
    checksum = calcChecksum(f"{message}{seq}")
    return Package(message=message, seq=seq, bytesData=len(message.encode("utf-8")))


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

    chunks = [message[i : i + 3] for i in range(0, len(message), 3)]

    seq = 0

    for chunk in chunks:
        package = mountPackage(chunk, seq)
        client.sendall(f"{package.message}|{package.seq}|{package.bytesData}".encode())

        expectedAckNumber = package.seq + package.bytesData

        while True:
            ack = client.recv(1024).decode()
            print(f"ACK recebido: {ack}")
            if ack == f"ACK = {expectedAckNumber}":
                break
            print(f"Esperando ACK correto: ACK = {expectedAckNumber}")

        seq = expectedAckNumber

    client.sendall("END".encode())
    print("Mensagem enviada:", message)
    return message


def main():
    client = handShake()

    print(f"A conversa entre você e o servidor começa aqui :D")

    while True:
        message = sendMessage(client)

        if message == "exit":
            break

    client.close()


if __name__ == "__main__":
    main()
