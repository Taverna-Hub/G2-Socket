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
# ○ fazer os comentarios adicionados (feito)


@dataclass
class Package:
    message: str
    seq: int
    bytesData: int
    checksum: int


HOST = "localhost"
PORT = 3001
MAX_WINDOW_SIZE = 5
TIMEOUT = 2

def handleErrors():
    while True:
        error = int(input(
            "\n[1] para simular perda de pacote\n"
            "[2] para simular falha de integridade\n"
            "[3] para continuar normalmente\n"
            "Digite: "
        ))

        if error not in [1, 2, 3]:
            print("\nDigite apenas [1], [2] ou [3]\n")
        else:
            break

    return error

def calcChecksum(data: bytes, isCorrupt: bool) -> int:
    if len(data) % 2 != 0:
        data += b"\x00"

    checksum = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i + 1]
        checksum += word
        checksum = (checksum & 0xFFFF) + (checksum >> 16)

    checksum = ~checksum & 0xFFFF

    if isCorrupt:
        return checksum + 1

    return checksum


def mountPackage(message, seq, isCorrupt: bool):
    checksum = calcChecksum(message.encode(), isCorrupt)
    return Package(message=message, seq=seq, bytesData=len(message.encode("utf-8")), checksum=checksum)


def handShake():
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((HOST, PORT))
    client.settimeout(TIMEOUT)
    print("Escolha o modo de envio:")
    print("[1] - Sequencial")
    print("[2] - Em lotes \n")
    # sequencial -> repetição seletiva | em lotes -> go back n
    while True:
        tipo_operacao = input("Digite o modo escolhido: ")
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

# sequential -> repetição seletiva
def sendMessageSequential(client, message):
    errorMode = handleErrors()

    chunks = [message[i:i + 3] for i in range(0, len(message), 3)]
    seq = 0
    tries = 0

    for chunk in chunks:
        if errorMode not in [1, 3]:
            package = mountPackage(chunk, seq, True)
            integralPackage = mountPackage(chunk, seq, False)
        else: 
            package = mountPackage(chunk, seq, False)
            
        expectedAck = seq + package.bytesData

        while True:
            if tries > 0 and integralPackage:
                package = integralPackage
                print(f"Enviando pacote: {package.seq}")
                client.sendall(f"{package.message}|{package.seq}|{package.bytesData}|{package.checksum}\n".encode())
                tries = 0
            else:
                print(f"Enviando pacote: {package.seq}")
                client.sendall(f"{package.message}|{package.seq}|{package.bytesData}|{package.checksum}\n".encode())

            ready = select.select([client], [], [], TIMEOUT)
            print(f"tempo limite: {TIMEOUT}seg")
            start_timer = time.perf_counter()
            if ready[0]:
                ack = client.recv(1024).decode()
                print(f"ACK recebido: {ack}")

                if ack.strip() == f"ACK = {expectedAck}":
                    print('ack correto:', ack)
                    tempo_atual = time.perf_counter()
                    tempo_decorrido = tempo_atual - start_timer
                    print(f"Timer: {tempo_decorrido:.3f}s")
                    break
                elif ack == f"NAK = {seq}":
                    print("Recebido NAK, reenviando pacote...")
                    continue
            print(f"Nenhum ACK ou ACK incorreto. Reenviando pacote {package.seq}...")
            tries += 1

        seq = expectedAck

    client.sendall("END\n".encode())
    print("Mensagem enviada:", message)
    return message

#go bacn n -> 1 timer, 1 ack, 1 lista de coisas
def sendMessageParallel(client, message, window_size):
    chunks = [message[i:i + 3] for i in range(0, len(message), 3)]

    pending = {}
    seq = 0
    expectedAck = seq

    for chunk in chunks:
        package = mountPackage(chunk, seq, False)

        pending[seq] = f"{package.message}|{package.seq}|{package.bytesData}|{package.checksum}\n"    
        seq += package.bytesData

    while True:
        if not pending:
            break

        pkg_list = []
        keys = list(pending.keys())
        keys.sort()

        for key in keys[:window_size]:
            pkg_list.append(pending[key])
            
        # print(len(pkg_list))
        # print(pkg_list)
        batch = "".join(pkg_list)
        client.sendall(f"[{batch}]".encode())

        print("=-"*30)
        print(f"pacotes: \n{batch}")
        print(f"tempo limite: {TIMEOUT}seg")
        start_timer = time.perf_counter()

        try:
            last_pkg = pkg_list[-1]
            last_seq = int(last_pkg.split('|')[1])
            last_bytes = int(last_pkg.split('|')[2])
            expectedAck = last_seq + last_bytes

            ack = client.recv(1024).decode()
            ack = ack.strip('\n')

            print(f"ack esperado: {expectedAck}")
            print(f"ack recebido: {ack}")

            if expectedAck == int(ack):
                print('ack correto:', ack)
                tempo_atual = time.perf_counter()
                tempo_decorrido = tempo_atual - start_timer
                print(f"Timer: {tempo_decorrido:.3f}s")

                for key in keys[:window_size]:
                    if key in pending:
                        del pending[key]
            else:
                print("ACK incorreto, retransmitindo...")
        except socket.timeout:
            print("tempo limite exedido...")
            continue

    client.sendall("END\n".encode())
    print("Mensagem enviada:", message)
    return message

def checkInput(tamanho_maximo):
    while True:
        print("--"*30)
        print(f"Se desejar sair escreva 'exit' ")
        message = input("c: ")

        if len(message) > tamanho_maximo:
            print(f"Tamanho de pensagem estourado. Por favor escreva a mensagem até {tamanho_maximo}.")
        else:
            break
    
    return message
    



def checkInput(tamanho_maximo):
    while True:
        print("--"*30)
        print("Caso deseje sair digite 'exit'")
        message = input("c: ")

        if len(message) > tamanho_maximo:
            print(f"Tamanho de pensagem estourado. Por favor escreva a mensagem até {tamanho_maximo}.\n")
        else:
            break
    
    return message
    

def main():
    client, tipo_operacao, tamanho_maximo, window_size = handShake()

    print(f"\n A conversa entre você e o servidor começa aqui!")

    while True:
        message = checkInput(tamanho_maximo)
        if tipo_operacao == "1":
            message = sendMessageSequential(client, message)
        elif tipo_operacao == '2':
            message = sendMessageParallel(client, message, window_size)
        if message == "exit":
            break

    client.close()


if __name__ == "__main__":
    main()
