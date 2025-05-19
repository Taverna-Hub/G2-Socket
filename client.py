import socket
import select
import time
from dataclasses import dataclass


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

def handleErrors(max_packages: int):
    while True:
        try:
            mode = int(input(
                "\n[1] para simular perda de pacote\n"
                "[2] para simular falha de integridade\n"
                "[3] para continuar normalmente\n"
                "Digite: "
            ))
            if mode not in (1, 2, 3):
                raise ValueError
            if mode in (1, 2):
                pkg = int(input("Indique o índice do pacote (0 a {}): ".format(max_packages - 1)))
                if not (0 <= pkg < max_packages):
                    print(f"Pacote fora do intervalo 0-{max_packages-1}.")
                    continue
            else:
                pkg = -1
            return mode, pkg
        except ValueError:
            print("Entrada inválida, tente novamente.")
# ===========================================
#
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
# ===========================================
#
def mountPackage(message, seq, isCorrupt: bool):
    checksum = calcChecksum(message.encode(), isCorrupt)
    return Package(
        message=message,
        seq=seq,
        bytesData=len(message.encode("utf-8")),
        checksum=checksum,
    )
# ===========================================
#
def handShake():
    print("\n🔌 Iniciando handshake com o servidor...\n")
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((HOST, PORT))
    client.settimeout(TIMEOUT)
    print("Escolha o modo de envio:")
    print("[1] - Repetição Seletiva")
    print("[2] - Em lotes (Go-Back-N) \n")
    # sequencial -> repetição seletiva | em lotes -> go back n
    while True:
        tipo_operacao = input("Digite o modo escolhido: ")
        if tipo_operacao not in ["1", "2"]:
            print("Modo de operação inválido, tente novamente.")
            continue
        else:
            break
    print(f"Você escolheu o modo {tipo_operacao} [{"Repetição Seletiva" if tipo_operacao == "1" else "Go-Back-n"}]\n")
    tamanho_maximo = input("Digite o tamanho máximo: ")
    window_size = int(input("Digite o tamanho da janela: "))
    print("\n")
    if window_size > MAX_WINDOW_SIZE:
        print(f"Janela máxima é {MAX_WINDOW_SIZE}, ajustando para {MAX_WINDOW_SIZE}...")
        window_size = MAX_WINDOW_SIZE
    client.sendall(f"{tipo_operacao},{tamanho_maximo},{window_size}".encode())

    resposta = client.recv(1024).decode()
    print(f"Resposta do servidor: {resposta}\n")
    print("✅ Handshake concluído!\n")

    return client, tipo_operacao, int(tamanho_maximo), int(window_size)
# ===========================================
#
# sequential -> repetição seletiva
def sendMessageSequential(client: socket.socket, message: str):
    errorMode = 0
    errorPackage = -1

    chunks = [message[i : i + 3] for i in range(0, len(message), 3)]
    
    print("\n")
    if message != "exit":
        print("📦 Dividindo mensagem em pacotes...")
        for c, chunk in enumerate(chunks):
            print(f"🔹 Pacote {c}: '{chunk}'")
        errorMode, errorPackage = handleErrors(len(chunks))
    
    print("🚀 Enviando pacotes ao servidor...")

    seq = 0
    for i, chunk in enumerate(chunks):
        tries = 0
        integralPackage = None

        isCorrupt = (errorMode == 2 and i == errorPackage and tries == 0)
        package = mountPackage(chunk, seq, isCorrupt)
        if isCorrupt:
            integralPackage = mountPackage(chunk, seq, False)

        expectedAck = seq + package.bytesData

        while True:

            toSend = integralPackage if (tries > 0 and integralPackage) else package
            
            print("\n" + "—" * 40)
            print(f"⏱️  Tempo limite até o Timeout: {TIMEOUT} second(s)")

            if errorMode == 1 and i == errorPackage and tries == 0:
                print(f"🚫  Simulando perda do pacote seq={toSend.seq} (tentativa {tries + 1})")
            else:
                tag = " [CORROMPIDO]" if (toSend is package and isCorrupt) else ""
                print(f"📤  Enviando pacote: {tag}")
                print("-=-"*5)
                print(f"Mensagem: {toSend.message} ")
                print(f"Seq: {toSend.seq}")
                print(f"Bytes: {toSend.bytesData} ")
                print(f"CheckSum: {toSend.checksum} ")
                print(f"(tentativa {tries + 1})")
                print("-=-"*5)
                
                client.sendall(f"{toSend.message}|{toSend.seq}|{toSend.bytesData}|{toSend.checksum}\n".encode())
            
            client.settimeout(TIMEOUT)
            start_time = time.perf_counter()
            try:
                data = client.recv(1024).decode().strip()
                elapsed = time.perf_counter() - start_time
                print(f"✅  Recebido: '{data}' (em {elapsed:.3f}s)")
            except socket.timeout:
                elapsed = time.perf_counter() - start_time
                print(f"⚠️  Timeout após {elapsed:.3f}s para seq={toSend.seq}. Retransmitindo...")
                tries += 1
                continue  

            if data == f"ACK = {expectedAck}":
                print(f"🎉  ACK correto {data}. Avançando seq.")
                if i == errorPackage:
                    errorMode = 0
                break  

            elif data == f"NAK = {package.seq}":
                print(f"🔄  NAK recebido para seq={package.seq}. Retransmitindo...")
                tries += 1
                continue  

        seq = expectedAck

    client.sendall("END\n".encode())
    print("✉️  Mensagem enviada completamente.\n")
    return message
