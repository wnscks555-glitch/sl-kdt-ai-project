from decimal import Decimal
import socket
import struct
import threading
import unittest

from src.modbus import (
    ModbusClient, ModbusException, ModbusResponseError, ModbusServer, ModbusTimeout, READ_COILS, READ_HOLDING, Table,
    ValueConversionError, from_words, handle_pdu, restore_value, to_words,
)


def request(transaction, pdu, unit=1, protocol=0, length=None):
    size = len(pdu) + 1 if length is None else length
    return struct.pack(">HHHB", transaction, protocol, size, unit) + pdu


def read_pdu(function, start, count):
    return struct.pack(">BHH", function, start, count)


def fc16(start, count, values, size=None):
    body = b"".join(struct.pack(">H", value) for value in values)
    return struct.pack(">BHHB", 0x10, start, count, len(body) if size is None else size) + body


class FrameTests(unittest.TestCase):
    def setUp(self):
        self.table = Table()
        self.table.holding[0] = 7
        self.server = ModbusServer(self.table)
        self.addCleanup(self.server.close)

    def connect(self):
        connection = socket.create_connection(("127.0.0.1", self.server.port), timeout=2)
        connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.addCleanup(connection.close)
        return connection

    def receive(self, connection, size=11):
        data = b""
        while len(data) < size:
            chunk = connection.recv(size - len(data))
            if not chunk:
                break
            data += chunk
        return data

    def closed(self, connection):
        try:
            return connection.recv(16) == b""
        except ConnectionError:
            return True

    def test_t159_split_merged_and_truncated(self):
        connection = self.connect()
        for byte in request(1, read_pdu(READ_HOLDING, 0, 1)):
            connection.sendall(bytes((byte,)))
        self.assertEqual(self.receive(connection), bytes.fromhex("0001 0000 0005 01 03 02 0007"))

        connection.sendall(request(2, read_pdu(READ_HOLDING, 0, 1)) + request(3, read_pdu(READ_HOLDING, 0, 1)))
        replies = self.receive(connection, 22)
        self.assertEqual(replies[:2], b"\x00\x02")
        self.assertEqual(replies[11:13], b"\x00\x03")

        connection.sendall(request(4, read_pdu(READ_HOLDING, 0, 1))[:8])
        connection.shutdown(socket.SHUT_WR)
        self.assertTrue(self.closed(connection))

    def test_t160_damaged_frames_close_the_connection(self):
        full = fc16(1, 124, [0] * 124)
        self.assertEqual(len(full) + 1, 255)
        for frame in (request(1, read_pdu(3, 0, 1), protocol=1), request(1, b"\x03", length=1),
                      request(1, b"\x03" * 254), request(1, full)):
            connection = self.connect()
            connection.sendall(frame)
            self.assertTrue(self.closed(connection), frame[:8].hex())

    def test_t160_valid_request_before_damage_survives_any_split(self):
        good = request(1, struct.pack(">BHH", 6, 0, 9))
        bad = request(2, read_pdu(3, 0, 1), protocol=1)
        stream = good + bad
        for pieces in ((stream,), (good, bad), (stream[:len(good) + 5], stream[len(good) + 5:])):
            self.table.holding[0] = 7
            connection = self.connect()
            replies = b""
            for piece in pieces:
                connection.sendall(piece)
            while True:
                chunk = connection.recv(64)
                if not chunk:
                    break
                replies += chunk
            self.assertEqual(self.table.holding[0], 9)
            self.assertEqual(replies, good)

    def test_t160_other_unit_is_dropped_silently(self):
        connection = self.connect()
        connection.sendall(request(1, read_pdu(READ_HOLDING, 0, 1), unit=2))
        connection.sendall(request(2, read_pdu(READ_HOLDING, 0, 1)))
        self.assertEqual(self.receive(connection)[:2], b"\x00\x02")


class PduTests(unittest.TestCase):
    def test_t161_exceptions(self):
        cases = [
            (b"\x07", 0x87, 1),
            (read_pdu(3, 16, 1), 0x83, 2),
            (read_pdu(3, 15, 2), 0x83, 2),
            (read_pdu(3, 0, 0), 0x83, 3),
            (read_pdu(3, 0, 126), 0x83, 3),
            (read_pdu(1, 0, 2001), 0x81, 3),
            (struct.pack(">BHHB", 0x10, 1, 124, 248) + b"\x00\x01", 0x90, 3),
            (fc16(1, 2, [1, 1], size=3), 0x90, 3),
            (struct.pack(">BHH", 5, 8, 0x1234), 0x85, 3),
            (struct.pack(">BHH", 5, 0, 0xFF00), 0x85, 2),
            (struct.pack(">BHH", 6, 1, 1), 0x86, 2),
            (b"\x03\x00\x00", 0x83, 3),
            (fc16(0, 123, [1] * 123), 0x90, 2),
            (fc16(2, 1, [1]), 0x90, 2),
            (fc16(0, 3, [1, 1, 1]), 0x90, 2),
            (struct.pack(">BHH", 5, 7, 0xFF00), 0x85, 2),
        ]
        for pdu, function, code in cases:
            table = Table()
            before = (list(table.coils), list(table.holding))
            self.assertEqual(handle_pdu(pdu, table), bytes((function, code)), pdu.hex())
            self.assertEqual((table.coils, table.holding), before)

    def test_t161_internal_error_is_exception_4(self):
        table = Table()
        table.holding = None
        self.assertEqual(handle_pdu(read_pdu(3, 0, 1), table), b"\x83\x04")

    def test_t162_normal_responses(self):
        table = Table()
        table.coils[0] = table.coils[2] = table.coils[9] = True
        self.assertEqual(handle_pdu(read_pdu(READ_COILS, 0, 10), table), bytes.fromhex("01 02 05 02"))
        table.discrete[1] = True
        self.assertEqual(handle_pdu(read_pdu(2, 0, 3), table), bytes.fromhex("02 01 02"))
        table.input_registers[1] = 0xABCD
        self.assertEqual(handle_pdu(read_pdu(4, 1, 2), table), bytes.fromhex("04 04 ABCD 0000"))

        coil = struct.pack(">BHH", 5, 8, 0xFF00)
        self.assertEqual(handle_pdu(coil, table), coil)
        self.assertTrue(table.coils[8])
        register = struct.pack(">BHH", 6, 0, 0x1234)
        self.assertEqual(handle_pdu(register, table), register)
        self.assertEqual(table.holding[0], 0x1234)
        self.assertEqual(handle_pdu(fc16(1, 2, [3, 1]), table), bytes.fromhex("10 0001 0002"))
        self.assertEqual(table.holding[1:3], [3, 1])

    def test_unassigned_address_reads_zero_and_cannot_be_written(self):
        table = Table()
        self.assertEqual(handle_pdu(read_pdu(3, 3, 13), table), bytes((3, 26)) + bytes(26))
        self.assertEqual(handle_pdu(struct.pack(">BHH", 6, 3, 1), table), b"\x86\x02")

    def test_t165_judge_cannot_use_single_register_write(self):
        self.assertEqual(handle_pdu(struct.pack(">BHH", 6, 2, 1), Table()), b"\x86\x02")


