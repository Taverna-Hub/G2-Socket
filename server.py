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
    print(f"🛎️  Servidor ouvindo na porta {PORT}...")

    conn, addr = server.accept()
    print(f"👤 Cliente conectado: {addr}")

    dados = conn.recv(1024).decode()
    tipo_operacao, tamanho_maximo, window_size = dados.split(",")
    print(
        f"Configurações recebidas do cliente: \nModo de operação = {tipo_operacao} \nTamanho máximo = {tamanho_maximo} \nJanela = {window_size}\n"
    )

    conn.sendall("Configurações aplicadas com sucesso".encode())
    print("✅ Handshake concluído com o cliente!\n") 
    return server, conn, tipo_operacao, int(tamanho_maximo),int(window_size)
# ===========================================
#
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
# ===========================================
#
def validateChecksum(data: bytes, received_checksum: int) -> bool:
    calculated = calcChecksum(data)
    return calculated == received_checksum
# ===========================================
#
def reciveSelective(conn):
    fullmessage = []
    expectedSeq = 0
    BUFFER = {}
    text_buffer = "" 
    while True:
        chunk = conn.recv(1024).decode()
        
        text_buffer += chunk

        while "\n" in text_buffer:
            line, text_buffer = text_buffer.split("\n", 1)

            if line == "END":
                print("\n" + "=-" * 30)
                print("🎉 Fim da transmissão. Mensagem completa recebida:\n  ")
                return ''.join(fullmessage)

            print("\n" + "—" * 40)
            print(f"📥 Pacote bruto recebido: '{line}'")

            try:
                message, seq, bytesData, checksum = line.split("|")
                seq = int(seq.strip())
                bytesData = int(bytesData.strip())
                checksum = int(checksum.strip())
                print(f"   📄 Conteúdo : {message}")
                print(f"   🔢 Sequência: {seq}")
                print(f"   📦 Tamanho  : {bytesData} bytes")
                print(f"   🧮 Checksum : {checksum}")
                
                isValid = validateChecksum(message.encode(), checksum)

                if isValid:

                    if seq == expectedSeq:
                        fullmessage.append(message)
                        expectedSeq = seq + bytesData
                        print(f"   📍 Pacote na ordem. Novo expectedSeq = {expectedSeq}")

                        while expectedSeq in BUFFER:
                            fullmessage.append(BUFFER[expectedSeq])
                            del BUFFER[expectedSeq]
                            print(f"   📥 Entregando pacote em buffer seq={expectedSeq}")
                            expectedSeq += len(fullmessage[-1])

                    elif seq > expectedSeq:
                        BUFFER[seq] = message
                        print(f"🔄 Fora de ordem. Buffering pacote seq={seq}")
                    ackNumber = seq + bytesData 
                    print(f"📤 Enviando ACK = {ackNumber}\n")
                    conn.sendall(f"ACK = {ackNumber}\n".encode())

                else:
                    print(f"⚠️  Checksum inválido para seq={seq}. Enviando NAK\n")
                    conn.sendall(f"NAK = {seq}\n".encode())
                    continue


            except Exception as e:
                print(f"❌ Erro ao processar linha '{line}'. Detalhes: {e}")
# ===========================================
#
def reciveGBN(conn):
    fullmessage = []
    expectedSeq = 0
    while True:

        packages = conn.recv(1024).decode()
        packages = packages.rstrip('\n')
        packages = packages.strip('[]')
        print("\n" + "="*60)
        print("📥 Pacotes brutos recebidos:")
        for line in packages.split('\n'):
            if line:
                print(f" ➡️   {line}")

        packages_list = [ line for line in packages.split('\n') if line ]

        for chunk in packages_list:
            if chunk == "END":
                print("🎉 Fim da transmissão.")
                return ''.join(fullmessage)

            message, seq, bytesData, checksum = chunk.split('|')
            seq = int(seq.strip())
            bytesData = int(bytesData.strip())
            checksum = int(checksum.strip())
            print("\n" + "-"*60)
            print(f"🔍 Processando pacote: '{chunk}'")
            print(f"   📄 Conteúdo : {message}")
            print(f"   🔢 Sequência: {seq}")
            print(f"   📦 Bytes   : {bytesData} bytes")
            print(f"   🧮 Checksum: {checksum}")

            isChecksumValid = validateChecksum(message.encode(), checksum)

            if seq == expectedSeq:
                if isChecksumValid:
                    fullmessage.append(message)
                    expectedSeq += bytesData  
                    print(f"✅ Pacote na ordem. Novo expectedSeq = {expectedSeq}")
                else:
                    print(f"⚠️  Checksum inválido para seq={seq}. Solicitando retransmissão...")
                    break
            else:
                print(f"❗ Fora de ordem. Esperado={expectedSeq}, recebido={seq}. Solicitando retransmissão.")
                break  

        print(f"\n📤 Enviando ACK = {expectedSeq}\n")
        conn.sendall(f"{expectedSeq}\n".encode())
# ===========================================   
#    
def main():

    server, conn, tipo_operacao, tamanho_maximo, window_size = handShake()

    wholeChunks = []

    print(f"")

    while True:

        if tipo_operacao == "1":
            message = reciveSelective(conn=conn)
        elif tipo_operacao == "2":
            message = reciveGBN(conn)

        if message == 'exit':
            print("🔌 Conexão encerrada pelo cliente.")
            break
        
        if message:
            print(message)

    conn.close()
    server.close()
# ===========================================
#
if __name__ == "__main__":
    main()
