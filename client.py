import socket
import select
import time
from dataclasses import dataclass


# Checklist
# Perda de pacote ?
# Falha de Integridade ?
# Talvez repetir so pro GOBACKN
# Printar checksum

@dataclass
class Package:
    message: str
    seq: int
    bytesData: int
    checksum: int


HOST = "localhost"
PORT = 3000
MAX_WINDOW_SIZE = 5
TIMEOUT = 1

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
            packError = int(input("Indique o pacote em o erro deverá acontecer: "))
            break
            

    return error, packError

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

        if errorMode == 2:
            package = mountPackage(chunk, seq, True)
            integralPackage = mountPackage(chunk, seq, False)
        else: 
            package = mountPackage(chunk, seq, False)
            
        expectedAck = seq + package.bytesData

        while True:
            print('-'*30)
            if tries > 0 and integralPackage:
                package = integralPackage
                print(f"Enviando pacote: {package.seq}")
                client.sendall(f"{package.message}|{package.seq}|{package.bytesData}|{package.checksum}\n".encode())
                tries = 0
            else:
                print(f"Enviando pacote: {package.seq}")
                client.sendall(f"{package.message}|{package.seq}|{package.bytesData}|{package.checksum}\n".encode())

            print(f"tempo limite: {TIMEOUT}seg")
            start_timer = time.perf_counter()
            tempo_decorrido = 0

            if errorMode == 1:
                time.sleep(3)
                tempo_atual = time.perf_counter()
                tempo_decorrido = tempo_atual - start_timer
                print(f"Timer: {tempo_decorrido:.3f}s")

            if tempo_decorrido < 2:
                ack = client.recv(1024).decode()
                print(f"ACK recebido do server: {ack}")

                if ack.strip() == f"ACK = {expectedAck}":
                    print('ACK correto:', ack)
                    tempo_atual = time.perf_counter()
                    tempo_decorrido = tempo_atual - start_timer
                    print(f"Timer: {tempo_decorrido:.3f}s")
                    break
                elif ack == f"NAK = {seq}":
                    print("Recebido NAK, reenviando pacote...")
                    continue
            else:
                print(f"Nenhum ACK ou ACK incorreto. Reenviando pacote {package.seq}...")
                client.recv(1024).decode()
            
            if errorMode == 2:
                tries += 1
                
            errorMode = 0

        seq = expectedAck

    client.sendall("END\n".encode())
    print("Mensagem enviada:", message)
    return message

#go back n -> 1 timer, 1 ack, 1 lista de coisas
def sendMessageParallel(client, message, window_size):
    errorMode = 0
    errorPackage = -1
    tries = 0

    chunks = [message[i:i + 3] for i in range(0, len(message), 3)]
    
    if message != 'exit':
        for c, chunk in enumerate(chunks):
            print("pacote: ", c, "conteudo: ", chunk)
        errorMode , errorPackage = handleErrors()
    pending = {}
    seq = 0
    expectedAck = seq
    print("erroMode = ", errorMode)
    for i, chunk in enumerate(chunks):
        print(i," = ", chunk, " = ", errorPackage)
        if errorMode == 2 and i == errorPackage:
            print("entrou")
            correct_package = mountPackage(chunk, seq, False)
            package = mountPackage(chunk, seq, True) # você pode mudar a condição para testar diferentes cenários
        else: 
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
            
        
        batch = "".join(pkg_list)
        client.sendall(f"[{batch}]".encode())

        print("=-"*30)
        print(f"pacotes: \n{batch}")
        print(f"tempo limite: {TIMEOUT}seg")
        start_timer = time.perf_counter()
        tempo_decorrido = 0

        
        if errorMode == 1:
            del pkg_list[errorPackage]
        print(pkg_list)
        last_pkg = pkg_list[-1]
        last_seq = int(last_pkg.split('|')[1])
        last_bytes = int(last_pkg.split('|')[2])
        expectedAck = last_seq + last_bytes

        ack = client.recv(1024).decode()
        ack = ack.strip('\n')

        print(f"ack esperado: {expectedAck}")

        tempo_atual = time.perf_counter()
        tempo_decorrido = tempo_atual - start_timer
        print(f"Timer: {tempo_decorrido:.3f}s")
        if tempo_decorrido <= TIMEOUT:
           
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
                print(pending)
                for key in keys[:window_size]:
                    if key == ack:
                        break
                    print('--'*10)
                    print(pending[key])
                    if int(key) < int(ack):
                        del pending[key]
                pending[int(ack)] = f"{correct_package.message}|{correct_package.seq}|{correct_package.bytesData}|{correct_package.checksum}\n"
                print('--'*10)
                print(pending)
                
        else:
            print("tempo limite exedido...")
            errorMode = 0
            continue

    client.sendall("END\n".encode())
    print("Mensagem enviada:", message)
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