class FakeServer:
    """요청 하나마다 reply가 만든 바이트를 돌려준다."""

    def __init__(self, reply):
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen()
        self.port = self.listener.getsockname()[1]
        self.reply = reply
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self):
        connection, _ = self.listener.accept()
        with connection:
            frame = connection.recv(512)
            answer = self.reply(frame)
            if answer:
                connection.sendall(answer)
            connection.recv(16)

    def close(self):
        self.listener.close()


class ClientTests(unittest.TestCase):
    def client(self, reply, timeout=2):
        server = FakeServer(reply)
        self.addCleanup(server.close)
        client = ModbusClient(server.port, timeout)
        self.addCleanup(client.close)
        return client

    def test_t163_mismatched_responses_close_the_connection(self):
        read = lambda client: client.read_registers(READ_HOLDING, 0, 1)
        write = lambda client: client.write_register(0, 1)
        cases = [
            (lambda frame: b"\x00\x09\x00\x00\x00\x05\x01\x03\x02\x00\x01", read),
            (lambda frame: frame[:4] + b"\x00\x05\x01\x04\x02\x00\x01", read),
            (lambda frame: frame[:4] + b"\x00\x05\x01\x03\x03\x00\x01", read),
            (lambda frame: frame[:-1] + bytes((frame[-1] ^ 1,)), write),
        ]
        for reply, call in cases:
            client = self.client(reply)
            with self.assertRaises(ModbusResponseError):
                call(client)
            self.assertTrue(client.closed)

    def test_t163_exception_response_keeps_connection(self):
        client = self.client(lambda frame: frame[:4] + b"\x00\x03\x01\x83\x02")
        with self.assertRaises(ModbusException) as caught:
            client.read_registers(READ_HOLDING, 0, 1)
        self.assertEqual(caught.exception.code, 2)
        self.assertFalse(client.closed)

    def test_eof_and_timeout(self):
        client = self.client(lambda frame: None, timeout=0.05)
        with self.assertRaises(ModbusTimeout):
            client.read_registers(READ_HOLDING, 0, 1)
        self.assertTrue(client.closed)

    def test_transaction_id_wraps_to_one(self):
        table = Table()
        server = ModbusServer(table)
        self.addCleanup(server.close)
        client = ModbusClient(server.port)
        self.addCleanup(client.close)
        client.transaction = 65534
        client.read_registers(READ_HOLDING, 0, 1)
        self.assertEqual(client.transaction, 65535)
        client.read_registers(READ_HOLDING, 0, 1)
        self.assertEqual(client.transaction, 1)

    def test_client_round_trip_over_socket(self):
        table = Table()
        server = ModbusServer(table)
        self.addCleanup(server.close)
        frames = []
        client = ModbusClient(server.port, on_frame=lambda *row: frames.append(row))
        self.addCleanup(client.close)
        client.write_coil(8, True)
        client.write_registers(1, [5, 2])
        client.write_register(0, 9)
        self.assertEqual(client.read_bits(READ_COILS, 8, 2), [True, False])
        self.assertEqual(client.read_registers(READ_HOLDING, 0, 3), [9, 5, 2])
        self.assertEqual([row[0] for row in frames[:2]], ["request", "response"])


class ValueTests(unittest.TestCase):
    def test_t164_conversion(self):
        cases = [("10.250", (0x0000, 0x280A)), ("-0.001", (0xFFFF, 0xFFFF)), ("2147483.647", (0x7FFF, 0xFFFF)),
                 ("-2147483.648", (0x8000, 0x0000)), ("1.2300", (0, 1230))]
        for text, words in cases:
            self.assertEqual(to_words(text), words)
            self.assertEqual(from_words(*words), int(Decimal(text) * 1000))
        self.assertEqual(restore_value(0x0000, 0x280A), "10.250")
        self.assertEqual(restore_value(0xFFFF, 0xFFFF), "-0.001")
        self.assertEqual(restore_value(0x7FFF, 0xFFFF), "2147483.647")
        self.assertEqual(restore_value(0x8000, 0x0000), "-2147483.648")

    def test_t164_rejected(self):
        for text in ("2147483.648", "-2147483.649", "1.2345", "", "abc", "NaN", "1e3", None):
            with self.assertRaises(ValueConversionError):
                to_words(text)


if __name__ == "__main__":
    unittest.main()
