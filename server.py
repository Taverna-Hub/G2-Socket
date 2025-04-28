import socket
from dataclasses import dataclass

HOST = "localhost"
PORT = 3001

# Checklist
# ○ Printar o timer
# ○ Receber go-back-n corretamente

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
    tipo_operacao, tamanho_maximo, window_size = dados.split(",")
    print(
        f"Configurações recebidas do cliente: Modo de operação = {tipo_operacao}, Tamanho máximo = {tamanho_maximo}, Janela = {window_size}"
    )

    conn.sendall("Configurações aplicadas com sucesso".encode())

    return server, conn, tipo_operacao, int(tamanho_maximo),int(window_size)

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

def validateChecksum(data: bytes, received_checksum: int) -> bool:
    calculated = calcChecksum(data)
    return calculated == received_checksum

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
                print("=-"*30)

                print("Fim da transmissão.")
                return ''.join(fullmessage)

            try:
                message, seq, bytesData, checksum = line.split("|")
                seq = int(seq.strip())
                bytesData = int(bytesData.strip())
                checksum = int(checksum.strip())
                print("=-"*30)
                print(f"Message: {message}")
                print(f"Sequência: {seq}")
                print(f"Bytes Data: {bytesData}")
                print(f"Checksum: {checksum}")

                
                isChecksumValid = validateChecksum(message.encode(), checksum)
                

                if isChecksumValid:
                    if seq == expectedSeq:
                        fullmessage.append(message)
                        expectedSeq = seq + bytesData

                        while expectedSeq in BUFFER:
                            fullmessage.append(BUFFER[expectedSeq])
                            del BUFFER[expectedSeq]
                            expectedSeq += len(fullmessage[-1])

                    elif seq > expectedSeq:
                            BUFFER[seq] = message
                    ackNumber = seq + bytesData 
                else:
                    print("Checksum inválido!")
                    conn.sendall(f"NAK = {seq}\n".encode())
                    continue

                
                print(f"Enviando ACK = {ackNumber}")
                conn.sendall(f"ACK = {ackNumber}\n".encode())

            except Exception as e:
                print(f"Erro ao processar chunk: {chunk}, erro: {e}")

def reciveGBN(conn):
    fullmessage = []
    expectedSeq = 0
    while True:
        packages = conn.recv(1024).decode()
        print("=-"*30)
        print(packages)
        packages = packages.strip()
        packages_list = packages.split('\n')
        


        for chunk in packages_list:
            if chunk == "END":
                print("Fim da transmissão.")
                return ''.join(fullmessage)
            # print(chunk)
            message, seq, bytesData, checksum = chunk.split('|')
            seq = int(seq.strip())
            bytesData = int(bytesData.strip())
            checksum = int(checksum.strip())
            print(f"mensagem: {message}")
            print(f"seq: {seq}")
            print(f"bytes: {bytesData}")
            print(f"checksum: {checksum}")
            print("--"*30)
            isChecksumValid = validateChecksum(message.encode(), checksum)

            if isChecksumValid:
                fullmessage.append(message)
                expectedSeq = seq + bytesData
                continue

            else:
                print("Checksum inválido!")
                # conn.sendall(f"NAK = {seq + 3}\n".encode())
                continue

        

        ackNumber = seq + bytesData
        print(f"Enviando ACK = {ackNumber}")
        conn.sendall(f"{ackNumber}\n".encode())
        



    # ['als|0|3|11155\n', 'kjf|3|3|11925\n', 'li |6|3|29590\n', 'f9u|9|3|9414\n', 'aej|12|3|13466\n']
    #  message.pkg, seq.pkg

def main():

    server, conn, tipo_operacao, tamanho_maximo, window_size = handShake()

    wholeChunks = []
    while True:

        if tipo_operacao == "1":
            message = reciveSelective(conn=conn)
        elif tipo_operacao == "2":
            message = reciveGBN(conn)

        if message == 'exit':
            break
        
        if message:
            print(message)

    conn.close()
    server.close()


if __name__ == "__main__":
    main()
