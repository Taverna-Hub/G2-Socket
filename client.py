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
PORT = 3001
MAX_WINDOW_SIZE = 5
TIMEOUT = 1

def chooseErrorMode(max_packages: int):
    while True:
        try:
            mode = int(input(
                "\n[1] para simular perda de pacote\n"
                "[2] para simular falha de integridade\n"
                "[3] para simular troca de ordem\n"
                "[4] para continuar normalmente\n"
                "Digite: "
            ))
            if mode not in (1, 2, 3, 4):
                raise ValueError
            if mode in (1, 2, 3):
                pkg = int(input("Indique o índice do pacote (0 a {}): ".format(max_packages - 1)))
                if not (0 <= pkg < max_packages):
                    print(f"Pacote fora do intervalo 0-{max_packages-1}.")
                    continue
            else:
                pkg = -1
            return mode, pkg
        except ValueError:
            print("Entrada inválida, tente novamente.") 

def handleErrors(batch: list[bytes], error_type: int, pgk_idx: int) -> list[bytes]:
    
    if error_type == 1:
        # perder somente o pacote pkg_idx
        return [p for i,p in enumerate(batch) if i != pkg_idx]
    elif error_type == 2:
        # corrompe somente o pacote pkg_idx
        corrupted = bytearray(batch[pkg_idx])
        corrupted[0] ^= 0xFF
        new_batch = batch.copy()
        new_batch[pkg_idx] = bytes(corrupted)
        return new_batch
    elif error_type == 3:
        # swap: troca pacote pkg_idx com outro aleatório
        n = len(batch)
        if 0 <= pkg_idx < n and n >= 2:
            import random
            j = random.choice([i for i in range(n) if i != pkg_idx])
            batch[pkg_idx], batch[j] = batch[j], batch[pkg_idx]
        return batch
    else:
        # modo normal
        return batch

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
def sendSelective(client: socket.socket, message: str, window_size: int):
    errorMode, errorPackage = (0, -1)
    chunks = [message[i : i + 3] for i in range(0, len(message), 3)]
    print("\n")
    if message != "exit":
        print("📦 Dividindo mensagem em pacotes...")
        for c, chunk in enumerate(chunks):
            print(f"🔹 Pacote {c}: '{chunk}'")
        errorMode, errorPackage = chooseErrorMode(len(chunks))
        
    print("🚀 Iniciando envio em janela paralela...\n")

    pending = {}
    seq = 0
    for i, chunk in enumerate(chunks):
        isCorrupt = (errorMode == 2 and i == errorPackage)
        pkg = mountPackage(chunk, seq, isCorrupt)
        integ = mountPackage(chunk, seq, False) if isCorrupt else None
        pending[seq] = { 'pkg': pkg, 'integ': integ, 'start': None, 'tries': 0 }
        seq += pkg.bytesData

    while pending:
        now = time.perf_counter()

        window_keys = sorted(pending.keys())[:window_size]

        if errorMode == 3:
            out_of_order_seq = errorPackage * 3
            if out_of_order_seq in window_keys:
                if pending[out_of_order_seq]['tries'] == 0:
                    from random import randint
                    other_keys = [k for k in window_keys if k != out_of_order_seq]
                    insert_at = randint(0, len(other_keys))
                    window_keys = other_keys[:insert_at] + [out_of_order_seq] + other_keys[insert_at:]

        for s in window_keys:
            info = pending[s]

            if info['start'] is None or (now - info['start'] >= TIMEOUT):
                toSend = info['pkg'] if info['tries'] == 0 else (info['integ'] or info['pkg'])
                print("\n" + "—"*40)
                print(f"⏱️  Tempo limite até o Timeout: {TIMEOUT} second(s)")
                if errorMode == 1 and s == errorPackage * 3 and info['tries'] == 0:
                    print(f"🚫  Simulando perda do pacote seq={s} (tentativa {info['tries']+1})")
                else:
                    tag = " [CORROMPIDO]" if (info['tries'] == 0 and toSend is info['pkg'] and errorMode == 2 and s == errorPackage * 3) else ""
                    print(f"📤  Enviando pacote seq={toSend.seq}{tag} (tentativa {info['tries']+1})")
                    print(f"   Mensagem: {toSend.message}")
                    print(f"   Seq: {toSend.seq}")
                    print(f"   Bytes: {toSend.bytesData}")
                    print(f"   CheckSum: {toSend.checksum}")
                    client.sendall(f"{toSend.message}|{toSend.seq}|{toSend.bytesData}|{toSend.checksum}\n".encode())
                info['start'] = time.perf_counter()
                info['tries'] += 1

        ack_buffer = ''
        start_time = time.perf_counter()

        while time.perf_counter() - start_time < TIMEOUT:
            ready, _, _ = select.select([client], [], [], 0.1)
            if ready:
                part = client.recv(1024).decode()
                ack_buffer += part
            else:
                break

        if ack_buffer:
            responses = ack_buffer.strip().split('\n')
            for resp in responses:
                if not resp:
                    continue
                print(f"✅ Recebido do servidor: '{resp}'")
                if resp.startswith("ACK ="):
                    try:
                        ack_num = int(resp.split('=')[1].strip())
                        for s in list(pending):
                            if s + pending[s]['pkg'].bytesData == ack_num:
                                print(f"🎉 ACK correto {ack_num}. Removendo seq={s} da janela.")
                                del pending[s]
                                break
                    except ValueError:
                        print(f"⚠️ Erro ao interpretar ACK: '{resp}'")
                elif resp.startswith("NAK ="):
                    try:
                        nak_seq = int(resp.split('=')[1].strip())
                        print(f"🔄 NAK recebido para seq={nak_seq}. Irá retransmitir na próxima janela.")
                        if nak_seq in pending:
                            pending[nak_seq]['start'] = None
                        if errorMode == 3 and nak_seq == errorPackage * 3:
                            print(f"✅ Corrigindo ordem do pacote seq={nak_seq} após NAK.")
                            errorMode = 0
                    except ValueError:
                        print(f"⚠️ Erro ao interpretar NAK: '{resp}'")
        else:
            print("🔍 Pendentes atuais na janela:", list(pending.keys()))
            print(f"⚠️ Timeout de ACKs. Retransmitindo pacotes pendentes na próxima janela.")

    client.sendall("END\n".encode())
    print("✉️  Mensagem enviada completamente.\n")
    return message