# ===========================================
#
# go back n -> 1 timer, 1 ack, 1 lista de coisas
def sendMessageParallel(client: socket.socket, message: str, window_size: int):
    errorMode = 0
    errorPackage = -1
    tries = 0

    chunks = [message[i : i + 3] for i in range(0, len(message), 3)]

    if message != "exit":
        print("📦 Dividindo mensagem em pacotes...")
        for c, chunk in enumerate(chunks):
            print(f"🔹 Pacote {c}: '{chunk}'")
        errorMode, errorPackage = handleErrors(len(chunks))

    pending = {}
    seq = 0
    expectedAck = seq
    print("erroMode = ", errorMode)

    for i, chunk in enumerate(chunks):
        if errorMode == 2 and i == errorPackage:
            correctPackage = mountPackage(chunk, seq, False)
            package = mountPackage(chunk, seq, True)
        else:
            package = mountPackage(chunk, seq, False)

        expectedAck = seq + package.bytesData

        pending[seq] = (
            f"{package.message}|{package.seq}|{package.bytesData}|{package.checksum}\n"
        )

        seq += package.bytesData

    print(f"✅ Total de pacotes pendentes: {len(pending)}")

    while True:
        if not pending:
            break

        packageList = []
        keys = list(pending.keys())
        keys.sort()

        for key in keys[:window_size]:
            packageList.append(pending[key])

        batch = "".join(packageList)

        if errorMode == 1:
            errorSeq = errorPackage * 3
            print(f"🚫 Simulando perda do pacote seq={errorSeq} nesta janela")
            for i, pkg in enumerate(packageList):
                seqInPackage = int(pkg.split("|")[1])
                if seqInPackage == errorSeq:
                    print(
                        f"❌ Removendo pacote com seq {seqInPackage} (errorPackage {errorPackage})"
                    )
                    del packageList[i]
                    errorMode = 0
                    batch = "".join(packageList)
                    break

        print("—" * 40)
        print("🚀 Enviando pacotes ao servidor...")
        print("📦 Pacotes enviados:")
        for p in packageList:
            print(f"➡️  {p.strip()}")

        client.sendall(f"[{batch}]".encode())

        print("\n")
        print(f"⏱️ Aguardando ACK (timeout: {TIMEOUT}s)...")
        start_timer = time.perf_counter()
        eslapsedTime = 0

        last_pkg = packageList[-1]
        last_seq = int(last_pkg.split("|")[1])
        last_bytes = int(last_pkg.split("|")[2])
        expectedAck = last_seq + last_bytes

        ack = client.recv(1024).decode()
        ack = ack.strip("\n")

        print(f"⏲️ Tempo decorrido: {eslapsedTime:.3f}s")
        print(f"✅ ACK esperado: {expectedAck} | Recebido: {ack}")

        tempo_atual = time.perf_counter()
        eslapsedTime = tempo_atual - start_timer
        print(f"Timer: {eslapsedTime:.3f}s")
        if eslapsedTime <= TIMEOUT:

            print(f"ack recebido: {ack}")

            if expectedAck == int(ack):
                print(f"👍 ACK correto! {ack}")
                tempo_atual = time.perf_counter()
                eslapsedTime = tempo_atual - start_timer
                print(f"Timer: {eslapsedTime:.3f}s")

                for key in keys[:window_size]:
                    if key in pending:
                        del pending[key]
            else:
                print("⚠️ ACK incorreto, retransmitindo pacotes...")
                for key in keys[:window_size]:
                    if key == ack:
                        break
                    if int(key) < int(ack):
                        del pending[key]

                if errorMode == 2:
                    pending[int(ack)] = (
                        f"{correctPackage.message}|{correctPackage.seq}|{correctPackage.bytesData}|{correctPackage.checksum}\n"
                    )
                print("--" * 10)

        else:
            print("⛔ Tempo limite excedido, retransmitindo...")
            errorMode = 0
            continue

    client.sendall("END\n".encode())
    print(f"✉️  Transmissão finalizada. Mensagem: '{message}'\n")
    return message
# ===========================================
#
def checkInput(tamanho_maximo):
    while True:
        print("--" * 30)
        print("Caso deseje sair digite 'exit'")
        message = input("c: ")

        if len(message) > tamanho_maximo:
            print(f"⚠️  Entrada inválida — máximo permitido: {tamanho_maximo} caracteres.\n")

        else:
            break

    return message
# ===========================================
#
def main():
    client, tipo_operacao, tamanho_maximo, window_size = handShake()

    print(f"\n A conversa entre você e o servidor começa aqui!")

    while True:
        message = checkInput(tamanho_maximo)
        if tipo_operacao == "1":
            message = sendMessageSequential(client, message)
        elif tipo_operacao == "2":
            message = sendMessageParallel(client, message, window_size)
        if message == "exit":
            print("🔌 Conexão encerrada. Até a próxima!")
            break

    client.close()
# ===========================================
#
if __name__ == "__main__":
    main()
