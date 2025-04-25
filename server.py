import socket
from dataclasses import dataclass

HOST = "localhost"
PORT = 3001


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

    return server, conn, tipo_operacao, tamanho_maximo

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

def reciveMessage(conn):
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
                print("Fim da transmissão.")
                return ''.join(fullmessage)

            try:
                message, seq, bytesData, checksum = line.split("|")
                seq = int(seq.strip())
                bytesData = int(bytesData.strip())
                checksum = int(checksum.strip())

                print(f"Message: {message}")
                print(f"Sequência: {seq}")
                print(f"Bytes Data: {bytesData}")
                print(f"Checksum: {checksum}")

                
                isChecksumValid = validateChecksum(message.encode(), checksum)
                

                # print(isChecksumValid)
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
                    ackNumber = seq 


                print(f"Enviando ACK = {ackNumber}")
                conn.sendall(f"ACK = {ackNumber}\n".encode())

            except Exception as e:
                print(f"Erro ao processar chunk: {chunk}, erro: {e}")



def main():

    server, conn, tipo_operacao, tamanho_maximo = handShake()

    wholeChunks = []
    while True:
        message = reciveMessage(conn=conn)



        if message == 'exit':
            break
        
        if message:
            print(message)

    conn.close()
    server.close()


if __name__ == "__main__":
    main()