# ===========================================
#
def sendGBN(client: socket.socket, message: str, window_size: int):
    errorMode, errorPackage, tries = (0, -1, 0)
    chunks = [message[i : i + 3] for i in range(0, len(message), 3)]

    if message != "exit":
        print("📦 Dividindo mensagem em pacotes...")
        for c, chunk in enumerate(chunks):
            print(f"🔹 Pacote {c}: '{chunk}'")
        errorMode, errorPackage = chooseErrorMode(len(chunks))

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

        windowKeys = sorted(pending)[:window_size]
        
        batchLines = []
        for k in windowKeys:
            if errorMode == 1 and k == errorPackage * 3:
                print(f"🚫 Simulando perda do pacote seq={k} nesta janela")
                errorMode = 0
                continue
            batchLines.append(pending[k])
        batch = "".join(batchLines)

        print("—" * 40)
        print("🚀 Enviando pacotes ao servidor...")
        print("📦 Pacotes enviados:")
        for p in batchLines:
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
                    if key == int(ack):
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
            message = sendSelective(client, message, window_size)
        elif tipo_operacao == "2":
            message = sendGBN(client, message, window_size)
        if message == "exit":
            print("🔌 Conexão encerrada. Até a próxima!")
            break

    client.close()
# ===========================================
#
if __name__ == "__main__":
    main()
