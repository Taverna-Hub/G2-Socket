import socket
import select
import time
from dataclasses import dataclass


# Checklist
# ○ Soma de verificação (feito)
# ○ Temporizador (feito)
# ○ Número de sequência (feito)
# ○ Reconhecimento (feito)
# ○ Reconhecimento negativo (feito acho?)
# ○ Janela, paralelismo (feito)
# ○ escolher modo de envio lotes e sequencial (feito)
# ○ tornar tamanho maximo util (feito)


@dataclass
class Package:
    message: str
    seq: int
    bytesData: int
    checksum: int


HOST = "localhost"
PORT = 3001
MAX_WINDOW_SIZE = 5


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
    checksum = calcChecksum(message.encode())
    return Package(message=message, seq=seq, bytesData=len(message.encode("utf-8")), checksum=checksum)


def handShake():
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((HOST, PORT))
    print("Escolha o modo de envio: Sequencial [1] em lotes [2]\n")
    while True:
        tipo_operacao = input("Digite o modo de operação: ")
        if tipo_operacao not in ["1", "2"]:
            print("Modo de operação inválido, tente novamente.")
            continue
        else:
            break
    print(f"Você escolheu o modo {tipo_operacao}\n")
    tamanho_maximo = input("Digite o tamanho máximo: ")
    window_size = int(input("Digite o tamanho da janela: "))
    if window_size > MAX_WINDOW_SIZE:
        print(f"Janela máxima é {MAX_WINDOW_SIZE}, ajustando para {MAX_WINDOW_SIZE}...")
        window_size = MAX_WINDOW_SIZE
    client.sendall(f"{tipo_operacao},{tamanho_maximo},{window_size}".encode())

    resposta = client.recv(1024).decode()
    print(f"Resposta do servidor: {resposta}")

    return client, tipo_operacao, int(tamanho_maximo), int(window_size)


def sendMessageSequential(client,tamanho_maximo):
    message = input("c: ")
    chunks = [message[i:i + tamanho_maximo] for i in range(0, len(message), tamanho_maximo)]
    seq = 0
    TIMEOUT = 2

    for chunk in chunks:
        package = mountPackage(chunk, seq)
        expectedAck = seq + package.bytesData

        while True:
            print(f"Enviando pacote: {package.seq}")
            client.sendall(f"{package.message}|{package.seq}|{package.bytesData}|{package.checksum}\n".encode())

            ready = select.select([client], [], [], TIMEOUT)
            if ready[0]:
                ack = client.recv(1024).decode()
                print(f"ACK recebido: {ack}")

                if ack.strip() == f"ACK = {expectedAck}":
                    break
                elif ack == f"NAK = {seq}":
                    print("Recebido NAK, reenviando pacote...")
                    continue
            print(f"Nenhum ACK ou ACK incorreto. Reenviando pacote {package.seq}...")

        seq = expectedAck

    client.sendall("END\n".encode())
    print("Mensagem enviada:", message)
    return message


def sendMessageParallel(client, tamanho_maximo, window_size):
    message = input("c: ")
    chunks = [message[i:i + tamanho_maximo] for i in range(0, len(message), tamanho_maximo)]
    TIMEOUT = 2
    seq = 0
    base = 0
    next_seq = 0
    pending = {}
    total_chunks = len(chunks)
    while base < total_chunks:

        while next_seq < base + window_size and next_seq < total_chunks:
            
            chunk = chunks[next_seq]
            package = mountPackage(chunk, seq)
            expected_ack = seq + package.bytesData

            print(f"Enviando pacote: {package.seq}")
            client.sendall(f"{package.message}|{package.seq}|{package.bytesData}|{package.checksum}\n".encode())

            pending[expected_ack] = (package, time.time())
            seq = expected_ack
            next_seq += 1

        ready = select.select([client], [], [], TIMEOUT)
        if ready[0]:
            data = client.recv(1024).decode().strip()
            lines = data.split("\n")
            for line in lines:
                print(f"ACK recebido: {line}")
                if line.startswith("ACK = "):
                    ack_num = int(line.split("=")[1].strip())
                    keys = sorted(pending.keys())
                    for key in keys:
                        if key <= ack_num:
                            del pending[key]
                            base += 1
                elif line.startswith("NAK = "):
                    nak_seq = int(line.split("=")[1].strip())
                    for ack_num, (pkg, _) in pending.items():
                        if pkg.seq == nak_seq:
                            print(f"Reenviando pacote (NAK): {pkg.seq}")
                            client.sendall(f"{pkg.message}|{pkg.seq}|{pkg.bytesData}|{pkg.checksum}\n".encode())
                            pending[ack_num] = (pkg, time.time())
                        else:
                            break
        else:
            now = time.time()
            for ack_num, (pkg, send_time) in list(pending.items()):
                if now - send_time >= TIMEOUT:
                    print(f"Timeout! Reenviando pacote: {pkg.seq}")
                    client.sendall(f"{pkg.message}|{pkg.seq}|{pkg.bytesData}|{pkg.checksum}\n".encode())
                    pending[ack_num] = (pkg, time.time())

    client.sendall("END\n".encode())
    print("Mensagem enviada:", message)
    return message


def main():
    client, tipo_operacao, tamanho_maximo, window_size = handShake()

    print(f"\n A conversa entre você e o servidor começa aqui :D")

    while True:
        if tipo_operacao == "1":
            message = sendMessageSequential(client,tamanho_maximo)
        elif tipo_operacao == '2':
            message = sendMessageParallel(client, tamanho_maximo, window_size)
        if message == "exit":
            break

    client.close()


if __name__ == "__main__":
    main()
